"""Relationship Health Model — Multi-dimensional relationship assessment.

Replaces simple "days since contact" with a richer health model that
considers interaction quality, reciprocity, baseline frequency, and trends.

Dimensions:
    - quality_score: Deep conversation > shallow greeting
    - reciprocity_ratio: Balance of who initiates contact
    - baseline_gap_days: Normal contact interval for this relationship
    - trend: warming / stable / cooling transition detection
    - overall_score: Weighted composite score

Zero LLM cost — pure statistical inference from conversation data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum message length to count as a "quality" interaction
QUALITY_MESSAGE_MIN_LENGTH = 20

# Lookback window for baseline frequency calculation
BASELINE_LOOKBACK_DAYS = 180

# Lookback window for trend comparison
TREND_RECENT_DAYS = 30
TREND_PREVIOUS_DAYS = 30

# Minimum interactions required for meaningful analysis
MIN_INTERACTIONS_FOR_ANALYSIS = 3

# Weight configuration for overall score
WEIGHT_QUALITY = 0.30
WEIGHT_RECIPROCITY = 0.20
WEIGHT_FREQUENCY = 0.25
WEIGHT_TREND = 0.25

# Reciprocity threshold below which reminders are suppressed
RECIPROCITY_SUPPRESSION_THRESHOLD = 0.2

# Trend ratio thresholds
TREND_WARMING_RATIO = 1.3
TREND_COOLING_RATIO = 0.7


# ---------------------------------------------------------------------------
# Enums & Data types
# ---------------------------------------------------------------------------


class RelationshipTrend(str, Enum):
    """Directional trend of a relationship."""
    WARMING = "warming"
    STABLE = "stable"
    COOLING = "cooling"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RelationshipHealth:
    """Immutable multi-dimensional relationship health assessment."""
    quality_score: int          # 0-100: interaction depth/quality
    reciprocity_ratio: float    # 0.0-1.0: balance of initiation
    baseline_gap_days: int      # average days between interactions
    trend: RelationshipTrend    # warming / stable / cooling
    overall_score: int          # 0-100: weighted composite
    interaction_count: int      # total interactions in lookback window
    data_sufficient: bool       # whether enough data for reliable assessment


# ---------------------------------------------------------------------------
# Default for insufficient data
# ---------------------------------------------------------------------------

_UNKNOWN_HEALTH = RelationshipHealth(
    quality_score=50,
    reciprocity_ratio=0.5,
    baseline_gap_days=0,
    trend=RelationshipTrend.UNKNOWN,
    overall_score=50,
    interaction_count=0,
    data_sufficient=False,
)


# ---------------------------------------------------------------------------
# Assessment logic
# ---------------------------------------------------------------------------


def _compute_quality_score(
    messages: List[Dict[str, Any]],
) -> int:
    """Score interaction quality based on message depth.

    Messages longer than QUALITY_MESSAGE_MIN_LENGTH are considered
    "deep" interactions. The score is the percentage of deep messages.
    """
    if not messages:
        return 50

    deep_count = sum(
        1 for msg in messages
        if len(msg.get("content", "")) >= QUALITY_MESSAGE_MIN_LENGTH
    )
    total = len(messages)

    return min(100, int((deep_count / total) * 100))


def _compute_reciprocity(
    user_initiated: int,
    contact_initiated: int,
) -> float:
    """Compute reciprocity as the ratio of contact-initiated interactions.

    Returns 0.5 for perfectly balanced, <0.5 means user always initiates,
    >0.5 means contact initiates more.

    Returns 0.5 (neutral) if no interactions exist.
    """
    total = user_initiated + contact_initiated
    if total == 0:
        return 0.5
    return contact_initiated / total


def _compute_baseline_gap(
    interaction_dates: List[date],
) -> int:
    """Compute average gap between interactions over the lookback window.

    Returns 0 if fewer than 2 interactions.
    """
    if len(interaction_dates) < 2:
        return 0

    sorted_dates = sorted(interaction_dates)
    gaps = [
        (sorted_dates[i + 1] - sorted_dates[i]).days
        for i in range(len(sorted_dates) - 1)
    ]

    return int(sum(gaps) / len(gaps)) if gaps else 0


def _compute_trend(
    recent_count: int,
    previous_count: int,
) -> RelationshipTrend:
    """Compare recent vs previous period interaction rates.

    Uses TREND_WARMING_RATIO and TREND_COOLING_RATIO thresholds.
    """
    if previous_count == 0 and recent_count == 0:
        return RelationshipTrend.UNKNOWN
    if previous_count == 0:
        return RelationshipTrend.WARMING

    ratio = recent_count / previous_count

    if ratio >= TREND_WARMING_RATIO:
        return RelationshipTrend.WARMING
    if ratio <= TREND_COOLING_RATIO:
        return RelationshipTrend.COOLING
    return RelationshipTrend.STABLE


def _compute_overall_score(
    quality: int,
    reciprocity: float,
    baseline_gap: int,
    trend: RelationshipTrend,
    days_since_contact: Optional[int],
) -> int:
    """Weighted combination of all dimensions into 0-100 score."""
    # Reciprocity score: 0.5 is ideal (50/50), penalize extremes
    reciprocity_score = int(100 - abs(reciprocity - 0.5) * 200)
    reciprocity_score = max(0, min(100, reciprocity_score))

    # Frequency score: based on how current gap compares to baseline
    if baseline_gap > 0 and days_since_contact is not None:
        gap_ratio = days_since_contact / baseline_gap
        if gap_ratio <= 1.0:
            frequency_score = 100
        elif gap_ratio <= 2.0:
            frequency_score = int(100 - (gap_ratio - 1.0) * 50)
        else:
            frequency_score = max(0, int(50 - (gap_ratio - 2.0) * 25))
    else:
        frequency_score = 50

    # Trend score
    trend_scores = {
        RelationshipTrend.WARMING: 80,
        RelationshipTrend.STABLE: 60,
        RelationshipTrend.COOLING: 30,
        RelationshipTrend.UNKNOWN: 50,
    }
    trend_score = trend_scores[trend]

    weighted = (
        quality * WEIGHT_QUALITY
        + reciprocity_score * WEIGHT_RECIPROCITY
        + frequency_score * WEIGHT_FREQUENCY
        + trend_score * WEIGHT_TREND
    )

    return max(0, min(100, int(weighted)))


async def assess_relationship_health(
    db: AsyncSession,
    user_id: UUID,
    contact_id: UUID,
) -> RelationshipHealth:
    """Assess the multi-dimensional health of a relationship.

    Queries conversation history to compute quality, reciprocity,
    baseline frequency, and trend for the relationship between
    the user and a contact (PersonProfile).

    Returns RelationshipHealth with data_sufficient=False if
    insufficient interaction data exists.
    """
    try:
        from ..conversation.models import ConversationMessage, AssistantChatSession
        from ..member.models.person_profile import PersonProfile

        now = utc_now()
        lookback_start = now - timedelta(days=BASELINE_LOOKBACK_DAYS)
        recent_start = now - timedelta(days=TREND_RECENT_DAYS)
        previous_start = recent_start - timedelta(days=TREND_PREVIOUS_DAYS)

        # Get the contact's name for message content matching
        contact_stmt = select(PersonProfile.name).where(
            PersonProfile.id == contact_id
        )
        contact_result = await db.execute(contact_stmt)
        contact_name = contact_result.scalar_one_or_none()

        if contact_name is None:
            logger.debug(
                "Contact %s not found for health assessment", contact_id
            )
            return _UNKNOWN_HEALTH

        # Query messages from user's sessions that mention the contact
        # We look at user messages that reference the contact name
        session_stmt = (
            select(AssistantChatSession.id)
            .where(
                and_(
                    AssistantChatSession.user_id == user_id,
                    AssistantChatSession.started_at >= lookback_start,
                )
            )
        )
        session_result = await db.execute(session_stmt)
        session_ids = [row[0] for row in session_result.all()]

        if not session_ids:
            return _UNKNOWN_HEALTH

        # Get messages mentioning the contact
        msg_stmt = (
            select(
                ConversationMessage.content,
                ConversationMessage.role,
                ConversationMessage.created_at,
            )
            .where(
                and_(
                    ConversationMessage.session_id.in_(session_ids),
                    ConversationMessage.role == "user",
                    ConversationMessage.content.ilike(
                        "%{}%".format(
                            contact_name
                            .replace("\\", "\\\\")
                            .replace("%", "\\%")
                            .replace("_", "\\_")
                        )
                    ),
                )
            )
            .order_by(ConversationMessage.created_at.asc())
        )
        msg_result = await db.execute(msg_stmt)
        messages_raw = list(msg_result.all())

        if len(messages_raw) < MIN_INTERACTIONS_FOR_ANALYSIS:
            return RelationshipHealth(
                quality_score=50,
                reciprocity_ratio=0.5,
                baseline_gap_days=0,
                trend=RelationshipTrend.UNKNOWN,
                overall_score=50,
                interaction_count=len(messages_raw),
                data_sufficient=False,
            )

        # Build message dicts for quality analysis
        messages = [
            {
                "content": row.content or "",
                "role": row.role,
                "created_at": row.created_at,
            }
            for row in messages_raw
        ]

        # Compute quality
        quality = _compute_quality_score(messages)

        # Compute interaction dates for baseline and trend
        interaction_dates = [
            msg["created_at"].date()
            if hasattr(msg["created_at"], "date")
            else msg["created_at"]
            for msg in messages
            if msg["created_at"] is not None
        ]

        baseline_gap = _compute_baseline_gap(interaction_dates)

        # Trend: count interactions in recent vs previous period
        recent_count = sum(
            1 for d in interaction_dates
            if d >= recent_start.date()
        )
        previous_count = sum(
            1 for d in interaction_dates
            if previous_start.date() <= d < recent_start.date()
        )
        trend = _compute_trend(recent_count, previous_count)

        # Reciprocity: estimate based on message length heuristic.
        # Short messages mentioning the contact suggest user reaching out;
        # longer contextual messages suggest discussion about the contact
        # (possibly contact-initiated interaction being discussed).
        user_initiated = 0
        contact_initiated = 0

        for row in messages_raw:
            content = row.content or ""
            if len(content) < QUALITY_MESSAGE_MIN_LENGTH * 2:
                user_initiated += 1
            else:
                contact_initiated += 1

        reciprocity = _compute_reciprocity(user_initiated, contact_initiated)

        # Days since last contact
        days_since = None
        if interaction_dates:
            last_contact = max(interaction_dates)
            days_since = (utc_now().date() - last_contact).days

        overall = _compute_overall_score(
            quality, reciprocity, baseline_gap, trend, days_since,
        )

        health = RelationshipHealth(
            quality_score=quality,
            reciprocity_ratio=round(reciprocity, 2),
            baseline_gap_days=baseline_gap,
            trend=trend,
            overall_score=overall,
            interaction_count=len(messages_raw),
            data_sufficient=True,
        )

        logger.debug(
            "Relationship health assessed for user=%s contact=%s: "
            "quality=%d reciprocity=%.2f gap=%d trend=%s overall=%d",
            user_id, contact_id, quality, reciprocity, baseline_gap,
            trend.value, overall,
        )

        return health

    except Exception as exc:
        logger.error(
            "Relationship health assessment failed for user=%s contact=%s: %s",
            user_id, contact_id, exc,
        )
        return _UNKNOWN_HEALTH
