"""ImplicitFeedbackCollector — infers user preferences from behavioral patterns.

Collects four types of implicit signals (design doc section 5.3):
    1. viewed_no_action:    Insight shown but no interaction within threshold
    2. action_abandoned:    User started an action but didn't complete it
    3. topic_mentioned:     User mentioned related topic in conversation
    4. suggestion_followed: User actually did what the insight suggested

Each signal is recorded as a PreferenceSignal for downstream preference
extraction (E2 pipeline).
"""

import re
from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .insight_lifecycle import get_insight, transition_status, ensure_active_before
from .models import (
    ImplicitFeedbackType,
    Insight,
    InsightStatus,
)

logger = get_logger(__name__)

# Minimum word length for keyword matching to avoid false positives
_MIN_KEYWORD_LENGTH = 2

# Maximum number of insights to check per topic-mention scan
_MAX_TOPIC_SCAN_INSIGHTS = 50


class ImplicitFeedbackCollector:
    """Collects implicit user feedback signals from behavioral patterns."""

    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------
    # Signal 1: Viewed but no action
    # ------------------------------------------------------------------

    async def detect_viewed_no_action(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        *,
        hours_threshold: int = 24,
    ) -> List[UUID]:
        """Find insights shown > hours_threshold ago with no feedback.

        Returns insight IDs that were delivered (shown_at set) but never
        received any explicit feedback and are still active.
        """
        now = utc_now()
        cutoff = now - timedelta(hours=hours_threshold)

        filters = [
            Insight.user_id == user_id,
            Insight.shown_at.isnot(None),
            Insight.shown_at < cutoff,
            Insight.feedback.is_(None),
            Insight.status == InsightStatus.ACTIVE.value,
        ]
        if family_id is not None:
            filters.append(Insight.family_id == family_id)

        stmt = (
            select(Insight.id)
            .where(and_(*filters))
            .limit(100)
        )
        result = await self._db.execute(stmt)
        return [row[0] for row in result.all()]

    # ------------------------------------------------------------------
    # Signal 2: Action abandoned
    # ------------------------------------------------------------------

    async def record_action_abandoned(
        self,
        insight_id: UUID,
        user_id: UUID,
        action_type: str,
    ) -> Optional[Insight]:
        """Record that user started an action but abandoned it.

        Updates the insight's source_context with abandoned_action metadata
        and writes a preference signal.

        Returns the updated Insight, or None if not found / not applicable.
        """
        insight = await get_insight(self._db, insight_id)
        if insight is None:
            logger.warning(
                "record_action_abandoned: insight %s not found", insight_id,
            )
            return None

        if insight.user_id != user_id:
            logger.warning(
                "record_action_abandoned: user mismatch for insight %s", insight_id,
            )
            return None

        # Only track for active/acknowledged insights
        if insight.status not in (
            InsightStatus.ACTIVE.value,
            InsightStatus.ACKNOWLEDGED.value,
        ):
            return None

        # Build updated source_context immutably
        existing_context: Dict = dict(insight.source_context or {})
        abandoned_actions = list(existing_context.get("abandoned_actions", []))
        abandoned_actions = [
            *abandoned_actions,
            {
                "action_type": action_type,
                "timestamp": utc_now().isoformat(),
            },
        ]
        insight.source_context = {
            **existing_context,
            "abandoned_actions": abandoned_actions,
        }

        await self._write_implicit_signal(
            insight,
            ImplicitFeedbackType.ACTION_ABANDONED,
            extra_context={"abandoned_action_type": action_type},
        )

        await self._db.flush()
        logger.info(
            "Recorded action_abandoned: insight=%s, action=%s", insight_id, action_type,
        )
        return insight

    # ------------------------------------------------------------------
    # Signal 3: Topic mentioned in conversation
    # ------------------------------------------------------------------

    async def detect_topic_mentioned(
        self,
        user_id: UUID,
        message_content: str,
        family_id: Optional[UUID] = None,
    ) -> List[UUID]:
        """Check if message content relates to any active insights.

        Performs lightweight keyword matching between the message and
        active insight titles/content. Returns insight IDs whose keywords
        appear in the message.

        This is intentionally a simple text-overlap check (no LLM call)
        to keep cost at zero. For higher precision, callers can refine
        with an LLM in the outer layer.
        """
        if not message_content or len(message_content.strip()) < 3:
            return []

        message_lower = message_content.lower()

        filters = [
            Insight.user_id == user_id,
            Insight.status.in_([
                InsightStatus.ACTIVE.value,
                InsightStatus.ACKNOWLEDGED.value,
            ]),
            Insight.shown_at.isnot(None),
        ]
        if family_id is not None:
            filters.append(Insight.family_id == family_id)

        stmt = (
            select(Insight.id, Insight.title, Insight.content)
            .where(and_(*filters))
            .limit(_MAX_TOPIC_SCAN_INSIGHTS)
        )
        result = await self._db.execute(stmt)
        rows = result.all()

        matched_ids: List[UUID] = []
        for insight_id, title, content in rows:
            keywords = self._extract_keywords(title, content)
            if self._keywords_match(keywords, message_lower):
                matched_ids.append(insight_id)

        return matched_ids

    # ------------------------------------------------------------------
    # Signal 4: Suggestion followed
    # ------------------------------------------------------------------

    async def record_suggestion_followed(
        self,
        insight_id: UUID,
        user_id: UUID,
    ) -> Optional[Insight]:
        """Record that user actually followed through on a suggestion.

        Transitions insight to ACTED status with implicit feedback recorded.

        Returns the updated Insight, or None if not found / not applicable.
        """
        insight = await get_insight(self._db, insight_id)
        if insight is None:
            logger.warning(
                "record_suggestion_followed: insight %s not found", insight_id,
            )
            return None

        if insight.user_id != user_id:
            logger.warning(
                "record_suggestion_followed: user mismatch for insight %s",
                insight_id,
            )
            return None

        # Only transition from active/acknowledged
        current_status = InsightStatus(insight.status)
        if current_status not in (InsightStatus.ACTIVE, InsightStatus.ACKNOWLEDGED):
            logger.info(
                "record_suggestion_followed: insight %s in status %s, skipping",
                insight_id, current_status.value,
            )
            return None

        now = utc_now()

        # Step through ACTIVE if PENDING (should not happen, but defensive)
        ensure_active_before(insight, InsightStatus.ACTED)
        transition_status(insight, InsightStatus.ACTED)

        insight.feedback = ImplicitFeedbackType.SUGGESTION_FOLLOWED.value
        insight.feedback_at = now
        insight.feedback_source = "implicit"
        insight.acted_at = now

        await self._write_implicit_signal(
            insight,
            ImplicitFeedbackType.SUGGESTION_FOLLOWED,
        )

        await self._db.flush()
        logger.info(
            "Recorded suggestion_followed: insight=%s", insight_id,
        )
        return insight

    # ------------------------------------------------------------------
    # Batch processing: stale views
    # ------------------------------------------------------------------

    async def process_stale_views(self, user_id: UUID) -> int:
        """Batch process: find viewed-but-not-acted insights and write preference signals.

        Returns count of processed insights.
        """
        stale_ids = await self.detect_viewed_no_action(user_id)
        if not stale_ids:
            return 0

        processed = 0
        for insight_id in stale_ids:
            try:
                insight = await get_insight(self._db, insight_id)
                if insight is None:
                    continue

                await self._write_implicit_signal(
                    insight,
                    ImplicitFeedbackType.VIEWED_NO_ACTION,
                )
                processed += 1
            except Exception:
                logger.warning(
                    "Failed to process stale view for insight %s",
                    insight_id,
                    exc_info=True,
                )

        if processed > 0:
            await self._db.flush()
            logger.info(
                "Processed %d stale views for user %s", processed, user_id,
            )

        return processed

    # ------------------------------------------------------------------
    # Topic-mention signal recording (for external callers)
    # ------------------------------------------------------------------

    async def record_topic_mentioned(
        self,
        insight_id: UUID,
        user_id: UUID,
    ) -> Optional[Insight]:
        """Record that a conversation message referenced this insight's topic.

        Returns the updated Insight, or None if not found / not applicable.
        """
        insight = await get_insight(self._db, insight_id)
        if insight is None:
            return None

        if insight.user_id != user_id:
            return None

        if insight.status not in (
            InsightStatus.ACTIVE.value,
            InsightStatus.ACKNOWLEDGED.value,
        ):
            return None

        await self._write_implicit_signal(
            insight,
            ImplicitFeedbackType.TOPIC_MENTIONED,
        )
        await self._db.flush()
        logger.info(
            "Recorded topic_mentioned: insight=%s", insight_id,
        )
        return insight

    # ------------------------------------------------------------------
    # Viewed-no-action signal recording (for external callers)
    # ------------------------------------------------------------------

    async def record_viewed_no_action(
        self,
        insight_id: UUID,
        user_id: UUID,
    ) -> Optional[Insight]:
        """Record that an insight was viewed but user took no action.

        Returns the updated Insight, or None if not found / not applicable.
        """
        insight = await get_insight(self._db, insight_id)
        if insight is None:
            return None

        if insight.user_id != user_id:
            logger.warning(
                "record_viewed_no_action: user mismatch for insight %s",
                insight_id,
            )
            return None

        if insight.status not in (
            InsightStatus.ACTIVE.value,
            InsightStatus.ACKNOWLEDGED.value,
        ):
            return None

        await self._write_implicit_signal(
            insight,
            ImplicitFeedbackType.VIEWED_NO_ACTION,
        )
        await self._db.flush()
        logger.info(
            "Recorded viewed_no_action: insight=%s", insight_id,
        )
        return insight

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _write_implicit_signal(
        self,
        insight: Insight,
        signal_type: ImplicitFeedbackType,
        *,
        extra_context: Optional[Dict] = None,
    ) -> None:
        """Write a PreferenceSignal for an implicit feedback event."""
        try:
            from ..curation.models import PreferenceSignal
        except ImportError:
            logger.warning(
                "Cannot import PreferenceSignal — implicit signal not recorded",
            )
            return

        source_context = {
            "insight_type": insight.insight_type,
            "dedup_key": insight.dedup_key,
            "title": insight.title,
            "importance": insight.importance,
            "implicit": True,
            "implicit_type": signal_type.value,
        }
        if extra_context:
            source_context = {**source_context, **extra_context}

        signal = PreferenceSignal(
            user_id=insight.user_id,
            family_id=insight.family_id,
            signal_type=signal_type.value,
            source_type="insight",
            source_id=insight.id,
            source_context=source_context,
            category_key=f"implicit:{insight.insight_type}:{insight.dedup_key or 'none'}",
        )
        self._db.add(signal)

    @staticmethod
    def _extract_keywords(title: str, content: str) -> List[str]:
        """Extract meaningful keywords from insight title and content.

        Splits on non-word characters and filters out short/common words.
        """
        combined = f"{title} {content}"
        # Split on whitespace and punctuation, keep Chinese characters as-is
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", combined.lower())
        # Filter short words (but keep CJK single chars)
        return [
            t for t in tokens
            if len(t) > _MIN_KEYWORD_LENGTH or _is_cjk(t)
        ]

    @staticmethod
    def _keywords_match(keywords: List[str], message_lower: str) -> bool:
        """Check if enough keywords appear in the message for a match.

        Requires at least 2 keyword hits to reduce false positives.
        """
        if not keywords:
            return False

        hits = sum(1 for kw in keywords if kw in message_lower)
        # Require at least 2 hits (or 1 if we have very few keywords)
        threshold = min(2, max(1, len(keywords) // 3))
        return hits >= threshold


def _is_cjk(char: str) -> bool:
    """Check if a string contains CJK characters."""
    return any("\u4e00" <= c <= "\u9fff" for c in char)
