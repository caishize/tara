"""
Daily Briefing Service - Generates daily briefings for users.

Integrates internal events with external data sources (calendars, emails)
to provide comprehensive daily briefings.

Extracted from secretary/services/daily_briefing_service.py.
"""
import asyncio
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from zoneinfo import ZoneInfo

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now, local_today, local_now, DEFAULT_TIMEZONE, to_local_date
from ....db.session import get_db_session
from ....modules.conversation.display_builder import build_display_data

from ...date_manager.date_service import DateService

from ..schemas import (
    BriefingEvent,
    BriefingEntityRef,
    BriefingInsight,
    HouseholdStatus,
    UpcomingTrip,
    BriefingAlert,
    BriefingSuggestion,
    BriefingPeriod,
    DailyBriefing,
    DeferralSuggestionSchema,
    SecretaryAnnotationSchema,
    DayThemeSchema,
    TimeSlotSchema,
)

from ....core.cache import redis_client

from .event_aggregator import EventAggregator, get_event_icon, get_event_details, calculate_next_occurrence_wrapper
from .suggestion_generator import SuggestionGenerator
from .external_data_fetcher import ExternalDataFetcher
from .density_controller import DensityController
from .recommendation_engine import RecommendationEngine, Recommendation

logger = get_logger(__name__)

_BRIEFING_CACHE_TTL = 1800  # 30 minutes


# External data source types
EXTERNAL_CALENDAR_SOURCES = ["google_calendar", "outlook_calendar"]
EXTERNAL_EMAIL_SOURCES = ["google_gmail", "outlook_mail"]


class DailyBriefingService:
    """Service for generating daily briefings."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.date_service = DateService(session)
        self._event_aggregator = EventAggregator(session)
        self._suggestion_generator = SuggestionGenerator(session)
        self._density_controller = DensityController()
        self._recommendation_engine = RecommendationEngine(session)

    async def get_or_generate_briefing(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: Optional[date] = None,
        period: Optional[str] = None,
        force_refresh: bool = False,
    ) -> DailyBriefing:
        """Return a cached briefing or generate a fresh one.

        Cache key: ``briefing:daily:{user_id}:{date}:{period}``
        TTL: 30 minutes.  Redis failures fall through to generation.
        """
        # Resolve defaults so the cache key is deterministic.
        user_tz = await self._get_user_timezone(user_id)
        if target_date is None:
            target_date = local_today(user_tz)
        if period is None:
            now = local_now(user_tz)
            period = BriefingPeriod.from_hour(now.hour)

        cache_key = f"briefing:daily:{user_id}:{target_date.isoformat()}:{period}"

        # --- Try cache first ---
        if not force_refresh:
            try:
                cached = await redis_client.get(cache_key)
                if cached is not None:
                    logger.info("[BRIEFING CACHE] HIT  key=%s", cache_key)
                    return DailyBriefing.model_validate_json(cached)
            except Exception:
                logger.warning("[BRIEFING CACHE] Redis read error, falling through", exc_info=True)

        # --- Cache miss or force refresh → generate ---
        logger.info("[BRIEFING CACHE] MISS key=%s force=%s", cache_key, force_refresh)
        briefing = await self.generate_briefing(
            user_id=user_id,
            family_id=family_id,
            target_date=target_date,
            period=period,
        )

        # --- Write-through to cache ---
        try:
            await redis_client.set(cache_key, briefing.model_dump_json(), ttl=_BRIEFING_CACHE_TTL)
        except Exception:
            logger.warning("[BRIEFING CACHE] Redis write error", exc_info=True)

        return briefing

    async def _get_user_timezone(self, user_id: UUID) -> ZoneInfo:
        """Load per-user timezone from user_insight_settings."""
        from ...insight.models import UserInsightSettings

        stmt = select(UserInsightSettings.timezone).where(
            UserInsightSettings.user_id == user_id
        )
        result = await self.session.execute(stmt)
        tz_name = result.scalar_one_or_none()
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except (KeyError, ValueError):
                logger.warning("Invalid timezone '%s' for user %s, using default", tz_name, user_id)
        return DEFAULT_TIMEZONE

    async def generate_briefing(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: Optional[date] = None,
        period: Optional[str] = None,
    ) -> DailyBriefing:
        """Generate a daily briefing for the user.

        Integrates SecretaryOrchestrator (priority scoring, buffer insertion,
        annotations) and DensityController (adaptive content filtering).

        Phase 1 fetches are split into two groups:
        - Group A (main session): today_events + raw_curated — sequential,
          as orchestration depends on their results.
        - Group B (independent sessions): greeting, week_count, household,
          trips — parallel via asyncio.gather for faster total latency.
        """
        import time as _time
        _t_total = _time.perf_counter()

        user_tz = await self._get_user_timezone(user_id)

        if target_date is None:
            target_date = local_today(user_tz)

        if period is None:
            now = local_now(user_tz)
            period = BriefingPeriod.from_hour(now.hour)

        # --- Phase 0: Load family preferences (non-blocking on failure) ---
        _t0 = _time.perf_counter()
        family_prefs = await self._load_family_prefs(family_id)
        logger.info("[BRIEFING PERF] Phase 0 family_prefs: %.3fs", _time.perf_counter() - _t0)

        # --- Phase 1A: Main-session fetches (sequential, needed for orchestration) ---
        _t0 = _time.perf_counter()
        today_events = await self._event_aggregator.get_today_events(
            family_id, target_date, user_tz=user_tz,
        )
        logger.info("[BRIEFING PERF] Phase 1A today_events: %.3fs (%d)", _time.perf_counter() - _t0, len(today_events))

        _t0 = _time.perf_counter()
        raw_curated = await self._event_aggregator.get_raw_curated_events(
            family_id, target_date, user_tz=user_tz,
        )
        logger.info("[BRIEFING PERF] Phase 1A raw_curated: %.3fs (%d)", _time.perf_counter() - _t0, len(raw_curated))

        # --- Phase 1B: Independent-session fetches (parallel, read-only) ---
        async def _parallel_greeting():
            async with get_db_session() as s:
                svc = DailyBriefingService(s)
                return await svc._generate_greeting(
                    user_id, family_id, user_tz=user_tz,
                    target_date=target_date,
                )

        async def _parallel_week_count():
            async with get_db_session() as s:
                agg = EventAggregator(s)
                return await agg.get_week_remaining_count(
                    family_id, target_date,
                )

        async def _parallel_household():
            if period == BriefingPeriod.AFTERNOON:
                return []
            async with get_db_session() as s:
                svc = DailyBriefingService(s)
                return await svc._get_household_status(family_id, target_date)

        async def _parallel_trips():
            if period != BriefingPeriod.MORNING:
                return []
            async with get_db_session() as s:
                agg = EventAggregator(s)
                return await agg.get_upcoming_trips_for_briefing(
                    family_id, target_date, user_tz=user_tz,
                )

        _t0 = _time.perf_counter()
        greeting, week_count, household_status, upcoming_trips = await asyncio.gather(
            _parallel_greeting(),
            _parallel_week_count(),
            _parallel_household(),
            _parallel_trips(),
        )
        logger.info("[BRIEFING PERF] Phase 1B parallel: %.3fs", _time.perf_counter() - _t0)

        # --- Phase 1.5: Orchestrate day schedule ---
        _t0 = _time.perf_counter()
        orchestrated_day = await self._orchestrate_events(
            family_id, user_id, target_date, raw_curated, family_prefs,
        )
        logger.info("[BRIEFING PERF] Phase 1.5 orchestrate: %.3fs", _time.perf_counter() - _t0)

        _t0 = _time.perf_counter()
        emotional_trend = await self._compute_emotional_trend(user_id)
        logger.info("[BRIEFING PERF] emotional_trend: %.3fs", _time.perf_counter() - _t0)

        density_profile = self._density_controller.compute_profile(
            orchestrated_day, period, family_prefs=family_prefs,
            emotional_trend=emotional_trend, target_date=target_date,
        )

        # Filter afternoon events after fetch
        if period == BriefingPeriod.AFTERNOON:
            now = local_now(user_tz)
            current_time = now.strftime("%H:%M")
            today_events = [
                e for e in today_events
                if e.time == "\u5168\u5929" or not e.time or e.time >= current_time
            ]

        # --- Phase 1.6: Unified recommendation generation ---
        _t0 = _time.perf_counter()
        recommendations = await self._recommendation_engine.generate(
            user_id=user_id,
            family_id=family_id,
            target_date=target_date,
            period=period,
            limit=density_profile.max_recommendations + density_profile.max_annotations,
            orchestrated_day=orchestrated_day,
        )
        logger.info("[BRIEFING PERF] Phase 1.6 recommendations: %.3fs (%d)", _time.perf_counter() - _t0, len(recommendations))

        insights = self._recommendations_to_insights(recommendations)
        suggestions = self._recommendations_to_suggestions(recommendations)

        # Apply density-based limits
        insights = insights[:density_profile.max_recommendations]
        suggestions = suggestions[:density_profile.max_annotations]

        # --- Phase 2: Depends on today_events / period ---
        prep_reminders: List[str] = []
        tomorrow_preview: List[BriefingEvent] = []

        _t0 = _time.perf_counter()
        if period == BriefingPeriod.EVENING:
            tomorrow = target_date + timedelta(days=1)
            tomorrow_preview = await self._event_aggregator.get_today_events(
                family_id, tomorrow, user_tz=user_tz,
            )
            prep_reminders = await self._suggestion_generator.get_preparation_reminders(
                family_id, tomorrow, user_id=user_id,
            )
        else:
            prep_reminders = await self._suggestion_generator.get_preparation_reminders(
                family_id, target_date, user_id=user_id,
            )
        logger.info("[BRIEFING PERF] Phase 2 prep: %.3fs", _time.perf_counter() - _t0)

        # --- Phase 3: Detect alerts ---
        alerts = await self._detect_alerts(family_id, target_date, today_events)

        # Conditionally hide household / trips per density profile
        if not density_profile.show_household:
            household_status = []
        if not density_profile.show_upcoming_trips:
            upcoming_trips = []

        # Enrich alerts from orchestrator gap warnings
        alerts = list(alerts) + self._gap_warnings_to_alerts(orchestrated_day)

        # --- Phase 4: Apply clean desk algorithm ---
        # Preserve original event count before clean desk filtering
        original_event_count = len(today_events)

        # Tag each content item with its category for post-split reconstruction.
        # Events are scored highest (schedule is primary), then insights, then suggestions.
        scored_items = (
            [("event", e) for e in today_events]
            + [("insight", i) for i in insights]
            + [("suggestion", s) for s in suggestions]
        )
        urgency_items = [("alert", a) for a in alerts]

        clean_result = self._density_controller.apply_clean_desk(
            density_profile, urgency_items, scored_items,
        )

        # Reconstruct typed lists from visible items
        visible_set = set(id(tagged[1]) for tagged in clean_result.visible_items)
        today_events = [e for e in today_events if id(e) in visible_set]
        insights = [i for i in insights if id(i) in visible_set]
        suggestions = [s for s in suggestions if id(s) in visible_set]
        deferred_count = len(clean_result.deferred_items)

        # Build annotation schemas
        annotations = self._build_annotation_schemas(orchestrated_day)

        # Build preparation timelines for events with pending prep items
        _t0 = _time.perf_counter()
        prep_annotations = await self._build_preparation_timelines(
            raw_curated, orchestrated_day,
        )
        logger.info("[BRIEFING PERF] prep_timelines: %.3fs", _time.perf_counter() - _t0)
        annotations = annotations + prep_annotations

        # Build secretary summary from orchestrated day data
        secretary_summary = await self._build_secretary_summary(
            orchestrated_day, today_events, alerts, density_profile,
            emotional_state=density_profile.emotional_state if density_profile else None,
        )

        # E5: Create PendingActions for deferral suggestions
        await self._create_deferral_pending_actions(
            orchestrated_day, user_id, family_id,
        )

        logger.info("[BRIEFING PERF] === TOTAL: %.3fs ===", _time.perf_counter() - _t_total)

        return DailyBriefing(
            date=target_date,
            greeting=greeting,
            period=period,
            today_event_count=original_event_count,
            today_events=today_events,
            preparation_reminders=prep_reminders,
            week_remaining_count=week_count,
            smart_suggestions=suggestions,
            insights=insights,
            household_status=household_status,
            upcoming_trips=upcoming_trips,
            alerts=alerts,
            tomorrow_preview=tomorrow_preview,
            density_level=density_profile.density_level,
            density_score=orchestrated_day.density_score if orchestrated_day else 0.0,
            annotations=annotations,
            secretary_summary=secretary_summary,
            suggested_reorder=self._build_suggested_reorder(orchestrated_day),
            time_slots=self._build_time_slots(orchestrated_day),
            deferral_suggestions=self._build_deferral_suggestions(orchestrated_day),
            deferred_count=deferred_count,
            day_theme=self._build_day_theme_schema(orchestrated_day),
        )

    # -- deferral PendingActions (E5) ------------------------------------------

    async def _create_deferral_pending_actions(
        self,
        orchestrated_day,
        user_id: UUID,
        family_id: UUID,
    ) -> None:
        """Create PendingAction records for deferral suggestions (E5).

        Each deferral suggestion from the orchestrator becomes a SUGGEST_DEFER
        PendingAction so the user can confirm or dismiss it.

        Deduplication: if there is already a pending SUGGEST_DEFER action for
        this user, skip creation entirely to prevent duplicates from retries
        or repeated briefing generation.
        """
        if orchestrated_day is None or not orchestrated_day.deferral_suggestions:
            return

        try:
            from ...conversation.pending_action import PendingAction, ActionType

            # Dedup guard: skip if any pending deferral already exists for this user
            existing_stmt = (
                select(PendingAction.id)
                .where(
                    PendingAction.user_id == user_id,
                    PendingAction.action_type == ActionType.SUGGEST_DEFER.value,
                    PendingAction.status == "pending",
                )
                .limit(1)
            )
            existing = await self.session.execute(existing_stmt)
            if existing.scalar_one_or_none() is not None:
                logger.debug(
                    "Skipping deferral PendingAction creation for user %s: "
                    "existing pending deferral found",
                    user_id,
                )
                return

            for suggestion in orchestrated_day.deferral_suggestions:
                suggested_date_iso = None
                suggested_date_display = "稍后安排"
                if suggestion.suggested_new_date is not None:
                    suggested_date_iso = suggestion.suggested_new_date.isoformat()
                    suggested_date_display = suggestion.suggested_new_date.strftime(
                        "%m月%d日"
                    )

                pending = PendingAction(
                    user_id=user_id,
                    family_id=family_id,
                    action_type=ActionType.SUGGEST_DEFER.value,
                    payload={
                        "event_id": str(suggestion.event_id),
                        "suggested_new_date": suggested_date_iso,
                        "reason": suggestion.reason,
                    },
                    display_data=build_display_data(
                        "suggest_defer",
                        {
                            "event_title": suggestion.event_title,
                            "suggested_date_display": suggested_date_display,
                        },
                        description=suggestion.reason,
                    ),
                    expires_at=utc_now() + timedelta(hours=12),
                )
                self.session.add(pending)

            logger.info(
                "Created %d deferral PendingAction(s) for user %s",
                len(orchestrated_day.deferral_suggestions),
                user_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to create deferral PendingActions for user %s: %s",
                user_id, exc,
            )

    # -- greeting -------------------------------------------------------------

    # -- greeting template pools -----------------------------------------------
    # Each time slot has 4+ variants. Selection is deterministic per user+date
    # via hash so the same user sees the same greeting on refresh but a
    # different one each day.

    _GREETING_POOLS: Dict[str, list] = {
        "late_night": [
            ("\U0001f319", "夜深了，{title}，早点休息"),
            ("\U0001f319", "{title}，这么晚了还没睡呀"),
            ("\U0001f319", "{title}，夜深了，别太累了"),
            ("\U0001f319", "{title}，该休息啦，明天的事明天再说"),
        ],
        "early_morning": [
            ("\u2600\ufe0f", "早安，{title}"),
            ("\u2600\ufe0f", "{title}，新的一天开始啦"),
            ("\u2600\ufe0f", "早呀{title}，今天也要加油"),
            ("\u2600\ufe0f", "{title}早安，先看看今天的安排"),
            ("\u2600\ufe0f", "早上好{title}，精神不错的样子"),
        ],
        "morning": [
            ("\U0001f324\ufe0f", "上午好，{title}"),
            ("\U0001f324\ufe0f", "{title}，上午好呀"),
            ("\U0001f324\ufe0f", "上午好{title}，看看今天还有什么安排"),
            ("\U0001f324\ufe0f", "{title}，上午过得顺利吗"),
        ],
        "noon": [
            ("\U0001f31e", "中午好，{title}"),
            ("\U0001f31e", "{title}，中午了，记得吃饭"),
            ("\U0001f31e", "{title}中午好，歇一下再继续"),
            ("\U0001f31e", "中午好{title}，先吃饭再说"),
        ],
        "afternoon": [
            ("\u26c5", "下午好，{title}"),
            ("\u26c5", "{title}，下午好呀"),
            ("\u26c5", "下午好{title}，下午也要加油"),
            ("\u26c5", "{title}，下午过得怎么样"),
        ],
        "evening": [
            ("\U0001f306", "晚上好，{title}"),
            ("\U0001f306", "{title}，忙了一天辛苦了"),
            ("\U0001f306", "晚上好{title}，今天辛苦啦"),
            ("\U0001f306", "{title}，晚上好呀，放松一下吧"),
        ],
        "night": [
            ("\U0001f319", "夜深了，{title}，早点休息"),
            ("\U0001f319", "{title}，这么晚了还没睡呀"),
            ("\U0001f319", "{title}，夜深了，别太累了"),
            ("\U0001f319", "{title}，该休息啦，明天的事明天再说"),
        ],
    }

    @staticmethod
    def _time_slot_key(hour: int) -> str:
        """Map hour to greeting pool key."""
        if hour < 6:
            return "late_night"
        if hour < 9:
            return "early_morning"
        if hour < 12:
            return "morning"
        if hour < 14:
            return "noon"
        if hour < 18:
            return "afternoon"
        if hour < 22:
            return "evening"
        return "night"

    async def _generate_greeting(
        self,
        user_id: UUID,
        family_id: UUID,
        user_tz: Optional[ZoneInfo] = None,
        target_date: Optional[date] = None,
    ) -> str:
        """Generate a personalized time-based greeting with user name.

        Uses a template pool with hash-based selection so the same user sees
        the same greeting on refresh but a different one each day.
        """
        from ...member.models.user import User

        tz = user_tz or DEFAULT_TIMEZONE
        now = local_now(tz)
        hour = now.hour

        title = "\u8001\u677f"
        try:
            result = await self.session.execute(
                select(User.nickname, User.username).where(User.id == user_id)
            )
            row = result.one_or_none()
            if row:
                title = row[0] or row[1] or "\u8001\u677f"
        except Exception:
            pass

        slot_key = self._time_slot_key(hour)
        pool = self._GREETING_POOLS[slot_key]

        # Deterministic selection: same user + same date → same greeting
        selection_date = target_date or now.date()
        idx = hash(str(user_id) + str(selection_date)) % len(pool)
        icon, template = pool[idx]

        return f"{icon} {template.format(title=title)}"

    # -- alerts ---------------------------------------------------------------

    async def _detect_alerts(
        self,
        family_id: UUID,
        target_date: date,
        today_events: List[BriefingEvent],
    ) -> List[BriefingAlert]:
        """Detect anomalies in today's events."""
        alerts: List[BriefingAlert] = []
        alert_id = 0

        timed_events: List[tuple] = []
        for event in today_events:
            if event.time and event.time != "\u5168\u5929":
                try:
                    hour, minute = map(int, event.time.split(":"))
                    start_dt = datetime.combine(
                        target_date,
                        datetime.min.time().replace(hour=hour, minute=minute),
                    )
                    end_dt = start_dt + timedelta(hours=1)
                    timed_events.append((event, start_dt, end_dt))
                except (ValueError, TypeError):
                    pass

        _NON_CONFLICT_TYPES = {"holiday", "holiday_legal", "holiday_lunar", "holiday_solar_term"}
        seen_conflicts: set = set()
        for i, (event_a, start_a, end_a) in enumerate(timed_events):
            for j in range(i + 1, len(timed_events)):
                event_b, start_b, end_b = timed_events[j]

                if event_a.event_type in _NON_CONFLICT_TYPES or event_b.event_type in _NON_CONFLICT_TYPES:
                    continue

                if start_a < end_b and start_b < end_a:
                    conflict_key = frozenset([event_a.id, event_b.id])
                    if conflict_key not in seen_conflicts:
                        seen_conflicts.add(conflict_key)
                        alert_id += 1
                        alerts.append(BriefingAlert(
                            id=f"alert_{alert_id}",
                            alert_type="conflict",
                            severity="warning",
                            title="\u65f6\u95f4\u51b2\u7a81",
                            description=(
                                f"\u300c{event_a.title}\u300d\u4e0e"
                                f"\u300c{event_b.title}\u300d\u65f6\u95f4\u91cd\u53e0"
                            ),
                            related_event_ids=[event_a.id, event_b.id],
                            action_label="\u8c03\u6574\u65e5\u7a0b",
                            icon="\u26a0\ufe0f",
                        ))

        high_priority_types = {"task", "reminder", "deadline"}
        blocking_count = sum(
            1 for e in today_events
            if e.event_type in high_priority_types
        )
        if blocking_count >= 3:
            alert_id += 1
            alerts.append(BriefingAlert(
                id=f"alert_{alert_id}",
                alert_type="blocking",
                severity="info",
                title="\u4eca\u65e5\u5f85\u529e\u8f83\u591a",
                description=(
                    f"\u6709 {blocking_count} \u9879\u5f85\u529e/\u63d0\u9192\u9700\u8981\u5904\u7406"
                    f"\uff0c\u5efa\u8bae\u4f18\u5148\u5b89\u6392"
                ),
                related_event_ids=[],
                action_label="\u67e5\u770b\u5f85\u529e",
                icon="\U0001f4cb",
            ))

        return alerts

    # -- memory insights ------------------------------------------------------

    async def _get_memory_insights(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
        period: str = BriefingPeriod.MORNING,
    ) -> List[BriefingInsight]:
        """Get AI-generated insights from the unified InsightOrchestrator.

        Cross-channel dedup: insights already delivered via sidekick injection
        within the last 24 h are excluded.  After inclusion, each insight is
        marked as delivered via the ``briefing`` channel so that a later
        sidekick attempt will also be blocked.
        """
        from .insight_delivery_ledger import InsightDeliveryLedger

        insights: List[BriefingInsight] = []
        ledger = InsightDeliveryLedger()
        user_id_str = str(user_id)

        try:
            from .insight_orchestrator import InsightOrchestrator

            orchestrator = InsightOrchestrator(self.session)
            items = await orchestrator.get_for_briefing(user_id, family_id, limit=10)

            for item in items:
                # Cross-channel dedup: skip if already delivered
                if item.id and await ledger.was_delivered(user_id_str, str(item.id)):
                    continue

                urgency_score = item.urgency_score
                urgency = "high" if urgency_score >= 80 else ("low" if urgency_score < 40 else "normal")
                priority = max(1, item.importance_score // 10)

                insights.append(BriefingInsight(
                    id=item.id,
                    insight_type=item.insight_type,
                    title=item.title,
                    content=item.content,
                    priority=priority,
                    urgency=urgency,
                    action_options=[item.suggested_action] if item.suggested_action else [],
                    action_data={},
                    entity_refs=[
                        BriefingEntityRef(
                            entity_type=e.entity_type,
                            entity_id=e.entity_id,
                        )
                        for e in getattr(item, "entity_refs", [])
                    ],
                ))

        except Exception as e:
            logger.error("Error getting unified insights: %s", e)

        urgency_order = {"high": 0, "normal": 1, "low": 2}
        insights.sort(key=lambda x: (-x.priority, urgency_order.get(x.urgency, 1)))

        if period == BriefingPeriod.AFTERNOON:
            insights = [i for i in insights if i.priority >= 7]
            selected = insights[:3]
        elif period == BriefingPeriod.EVENING:
            reflective_types = {"observation", "followup", "correlation", "memory"}
            reflective = [i for i in insights if i.insight_type in reflective_types]
            others = [i for i in insights if i.insight_type not in reflective_types]
            selected = (reflective + others)[:4]
        else:
            selected = insights[:5]

        # Mark selected insights as delivered via briefing channel
        for insight in selected:
            if insight.id:
                await ledger.mark_delivered(user_id_str, str(insight.id), "briefing")

        return selected

    # -- household status -----------------------------------------------------

    async def _get_household_status(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[HouseholdStatus]:
        """Get household appliance maintenance and shipping statuses."""
        status_items: List[HouseholdStatus] = []

        try:
            from ...housing_housekeeping.services.appliance_maintainer import ApplianceMaintainer

            maintainer = ApplianceMaintainer(self.session)
            maintenance_due = await maintainer.check_maintenance_due(
                family_id=family_id,
                days_before=7,
            )

            for item in maintenance_due[:3]:
                days_until = item.get("days_until_maintenance", 0)
                appliance_type = item.get("type", "\u8bbe\u5907")
                brand = item.get("brand", "")

                type_names = {
                    "water_purifier": "\u51c0\u6c34\u5668\u6ee4\u82af",
                    "air_conditioner": "\u7a7a\u8c03",
                    "washing_machine": "\u6d17\u8863\u673a",
                    "refrigerator": "\u51b0\u7bb1",
                    "range_hood": "\u6cb9\u70df\u673a",
                    "water_heater": "\u70ed\u6c34\u5668",
                }
                appliance_name = type_names.get(appliance_type, appliance_type)
                if brand:
                    appliance_name = f"{brand}{appliance_name}"

                if days_until <= 0:
                    description = f"{appliance_name}\u5df2\u5230\u671f\uff0c\u9700\u8981\u7ef4\u62a4"
                    urgency = "high"
                elif days_until == 1:
                    description = f"{appliance_name}\u660e\u5929\u5230\u671f"
                    urgency = "high"
                elif days_until <= 3:
                    description = f"{appliance_name}{days_until}\u5929\u540e\u5230\u671f"
                    urgency = "normal"
                else:
                    description = f"{appliance_name}{days_until}\u5929\u540e\u9700\u8981\u7ef4\u62a4"
                    urgency = "low"

                status_items.append(HouseholdStatus(
                    id=f"maint_{item.get('appliance_id', '')}",
                    title="\u8bbe\u5907\u7ef4\u62a4\u63d0\u9192",
                    description=description,
                    icon="\U0001f527",
                    urgency=urgency,
                    action_label="\u67e5\u770b\u8be6\u60c5",
                ))
        except ImportError:
            logger.debug("Appliance maintainer service not available")
        except Exception as e:
            logger.error("Error getting appliance maintenance status: %s", e)

        try:
            from ...data_connection.services.external_data_service import ExternalDataService

            external_service = ExternalDataService(self.session)
            shipments = await external_service.get_shipping_updates(
                family_id=family_id,
                since_days=14,
                active_only=True,
                usage_type="daily_briefing",
            )

            for shipment in shipments[:2]:
                if shipment.estimated_delivery:
                    delivery_date = to_local_date(shipment.estimated_delivery)
                    days_until = (delivery_date - target_date).days
                    if days_until <= 3:
                        if days_until <= 0:
                            description = f"\u5feb\u9012\u4eca\u65e5\u9001\u8fbe - {shipment.courier}"
                        elif days_until == 1:
                            description = f"\u5feb\u9012\u660e\u5929\u9001\u8fbe - {shipment.courier}"
                        else:
                            description = f"\u5feb\u9012{days_until}\u5929\u540e\u9001\u8fbe - {shipment.courier}"

                        status_items.append(HouseholdStatus(
                            id=f"ship_{shipment.id}",
                            title="\u5305\u88f9\u914d\u9001",
                            description=description,
                            icon="\U0001f4e6",
                            urgency="normal" if days_until > 0 else "high",
                            action_label="\u67e5\u770b\u7269\u6d41",
                        ))
        except ImportError:
            logger.debug("External data service not available")
        except Exception as e:
            logger.error("Error getting shipping status: %s", e)

        return status_items[:5]

    # -- orchestration helpers ------------------------------------------------

    async def _load_family_prefs(self, family_id: UUID):
        """Load FamilyPreference for the family (returns None on failure)."""
        try:
            from ...curation.services.family_preference_repository import (
                FamilyPreferenceRepository,
            )
            repo = FamilyPreferenceRepository(self.session)
            return await repo.get_or_create_default(family_id)
        except Exception:
            # This path is intentionally non-blocking. Reset transaction state
            # so later reads in this request won't cascade with "transaction aborted".
            try:
                await self.session.rollback()
            except Exception:
                logger.debug("Rollback after FamilyPreference failure also failed", exc_info=True)
            logger.debug("Could not load FamilyPreference for %s", family_id, exc_info=True)
            return None

    async def _compute_emotional_trend(self, user_id: UUID) -> str:
        """Compute the user's emotional trend for density control.

        Returns the trend string ("declining", "improving", "stable").
        Falls back to "stable" on any error so briefing generation is unaffected.
        """
        try:
            from ...memory.emotional_trend_service import compute_emotional_trend

            result = await compute_emotional_trend(self.session, user_id)
            return result.trend if result.trend != "unknown" else "stable"
        except Exception:
            logger.debug(
                "Emotional trend computation failed for user %s, defaulting to stable",
                user_id,
                exc_info=True,
            )
            return "stable"

    async def _build_preparation_timelines(
        self,
        raw_curated: list,
        orchestrated_day,
    ) -> List[SecretaryAnnotationSchema]:
        """Build preparation timelines for events with undone prep items.

        Returns additional annotation schemas derived from preparation
        timelines.  Falls back to an empty list on failure.
        """
        if not raw_curated or orchestrated_day is None:
            return []

        try:
            from ...curation.services.orchestrator import (
                PreparationItem as OrchestratorPrepItem,
                SecretaryOrchestrator,
            )
            from ...curation.services.priority_engine import HybridPriorityEngine

            annotations: List[SecretaryAnnotationSchema] = []
            orchestrator = SecretaryOrchestrator(
                self.session,
                HybridPriorityEngine(calibration_enabled=False),
            )

            for event in raw_curated:
                prep_rows = getattr(event, "preparation_item_rows", None) or []
                pending_items = [r for r in prep_rows if not r.done]
                if not pending_items or not event.normalized_start:
                    continue

                orch_items = [
                    OrchestratorPrepItem(
                        title=item.text,
                        duration_minutes=30,
                        note=item.source,
                    )
                    for item in pending_items
                ]

                timeline = await orchestrator.build_preparation_timeline(
                    anchor_event=event,
                    preparation_items=orch_items,
                )

                for step in timeline.steps:
                    time_str = step.suggested_start.strftime("%H:%M")
                    annotations.append(SecretaryAnnotationSchema(
                        event_id=str(event.id),
                        text=f"[准备] {time_str} {step.text}（约{step.estimated_minutes}分钟）",
                        source="preparation_timeline",
                    ))

            return annotations
        except Exception:
            logger.debug(
                "Preparation timeline generation failed, skipping",
                exc_info=True,
            )
            return []

    async def _orchestrate_events(
        self,
        family_id: UUID,
        user_id: UUID,
        target_date: date,
        raw_curated: list,
        family_prefs,
        next_day_events: Optional[list] = None,
    ):
        """Run SecretaryOrchestrator on raw curated events.

        Returns an OrchestratedDay or None on failure / empty input.
        """
        if not raw_curated:
            return None
        try:
            from ...curation.services.orchestrator import SecretaryOrchestrator
            from ...curation.services.priority_engine import HybridPriorityEngine
            orchestrator = SecretaryOrchestrator(self.session, HybridPriorityEngine())
            # Load next-day events for evening_forward warning (UTC-aware)
            if next_day_events is None:
                try:
                    from ...curation.models import CuratedEvent
                    next_day = target_date + timedelta(days=1)
                    tz = DEFAULT_TIMEZONE
                    tomorrow_start_utc = datetime.combine(next_day, datetime.min.time(), tzinfo=tz).astimezone(ZoneInfo("UTC"))
                    tomorrow_end_utc = datetime.combine(next_day + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(ZoneInfo("UTC"))
                    stmt = (
                        select(CuratedEvent)
                        .where(
                            CuratedEvent.family_id == family_id,
                            CuratedEvent.is_active.is_(True),
                            CuratedEvent.normalized_start >= tomorrow_start_utc,
                            CuratedEvent.normalized_start < tomorrow_end_utc,
                        )
                        .order_by(CuratedEvent.normalized_start)
                    )
                    result = await self.session.execute(stmt)
                    next_day_events = list(result.scalars().all())
                except Exception:
                    logger.debug("Failed to load next-day events for evening_forward", exc_info=True)

            return await orchestrator.orchestrate_day(
                family_id=family_id,
                user_id=user_id,
                target_date=target_date,
                events=raw_curated,
                family_prefs=family_prefs,
                next_day_events=next_day_events,
            )
        except Exception:
            logger.warning(
                "Orchestration failed for family %s, continuing without",
                family_id,
                exc_info=True,
            )
            return None

    @staticmethod
    def _gap_warnings_to_alerts(orchestrated_day) -> List[BriefingAlert]:
        """Convert orchestrator GapWarnings into BriefingAlerts.

        Gaps that have already been auto-adjusted (have a suggestion with
        buffer slot inserted) are skipped — the orchestrator already handled
        them via time_slots.  Remaining gaps become soft "suggestion" alerts
        so the user is informed without alarm.
        """
        if orchestrated_day is None:
            return []

        # Collect event IDs that have buffer slots — those gaps are resolved.
        resolved_event_ids: set = set()
        for slot in orchestrated_day.slots:
            if slot.slot_type in ("buffer", "travel"):
                resolved_event_ids.add(slot.event_id)

        alerts: List[BriefingAlert] = []
        _GAP_ICONS = {
            "no_buffer": "\U0001f4a1",
            "impossible_commute": "\U0001f4a1",
            "back_to_back": "\U0001f4a1",
            "overloaded": "\U0001f525",
            "meal_conflict": "\U0001f37d\ufe0f",
        }
        gap_alert_idx = 0
        for gap in orchestrated_day.gaps:
            # Skip gaps whose affected events already have buffer/travel slots
            if gap.affected_event_ids and all(
                eid in resolved_event_ids for eid in gap.affected_event_ids
            ):
                continue

            alerts.append(BriefingAlert(
                id=f"gap_{gap_alert_idx}",
                alert_type=f"gap_{gap.gap_type}",
                severity="suggestion",
                title=gap.gap_type.replace("_", " ").title(),
                description=gap.suggestion or "",
                related_event_ids=[str(eid) for eid in gap.affected_event_ids],
                icon=_GAP_ICONS.get(gap.gap_type, "\U0001f4a1"),
            ))
            gap_alert_idx += 1
        return alerts

    @staticmethod
    def _build_annotation_schemas(orchestrated_day) -> List[SecretaryAnnotationSchema]:
        """Convert orchestrator annotations into schema objects."""
        if orchestrated_day is None:
            return []
        return [
            SecretaryAnnotationSchema(
                event_id=str(ann.event_id),
                text=ann.text,
                source=ann.source,
            )
            for ann in orchestrated_day.annotations
        ]

    @staticmethod
    def _build_day_theme_schema(orchestrated_day) -> Optional[DayThemeSchema]:
        """Convert orchestrator DayTheme into API schema."""
        if orchestrated_day is None or orchestrated_day.day_theme is None:
            return None
        theme = orchestrated_day.day_theme
        return DayThemeSchema(
            title=theme.title,
            primary_event_id=str(theme.primary_event_id) if theme.primary_event_id is not None else None,
            focus=theme.focus,
            prep_note=theme.prep_note,
            evening_forward=theme.evening_forward,
        )

    @staticmethod
    def _build_suggested_reorder(orchestrated_day) -> Optional[List[str]]:
        """Convert orchestrator suggested_reorder UUIDs to string list."""
        if orchestrated_day is None or orchestrated_day.suggested_reorder is None:
            return None
        return [str(uid) for uid in orchestrated_day.suggested_reorder]

    @staticmethod
    def _build_time_slots(orchestrated_day) -> List[TimeSlotSchema]:
        """Convert orchestrator TimeSlot tuples to API schemas."""
        if orchestrated_day is None or not orchestrated_day.slots:
            return []
        return [
            TimeSlotSchema(
                start=slot.start.strftime("%H:%M"),
                end=slot.end.strftime("%H:%M"),
                event_id=str(slot.event_id) if slot.event_id is not None else None,
                slot_type=slot.slot_type,
                note=slot.note,
            )
            for slot in orchestrated_day.slots
        ]

    @staticmethod
    def _build_deferral_suggestions(orchestrated_day) -> List[DeferralSuggestionSchema]:
        """Convert orchestrator DeferralSuggestion tuples to API schemas (E5)."""
        if orchestrated_day is None or not orchestrated_day.deferral_suggestions:
            return []
        return [
            DeferralSuggestionSchema(
                event_id=str(ds.event_id),
                event_title=ds.event_title,
                reason=ds.reason,
                suggested_new_date=ds.suggested_new_date,
                priority_level=ds.priority_level,
            )
            for ds in orchestrated_day.deferral_suggestions
        ]

    @staticmethod
    def _build_secretary_summary_fallback(
        orchestrated_day,
        today_events: List[BriefingEvent],
        alerts: List[BriefingAlert],
        density_profile,
        emotional_state: Optional[str] = None,
    ) -> str:
        """Warm rule-based fallback for secretary summary.

        Used when LLM call fails or is unavailable. Produces natural
        conversational Chinese instead of a dashboard-style status line.
        """
        event_count = len(today_events)
        if event_count == 0:
            return "今天没什么安排，难得清闲，好好享受一下。"

        density_level = density_profile.density_level if density_profile else "STANDARD"

        # Build the opening line based on density + emotional state
        if emotional_state == "stressed":
            if density_level == "FOCUSED":
                opening = f"今天有{event_count}件事，不过别担心，一件一件来就好。"
            else:
                opening = f"今天有{event_count}件事，节奏还行，记得给自己留点喘息的时间。"
        elif emotional_state == "relaxed" and density_level in ("RELAXED", "REFLECTIVE"):
            opening = f"今天就{event_count}件小事，可以从容安排。"
        elif density_level == "FOCUSED":
            opening = f"今天排了{event_count}件事，有点满，抓好重点就行。"
        elif density_level == "RELAXED":
            opening = f"今天安排不多，{event_count}件事，轻松搞定。"
        else:
            opening = f"今天有{event_count}件事，安排不算满。"

        parts = [opening]

        # Gap info — conversational phrasing
        gap_count = len(orchestrated_day.gaps) if orchestrated_day else 0
        if gap_count > 0:
            if gap_count == 1:
                parts.append("中间有段空闲可以喘口气。")
            else:
                parts.append(f"中间有{gap_count}段空闲可以喘口气。")

        # Alert info — conversational phrasing
        alert_count = len(alerts)
        if alert_count == 1:
            parts.append("有个小提醒别忘了看一下。")
        elif alert_count > 1:
            parts.append(f"有{alert_count}条提醒别忘了看一下。")

        return "".join(parts)

    async def _build_secretary_summary(
        self,
        orchestrated_day,
        today_events: List[BriefingEvent],
        alerts: List[BriefingAlert],
        density_profile,
        emotional_state: Optional[str] = None,
    ) -> Optional[str]:
        """Build a one-line secretary summary via Haiku LLM.

        Assembles structured context from the day's schedule and emotional
        state, then calls Haiku for a warm, natural summary. Falls back to
        ``_build_secretary_summary_fallback`` on failure.
        """
        fallback = self._build_secretary_summary_fallback(
            orchestrated_day, today_events, alerts, density_profile,
            emotional_state=emotional_state,
        )

        event_count = len(today_events)
        if event_count == 0:
            return fallback

        try:
            from ...insight.insight_content_generator import generate_summary_text

            density_level = density_profile.density_level if density_profile else "STANDARD"
            alert_count = len(alerts)
            gap_count = len(orchestrated_day.gaps) if orchestrated_day else 0

            # Build up to 5 event titles for context
            event_titles = [e.title for e in today_events[:5]]

            day_theme_name = ""
            if orchestrated_day and hasattr(orchestrated_day, "day_theme") and orchestrated_day.day_theme:
                day_theme_name = orchestrated_day.day_theme.title

            context_xml = (
                f"<daily_summary_context>\n"
                f"  <event_count>{event_count}</event_count>\n"
                f"  <event_titles>{', '.join(event_titles)}</event_titles>\n"
                f"  <density_level>{density_level}</density_level>\n"
                f"  <day_theme>{day_theme_name}</day_theme>\n"
                f"  <gap_count>{gap_count}</gap_count>\n"
                f"  <alert_count>{alert_count}</alert_count>\n"
                f"  <emotional_state>{emotional_state or 'neutral'}</emotional_state>\n"
                f"</daily_summary_context>"
            )
            return await generate_summary_text(
                context_xml=context_xml,
                fallback=fallback,
            )
        except Exception:
            return fallback

    # -- recommendation mapping ------------------------------------------------

    _SUGGESTION_STRATEGIES = frozenset({"smart_suggestion"})

    @staticmethod
    def _recommendations_to_insights(
        recommendations: List[Recommendation],
    ) -> List[BriefingInsight]:
        """Map Recommendation objects to BriefingInsight schemas.

        Insight-sourced and trip_correlation recommendations become insights.
        """
        insights: List[BriefingInsight] = []
        for rec in recommendations:
            if rec.source_strategy in DailyBriefingService._SUGGESTION_STRATEGIES:
                continue
            priority = max(1, int(rec.priority * 10))
            urgency = rec.metadata.get("urgency", "normal")
            if isinstance(urgency, (int, float)):
                urgency = "high" if urgency >= 80 else ("low" if urgency < 40 else "normal")

            action_options = rec.metadata.get("action_options", [])
            suggested = rec.metadata.get("suggested_action")
            if suggested and not action_options:
                action_options = [suggested]

            # Extract entity refs from recommendation metadata
            rec_entity_refs = [
                BriefingEntityRef(
                    entity_type=key.replace("related_", "").replace("_id", ""),
                    entity_id=val,
                )
                for key, val in rec.metadata.items()
                if key.startswith("related_") and key.endswith("_id") and val
            ]

            insights.append(BriefingInsight(
                id=str(rec.id),
                insight_type=rec.recommendation_type,
                title=rec.title,
                content=rec.content,
                priority=priority,
                urgency=urgency,
                action_options=action_options,
                action_data=rec.metadata.get("action_data", {}),
                entity_refs=rec_entity_refs,
            ))
        return insights

    @staticmethod
    def _recommendations_to_suggestions(
        recommendations: List[Recommendation],
    ) -> List[BriefingSuggestion]:
        """Map Recommendation objects to BriefingSuggestion schemas.

        Only smart_suggestion-sourced recommendations become suggestions.
        """
        suggestions: List[BriefingSuggestion] = []
        for rec in recommendations:
            if rec.source_strategy not in DailyBriefingService._SUGGESTION_STRATEGIES:
                continue
            suggestions.append(BriefingSuggestion(
                label=rec.title,
                action_type=rec.recommendation_type,
                action_data=rec.metadata.get("action_data", {}),
            ))
        return suggestions

    # -- backward-compat delegates (kept for any in-module callers) -----------

    def _get_event_icon(self, date_type: str) -> str:
        return get_event_icon(date_type)

    def _get_event_details(
        self,
        date_type: str,
        title: str,
        member_name: Optional[str],
    ) -> tuple:
        return get_event_details(date_type, title, member_name)

    def _calculate_next_occurrence(
        self,
        important_date,
        reference_date: date,
    ) -> Optional[date]:
        return calculate_next_occurrence_wrapper(important_date, reference_date)
