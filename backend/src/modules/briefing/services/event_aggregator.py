"""
Event aggregation for daily briefings.

Collects events from curated events, important dates, and trip plans,
converting them into BriefingEvent objects.
"""
from typing import List, Optional, Tuple
from datetime import date, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from zoneinfo import ZoneInfo

from ....config.logging import get_logger
from ....core.utils.timezone import (
    DEFAULT_TIMEZONE,
    local_date_range_to_utc,
    to_local_date,
)

from ...date_manager.models import ImportantDate
from ...date_manager.date_service import SYSTEM_FAMILY_ID
from ...member.models.member import Member
from ...trip.models.trip_plan import TripPlan
from ...trip.services.trip_status import compute_trip_status
from ...curation.services.date_occurrence_utils import calculate_next_occurrence

from ..schemas import (
    BriefingEvent,
    UpcomingTrip,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Icon / detail helpers (stateless)
# ---------------------------------------------------------------------------

def get_event_icon(date_type: str) -> str:
    """Return emoji icon for the given event type."""
    icons = {
        'birthday': '\U0001f382',
        'anniversary': '\U0001f491',
        'wedding_anniversary': '\U0001f48d',
        'memorial': '\U0001f56f\ufe0f',
        'holiday': '\U0001f389',
        'holiday_legal': '\U0001f3db\ufe0f',
        'holiday_lunar': '\U0001f319',
        'holiday_solar_term': '\U0001f33f',
        'vaccine': '\U0001f489',
        'checkup': '\U0001f3e5',
        'custom': '\U0001f4c5',
    }
    return icons.get(date_type, '\U0001f4c5')


def get_event_details(
    date_type: str,
    title: str,
    member_name: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Return (description, action_label) for the given event type."""
    if date_type == 'birthday':
        if member_name:
            return f"\u4eca\u5929\u662f{member_name}\u7684\u751f\u65e5", "\u53d1\u9001\u795d\u798f"
        return "\u8bb0\u5f97\u51c6\u5907\u793c\u7269\u548c\u795d\u798f", "\u53d1\u9001\u795d\u798f"
    elif date_type in ('anniversary', 'wedding_anniversary'):
        return "\u73cd\u8d35\u7684\u7eaa\u5ff5\u65e5", "\u67e5\u770b\u56de\u5fc6"
    elif date_type == 'memorial':
        return "\u7f05\u6000\u4e0e\u601d\u5ff5", None
    elif date_type in ('holiday', 'holiday_legal', 'holiday_lunar'):
        return "\u8282\u65e5\u5feb\u4e50", None
    elif date_type == 'vaccine':
        return "\u8bf7\u6309\u65f6\u63a5\u79cd\u75ab\u82d7", "\u67e5\u770b\u8be6\u60c5"
    elif date_type == 'checkup':
        return "\u5b9a\u671f\u4f53\u68c0\u5f88\u91cd\u8981", "\u67e5\u770b\u8be6\u60c5"
    else:
        return None, None


def calculate_next_occurrence_wrapper(
    important_date: ImportantDate,
    reference_date: date,
) -> Optional[date]:
    """Thin wrapper around curation's ``calculate_next_occurrence``."""
    return calculate_next_occurrence(
        important_date,
        start_date=reference_date,
        end_date=date(reference_date.year + 2, 12, 31),
    )


# ---------------------------------------------------------------------------
# EventAggregator
# ---------------------------------------------------------------------------

class EventAggregator:
    """Collects and converts events from multiple data sources."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _reset_failed_transaction(self, context: str) -> None:
        """Rollback failed transaction state for non-blocking fallback paths."""
        try:
            await self.session.rollback()
        except Exception:
            logger.debug("Rollback after %s failed", context, exc_info=True)

    # -- public entry point ---------------------------------------------------

    async def get_today_events(
        self,
        family_id: UUID,
        target_date: date,
        user_tz: Optional[ZoneInfo] = None,
    ) -> List[BriefingEvent]:
        """Get all events for *target_date*, preferring curated events."""
        from .external_data_fetcher import ExternalDataFetcher

        fetcher = ExternalDataFetcher(self.session)
        events: List[BriefingEvent] = []

        curated_found = False
        try:
            curated_found, curated_events = await self._get_curated_events(
                family_id, target_date, user_tz,
            )
            events.extend(curated_events)
        except Exception as e:
            logger.error("Error getting curated events for today: %s", e)
            await self._reset_failed_transaction("curated events for today")

        if curated_found:
            events = await self._append_external_events(
                fetcher, events, family_id, target_date,
            )
            events.sort(key=lambda x: (x.time is None or x.time == "\u5168\u5929", x.time or ""))
            return events

        # Full fallback to raw tables
        try:
            raw_events = await self._get_raw_important_date_events(family_id, target_date)
            events.extend(raw_events)
        except Exception as e:
            logger.error("Error getting today's important dates: %s", e)
            await self._reset_failed_transaction("important dates for today")

        try:
            trip_events = await self.get_trip_events_for_date(family_id, target_date)
            events.extend(trip_events)
        except Exception as e:
            logger.error("Error getting today's trip events: %s", e)
            await self._reset_failed_transaction("trip events for today")

        events = await self._append_external_events(
            fetcher, events, family_id, target_date,
        )
        events.sort(key=lambda x: (x.time is None or x.time == "\u5168\u5929", x.time or ""))
        return events

    # -- curated events -------------------------------------------------------

    async def _get_curated_events(
        self,
        family_id: UUID,
        target_date: date,
        user_tz: Optional[ZoneInfo] = None,
    ) -> Tuple[bool, List[BriefingEvent]]:
        """Return (found_flag, events) from the CuratedEvent table."""
        from ...curation.models import CuratedEvent

        tz = user_tz or DEFAULT_TIMEZONE
        day_start_utc, day_end_utc = local_date_range_to_utc(
            target_date, target_date, tz
        )

        stmt = (
            select(CuratedEvent)
            .options(
                selectinload(CuratedEvent.associations),
                selectinload(CuratedEvent.preparation_item_rows),
            )
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status.notin_(["cancelled", "completed"]),
                    or_(
                        and_(
                            CuratedEvent.normalized_start >= day_start_utc,
                            CuratedEvent.normalized_start <= day_end_utc,
                        ),
                        and_(
                            CuratedEvent.normalized_start <= day_start_utc,
                            CuratedEvent.normalized_end >= day_start_utc,
                        ),
                    ),
                )
            )
            .order_by(CuratedEvent.normalized_start.asc())
        )
        result = await self.session.execute(stmt)
        curated_events = list(result.scalars().all())

        if not curated_events:
            return False, []

        events: List[BriefingEvent] = []
        for ce in curated_events:
            icon = get_event_icon(ce.event_type or "custom")
            time_str = "\u5168\u5929"
            if ce.normalized_start:
                local_time = ce.normalized_start.astimezone(user_tz or DEFAULT_TIMEZONE)
                time_str = local_time.strftime("%H:%M")

            events.append(BriefingEvent(
                id=str(ce.id),
                title=ce.title,
                time=time_str,
                icon=icon,
                description=ce.location,
                event_type=ce.event_type or "general",
                trip_id=str(ce.trip_id) if ce.trip_id else None,
            ))

        return True, events

    async def get_raw_curated_events(
        self,
        family_id: UUID,
        target_date: date,
        user_tz: Optional[ZoneInfo] = None,
    ) -> list:
        """Return raw CuratedEvent ORM objects for orchestration.

        Unlike ``_get_curated_events`` which transforms to BriefingEvent,
        this returns the DB model objects needed by SecretaryOrchestrator.
        """
        from ...curation.models import CuratedEvent

        tz = user_tz or DEFAULT_TIMEZONE
        day_start_utc, day_end_utc = local_date_range_to_utc(
            target_date, target_date, tz
        )

        stmt = (
            select(CuratedEvent)
            .options(
                selectinload(CuratedEvent.associations),
                selectinload(CuratedEvent.preparation_item_rows),
            )
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status.notin_(["cancelled", "completed"]),
                    or_(
                        and_(
                            CuratedEvent.normalized_start >= day_start_utc,
                            CuratedEvent.normalized_start <= day_end_utc,
                        ),
                        and_(
                            CuratedEvent.normalized_start <= day_start_utc,
                            CuratedEvent.normalized_end >= day_start_utc,
                        ),
                    ),
                )
            )
            .order_by(CuratedEvent.normalized_start.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -- raw ImportantDate fallback -------------------------------------------

    async def _get_raw_important_date_events(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[BriefingEvent]:
        """Fallback: collect events directly from ImportantDate table."""
        events: List[BriefingEvent] = []
        family_filter = self._build_family_filter(family_id)

        stmt = select(ImportantDate).where(family_filter)
        result = await self.session.execute(stmt)
        all_dates = list(result.scalars().all())

        for d in all_dates:
            next_occurrence = calculate_next_occurrence_wrapper(d, target_date)
            if next_occurrence == target_date:
                event = await self._convert_to_briefing_event(d, family_id)
                events.append(event)
        return events

    async def _convert_to_briefing_event(
        self,
        important_date: ImportantDate,
        family_id: UUID,
    ) -> BriefingEvent:
        """Convert an ImportantDate to a BriefingEvent."""
        icon = get_event_icon(important_date.date_type)

        member_name = None
        if important_date.member_id:
            try:
                stmt = select(Member).where(Member.id == important_date.member_id)
                result = await self.session.execute(stmt)
                member = result.scalar_one_or_none()
                if member:
                    member_name = member.name
            except Exception as e:
                logger.warning("Could not get member name: %s", e)
                await self._reset_failed_transaction("member lookup for important date")

        description, action_label = get_event_details(
            important_date.date_type,
            important_date.title,
            member_name,
        )

        time_str = "\u5168\u5929"
        if hasattr(important_date, 'reminder_time') and important_date.reminder_time:
            time_str = important_date.reminder_time

        return BriefingEvent(
            id=str(important_date.id),
            title=important_date.title,
            time=time_str,
            icon=icon,
            description=description,
            action_label=action_label,
            event_type=important_date.date_type,
            member_id=str(important_date.member_id) if important_date.member_id else None,
            member_name=member_name,
        )

    # -- trips ----------------------------------------------------------------

    async def get_trip_events_for_date(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[BriefingEvent]:
        """Get trip-related BriefingEvents for a single date."""
        events: List[BriefingEvent] = []
        try:
            stmt = select(TripPlan).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.is_active.is_(True),
                    TripPlan.start_date <= target_date,
                    TripPlan.end_date >= target_date,
                    TripPlan.status.notin_(['cancelled', 'completed']),
                )
            )
            result = await self.session.execute(stmt)
            trips = list(result.scalars().all())

            for plan in trips:
                event = self._convert_trip_to_briefing_event(plan, target_date)
                events.append(event)
        except Exception as e:
            logger.error("Error getting trip events: %s", e)
            await self._reset_failed_transaction("trip events query")
        return events

    async def get_upcoming_trips(
        self,
        family_id: UUID,
        target_date: date,
        days_ahead: int = 3,
    ) -> List[TripPlan]:
        """Get TripPlan objects starting within *days_ahead*."""
        upcoming: List[TripPlan] = []
        try:
            end_check_date = target_date + timedelta(days=days_ahead)
            stmt = select(TripPlan).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.is_active.is_(True),
                    TripPlan.start_date > target_date,
                    TripPlan.start_date <= end_check_date,
                    TripPlan.status.notin_(['cancelled', 'completed']),
                )
            )
            result = await self.session.execute(stmt)
            upcoming = list(result.scalars().all())
        except Exception as e:
            logger.error("Error getting upcoming trips: %s", e)
            await self._reset_failed_transaction("upcoming trips query")
        return upcoming

    async def get_upcoming_trips_for_briefing(
        self,
        family_id: UUID,
        target_date: date,
        days_ahead: int = 14,
        user_tz: Optional[ZoneInfo] = None,
    ) -> List[UpcomingTrip]:
        """Get upcoming trips from curated_events (single source of truth)."""
        trips: List[UpcomingTrip] = []

        try:
            from ...curation.models import CuratedEvent

            end_check_date = target_date + timedelta(days=days_ahead)
            tz = user_tz or DEFAULT_TIMEZONE
            target_start_utc, end_check_utc = local_date_range_to_utc(
                target_date, end_check_date, tz
            )

            stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.event_type.in_(["travel", "business_trip"]),
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status.notin_(["cancelled", "completed"]),
                        or_(
                            and_(
                                CuratedEvent.normalized_start >= target_start_utc,
                                CuratedEvent.normalized_start <= end_check_utc,
                            ),
                            and_(
                                CuratedEvent.normalized_start <= target_start_utc,
                                CuratedEvent.normalized_end >= target_start_utc,
                            ),
                        ),
                    )
                )
                .order_by(CuratedEvent.normalized_start.asc())
            )
            result = await self.session.execute(stmt)
            curated_trips = list(result.scalars().all())

            for event in curated_trips:
                start = (
                    to_local_date(event.normalized_start, tz)
                    if event.normalized_start else target_date
                )
                end = (
                    to_local_date(event.normalized_end, tz)
                    if event.normalized_end else start
                )
                trip_type = "business" if event.event_type == "business_trip" else "leisure"
                effective = compute_trip_status(event.status or "planning", start, end)
                if effective in ("completed", "cancelled"):
                    continue
                trips.append(UpcomingTrip(
                    trip_id=str(event.id),
                    trip_name=event.title,
                    destination=event.location or event.title,
                    start_date=start,
                    end_date=end,
                    trip_type=trip_type,
                    status=effective,
                ))
        except Exception as e:
            logger.error("Error getting curated trips for briefing: %s", e)
            await self._reset_failed_transaction("curated trips for briefing")

        if not trips:
            trips = await self._fallback_upcoming_trips(family_id, target_date, days_ahead)

        return trips

    # -- events for a specific date (raw) -------------------------------------

    async def get_events_for_date(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[ImportantDate]:
        """Return raw ImportantDate objects matching *target_date*."""
        events: List[ImportantDate] = []
        try:
            family_filter = self._build_family_filter(family_id)
            stmt = select(ImportantDate).where(family_filter)
            result = await self.session.execute(stmt)
            all_dates = list(result.scalars().all())

            for d in all_dates:
                next_occurrence = calculate_next_occurrence_wrapper(d, target_date)
                if next_occurrence == target_date:
                    events.append(d)
        except Exception as e:
            logger.error("Error getting events for date: %s", e)
            await self._reset_failed_transaction("events for date query")
        return events

    # -- week remaining -------------------------------------------------------

    async def get_week_remaining_count(
        self,
        family_id: UUID,
        target_date: date,
    ) -> int:
        """Count remaining events in the next 7 days."""
        count = 0
        try:
            week_end = target_date + timedelta(days=7)
            try:
                family_filter = self._build_family_filter(family_id)
                stmt = select(ImportantDate).where(family_filter)
                result = await self.session.execute(stmt)
                all_dates = list(result.scalars().all())

                for d in all_dates:
                    for days_ahead in range(1, 8):
                        check_date = target_date + timedelta(days=days_ahead)
                        next_occurrence = calculate_next_occurrence_wrapper(d, check_date)
                        if next_occurrence == check_date:
                            count += 1
                            break
            except Exception as e:
                logger.error("Error counting important date events: %s", e)
                await self._reset_failed_transaction("week remaining important dates")

            try:
                stmt = select(TripPlan).where(
                    and_(
                        TripPlan.family_id == family_id,
                        TripPlan.is_active.is_(True),
                        TripPlan.start_date > target_date,
                        TripPlan.start_date <= week_end,
                        TripPlan.status.notin_(['cancelled', 'completed']),
                    )
                )
                result = await self.session.execute(stmt)
                trips = list(result.scalars().all())
                count += len(trips)
            except Exception as e:
                logger.error("Error counting trip events: %s", e)
                await self._reset_failed_transaction("week remaining trips")
        except Exception as e:
            logger.error("Error getting week remaining count: %s", e)
            await self._reset_failed_transaction("week remaining count")
        return count

    # -- private helpers ------------------------------------------------------

    @staticmethod
    def _build_family_filter(family_id: UUID):
        """Build the family_id filter including SYSTEM holidays."""
        if family_id != SYSTEM_FAMILY_ID:
            return or_(
                ImportantDate.family_id == family_id,
                ImportantDate.family_id == SYSTEM_FAMILY_ID,
            )
        return ImportantDate.family_id == family_id

    @staticmethod
    def _convert_trip_to_briefing_event(
        trip_plan: TripPlan,
        target_date: date,
    ) -> BriefingEvent:
        is_first_day = trip_plan.start_date == target_date
        is_last_day = trip_plan.end_date == target_date
        day_number = (target_date - trip_plan.start_date).days + 1
        total_days = (trip_plan.end_date - trip_plan.start_date).days + 1

        title = trip_plan.trip_name or f"{trip_plan.destination}\u65c5\u884c"
        if is_first_day:
            description = f"\u4eca\u5929\u51fa\u53d1\u53bb{trip_plan.destination}\uff01"
            icon = "\u2708\ufe0f"
        elif is_last_day:
            description = f"\u4eca\u5929\u4ece{trip_plan.destination}\u8fd4\u56de"
            icon = "\U0001f3e0"
        else:
            description = f"\u7b2c{day_number}\u5929/{total_days}\u5929 - {trip_plan.destination}"
            icon = "\U0001f5fa\ufe0f"

        return BriefingEvent(
            id=str(trip_plan.trip_id),
            title=title,
            time="\u5168\u5929",
            icon=icon,
            description=description,
            action_label="\u67e5\u770b\u884c\u7a0b",
            event_type="travel",
            trip_id=str(trip_plan.trip_id),
        )

    async def _append_external_events(
        self,
        fetcher: "ExternalDataFetcher",
        events: List[BriefingEvent],
        family_id: UUID,
        target_date: date,
    ) -> List[BriefingEvent]:
        """Append external calendar / shipping / flight events."""
        try:
            external_events = await fetcher.get_external_calendar_events(family_id, target_date)
            events.extend(external_events)
        except Exception as e:
            logger.error("Error getting external calendar events: %s", e)
            await self._reset_failed_transaction("external calendar events")

        try:
            shipping_events = await fetcher.get_shipping_events(family_id, target_date)
            events.extend(shipping_events)
        except Exception as e:
            logger.error("Error getting shipping events: %s", e)
            await self._reset_failed_transaction("shipping events")

        try:
            flight_events = await fetcher.get_flight_events(family_id, target_date)
            events.extend(flight_events)
        except Exception as e:
            logger.error("Error getting flight events: %s", e)
            await self._reset_failed_transaction("flight events")

        return events

    async def _fallback_upcoming_trips(
        self,
        family_id: UUID,
        target_date: date,
        days_ahead: int,
    ) -> List[UpcomingTrip]:
        """Fallback: load upcoming trips from TripPlan table."""
        trips: List[UpcomingTrip] = []
        try:
            end_check_date = target_date + timedelta(days=days_ahead)
            stmt = select(TripPlan).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.is_active.is_(True),
                    TripPlan.status.notin_(["cancelled", "completed"]),
                    or_(
                        and_(
                            TripPlan.start_date >= target_date,
                            TripPlan.start_date <= end_check_date,
                        ),
                        and_(
                            TripPlan.start_date <= target_date,
                            TripPlan.end_date >= target_date,
                        ),
                    ),
                )
            ).order_by(TripPlan.start_date.asc())
            result = await self.session.execute(stmt)
            trip_plans = list(result.scalars().all())

            for plan in trip_plans:
                effective = compute_trip_status(plan.status or "planning", plan.start_date, plan.end_date)
                if effective in ("completed", "cancelled"):
                    continue
                trips.append(UpcomingTrip(
                    trip_id=str(plan.trip_id),
                    trip_name=plan.trip_name,
                    destination=plan.destination,
                    start_date=plan.start_date,
                    end_date=plan.end_date,
                    trip_type=getattr(plan, "trip_type", None) or "leisure",
                    status=effective,
                ))
        except Exception as e:
            logger.error("Error getting fallback trips for briefing: %s", e)
            await self._reset_failed_transaction("fallback upcoming trips")
        return trips
