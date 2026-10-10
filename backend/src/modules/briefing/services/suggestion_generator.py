"""
Smart suggestion and preparation-reminder generation for daily briefings.

Contains logic for creating actionable suggestions based on the current
period (morning / afternoon / evening) and upcoming events.
"""
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ....config.logging import get_logger

from ...date_manager.models import ImportantDate

from ..schemas import (
    BriefingEvent,
    BriefingSuggestion,
    BriefingPeriod,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Stateless text helpers
# ---------------------------------------------------------------------------

def get_day_word(days_ahead: int) -> str:
    """Human-friendly Chinese label for *days_ahead* offset."""
    if days_ahead == 1:
        return "\u660e\u5929"
    elif days_ahead == 2:
        return "\u540e\u5929"
    elif days_ahead == 3:
        return "3\u5929\u540e"
    else:
        return f"{days_ahead}\u5929\u540e"


def extract_destination_from_name(name: Optional[str]) -> str:
    """Strip common Chinese travel suffixes from trip names."""
    if not name:
        return "\u672a\u77e5\u76ee\u7684\u5730"
    suffixes = ["\u51fa\u5dee", "\u65c5\u884c", "\u65c5\u6e38", "\u5ea6\u5047", "\u6e38", "\u884c", "\u4e4b\u65c5"]
    result = name
    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[:-len(suffix)]
            break
    return result if result else name


def format_preparation_reminder(
    event: ImportantDate,
    day_word: str,
    days_ahead: int,
) -> Optional[str]:
    """Return a warm, conversational preparation reminder, or ``None``."""
    if event.date_type == 'birthday':
        return f"{day_word}是{event.title}，想好送什么了吗？"
    elif event.date_type in ('anniversary', 'wedding_anniversary'):
        return f"{day_word}是{event.title}，记得准备点什么惊喜。"
    elif event.date_type == 'vaccine':
        return f"{day_word}要打疫苗，提前确认一下时间和地点。"
    elif event.date_type == 'checkup':
        return f"{day_word}有体检，别忘了做好准备。"
    elif event.date_type in ('holiday', 'holiday_legal'):
        if days_ahead <= 2:
            return f"{day_word}是{event.title}，好好享受假期吧。"
    elif event.date_type == 'holiday_solar_term':
        if days_ahead <= 3:
            return f"{day_word}是{event.title}"
    elif event.date_type == 'holiday_lunar':
        if days_ahead <= 3:
            return f"{day_word}是{event.title}"
    return None


# ---------------------------------------------------------------------------
# Suggestion label variant pools (PLAN-005)
# ---------------------------------------------------------------------------
# Each label has 3+ variants. Selection is deterministic per user+date
# via hash so the same user sees the same label on refresh but a different
# one each day. action_type and action_data remain unchanged.

_LABEL_POOLS: Dict[str, List[str]] = {
    "evening_done": [
        "今天的事项已告一段落，辛苦了",
        "忙了一天辛苦啦，好好歇歇",
        "今天的事都搞定了，歇一歇吧",
    ],
    "evening_review": [
        "回顾今天的收获",
        "看看今天都做了些什么",
        "今天还不错，回顾一下吧",
    ],
    "evening_trip": [
        "查看行程安排",
        "看看行程的详细安排",
        "回顾一下行程",
    ],
    "afternoon_remaining": [
        "下午还有 {count} 项安排",
        "下午剩 {count} 件事，加油",
        "下午还有 {count} 件事要处理",
    ],
    "afternoon_free": [
        "下午暂无安排，可以处理待办",
        "下午清闲，趁机处理一下待办吧",
        "下午没什么安排，歇一会儿也行",
    ],
    "afternoon_prep": [
        "查看待准备事项",
        "看看还有什么要准备的",
        "别忘了准备的事项",
    ],
    "morning_trip": [
        "查看行程详情",
        "看看今天的行程安排",
        "出发前看看行程",
    ],
    "morning_birthday": [
        "发送祝福",
        "送上生日祝福",
        "赶紧发个祝福吧",
    ],
    "morning_prep": [
        "查看待准备事项",
        "看看还有什么要准备的",
        "别忘了准备的事项",
    ],
    "morning_tasks": [
        "完成今日待办",
        "看看今天要做的事",
        "今天的待办清单",
    ],
    "morning_empty": [
        "查看智能洞察",
        "看看有什么新发现",
        "看看有什么值得关注的",
    ],
}


def _pick_label(pool_key: str, fallback: str, **fmt_kwargs: object) -> str:
    """Pick a label variant from a pool. Without user context, returns first variant."""
    pool = _LABEL_POOLS.get(pool_key)
    if not pool:
        return fallback
    label = pool[0]
    if fmt_kwargs:
        try:
            label = label.format(**fmt_kwargs)
        except (KeyError, IndexError):
            pass
    return label


def _pick_label_for_date(
    pool_key: str,
    user_id: UUID,
    target_date: date,
    fallback: str,
    **fmt_kwargs: object,
) -> str:
    """Pick a label variant deterministically based on user_id + date."""
    pool = _LABEL_POOLS.get(pool_key)
    if not pool:
        return fallback
    idx = hash(str(user_id) + str(target_date)) % len(pool)
    label = pool[idx]
    if fmt_kwargs:
        try:
            label = label.format(**fmt_kwargs)
        except (KeyError, IndexError):
            pass
    return label


# ---------------------------------------------------------------------------
# SuggestionGenerator
# ---------------------------------------------------------------------------

class SuggestionGenerator:
    """Generates smart suggestions and preparation reminders."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -- preparation reminders ------------------------------------------------

    async def get_preparation_reminders(
        self,
        family_id: UUID,
        target_date: date,
        user_id: Optional[UUID] = None,
    ) -> List[str]:
        """Get preparation reminders for upcoming events (next 3 days)."""
        from .event_aggregator import EventAggregator

        aggregator = EventAggregator(self.session)
        reminders: List[str] = []

        # 1. Curated / Kanban preparation items
        try:
            from ...views.services.kanban_service import KanbanService

            kanban_svc = KanbanService(self.session)
            if user_id:
                upcoming = await kanban_svc.get_upcoming_events(
                    family_id=family_id,
                    user_id=user_id,
                    days=3,
                )
            else:
                from ...curation.models import CuratedEvent

                day_start_utc = datetime.combine(
                    target_date, datetime.min.time()
                ).replace(tzinfo=timezone.utc)
                day_end_utc = datetime.combine(
                    target_date + timedelta(days=3), datetime.max.time()
                ).replace(tzinfo=timezone.utc)

                stmt = (
                    select(CuratedEvent)
                    .where(and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status.notin_(["cancelled", "completed"]),
                        CuratedEvent.normalized_start >= day_start_utc,
                        CuratedEvent.normalized_start <= day_end_utc,
                    ))
                    .order_by(CuratedEvent.normalized_start)
                )
                result = await self.session.execute(stmt)
                events_raw = result.scalars().all()
                upcoming = [kanban_svc._to_kanban_event(ev) for ev in events_raw]

            for ev in upcoming:
                pending_items = [p for p in ev.preparation_items if not p.done]
                for p in pending_items:
                    reminders.append(
                        f"\u300c{ev.title}\u300d\u5f85\u51c6\u5907: {p.item}"
                    )
        except Exception as e:
            logger.error("Error getting curated prep reminders: %s", e)

        # 2. Raw ImportantDate look-ahead + travel
        try:
            for days_ahead in range(1, 4):
                check_date = target_date + timedelta(days=days_ahead)
                events = await aggregator.get_events_for_date(family_id, check_date)

                for event in events:
                    day_word = get_day_word(days_ahead)
                    reminder = format_preparation_reminder(event, day_word, days_ahead)
                    if reminder:
                        reminders.append(reminder)

            upcoming_travel = await aggregator.get_upcoming_trips(
                family_id, target_date, days_ahead=3,
            )
            seen_trips: set = set()
            for travel in upcoming_travel:
                days_until = (travel.start_date - target_date).days
                day_word = get_day_word(days_until)
                destination = travel.destination
                if not destination or destination == "\u5f85\u5b9a":
                    destination = extract_destination_from_name(travel.trip_name)
                trip_key = f"{destination}_{travel.start_date}"
                if trip_key not in seen_trips:
                    reminders.append(
                        f"{day_word}\u51fa\u53d1\u53bb{destination}\uff0c\u8bb0\u5f97\u6536\u62fe\u884c\u674e"
                    )
                    seen_trips.add(trip_key)

        except Exception as e:
            logger.error("Error getting preparation reminders: %s", e)

        return reminders[:5]

    # -- smart suggestions ----------------------------------------------------

    async def generate_smart_suggestions(
        self,
        today_events: List[BriefingEvent],
        prep_reminders: List[str],
        period: str = BriefingPeriod.MORNING,
    ) -> List[BriefingSuggestion]:
        """Generate structured smart suggestions based on events and period."""
        suggestions: List[BriefingSuggestion] = []

        if period == BriefingPeriod.EVENING:
            suggestions = self._evening_suggestions(today_events)
            return suggestions[:3]

        if period == BriefingPeriod.AFTERNOON:
            suggestions = self._afternoon_suggestions(today_events, prep_reminders)
            return suggestions[:3]

        # Morning
        suggestions = self._morning_suggestions(today_events, prep_reminders)
        return suggestions[:3]

    # -- period-specific builders (pure logic, no I/O) ------------------------

    @staticmethod
    def _evening_suggestions(
        today_events: List[BriefingEvent],
    ) -> List[BriefingSuggestion]:
        suggestions: List[BriefingSuggestion] = []
        if today_events:
            suggestions.append(BriefingSuggestion(
                label=_pick_label("evening_done", "今天的事项已告一段落，辛苦了"),
                action_type="view_insights",
                action_data={},
            ))
        suggestions.append(BriefingSuggestion(
            label=_pick_label("evening_review", "回顾今天的收获"),
            action_type="view_insights",
            action_data={},
        ))
        if any(e.event_type == 'travel' for e in today_events):
            travel_event = next(e for e in today_events if e.event_type == 'travel')
            suggestions.append(BriefingSuggestion(
                label=_pick_label("evening_trip", "查看行程安排"),
                action_type="navigate_to_trip",
                action_data={"trip_id": travel_event.id},
            ))
        return suggestions

    @staticmethod
    def _afternoon_suggestions(
        today_events: List[BriefingEvent],
        prep_reminders: List[str],
    ) -> List[BriefingSuggestion]:
        suggestions: List[BriefingSuggestion] = []
        remaining = len(today_events)
        if remaining > 0:
            suggestions.append(BriefingSuggestion(
                label=_pick_label(
                    "afternoon_remaining",
                    f"下午还有 {remaining} 项安排",
                    count=remaining,
                ),
                action_type="navigate_to_kanban",
                action_data={"section": "this_week"},
            ))
        else:
            suggestions.append(BriefingSuggestion(
                label=_pick_label("afternoon_free", "下午暂无安排，可以处理待办"),
                action_type="navigate_to_kanban",
                action_data={"section": "this_week"},
            ))
        for reminder in prep_reminders:
            if '出发' in reminder or '行李' in reminder:
                suggestions.append(BriefingSuggestion(
                    label=_pick_label("afternoon_prep", "查看待准备事项"),
                    action_type="navigate_to_kanban",
                    action_data={"section": "needs_preparation"},
                ))
                break
        return suggestions

    @staticmethod
    def _morning_suggestions(
        today_events: List[BriefingEvent],
        prep_reminders: List[str],
    ) -> List[BriefingSuggestion]:
        suggestions: List[BriefingSuggestion] = []

        for event in today_events:
            if event.event_type == 'travel' and event.trip_id:
                suggestions.append(BriefingSuggestion(
                    label=_pick_label("morning_trip", "查看行程详情"),
                    action_type="navigate_to_trip",
                    action_data={"trip_id": event.trip_id},
                ))
                break

        for event in today_events:
            if event.event_type == 'birthday':
                member_name = event.member_name or event.title.replace("的生日", "")
                suggestions.append(BriefingSuggestion(
                    label=_pick_label("morning_birthday", "发送祝福"),
                    action_type="open_chat",
                    action_data={"prefill_text": f"给{member_name}发生日祝福"},
                ))
                break

        if not any(e.event_type == 'travel' for e in today_events):
            for reminder in prep_reminders:
                if '出发' in reminder or '旅行' in reminder or '行李' in reminder:
                    suggestions.append(BriefingSuggestion(
                        label=_pick_label("morning_prep", "查看待准备事项"),
                        action_type="navigate_to_kanban",
                        action_data={"section": "needs_preparation"},
                    ))
                    break

        task_events = [e for e in today_events if e.event_type in ('task', 'reminder', 'deadline')]
        if task_events:
            suggestions.append(BriefingSuggestion(
                label=_pick_label("morning_tasks", "完成今日待办"),
                action_type="navigate_to_kanban",
                action_data={"section": "this_week"},
            ))

        if not today_events:
            suggestions.append(BriefingSuggestion(
                label=_pick_label("morning_empty", "查看智能洞察"),
                action_type="view_insights",
                action_data={},
            ))

        return suggestions
