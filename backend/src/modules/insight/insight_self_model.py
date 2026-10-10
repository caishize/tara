"""M4 Secretary Self-Model — Meta-learning layer for insight performance tracking.

Tracks the secretary's own insight performance trends, identifying which
insight types are improving, stable, or declining. Generates recommendations
for weight adjustments to improve overall accuracy.

Zero LLM cost — pure rule-based analysis derived from existing insight
feedback data in the ``insights`` table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .models import Insight, InsightStatus

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Periods for trend comparison
SHORT_WINDOW_DAYS = 7
LONG_WINDOW_DAYS = 30

# A type is "declining" when its short-window accuracy drops below
# this fraction of the long-window accuracy.
DECLINING_THRESHOLD = 0.7

# Minimum number of insights in a window to be statistically meaningful.
MIN_SAMPLE_SIZE = 5

# Weight multipliers applied by the pipeline
WEIGHT_DECLINING = 0.7
WEIGHT_STABLE = 1.0
WEIGHT_IMPROVING = 1.2

# Terminal statuses that indicate user feedback was received
_POSITIVE_STATUSES = frozenset({
    InsightStatus.ACTED.value,
    InsightStatus.ACKNOWLEDGED.value,
})
_NEGATIVE_STATUSES = frozenset({
    InsightStatus.DISMISSED.value,
})
_TERMINAL_STATUSES = _POSITIVE_STATUSES | _NEGATIVE_STATUSES | frozenset({
    InsightStatus.EXPIRED.value,
})

# Max types to report as "best performing"
MAX_BEST_TYPES = 3


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InsightPerformanceMetrics:
    """Performance metrics for a single insight type within a time period."""

    insight_type: str
    period: str  # e.g. "7d", "30d"
    total_generated: int
    useful_count: int
    dismissed_count: int
    acted_count: int
    accuracy_rate: float  # (useful + acted) / total, 0.0-1.0
    trend: str  # "improving", "stable", "declining"


@dataclass(frozen=True)
class SelfModelReport:
    """Aggregated self-model report across all insight types."""

    metrics_by_type: Dict[str, InsightPerformanceMetrics]
    declining_types: List[str]
    best_performing_types: List[str]
    recommendations: List[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_accuracy(useful: int, acted: int, total: int) -> float:
    """Compute accuracy rate with safe division."""
    if total == 0:
        return 0.0
    return (useful + acted) / total


def _determine_trend(
    short_accuracy: float,
    long_accuracy: float,
    short_total: int,
    long_total: int,
) -> str:
    """Determine trend by comparing short vs long window accuracy.

    Returns "improving", "stable", or "declining".
    Insufficient data in either window defaults to "stable".
    """
    if short_total < MIN_SAMPLE_SIZE or long_total < MIN_SAMPLE_SIZE:
        return "stable"

    if long_accuracy == 0.0:
        # Cannot compute ratio; treat any positive short accuracy as improving
        return "improving" if short_accuracy > 0.0 else "stable"

    ratio = short_accuracy / long_accuracy
    if ratio < DECLINING_THRESHOLD:
        return "declining"
    if ratio > (1.0 / DECLINING_THRESHOLD):  # ~1.43
        return "improving"
    return "stable"


def _build_recommendations(
    declining: List[str],
    best: List[str],
) -> List[str]:
    """Generate human-readable recommendations based on trends."""
    recommendations: List[str] = []

    for dtype in declining:
        recommendations.append(
            f"reduce {dtype} insight frequency — accuracy declining"
        )

    if best:
        best_str = ", ".join(best)
        recommendations.append(
            f"maintain or increase weight for high-performing types: {best_str}"
        )

    if not declining and not best:
        recommendations.append(
            "all insight types performing within normal range"
        )

    return recommendations


# ---------------------------------------------------------------------------
# Core query helper
# ---------------------------------------------------------------------------


async def _query_window_stats(
    db: AsyncSession,
    family_id: UUID,
    days: int,
) -> Dict[str, Tuple[int, int, int, int]]:
    """Query insight stats grouped by type for a given time window.

    Returns:
        Dict mapping insight_type -> (total, useful_count, dismissed_count, acted_count)
    """
    cutoff = utc_now() - timedelta(days=days)

    useful_case = case(
        (Insight.feedback == "useful", 1),
        else_=0,
    )
    acknowledged_case = case(
        (Insight.status == InsightStatus.ACKNOWLEDGED.value, 1),
        else_=0,
    )
    dismissed_case = case(
        (Insight.status == InsightStatus.DISMISSED.value, 1),
        else_=0,
    )
    acted_case = case(
        (Insight.status == InsightStatus.ACTED.value, 1),
        else_=0,
    )

    stmt = (
        select(
            Insight.insight_type,
            func.count(Insight.id).label("total"),
            func.sum(useful_case + acknowledged_case).label("useful_count"),
            func.sum(dismissed_case).label("dismissed_count"),
            func.sum(acted_case).label("acted_count"),
        )
        .where(
            and_(
                Insight.family_id == family_id,
                Insight.created_at >= cutoff,
                Insight.status.in_(list(_TERMINAL_STATUSES)),
            )
        )
        .group_by(Insight.insight_type)
    )

    result = await db.execute(stmt)
    rows = result.all()

    stats: Dict[str, Tuple[int, int, int, int]] = {}
    for row in rows:
        stats[row.insight_type] = (
            int(row.total),
            int(row.useful_count or 0),
            int(row.dismissed_count or 0),
            int(row.acted_count or 0),
        )

    return stats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_self_report(
    db: AsyncSession,
    family_id: UUID,
) -> SelfModelReport:
    """Generate a self-model report comparing 7d vs 30d insight performance.

    Queries the insights table grouped by type and status, compares short
    vs long window accuracy to detect trends, and produces recommendations.
    """
    try:
        short_stats = await _query_window_stats(db, family_id, SHORT_WINDOW_DAYS)
        long_stats = await _query_window_stats(db, family_id, LONG_WINDOW_DAYS)
    except Exception as exc:
        logger.error("Failed to query insight stats for self-model: %s", exc)
        return SelfModelReport(
            metrics_by_type={},
            declining_types=[],
            best_performing_types=[],
            recommendations=["insufficient data for self-model analysis"],
        )

    # Union of all types seen in either window
    all_types = sorted(set(short_stats.keys()) | set(long_stats.keys()))

    metrics_by_type: Dict[str, InsightPerformanceMetrics] = {}
    declining_types: List[str] = []
    type_accuracy_pairs: List[Tuple[str, float, int]] = []

    for itype in all_types:
        s_total, s_useful, s_dismissed, s_acted = short_stats.get(itype, (0, 0, 0, 0))
        l_total, l_useful, l_dismissed, l_acted = long_stats.get(itype, (0, 0, 0, 0))

        short_accuracy = _compute_accuracy(s_useful, s_acted, s_total)
        long_accuracy = _compute_accuracy(l_useful, l_acted, l_total)

        trend = _determine_trend(short_accuracy, long_accuracy, s_total, l_total)

        # Use the longer window for the canonical metrics
        accuracy = long_accuracy if l_total >= MIN_SAMPLE_SIZE else short_accuracy

        metrics = InsightPerformanceMetrics(
            insight_type=itype,
            period=f"{LONG_WINDOW_DAYS}d",
            total_generated=l_total,
            useful_count=l_useful,
            dismissed_count=l_dismissed,
            acted_count=l_acted,
            accuracy_rate=round(accuracy, 3),
            trend=trend,
        )
        metrics_by_type[itype] = metrics

        if trend == "declining":
            declining_types.append(itype)

        if l_total >= MIN_SAMPLE_SIZE:
            type_accuracy_pairs.append((itype, accuracy, l_total))

    # Best performing: highest accuracy with sufficient data
    type_accuracy_pairs.sort(key=lambda x: (-x[1], -x[2]))
    best_performing = [t[0] for t in type_accuracy_pairs[:MAX_BEST_TYPES]]

    recommendations = _build_recommendations(declining_types, best_performing)

    report = SelfModelReport(
        metrics_by_type=metrics_by_type,
        declining_types=declining_types,
        best_performing_types=best_performing,
        recommendations=recommendations,
    )

    logger.info(
        "Self-model report: family=%s types=%d declining=%s best=%s",
        family_id,
        len(metrics_by_type),
        declining_types,
        best_performing,
    )

    return report


async def get_type_weight_adjustments(
    db: AsyncSession,
    family_id: UUID,
) -> Dict[str, float]:
    """Return importance-score multipliers for each insight type.

    Declining types get reduced weight, improving types get a boost,
    and stable types keep their default weight.

    Used by the pipeline to adjust candidate importance scores before
    persist, closing the feedback loop.
    """
    try:
        short_stats = await _query_window_stats(db, family_id, SHORT_WINDOW_DAYS)
        long_stats = await _query_window_stats(db, family_id, LONG_WINDOW_DAYS)
    except Exception as exc:
        logger.warning(
            "Failed to compute type weight adjustments: %s — returning neutral weights",
            exc,
        )
        return {}

    all_types = set(short_stats.keys()) | set(long_stats.keys())
    weights: Dict[str, float] = {}

    for itype in all_types:
        s_total, s_useful, _, s_acted = short_stats.get(itype, (0, 0, 0, 0))
        l_total, l_useful, _, l_acted = long_stats.get(itype, (0, 0, 0, 0))

        short_accuracy = _compute_accuracy(s_useful, s_acted, s_total)
        long_accuracy = _compute_accuracy(l_useful, l_acted, l_total)

        trend = _determine_trend(short_accuracy, long_accuracy, s_total, l_total)

        if trend == "declining":
            weights[itype] = WEIGHT_DECLINING
        elif trend == "improving":
            weights[itype] = WEIGHT_IMPROVING
        else:
            weights[itype] = WEIGHT_STABLE

    if weights:
        non_neutral = {k: v for k, v in weights.items() if v != WEIGHT_STABLE}
        if non_neutral:
            logger.info(
                "Type weight adjustments (non-neutral): family=%s weights=%s",
                family_id, non_neutral,
            )

    return weights
