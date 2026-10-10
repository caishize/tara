"""PreferenceLearner - consolidates feedback signals into FamilyPreference rules.

Daily Celery task that reads from the unified ``insights`` table and
``event_associations`` over a 90-day window, applies exponential-decay
weighting, and writes learned rules into the FamilyPreference JSONB columns.

Consolidation logic:
- Exponential decay: recent feedback weighs more (half-life 30 days)
- Signal count >= 3 AND positive/negative ratio >= 70% -> create/update rule
- Confidence < 0.2 -> deactivate rule (auto-recovery test)
- Suppressed types auto-recover after 30 days (explicit expiration)
"""

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now
from ..models import EventAssociation, FamilyPreference
from .family_preference_repository import FamilyPreferenceRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WINDOW_DAYS = 90
_HALF_LIFE_DAYS = 30.0
_LN2 = math.log(2)
_MIN_SIGNAL_COUNT = 3
_RATIO_THRESHOLD = 0.70
_DEACTIVATION_THRESHOLD = 0.20
_SUPPRESSION_EXPIRY_DAYS = 30
_SUPPRESSION_REDIS_PREFIX = "pref:suppressed_at"
_SUPPRESSION_REDIS_TTL = _WINDOW_DAYS * 86400  # 90 days


# ---------------------------------------------------------------------------
# Intermediate data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _WeightedSignal:
    """A single feedback signal with its decay weight."""
    is_positive: bool
    weight: float


@dataclass(frozen=True)
class _DimensionResult:
    """Aggregated result for one dimension key (e.g. insight_type or association_type)."""
    key: str
    positive_weight: float
    negative_weight: float
    signal_count: int
    confidence: float


def _decay_weight(age_days: float) -> float:
    """Exponential decay: weight = exp(-ln(2) * age_days / half_life)."""
    return math.exp(-_LN2 * age_days / _HALF_LIFE_DAYS)


def _aggregate_signals(signals: List[_WeightedSignal]) -> Tuple[float, float, int]:
    """Return (positive_sum, negative_sum, count) from weighted signals."""
    positive = sum(s.weight for s in signals if s.is_positive)
    negative = sum(s.weight for s in signals if not s.is_positive)
    return positive, negative, len(signals)


def _compute_confidence(positive: float, negative: float) -> float:
    """Confidence = dominant_ratio considering both directions."""
    total = positive + negative
    if total <= 0:
        return 0.0
    return max(positive, negative) / total


# ---------------------------------------------------------------------------
# PreferenceLearner
# ---------------------------------------------------------------------------

class PreferenceLearner:
    """Consolidate feedback signals into FamilyPreference JSONB rules.

    Data sources:
    - ``insights``: unified insight table with ``feedback`` and
      ``feedback_at`` columns capturing user reactions.
    - ``event_associations``: confirmed/dismissed associations linked to an
      association_type.

    Target columns in FamilyPreference:
    - ``recommendation_weights``: learned from insight feedback
    - ``association_weights``: learned from association confirm/dismiss
    - ``suppressed_types``: insight types with sustained negative signals
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = FamilyPreferenceRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def consolidate(self, family_id: UUID) -> FamilyPreference:
        """Recompute preference rules from the last 90 days of feedback.

        Steps:
        1. Gather insight feedback signals (recommendation_weights)
        2. Gather association feedback signals (association_weights)
        3. Derive suppressed_types from recommendation signals
        4. Write changes via FamilyPreferenceRepository
        5. Update learning metadata
        """
        try:
            now = utc_now()
            cutoff = now - timedelta(days=_WINDOW_DAYS)

            recommendation_signals = await self._gather_insight_signals(
                family_id, cutoff, now,
            )
            association_signals = await self._gather_association_signals(
                family_id, cutoff, now,
            )

            recommendation_updates = self._derive_weight_updates(recommendation_signals)
            association_updates = self._derive_weight_updates(association_signals)
            suppressed = self._derive_suppressed_types(recommendation_signals)

            pref = await self._repo.get_or_create_default(family_id)

            if recommendation_updates:
                await self._repo.update_weights(
                    family_id, "recommendation_weights", recommendation_updates,
                )

            if association_updates:
                await self._repo.update_weights(
                    family_id, "association_weights", association_updates,
                )

            # Sync suppressed_types: add newly suppressed, remove recovered ones
            await self._sync_suppressed_types(family_id, pref, suppressed)

            # Update learning metadata
            total_signals = sum(
                r.signal_count for r in recommendation_signals
            ) + sum(
                r.signal_count for r in association_signals
            )
            pref.last_learned_at = now
            pref.learning_events_count = (pref.learning_events_count or 0) + total_signals
            pref.updated_at = now
            await self._db.flush()
            await self._db.refresh(pref)

            logger.info(
                "PreferenceLearner: consolidated family %s "
                "(recommendation_keys=%d, association_keys=%d, "
                "suppressed=%d, total_signals=%d)",
                family_id,
                len(recommendation_updates),
                len(association_updates),
                len(suppressed),
                total_signals,
            )
            return pref
        except Exception:
            logger.error(
                "PreferenceLearner: consolidation failed for family %s",
                family_id,
                exc_info=True,
            )
            raise

    async def consolidate_all_families(self) -> Dict[str, int]:
        """Run consolidation for every active family.

        Each family gets a fresh DB session to avoid stale/shared session
        issues in Celery task context.

        Returns a summary dict with counts.
        """
        from ..task_utils import get_active_families
        from ....db.session import create_celery_async_session

        engine, session_factory = create_celery_async_session()
        try:
            families = await get_active_families(session_factory)
        finally:
            await engine.dispose()

        success = 0
        errors = 0
        for fid in families:
            try:
                fid_engine, fid_sf = create_celery_async_session()
                try:
                    async with fid_sf() as session:
                        learner = PreferenceLearner(session)
                        await learner.consolidate(fid)
                        await session.commit()
                        success += 1
                finally:
                    await fid_engine.dispose()
            except Exception:
                logger.exception(
                    "PreferenceLearner: failed for family %s", fid,
                )
                errors += 1

        return {"families": len(families), "success": success, "errors": errors}

    # ------------------------------------------------------------------
    # Signal gathering
    # ------------------------------------------------------------------

    async def _gather_insight_signals(
        self,
        family_id: UUID,
        cutoff,
        now,
    ) -> List[_DimensionResult]:
        """Query insight feedback from unified Insight table, grouped by type."""
        try:
            from ...insight.models import Insight
        except ImportError:
            return []

        stmt = (
            select(
                Insight.insight_type,
                Insight.feedback,
                Insight.feedback_at,
            )
            .where(
                Insight.family_id == family_id,
                Insight.feedback.isnot(None),
                Insight.feedback_at >= cutoff,
                # Only count user-initiated feedback, not cascade/hygiene signals
                Insight.feedback_source == "user",
            )
        )
        result = await self._db.execute(stmt)
        all_rows = result.all()

        if not all_rows:
            return []

        # Group by insight_type
        _POSITIVE_FEEDBACK = frozenset({"useful"})
        grouped: Dict[str, List[_WeightedSignal]] = {}
        for insight_type, feedback, created_at in all_rows:
            age_days = (now - created_at).total_seconds() / 86400.0
            weight = _decay_weight(age_days)
            is_positive = feedback in _POSITIVE_FEEDBACK
            key = str(insight_type) if insight_type else "unknown"
            grouped.setdefault(key, []).append(
                _WeightedSignal(is_positive=is_positive, weight=weight),
            )

        return self._signals_to_results(grouped)

    async def _gather_association_signals(
        self,
        family_id: UUID,
        cutoff,
        now,
    ) -> List[_DimensionResult]:
        """Query event_associations grouped by association_type, apply decay."""
        stmt = (
            select(
                EventAssociation.association_type,
                EventAssociation.is_confirmed,
                EventAssociation.is_dismissed,
                EventAssociation.created_at,
            )
            .where(
                EventAssociation.family_id == family_id,
                EventAssociation.created_at >= cutoff,
                # Only count associations that have been acted upon
                (EventAssociation.is_confirmed == True) | (EventAssociation.is_dismissed == True),  # noqa: E712
            )
        )
        result = await self._db.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        grouped: Dict[str, List[_WeightedSignal]] = {}
        for assoc_type, is_confirmed, is_dismissed, created_at in rows:
            age_days = (now - created_at).total_seconds() / 86400.0
            weight = _decay_weight(age_days)
            is_positive = bool(is_confirmed)
            key = str(assoc_type) if assoc_type else "unknown"
            grouped.setdefault(key, []).append(
                _WeightedSignal(is_positive=is_positive, weight=weight),
            )

        return self._signals_to_results(grouped)

    # ------------------------------------------------------------------
    # Derivation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _signals_to_results(
        grouped: Dict[str, List[_WeightedSignal]],
    ) -> List[_DimensionResult]:
        """Convert grouped signals into DimensionResults."""
        results: List[_DimensionResult] = []
        for key, signals in grouped.items():
            positive, negative, count = _aggregate_signals(signals)
            confidence = _compute_confidence(positive, negative)
            results.append(_DimensionResult(
                key=key,
                positive_weight=positive,
                negative_weight=negative,
                signal_count=count,
                confidence=confidence,
            ))
        return results

    @staticmethod
    def _derive_weight_updates(
        results: List[_DimensionResult],
    ) -> Dict[str, float]:
        """From dimension results, derive JSONB weight updates.

        Rules:
        - signal_count >= 3 AND confidence >= 0.70 -> create/update
        - Positive dominant -> weight > 1.0 (up to 2.0)
        - Negative dominant -> weight < 1.0 (down to 0.1)
        - confidence < 0.20 -> deactivate (set weight to 0.1)
        """
        updates: Dict[str, float] = {}
        for r in results:
            if r.signal_count < _MIN_SIGNAL_COUNT:
                continue

            if r.confidence < _DEACTIVATION_THRESHOLD:
                updates[r.key] = 0.1
                continue

            if r.confidence < _RATIO_THRESHOLD:
                continue

            total = r.positive_weight + r.negative_weight
            if total <= 0:
                continue

            # Map to [0.1, 2.0] range
            positive_ratio = r.positive_weight / total
            weight = 0.1 + positive_ratio * 1.9
            updates[r.key] = round(weight, 3)

        return updates

    @staticmethod
    def _derive_suppressed_types(
        results: List[_DimensionResult],
    ) -> set:
        """Identify insight types that should be suppressed.

        Suppression criteria: signal_count >= 3 AND negative ratio >= 0.70
        """
        suppressed = set()
        for r in results:
            if r.signal_count < _MIN_SIGNAL_COUNT:
                continue
            total = r.positive_weight + r.negative_weight
            if total <= 0:
                continue
            negative_ratio = r.negative_weight / total
            if negative_ratio >= _RATIO_THRESHOLD:
                suppressed.add(r.key)
        return suppressed

    async def _sync_suppressed_types(
        self,
        family_id: UUID,
        pref: FamilyPreference,
        newly_suppressed: set,
    ) -> None:
        """Add newly suppressed types and remove recovered ones.

        Recovery happens via two mechanisms:
        1. Signal-based: type no longer meets suppression criteria (decay/new positive)
        2. Time-based: type has been suppressed for 30+ days (explicit expiration)
        """
        current_suppressed = set(pref.suppressed_types or [])

        # Check for time-expired suppressions (30-day auto-recovery)
        expired = await self._get_expired_suppressions(family_id, current_suppressed)

        # Add new suppressions and record their timestamps
        for type_name in newly_suppressed - current_suppressed:
            await self._repo.add_suppressed_type(family_id, type_name)
            await self._record_suppression_time(family_id, type_name)

        # Remove recovered types: signal-based OR time-expired
        signal_recovered = current_suppressed - newly_suppressed
        to_remove = signal_recovered | expired
        for type_name in to_remove:
            await self._repo.remove_suppressed_type(family_id, type_name)
            await self._clear_suppression_time(family_id, type_name)

        if expired:
            logger.info(
                "PreferenceLearner: auto-recovered %d expired suppressions "
                "for family %s: %s",
                len(expired), family_id, sorted(expired),
            )

    # ------------------------------------------------------------------
    # Suppression timestamp tracking (Redis)
    # ------------------------------------------------------------------

    @staticmethod
    def _suppression_key(family_id: UUID, type_name: str) -> str:
        return f"{_SUPPRESSION_REDIS_PREFIX}:{family_id}:{type_name}"

    @staticmethod
    async def _get_redis():
        """Get the global async Redis client, or None if unavailable."""
        try:
            from ....core.cache import redis_client

            if redis_client.client is None:
                return None
            return redis_client
        except Exception:
            return None

    async def _record_suppression_time(
        self, family_id: UUID, type_name: str,
    ) -> None:
        """Record when a type was first suppressed."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            key = self._suppression_key(family_id, type_name)
            # Only set if not already tracked (NX behavior via check)
            existing = await redis.get(key)
            if existing is None:
                await redis.set(
                    key, utc_now().isoformat(), ttl=_SUPPRESSION_REDIS_TTL,
                )
        except Exception:
            logger.debug(
                "Failed to record suppression time for %s", type_name,
                exc_info=True,
            )

    async def _clear_suppression_time(
        self, family_id: UUID, type_name: str,
    ) -> None:
        """Remove suppression timestamp when a type recovers."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            await redis.delete(self._suppression_key(family_id, type_name))
        except Exception:
            logger.debug(
                "Failed to clear suppression time for %s", type_name,
                exc_info=True,
            )

    async def _get_expired_suppressions(
        self, family_id: UUID, current_suppressed: Set[str],
    ) -> Set[str]:
        """Return types that have been suppressed for longer than 30 days."""
        if not current_suppressed:
            return set()

        redis = await self._get_redis()
        if redis is None:
            return set()

        now = utc_now()
        expiry_cutoff = now - timedelta(days=_SUPPRESSION_EXPIRY_DAYS)
        expired: Set[str] = set()

        for type_name in current_suppressed:
            try:
                key = self._suppression_key(family_id, type_name)
                raw = await redis.get(key)
                if raw is None:
                    # No timestamp recorded -- backfill it now so it starts
                    # the 30-day clock from today.
                    await redis.set(
                        key, now.isoformat(), ttl=_SUPPRESSION_REDIS_TTL,
                    )
                    continue
                suppressed_at = datetime.fromisoformat(raw)
                if suppressed_at < expiry_cutoff:
                    expired.add(type_name)
            except Exception:
                logger.debug(
                    "Failed to check suppression expiry for %s",
                    type_name,
                    exc_info=True,
                )

        return expired
