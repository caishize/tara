"""
Schedule conflict detection for curated events.

Deterministic (non-LLM) detection of time overlaps between curated events
that represent physical commitments (business_trip, travel, meeting, appointment).
Holidays, birthdays, and other date-based events are excluded.

Smart resolution: classifies each conflict as user_confirm or auto_resolve
based on event importance signals (confidence, source types, event type).

Trip-level aggregation: Day events belonging to the same trip are aggregated
into a single virtual event spanning the full trip range before overlap checks.
This prevents false negatives (missing conflicts between trips whose individual
Day events don't overlap) and false positives (same-trip Days conflicting).
"""
import logging
from copy import copy
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....config.settings import settings
from ....core.utils.timezone import format_local_datetime

from ..models import CuratedEvent
from ..schemas import ConflictAlert, ConflictPriority

logger = get_logger(__name__)


# Event types that can have schedule conflicts
CONFLICT_EVENT_TYPES: Set[str] = {
    "business_trip", "travel", "meeting", "appointment",
}

# Maximum number of nearby events to check for conflicts
_MAX_NEARBY_EVENTS = 100


async def detect_conflicts(
    session: AsyncSession,
    family_id: UUID,
    core_event: CuratedEvent,
    user_id: Optional[UUID] = None,
    exclude_event_ids: Optional[Set[UUID]] = None,
    read_only: bool = False,
) -> List[ConflictAlert]:
    """
    Detect schedule conflicts between the core event and other active events.

    When user_id and family_id are provided, applies smart resolution:
    - Auto-resolves conflicts where one event is low-importance
    - Creates PendingAction for conflicts needing user confirmation

    Args:
        session: Database session.
        family_id: Family ID to scope the query.
        core_event: The event to check conflicts against (may represent
            a full trip range when caller expands Day events).
        user_id: Optional user ID for PendingAction creation.
        exclude_event_ids: Additional event IDs to exclude from nearby
            query (e.g. all Day events of the same trip as core_event).
        read_only: When True, only detect overlaps and build raw
            ConflictAlerts without performing auto-resolution or
            creating PendingActions. Used for read paths (e.g. graph display).

    Returns:
        List of ConflictAlert for each overlapping event pair.
    """
    if core_event.event_type not in CONFLICT_EVENT_TYPES:
        return []

    if not core_event.normalized_start:
        return []

    core_start = core_event.normalized_start
    core_end = core_event.normalized_end or core_start

    exclude_ids = {core_event.id}
    if exclude_event_ids:
        exclude_ids |= exclude_event_ids

    nearby_events = await _query_nearby_events(
        session, family_id, exclude_ids, core_start, core_end,
    )

    # Aggregate nearby Day events by trip so conflict detection uses
    # full trip ranges instead of individual Day 09:00-18:00 windows.
    nearby_events = _aggregate_by_trip(nearby_events)

    conflicts: List[ConflictAlert] = []
    for other in nearby_events:
        other_start = other.normalized_start
        other_end = other.normalized_end or other_start

        if not other_start:
            continue

        # Strict inequality so adjacent events
        # (A ends exactly when B starts) are NOT flagged as conflicts.
        if core_start < other_end and other_start < core_end:
            conflict = build_conflict_alert(
                core_event, core_start, core_end,
                other, other_start, other_end,
            )

            # Smart resolution (skipped in read-only mode)
            if not read_only:
                resolution = classify_conflict_importance(core_event, other)
                if resolution == "auto_resolve":
                    event_to_adjust = _pick_event_to_adjust(
                        core_event, other,
                    )
                    anchor = core_event if event_to_adjust.id == other.id else other
                    anchor_end = anchor.normalized_end or anchor.normalized_start
                    await resolve_conflict_auto(
                        session, event_to_adjust, anchor_end,
                    )
                    conflict = ConflictAlert(
                        **{
                            **conflict.model_dump(),
                            "auto_resolved": True,
                            "resolution_note": (
                                f"已自动调整{event_to_adjust.title}至"
                                f"{format_local_datetime(event_to_adjust.normalized_start, format_str='%m.%d')}后"
                            ),
                        }
                    )
                elif resolution == "user_confirm" and user_id is not None:
                    pending_action_id = await _create_reschedule_action(
                        session, user_id, family_id,
                        core_event, other,
                        conflict.suggestion,
                    )
                    if pending_action_id:
                        conflict = ConflictAlert(
                            **{
                                **conflict.model_dump(),
                                "pending_action_id": pending_action_id,
                            }
                        )

            conflicts.append(conflict)

    return conflicts


async def _query_nearby_events(
    session: AsyncSession,
    family_id: UUID,
    exclude_event_ids: Set[UUID],
    core_start: datetime,
    core_end: datetime,
) -> List[CuratedEvent]:
    """Query active conflictable events in a window around the core event."""
    window_days = max(0, int(settings.curation_conflict_window_days))
    window_start = core_start - timedelta(days=window_days)
    window_end = core_end + timedelta(days=window_days)

    stmt = (
        select(CuratedEvent)
        .where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                CuratedEvent.id.notin_(exclude_event_ids),
                CuratedEvent.event_type.in_(list(CONFLICT_EVENT_TYPES)),
                CuratedEvent.normalized_start <= window_end,
                or_(
                    CuratedEvent.normalized_end >= window_start,
                    and_(
                        CuratedEvent.normalized_end.is_(None),
                        CuratedEvent.normalized_start >= window_start,
                    ),
                ),
            )
        )
        .order_by(CuratedEvent.normalized_start)
        .limit(_MAX_NEARBY_EVENTS)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _normalize_destination(dest: str) -> str:
    """Normalize destination string for grouping."""
    from .trip_grouping import normalize_destination
    return normalize_destination(dest)


def _aggregate_by_trip(events: List[CuratedEvent]) -> List[CuratedEvent]:
    """Aggregate Day events belonging to the same trip into virtual trip-level events.

    Standalone events (no trip_id, not a "Day " event) pass through unchanged.
    For each group of Day events sharing a trip, a single virtual event is
    created with normalized_start/end spanning the full trip range.
    """
    trip_groups: Dict[str, List[CuratedEvent]] = {}
    standalone: List[CuratedEvent] = []

    for ev in events:
        group_key = None
        if ev.trip_id:
            group_key = f"trip:{ev.trip_id}"
        elif (ev.title or "").startswith("Day ") and ev.location:
            norm_loc = _normalize_destination(ev.location)
            if norm_loc:
                group_key = f"loc:{norm_loc}"

        if group_key:
            trip_groups.setdefault(group_key, []).append(ev)
        else:
            standalone.append(ev)

    aggregated: List[CuratedEvent] = []
    for group_events in trip_groups.values():
        if len(group_events) == 1:
            aggregated.append(group_events[0])
        else:
            representative = group_events[0]
            virtual = copy(representative)
            starts = [e.normalized_start for e in group_events if e.normalized_start]
            ends = [
                (e.normalized_end or e.normalized_start)
                for e in group_events if e.normalized_start
            ]
            if starts:
                virtual.normalized_start = min(starts)
            if ends:
                virtual.normalized_end = max(ends)
            # Strip "Day N · " prefix for cleaner conflict descriptions
            title = virtual.title or ""
            if title.startswith("Day ") and " · " in title:
                virtual.title = title.split(" · ", 1)[1]
            aggregated.append(virtual)

    return aggregated + standalone


def build_conflict_alert(
    event_a: CuratedEvent,
    a_start: datetime,
    a_end: datetime,
    event_b: CuratedEvent,
    b_start: datetime,
    b_end: datetime,
) -> ConflictAlert:
    """Build a ConflictAlert for two overlapping events."""
    a_start_str = format_local_datetime(a_start, format_str="%m.%d")
    a_end_str = format_local_datetime(a_end, format_str="%m.%d")
    b_start_str = format_local_datetime(b_start, format_str="%m.%d")
    b_end_str = format_local_datetime(b_end, format_str="%m.%d")

    description = (
        f"{event_a.title}({a_start_str}-{a_end_str}) 与 "
        f"{event_b.title}({b_start_str}-{b_end_str}) 时间冲突"
    )

    suggestion = generate_conflict_suggestion(
        event_a, a_start, a_end,
        event_b, b_start, b_end,
    )

    priority = determine_conflict_priority(a_start, a_end, b_start, b_end)

    return ConflictAlert(
        id=f"conflict-{event_a.id}-{event_b.id}",
        title="日程冲突",
        description=description,
        suggestion=suggestion,
        conflicting_event_ids=[str(event_a.id), str(event_b.id)],
        priority=priority,
    )


def generate_conflict_suggestion(
    event_a: CuratedEvent,
    a_start: datetime,
    a_end: datetime,
    event_b: CuratedEvent,
    b_start: datetime,
    b_end: datetime,
) -> str:
    """Generate a deterministic suggestion based on event types and overlap."""
    type_a = event_a.event_type
    type_b = event_b.event_type

    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    overlap_days = (overlap_end - overlap_start).days + 1

    # Full containment: one event entirely inside the other
    a_contains_b = a_start <= b_start and a_end >= b_end
    b_contains_a = b_start <= a_start and b_end >= a_end

    if a_contains_b or b_contains_a:
        contained = event_b if a_contains_b else event_a
        container = event_a if a_contains_b else event_b
        return (
            f"{contained.title}完全在{container.title}期间内，"
            f"建议重新安排{contained.title}的时间"
        )

    # Business trip vs travel: suggest rescheduling the travel
    if type_a == "business_trip" and type_b == "travel":
        reschedule_after = format_local_datetime(a_end, format_str="%m.%d")
        return (
            f"建议调整{event_b.title}至{reschedule_after}后，"
            f"或与{event_a.title}错开时间"
        )
    if type_b == "business_trip" and type_a == "travel":
        reschedule_after = format_local_datetime(b_end, format_str="%m.%d")
        return (
            f"建议调整{event_a.title}至{reschedule_after}后，"
            f"或与{event_b.title}错开时间"
        )

    # Same type: suggest user choose
    if type_a == type_b:
        return f"两个{event_a.title}和{event_b.title}时间重叠，建议选择保留其中一个"

    # Partial overlap (≤1 day): suggest adjusting start/end
    if overlap_days <= 1:
        return (
            f"重叠时间较短（约{overlap_days}天），"
            f"建议微调{event_b.title}的起止时间以避免冲突"
        )

    # General case
    return (
        f"建议调整{event_b.title}的时间安排，"
        f"避免与{event_a.title}冲突"
    )


# --- Smart Resolution Helpers ---

# Source types that indicate explicit user intent
_USER_EXPLICIT_SOURCES: Set[str] = {
    "user_created", "conversation", "extracted_schedule", "manual",
}

# Event types that are typically high-importance
_HIGH_IMPORTANCE_EVENT_TYPES: Set[str] = {
    "business_trip", "meeting", "appointment",
}


def _is_event_important(event: CuratedEvent) -> bool:
    """Determine if an event is important based on confidence and source signals."""
    confidence = event.confidence or 0.0
    source_types = set(event.source_types or [])
    has_user_source = bool(source_types & _USER_EXPLICIT_SOURCES)
    has_confirmed_items = any(
        item.get("confirmed", False)
        for item in (event.timeline_items or [])
    )

    if confidence >= 0.8 and has_user_source:
        return True

    if event.event_type in _HIGH_IMPORTANCE_EVENT_TYPES:
        return True

    if has_confirmed_items:
        return True

    return False


def classify_conflict_importance(
    event_a: CuratedEvent,
    event_b: CuratedEvent,
) -> str:
    """Classify how a conflict should be resolved.

    Returns:
        "user_confirm" -- both events are important, user must decide
        "auto_resolve" -- at least one event is low-importance, secretary handles it
    """
    a_important = _is_event_important(event_a)
    b_important = _is_event_important(event_b)

    if a_important and b_important:
        return "user_confirm"

    return "auto_resolve"


def _pick_event_to_adjust(
    event_a: CuratedEvent,
    event_b: CuratedEvent,
) -> CuratedEvent:
    """Pick the less-important event to reschedule."""
    a_important = _is_event_important(event_a)
    b_important = _is_event_important(event_b)

    if a_important and not b_important:
        return event_b
    if b_important and not a_important:
        return event_a

    # Both low-importance: pick the one with lower confidence
    a_conf = event_a.confidence or 0.0
    b_conf = event_b.confidence or 0.0
    return event_b if a_conf >= b_conf else event_a


def _snap_to_weekend_if_needed(
    event_title: str,
    proposed_start: datetime,
) -> datetime:
    """If trip name contains weekend keywords, snap proposed start to next Saturday."""
    weekend_keywords = [
        str(keyword).strip()
        for keyword in (settings.curation_weekend_trip_keywords or [])
        if str(keyword).strip()
    ]
    if not weekend_keywords:
        return proposed_start

    safe_title = event_title or ""
    is_weekend_trip = any(kw in safe_title for kw in weekend_keywords)
    if not is_weekend_trip:
        return proposed_start
    weekday = proposed_start.weekday()  # 0=Mon ... 5=Sat, 6=Sun
    if weekday < 5:  # Mon-Fri -> snap to next Saturday
        days_to_saturday = 5 - weekday
        return proposed_start + timedelta(days=days_to_saturday)
    return proposed_start  # Already Sat/Sun


async def resolve_conflict_auto(
    session: AsyncSession,
    event_to_adjust: CuratedEvent,
    anchor_end: datetime,
) -> None:
    """Auto-resolve by moving event_to_adjust after anchor_end + configured day buffer."""
    original_start = event_to_adjust.normalized_start
    original_end = event_to_adjust.normalized_end or original_start
    duration = original_end - original_start

    buffer_days = max(0, int(settings.curation_auto_resolve_buffer_days))
    new_start = anchor_end + timedelta(days=buffer_days)
    new_start = _snap_to_weekend_if_needed(event_to_adjust.title, new_start)
    new_end = new_start + duration

    event_to_adjust.normalized_start = new_start
    event_to_adjust.normalized_end = new_end

    await session.flush()

    logger.info(
        "Auto-resolved conflict: moved '%s' from %s to %s",
        event_to_adjust.title, original_start.date(), new_start.date(),
    )


async def _create_reschedule_action(
    session: AsyncSession,
    user_id: UUID,
    family_id: UUID,
    event_a: CuratedEvent,
    event_b: CuratedEvent,
    suggestion: str,
) -> Optional[str]:
    """Create a PendingAction for user-confirmed conflict resolution."""
    try:
        from ...conversation.pending_action_service import PendingActionService
        from ...conversation.pending_action import (
            ActionType,
            ActionStatus,
            PendingAction,
        )

        # Check for existing pending reschedule action for this event pair
        event_to_adjust = _pick_event_to_adjust(event_a, event_b)
        existing_stmt = (
            select(PendingAction)
            .where(
                and_(
                    PendingAction.user_id == user_id,
                    PendingAction.action_type == ActionType.RESCHEDULE_EVENT.value,
                    PendingAction.status == ActionStatus.PENDING.value,
                )
            )
        )
        existing_result = await session.execute(existing_stmt)
        for existing in existing_result.scalars():
            if existing.payload and existing.payload.get("event_id") == str(event_to_adjust.id):
                return str(existing.id)

        service = PendingActionService(session)

        event_to_adjust = _pick_event_to_adjust(event_a, event_b)
        anchor = event_a if event_to_adjust.id == event_b.id else event_b
        anchor_end = anchor.normalized_end or anchor.normalized_start

        buffer_days = max(0, int(settings.curation_auto_resolve_buffer_days))
        new_start = anchor_end + timedelta(days=buffer_days)
        new_start = _snap_to_weekend_if_needed(event_to_adjust.title, new_start)
        original_duration = (
            (event_to_adjust.normalized_end or event_to_adjust.normalized_start)
            - event_to_adjust.normalized_start
        )
        new_end = new_start + original_duration

        action = await service.create(
            user_id=user_id,
            family_id=family_id,
            action_type=ActionType.RESCHEDULE_EVENT.value,
            payload={
                "event_id": str(event_to_adjust.id),
                "family_id": str(family_id),
                "trip_id": str(event_to_adjust.trip_id) if event_to_adjust.trip_id else None,
                "trip_day_label": event_to_adjust.trip_day_label,
                "new_start": new_start.isoformat(),
                "new_end": new_end.isoformat(),
                "reason": suggestion,
            },
            display_data={
                "title": f"确认调整「{event_to_adjust.title}」日程",
                "description": suggestion,
                "details": [
                    {"label": "冲突事件", "value": f"{event_a.title} 与 {event_b.title}"},
                    {"label": "调整方案", "value": f"{event_to_adjust.title} → {format_local_datetime(new_start, format_str='%m月%d日')}"},
                ],
            },
            ttl_minutes=60,
        )
        return str(action.id)
    except Exception as e:
        logger.error(f"Failed to create reschedule PendingAction: {e}")
        return None


# --- Spatial Conflict Detection ---

from .constants import MAJOR_CITIES

# Simple province mapping for major cities
CITY_PROVINCE: Dict[str, str] = {
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    "广州": "广东", "深圳": "广东", "珠海": "广东", "东莞": "广东", "佛山": "广东",
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江",
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏",
    "武汉": "湖北", "成都": "四川", "西安": "陕西",
    "长沙": "湖南", "郑州": "河南", "青岛": "山东", "济南": "山东",
    "大连": "辽宁", "沈阳": "辽宁", "哈尔滨": "黑龙江",
    "厦门": "福建", "福州": "福建", "昆明": "云南", "合肥": "安徽",
}


def _extract_city_from_event(event: CuratedEvent) -> Optional[str]:
    """Extract city name from event's city or location field."""
    if event.city:
        city = event.city.strip()
        if city:
            return city
    if event.location:
        for city in MAJOR_CITIES:
            if city in event.location:
                return city
    return None


def _estimate_min_travel_hours(city_a: str, city_b: str) -> float:
    """Estimate minimum travel time between two cities.

    Same province: 2 hours (high-speed rail within province)
    Cross province: 4 hours (train/flight + transfers)
    """
    prov_a = CITY_PROVINCE.get(city_a)
    prov_b = CITY_PROVINCE.get(city_b)
    if prov_a and prov_b and prov_a == prov_b:
        return 2.0
    return 4.0


async def detect_spatial_conflicts(
    session: AsyncSession,
    family_id: UUID,
    events: List[CuratedEvent],
) -> List[ConflictAlert]:
    """Detect same-day different-city events with insufficient travel time.

    Algorithm:
    1. Group events by date (normalized_start.date())
    2. For each day, extract city from each event's location/city field
    3. If same day has events in different cities:
       - Calculate gap_hours between events
       - Estimate min travel time: same_province=2h, cross_province=4h
       - If gap_hours < min_travel_time -> spatial conflict
    """
    day_events: Dict[str, List[CuratedEvent]] = {}
    for ev in events:
        if not ev.normalized_start:
            continue
        day_key = ev.normalized_start.date().isoformat()
        day_events.setdefault(day_key, []).append(ev)

    conflicts: List[ConflictAlert] = []

    for day_key, day_list in day_events.items():
        if len(day_list) < 2:
            continue

        # Build list of (event, city) for events with known cities
        city_events = []
        for ev in day_list:
            city = _extract_city_from_event(ev)
            if city:
                city_events.append((ev, city))

        if len(city_events) < 2:
            continue

        # Sort by start time for gap calculation
        city_events.sort(key=lambda x: x[0].normalized_start)

        # Check consecutive pairs for spatial conflicts
        for i in range(len(city_events) - 1):
            ev_a, city_a = city_events[i]
            ev_b, city_b = city_events[i + 1]

            if city_a == city_b:
                continue

            end_a = ev_a.normalized_end or ev_a.normalized_start
            start_b = ev_b.normalized_start
            gap_hours = (start_b - end_a).total_seconds() / 3600.0

            min_travel = _estimate_min_travel_hours(city_a, city_b)

            if gap_hours < min_travel:
                a_start_str = format_local_datetime(ev_a.normalized_start, format_str="%H:%M")
                b_start_str = format_local_datetime(ev_b.normalized_start, format_str="%H:%M")

                description = (
                    f"{ev_a.title}({city_a} {a_start_str}) 与 "
                    f"{ev_b.title}({city_b} {b_start_str}) "
                    f"间隔仅{gap_hours:.1f}小时，"
                    f"但{city_a}到{city_b}至少需要{min_travel:.0f}小时"
                )
                suggestion = (
                    f"建议调整{ev_b.title}的时间，"
                    f"为{city_a}到{city_b}的交通预留至少{min_travel:.0f}小时"
                )

                conflict = ConflictAlert(
                    id=f"spatial-{ev_a.id}-{ev_b.id}",
                    title="行程空间冲突",
                    description=description,
                    suggestion=suggestion,
                    conflicting_event_ids=[str(ev_a.id), str(ev_b.id)],
                    priority=ConflictPriority.HIGH,
                )
                conflicts.append(conflict)

    return conflicts


def determine_conflict_priority(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> ConflictPriority:
    """Determine conflict priority based on overlap extent."""
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    overlap_duration = overlap_end - overlap_start

    a_duration = a_end - a_start
    b_duration = b_end - b_start
    shorter_duration = min(a_duration, b_duration)

    # Zero-duration event fully overlapped by any event
    if shorter_duration.total_seconds() == 0:
        return ConflictPriority.HIGH

    # Full containment or >50% overlap
    overlap_ratio = overlap_duration / shorter_duration
    if overlap_ratio >= 0.5:
        return ConflictPriority.HIGH

    # 1-2 days overlap
    if overlap_duration.days <= 2:
        return ConflictPriority.MEDIUM

    return ConflictPriority.HIGH
