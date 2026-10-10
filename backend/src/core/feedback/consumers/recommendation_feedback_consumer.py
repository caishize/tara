"""RecommendationFeedbackConsumer - learns recommendation preferences and suppression.

Consumes:
    INSIGHT_USEFUL       - user marked an insight as helpful
    INSIGHT_IGNORED      - insight was shown but not acted on for 24h
    INSIGHT_NEVER_AGAIN  - user permanently suppressed an insight type
    SUGGESTION_ACTED     - user acted on a suggestion
    SUGGESTION_DISMISSED - user dismissed a suggestion

Writes to:
    FamilyPreference.recommendation_weights  (JSONB)
    FamilyPreference.suppressed_types        (JSONB list)

Learning logic:
    INSIGHT_USEFUL       -> type weight x1.1
    INSIGHT_IGNORED      -> type weight x0.98, shown_count+1, 3 ignores -> suppress 30d
    INSIGHT_NEVER_AGAIN  -> permanent suppress
    SUGGESTION_ACTED     -> type weight x1.1
    SUGGESTION_DISMISSED -> type weight x0.8, consecutive 3 -> suppress 7d

Expected ``data`` payloads:
    INSIGHT_USEFUL:       {"insight_type": "follow_up"}
    INSIGHT_IGNORED:      {"insight_type": "relationship_maintenance"}
    INSIGHT_NEVER_AGAIN:  {"insight_type": "favor_reciprocation"}
    SUGGESTION_ACTED:     {"suggestion_type": "contact_reminder"}
    SUGGESTION_DISMISSED: {"suggestion_type": "gift_reminder"}

recommendation_weights structure:
    {
        "follow_up": {"weight": 1.1, "shown_count": 3, "ignore_count": 0, "dismiss_streak": 0},
        "relationship_maintenance": {"weight": 0.96, "shown_count": 5, "ignore_count": 2, ...},
        ...
    }
"""

import logging
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...utils.timezone import utc_now
from ..feedback_bus import FeedbackConsumer, FeedbackEvent, FeedbackSignal

logger = logging.getLogger(__name__)

# Multipliers
_USEFUL_MULTIPLIER = 1.1
_IGNORED_MULTIPLIER = 0.98
_ACTED_MULTIPLIER = 1.1
_DISMISSED_MULTIPLIER = 0.8
_DEFERRED_MULTIPLIER = 1.02   # weak positive: user wants it later
_NOT_USEFUL_MULTIPLIER = 0.95  # stronger than ignored, weaker than dismissed

# Suppression thresholds
_IGNORE_SUPPRESS_THRESHOLD = 3     # auto-suppress after N ignores
_DISMISS_STREAK_THRESHOLD = 3      # auto-suppress after N consecutive dismissals
_SUPPRESS_TTL_DAYS = 30            # auto-suppress expires after 30 days

# Weight bounds
_MIN_WEIGHT = 0.1
_MAX_WEIGHT = 3.0
_DEFAULT_WEIGHT = 1.0


def _get_type_stats(weights: dict, type_name: str) -> Dict[str, Any]:
    """Return the stats dict for a recommendation type, with defaults."""
    entry = weights.get(type_name)
    if isinstance(entry, dict):
        return dict(entry)
    # Legacy or missing: treat bare float as weight-only
    raw_weight = entry if isinstance(entry, (int, float)) else _DEFAULT_WEIGHT
    return {
        "weight": raw_weight,
        "shown_count": 0,
        "ignore_count": 0,
        "dismiss_streak": 0,
    }


def _clamp_weight(w: float) -> float:
    return max(_MIN_WEIGHT, min(_MAX_WEIGHT, w))


class RecommendationFeedbackConsumer:
    """Adjusts recommendation_weights and suppressed_types from insight/suggestion feedback."""

    def __init__(self, db: async_sessionmaker) -> None:
        self._session_factory = db

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        return [
            FeedbackSignal.INSIGHT_USEFUL,
            FeedbackSignal.INSIGHT_IGNORED,
            FeedbackSignal.INSIGHT_NEVER_AGAIN,
            FeedbackSignal.INSIGHT_DEFERRED,
            FeedbackSignal.INSIGHT_NOT_USEFUL,
            FeedbackSignal.SUGGESTION_ACTED,
            FeedbackSignal.SUGGESTION_DISMISSED,
        ]

    async def on_feedback(self, event: FeedbackEvent) -> None:
        try:
            async with self._session_factory() as session:
                self._session = session
                if event.signal == FeedbackSignal.INSIGHT_USEFUL:
                    await self._handle_insight_useful(event)
                elif event.signal == FeedbackSignal.INSIGHT_IGNORED:
                    await self._handle_insight_ignored(event)
                elif event.signal == FeedbackSignal.INSIGHT_NEVER_AGAIN:
                    await self._handle_never_again(event)
                elif event.signal == FeedbackSignal.INSIGHT_DEFERRED:
                    await self._handle_insight_deferred(event)
                elif event.signal == FeedbackSignal.INSIGHT_NOT_USEFUL:
                    await self._handle_insight_not_useful(event)
                elif event.signal == FeedbackSignal.SUGGESTION_ACTED:
                    await self._handle_suggestion_acted(event)
                elif event.signal == FeedbackSignal.SUGGESTION_DISMISSED:
                    await self._handle_suggestion_dismissed(event)
                await session.commit()
        except Exception as exc:
            logger.error(
                "RecommendationFeedbackConsumer failed for %s (family=%s): %s",
                event.signal.value, event.family_id, exc,
                exc_info=True,
            )

    # -- Insight handlers ----------------------------------------------------

    async def _handle_insight_useful(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("insight_type")
        if not type_name:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)

        stats["weight"] = _clamp_weight(stats["weight"] * _USEFUL_MULTIPLIER)
        stats["shown_count"] = stats["shown_count"] + 1
        # Reset negative streaks on positive feedback
        stats["dismiss_streak"] = 0

        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )
        logger.info(
            "RecommendationFeedbackConsumer: %s useful, weight -> %.3f (family=%s)",
            type_name, stats["weight"], event.family_id,
        )

    async def _handle_insight_ignored(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("insight_type")
        if not type_name:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)

        stats["weight"] = _clamp_weight(stats["weight"] * _IGNORED_MULTIPLIER)
        stats["shown_count"] = stats["shown_count"] + 1
        stats["ignore_count"] = stats["ignore_count"] + 1

        # Auto-suppress after threshold ignores (with TTL timestamp)
        will_suppress = stats["ignore_count"] >= _IGNORE_SUPPRESS_THRESHOLD
        if will_suppress:
            stats["suppressed_at"] = utc_now().isoformat()

        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )

        if will_suppress:
            await repo.add_suppressed_type(event.family_id, type_name)
            logger.info(
                "RecommendationFeedbackConsumer: auto-suppressed %s after %d ignores (family=%s, ttl=%dd)",
                type_name, stats["ignore_count"], event.family_id, _SUPPRESS_TTL_DAYS,
            )
        else:
            logger.info(
                "RecommendationFeedbackConsumer: %s ignored (%d/%d), weight -> %.3f (family=%s)",
                type_name, stats["ignore_count"], _IGNORE_SUPPRESS_THRESHOLD,
                stats["weight"], event.family_id,
            )

    async def _handle_never_again(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("insight_type")
        if not type_name:
            return

        repo = await self._get_repo()
        await repo.add_suppressed_type(event.family_id, type_name)

        # Mark as permanent suppression (not subject to TTL expiry)
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)
        stats["permanent"] = True
        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )
        logger.info(
            "RecommendationFeedbackConsumer: permanently suppressed %s (family=%s)",
            type_name, event.family_id,
        )

    async def _handle_insight_deferred(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("insight_type")
        if not type_name:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)

        stats["weight"] = _clamp_weight(stats["weight"] * _DEFERRED_MULTIPLIER)
        stats["shown_count"] = stats["shown_count"] + 1

        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )
        logger.info(
            "RecommendationFeedbackConsumer: %s deferred (weak positive), weight -> %.3f (family=%s)",
            type_name, stats["weight"], event.family_id,
        )

    async def _handle_insight_not_useful(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("insight_type")
        if not type_name:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)

        stats["weight"] = _clamp_weight(stats["weight"] * _NOT_USEFUL_MULTIPLIER)
        stats["shown_count"] = stats["shown_count"] + 1
        stats["not_useful_count"] = stats.get("not_useful_count", 0) + 1

        # Auto-suppress after threshold not-useful signals (same as ignore logic)
        will_suppress = stats["not_useful_count"] >= _IGNORE_SUPPRESS_THRESHOLD
        if will_suppress:
            stats["suppressed_at"] = utc_now().isoformat()

        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )

        if will_suppress:
            await repo.add_suppressed_type(event.family_id, type_name)
            logger.info(
                "RecommendationFeedbackConsumer: auto-suppressed %s after %d not_useful signals (family=%s, ttl=%dd)",
                type_name, stats["not_useful_count"], event.family_id, _SUPPRESS_TTL_DAYS,
            )
        else:
            logger.info(
                "RecommendationFeedbackConsumer: %s not_useful (%d/%d), weight -> %.3f (family=%s)",
                type_name, stats["not_useful_count"], _IGNORE_SUPPRESS_THRESHOLD,
                stats["weight"], event.family_id,
            )

    # -- Suggestion handlers -------------------------------------------------

    async def _handle_suggestion_acted(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("suggestion_type")
        if not type_name:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)

        stats["weight"] = _clamp_weight(stats["weight"] * _ACTED_MULTIPLIER)
        stats["shown_count"] = stats["shown_count"] + 1
        stats["dismiss_streak"] = 0

        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )
        logger.info(
            "RecommendationFeedbackConsumer: %s acted, weight -> %.3f (family=%s)",
            type_name, stats["weight"], event.family_id,
        )

    async def _handle_suggestion_dismissed(self, event: FeedbackEvent) -> None:
        type_name = event.data.get("suggestion_type")
        if not type_name:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current: dict = dict(pref.recommendation_weights or {})
        stats = _get_type_stats(current, type_name)

        stats["weight"] = _clamp_weight(stats["weight"] * _DISMISSED_MULTIPLIER)
        stats["shown_count"] = stats["shown_count"] + 1
        stats["dismiss_streak"] = stats["dismiss_streak"] + 1

        await repo.update_weights(
            event.family_id, "recommendation_weights", {type_name: stats},
        )

        # Auto-suppress after consecutive dismissal streak
        if stats["dismiss_streak"] >= _DISMISS_STREAK_THRESHOLD:
            await repo.add_suppressed_type(event.family_id, type_name)
            logger.info(
                "RecommendationFeedbackConsumer: auto-suppressed %s after %d dismissals (family=%s)",
                type_name, stats["dismiss_streak"], event.family_id,
            )
        else:
            logger.info(
                "RecommendationFeedbackConsumer: %s dismissed (%d/%d), weight -> %.3f (family=%s)",
                type_name, stats["dismiss_streak"], _DISMISS_STREAK_THRESHOLD,
                stats["weight"], event.family_id,
            )

    # -- Repo access ---------------------------------------------------------

    async def _get_repo(self):
        from ....modules.curation.services.family_preference_repository import (
            FamilyPreferenceRepository,
        )
        return FamilyPreferenceRepository(self._session)
