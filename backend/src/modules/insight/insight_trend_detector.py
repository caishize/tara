"""Rule-driven trend detection engine. Zero LLM cost.

Detects behavioral patterns and generates trend_alert insights for:
- Commitment slippage (deferred 2+ times)
- Relationship cooling (recent reminders with no engagement)
- Schedule overload (high density 5+ consecutive days)
- Family time deficit (< 2 family events in 7 days)
- Social debt accumulation (pending favors increasing)
- Emotion decline (negative words in conversations 3+ consecutive days)
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from datetime import timedelta
from typing import List
from uuid import UUID

from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .models import (
    EntitySpec,
    GenerationLevel,
    InformationTier,
    Insight,
    InsightCandidate,
    InsightEntity,
    InsightStatus,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COMMITMENT_DEFER_THRESHOLD = 2
_RELATIONSHIP_COOLING_WINDOW_DAYS = 60
_OVERLOAD_DENSITY_THRESHOLD = 0.8
_OVERLOAD_CONSECUTIVE_DAYS = 5
_FAMILY_TIME_MIN_EVENTS = 2
_FAMILY_TIME_WINDOW_DAYS = 7
_SOCIAL_DEBT_WINDOW_DAYS = 30

# Emotion decline detection constants
_EMOTION_DECLINE_WINDOW_DAYS = 7
_EMOTION_DECLINE_CONSECUTIVE_DAYS = 3

# Negative sentiment keywords for emotion decline detection.
# Matched against user-role message content in assistant_chat_messages.
_NEGATIVE_EMOTION_WORDS: frozenset = frozenset({
    "累", "烦", "难", "没意思", "焦虑", "压力", "担心",
    "失眠", "痛苦", "绝望", "沮丧", "郁闷", "烦躁", "疲惫",
    "崩溃", "难受", "委屈", "无聊", "没劲", "烦死",
})

_FAMILY_EVENT_TYPES = frozenset({
    "family_gathering", "birthday_party", "holiday_celebration",
    "casual_visit",
})


class InsightTrendDetector:
    """Rule-driven trend detection engine. Zero LLM cost.

    Detects behavioral patterns and generates trend_alert insights
    for: commitment slippage, relationship cooling, schedule overload,
    family time deficit, social debt accumulation.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def detect(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Run all trend detectors and return candidates."""
        candidates: List[InsightCandidate] = []
        candidates.extend(await self._commitment_slip(user_id, family_id))
        candidates.extend(await self._relationship_cooling(user_id, family_id))
        candidates.extend(await self._schedule_overload(user_id, family_id))
        candidates.extend(await self._family_time_deficit(user_id, family_id))
        candidates.extend(await self._social_debt_accumulation(user_id, family_id))
        candidates.extend(await self._emotion_decline(user_id, family_id))
        return candidates

    # ------------------------------------------------------------------
    # Detection: commitment slippage
    # ------------------------------------------------------------------

    async def _commitment_slip(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Find insights that were deferred 2+ times — commitment slip signal."""
        now = utc_now()
        window_start = now - timedelta(days=90)

        # Count defer feedback per dedup_key for commitment-related insights
        stmt = (
            select(
                Insight.dedup_key,
                Insight.title,
                func.count().label("defer_count"),
            )
            .where(
                Insight.user_id == user_id,
                Insight.family_id == family_id,
                Insight.feedback == "defer",
                Insight.feedback_at >= window_start,
                Insight.dedup_key.isnot(None),
                or_(
                    Insight.insight_type == "commitment",
                    Insight.dedup_key.like("commitment:%"),
                ),
            )
            .group_by(Insight.dedup_key, Insight.title)
            .having(func.count() >= _COMMITMENT_DEFER_THRESHOLD)
        )

        result = await self._db.execute(stmt)
        rows = result.all()

        candidates: List[InsightCandidate] = []
        for row in rows:
            dedup_key = row.dedup_key or ""
            title = row.title or ""
            defer_count = row.defer_count

            candidates.append(InsightCandidate(
                insight_type="trend_alert",
                title="承诺延后提醒",
                content=f"「{title}」已延后{defer_count}次，是否重新评估？",
                importance=65,
                urgency=60,
                context_hint=f"已延后{defer_count}次",
                best_action_window="本周内",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L2_FORMAL.value,
                dedup_key=f"trend:commitment_slip:{dedup_key}",
                expires_at=now + timedelta(days=14),
                user_id=user_id,
                family_id=family_id,
            ))

        return candidates

    # ------------------------------------------------------------------
    # Detection: relationship cooling
    # ------------------------------------------------------------------

    async def _relationship_cooling(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Find persons with repeated relationship reminders — cooling signal."""
        now = utc_now()
        window_start = now - timedelta(days=_RELATIONSHIP_COOLING_WINDOW_DAYS)

        # Find person entities with 2+ relationship insights in the window
        stmt = (
            select(
                InsightEntity.entity_id,
                func.count(Insight.id.distinct()).label("reminder_count"),
            )
            .join(Insight, InsightEntity.insight_id == Insight.id)
            .where(
                Insight.user_id == user_id,
                Insight.family_id == family_id,
                Insight.insight_type.in_(["relationship", "relationship_maintenance"]),
                Insight.created_at >= window_start,
                InsightEntity.entity_type == "person",
            )
            .group_by(InsightEntity.entity_id)
            .having(func.count(Insight.id.distinct()) >= 2)
        )

        result = await self._db.execute(stmt)
        cooling_persons = result.all()

        if not cooling_persons:
            return []

        # Check for pending favors for these persons
        person_ids = [row.entity_id for row in cooling_persons]
        pending_favor_persons = await self._get_persons_with_pending_favors(
            family_id, person_ids,
        )

        candidates: List[InsightCandidate] = []
        for row in cooling_persons:
            person_id = row.entity_id
            has_pending_favor = person_id in pending_favor_persons

            content = "与该联系人的关系在降温"
            if has_pending_favor:
                content += "，且有人情待还"

            candidates.append(InsightCandidate(
                insight_type="trend_alert",
                title="关系降温提醒",
                content=content,
                importance=70 if has_pending_favor else 60,
                urgency=65 if has_pending_favor else 55,
                entities=[EntitySpec(
                    entity_type="person",
                    entity_id=str(person_id),
                    role="primary",
                )],
                context_hint=f"{_RELATIONSHIP_COOLING_WINDOW_DAYS}天内多次提醒",
                best_action_window="近期",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L2_FORMAL.value,
                dedup_key=f"trend:relationship_cooling:{person_id}",
                expires_at=now + timedelta(days=30),
                user_id=user_id,
                family_id=family_id,
            ))

        return candidates

    async def _get_persons_with_pending_favors(
        self, family_id: UUID, person_ids: List[UUID],
    ) -> frozenset:
        """Return set of person IDs that have pending favor records."""
        # Import here to avoid circular dependency
        from ..relationship.models import FavorRecord

        stmt = (
            select(FavorRecord.contact_id)
            .where(
                FavorRecord.family_id == family_id,
                FavorRecord.contact_id.in_(person_ids),
                FavorRecord.status == "pending",
                FavorRecord.direction == "receive",
            )
            .distinct()
        )

        result = await self._db.execute(stmt)
        return frozenset(row[0] for row in result.all())

    # ------------------------------------------------------------------
    # Detection: schedule overload
    # ------------------------------------------------------------------

    async def _schedule_overload(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Detect schedule overload via curated event count as density proxy."""
        now = utc_now()
        window_start = now - timedelta(days=_OVERLOAD_CONSECUTIVE_DAYS)

        # Use curated_events count per day as density proxy
        from ..curation.models import CuratedEvent

        day_trunc = func.date_trunc(literal_column("'day'"), CuratedEvent.normalized_start)
        stmt = (
            select(
                day_trunc.label("day"),
                func.count().label("event_count"),
            )
            .where(
                CuratedEvent.user_id == user_id,
                CuratedEvent.normalized_start >= window_start,
                CuratedEvent.normalized_start <= now,
                CuratedEvent.status != "cancelled",
            )
            .group_by(day_trunc)
        )

        result = await self._db.execute(stmt)
        daily_counts = result.all()

        # Consider 5+ events/day as "overloaded" (proxy for density > 0.8)
        overloaded_days = sum(1 for row in daily_counts if row.event_count >= 5)

        if overloaded_days < _OVERLOAD_CONSECUTIVE_DAYS:
            return []

        return [InsightCandidate(
            insight_type="trend_alert",
            title="日程过载提醒",
            content="本周日程过载，建议适当延后非紧急事项",
            importance=75,
            urgency=70,
            context_hint=f"连续{overloaded_days}天日程密集",
            best_action_window="今天",
            generation_level=GenerationLevel.L1_RULE.value,
            information_tier=InformationTier.L2_FORMAL.value,
            dedup_key=f"trend:schedule_overload:{user_id}",
            expires_at=now + timedelta(days=3),
            user_id=user_id,
            family_id=family_id,
        )]

    # ------------------------------------------------------------------
    # Detection: family time deficit
    # ------------------------------------------------------------------

    async def _family_time_deficit(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Detect lack of family events in the last 7 days."""
        now = utc_now()
        window_start = now - timedelta(days=_FAMILY_TIME_WINDOW_DAYS)

        from ..curation.models import CuratedEvent

        stmt = (
            select(func.count())
            .where(
                CuratedEvent.user_id == user_id,
                CuratedEvent.normalized_start >= window_start,
                CuratedEvent.normalized_start <= now,
                CuratedEvent.event_type.in_(list(_FAMILY_EVENT_TYPES)),
                CuratedEvent.status != "cancelled",
            )
        )

        result = await self._db.execute(stmt)
        family_event_count = result.scalar() or 0

        if family_event_count >= _FAMILY_TIME_MIN_EVENTS:
            return []

        return [InsightCandidate(
            insight_type="trend_alert",
            title="家庭时间提醒",
            content="最近家庭时间偏少，考虑安排一次家人聚会？",
            importance=60,
            urgency=50,
            context_hint=f"过去{_FAMILY_TIME_WINDOW_DAYS}天仅{family_event_count}次家庭活动",
            best_action_window="本周末",
            generation_level=GenerationLevel.L1_RULE.value,
            information_tier=InformationTier.L1_PASSIVE.value,
            dedup_key=f"trend:family_time_deficit:{user_id}",
            expires_at=now + timedelta(days=7),
            user_id=user_id,
            family_id=family_id,
        )]

    # ------------------------------------------------------------------
    # Detection: social debt accumulation
    # ------------------------------------------------------------------

    async def _social_debt_accumulation(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Detect increasing pending favors (direction=receive, status=pending)."""
        now = utc_now()
        from ..relationship.models import FavorRecord

        # Current pending count
        current_stmt = (
            select(func.count())
            .where(
                FavorRecord.family_id == family_id,
                FavorRecord.status == "pending",
                FavorRecord.direction == "receive",
            )
        )
        current_result = await self._db.execute(current_stmt)
        current_count = current_result.scalar() or 0

        if current_count == 0:
            return []

        # Count 30 days ago (pending favors created before that window)
        window_start = now - timedelta(days=_SOCIAL_DEBT_WINDOW_DAYS)
        old_stmt = (
            select(func.count())
            .where(
                FavorRecord.family_id == family_id,
                FavorRecord.status == "pending",
                FavorRecord.direction == "receive",
                FavorRecord.created_at <= window_start,
            )
        )
        old_result = await self._db.execute(old_stmt)
        old_count = old_result.scalar() or 0

        # Accumulation: current > old means new debts added
        new_debts = current_count - old_count
        if new_debts <= 0:
            return []

        return [InsightCandidate(
            insight_type="trend_alert",
            title="人情债累积提醒",
            content=f"人情债在累积（当前{current_count}笔，近期新增{new_debts}笔）",
            importance=65,
            urgency=55,
            context_hint=f"当前{current_count}笔待还",
            best_action_window="近期节日",
            generation_level=GenerationLevel.L1_RULE.value,
            information_tier=InformationTier.L2_FORMAL.value,
            dedup_key=f"trend:social_debt:{family_id}",
            expires_at=now + timedelta(days=14),
            user_id=user_id,
            family_id=family_id,
        )]

    # ------------------------------------------------------------------
    # Detection: emotion decline
    # ------------------------------------------------------------------

    async def _emotion_decline(
        self, user_id: UUID, family_id: UUID,
    ) -> List[InsightCandidate]:
        """Detect emotion decline via negative keywords in recent conversations.

        Queries ``assistant_chat_messages`` (via ``assistant_chat_sessions``)
        for user-role messages containing negative sentiment words.
        If negative words appear on _EMOTION_DECLINE_CONSECUTIVE_DAYS or more
        distinct calendar days in the past _EMOTION_DECLINE_WINDOW_DAYS days,
        a TREND_ALERT candidate is generated.

        Dependency: ``assistant_chat_sessions`` + ``assistant_chat_messages``
        tables from the conversation module.  Wrapped in try/except so that
        missing tables or schema changes degrade gracefully to no candidates.
        """
        try:
            # Import conversation models here to avoid circular dependency.
            from ..conversation.models import AssistantChatSession, ConversationMessage

            now = utc_now()
            window_start = now - timedelta(days=_EMOTION_DECLINE_WINDOW_DAYS)

            # Build OR filter: any message content containing a negative word.
            # We use LIKE patterns at the DB level for efficiency.
            negative_filters = [
                ConversationMessage.content.contains(word)
                for word in _NEGATIVE_EMOTION_WORDS
            ]

            day_trunc = func.date_trunc(
                literal_column("'day'"), ConversationMessage.created_at
            ).label("day")

            stmt = (
                select(day_trunc)
                .join(
                    AssistantChatSession,
                    ConversationMessage.session_id == AssistantChatSession.id,
                )
                .where(
                    AssistantChatSession.user_id == user_id,
                    ConversationMessage.role == "user",
                    ConversationMessage.created_at >= window_start,
                    ConversationMessage.created_at <= now,
                    ConversationMessage.is_superseded.is_(False),
                    or_(*negative_filters),
                )
                .group_by(day_trunc)
            )

            result = await self._db.execute(stmt)
            negative_days = result.all()

            if len(negative_days) < _EMOTION_DECLINE_CONSECUTIVE_DAYS:
                return []

            # Extract date objects and sort for consecutive-day detection.
            negative_days_sorted = sorted(row.day.date() for row in negative_days)

            # Compute the longest consecutive streak.
            max_streak = 1
            current_streak = 1
            for i in range(1, len(negative_days_sorted)):
                delta = (negative_days_sorted[i] - negative_days_sorted[i - 1]).days
                if delta == 1:
                    current_streak += 1
                    if current_streak > max_streak:
                        max_streak = current_streak
                elif delta > 1:
                    current_streak = 1

            if max_streak < _EMOTION_DECLINE_CONSECUTIVE_DAYS:
                return []

            return [InsightCandidate(
                insight_type="trend_alert",
                title="情绪状态关注",
                content=(
                    f"连续{max_streak}天的对话中出现较多情绪偏低的表达，"
                    "记得关注一下自己的状态，有需要随时说。"
                ),
                importance=70,
                urgency=60,
                context_hint=f"检测到连续{max_streak}天情绪偏低，需要关注",
                best_action_window="今天",
                generation_level=GenerationLevel.L1_RULE.value,
                information_tier=InformationTier.L1_PASSIVE.value,
                dedup_key=f"trend:emotion_decline:{user_id}",
                expires_at=now + timedelta(days=3),
                user_id=user_id,
                family_id=family_id,
            )]

        except Exception:
            # Graceful degradation: conversation model unavailable or schema mismatch.
            logger.warning(
                "emotion_decline detector skipped — conversation model unavailable",
                exc_info=True,
            )
            return []
