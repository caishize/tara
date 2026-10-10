"""Travel Service for trip planning and itinerary management."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ..models import TripPlan, TripItinerary
from ....core.utils.timezone import utc_now

logger = get_logger(__name__)


class TripService:
    """Service for travel planning and management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_event(
        self,
        family_id: UUID,
        user_id: UUID,
        title: Optional[str],
        destination: Optional[str],
        start_date_str: Optional[str],
        end_date_str: Optional[str],
        event_type: str = "travel",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a travel event (trip) from tool arguments."""
        destination = (destination or "").strip()
        if not destination:
            return {"success": False, "message": "请提供目的地"}

        title = (title or "").strip() or None

        start_date = (
            datetime.strptime(start_date_str, "%Y-%m-%d").date()
            if start_date_str
            else (utc_now() + timedelta(days=7)).date()
        )
        end_date = (
            datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if end_date_str
            else start_date + timedelta(days=2)
        )

        existing = await self.find_matching_trip(
            family_id, destination, start_date, end_date
        )
        if existing:
            if title:
                existing.trip_name = title
            # Extend date range rather than overwrite
            existing.start_date = min(existing.start_date, start_date) if existing.start_date else start_date
            existing.end_date = max(existing.end_date, end_date) if existing.end_date else end_date
            if notes:
                existing.notes = notes
            existing.updated_at = utc_now()
            await self.db.flush()

            await self.create_trip_memory(
                user_id=user_id,
                family_id=family_id,
                trip=existing,
                action="更新",
            )

            logger.info("Merged into existing trip %s for %s", existing.trip_id, destination)
            return {
                "success": True,
                "trip_id": str(existing.trip_id),
                "title": existing.trip_name,
                "destination": destination,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "message": f"已更新行程「{existing.trip_name}」",
                "merged": True,
            }

        category = "business" if event_type in ("business_trip", "conference", "client_visit") else "personal"
        trip_type = event_type if event_type in (
            "leisure", "family", "visit", "business_trip", "conference", "client_visit", "other"
        ) else "other"

        trip = TripPlan(
            family_id=family_id,
            created_by=user_id,
            trip_name=title or f"{destination}之旅",
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            category=category,
            trip_type=trip_type,
            status="planning",
            participants=[user_id],
            notes=notes,
        )
        self.db.add(trip)
        await self.db.flush()

        # Auto-create memory so search_memory can find trip data
        await self.create_trip_memory(
            user_id=user_id,
            family_id=family_id,
            trip=trip,
            action="创建",
        )

        return {
            "success": True,
            "trip_id": str(trip.trip_id),
            "title": trip.trip_name,
            "destination": destination,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "message": f"已创建行程「{trip.trip_name}」",
        }

    async def add_itinerary(
        self,
        family_id: UUID,
        user_id: UUID,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add daily itinerary to an existing trip.

        Supports both single-day and batch multi-day modes:
        - Single day: pass ``schedule`` (list of activities)
        - Batch: pass ``days`` (list of {day_number?, schedule} dicts)

        When ``day_number`` is omitted the next available day is used
        automatically.
        """
        trip_id = args.get("trip_id")
        if not trip_id:
            return {"success": False, "message": "请提供行程ID"}

        stmt = select(TripPlan).where(
            and_(
                TripPlan.trip_id == trip_id,
                TripPlan.family_id == family_id,
            )
        )
        result = await self.db.execute(stmt)
        trip = result.scalar_one_or_none()

        if not trip:
            return {"success": False, "message": f"未找到行程 {trip_id}"}

        # --- Batch mode: ``days`` is a list of day dicts ------------------
        days = args.get("days")
        if days and isinstance(days, list):
            return await self._add_itinerary_batch(trip, days)

        # --- Single-day mode ----------------------------------------------
        schedule = args.get("schedule", [])

        # Auto-increment: find the next available day_number when not given
        day_number = args.get("day_number")
        if day_number is None:
            max_stmt = (
                select(func.max(TripItinerary.day_number))
                .where(TripItinerary.trip_id == trip.trip_id)
            )
            max_result = await self.db.execute(max_stmt)
            max_day = max_result.scalar()
            day_number = (max_day or 0) + 1

        # Upsert: update if exists
        existing_stmt = select(TripItinerary).where(
            and_(
                TripItinerary.trip_id == trip.trip_id,
                TripItinerary.day_number == day_number,
            )
        )
        existing_result = await self.db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.schedule = schedule
            await self.db.flush()
            self._sync_trip_end_date(trip, day_number)
            return self._itinerary_response(trip, day_number, 1, updated=True)

        itinerary = TripItinerary(
            trip_id=trip.trip_id,
            day_number=day_number,
            schedule=schedule,
        )
        self.db.add(itinerary)
        await self.db.flush()

        self._sync_trip_end_date(trip, day_number)

        return self._itinerary_response(trip, day_number, 1, updated=False)

    async def _add_itinerary_batch(
        self,
        trip: "TripPlan",
        days: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Add multiple days of itinerary in one call."""
        from sqlalchemy import func as sa_func

        # Find current max day_number for auto-increment
        max_stmt = (
            select(sa_func.max(TripItinerary.day_number))
            .where(TripItinerary.trip_id == trip.trip_id)
        )
        max_result = await self.db.execute(max_stmt)
        next_day = (max_result.scalar() or 0) + 1

        saved_days: List[int] = []
        for day_data in days:
            day_number = day_data.get("day_number") or next_day
            schedule = day_data.get("schedule", day_data.get("activities", []))

            # Upsert
            existing_stmt = select(TripItinerary).where(
                and_(
                    TripItinerary.trip_id == trip.trip_id,
                    TripItinerary.day_number == day_number,
                )
            )
            existing_result = await self.db.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                existing.schedule = schedule
            else:
                self.db.add(TripItinerary(
                    trip_id=trip.trip_id,
                    day_number=day_number,
                    schedule=schedule,
                ))

            saved_days.append(day_number)
            if day_number >= next_day:
                next_day = day_number + 1

        await self.db.flush()

        max_day = max(saved_days)
        self._sync_trip_end_date(trip, max_day)

        return self._itinerary_response(trip, saved_days[0], len(saved_days))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def find_matching_trip(
        self,
        family_id: UUID,
        destination: str,
        start_date: date,
        end_date: date,
        proximity_days: int = 3,
    ) -> Optional[TripPlan]:
        """Find an existing non-terminal trip with same destination and overlapping/near dates.

        Matches trips whose date ranges overlap or are within *proximity_days*
        of the requested range.  This prevents "Tokyo Feb 10-14" and
        "Tokyo Feb 17-20" from becoming separate trips when they're logically
        the same journey.
        """
        stmt = (
            select(TripPlan)
            .where(and_(
                TripPlan.family_id == family_id,
                func.lower(TripPlan.destination) == destination.lower(),
                TripPlan.canonical_trip_id.is_(None),
                TripPlan.is_active.is_(True),
                TripPlan.status.notin_(["cancelled", "completed"]),
                TripPlan.start_date <= end_date + timedelta(days=proximity_days),
                TripPlan.end_date >= start_date - timedelta(days=proximity_days),
            ))
            .order_by(
                # Prefer longer trips (superset date ranges) over shorter ones
                (TripPlan.end_date - TripPlan.start_date).desc(),
                TripPlan.updated_at.desc(),
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def merge_trips(
        self,
        family_id: UUID,
        primary_trip_id: UUID,
        merge_trip_ids: List[UUID],
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge secondary trips into a canonical primary trip.

        This is a logical merge:
        - primary trip remains active and canonical
        - secondary trips are marked superseded (canonical_trip_id + is_active=false)
        - primary date range expands to cover all merged trips
        - active curated events pointing to secondary trips are re-pointed
        """
        merge_ids = [tid for tid in merge_trip_ids if tid != primary_trip_id]
        if not merge_ids:
            return {
                "success": False,
                "message": "没有可合并的次级行程",
            }

        primary_stmt = select(TripPlan).where(
            and_(
                TripPlan.trip_id == primary_trip_id,
                TripPlan.family_id == family_id,
            )
        )
        primary = (await self.db.execute(primary_stmt)).scalar_one_or_none()
        if not primary:
            return {
                "success": False,
                "message": f"未找到主行程 {primary_trip_id}",
            }

        secondary_stmt = select(TripPlan).where(
            and_(
                TripPlan.family_id == family_id,
                TripPlan.trip_id.in_(merge_ids),
            )
        )
        secondary_trips = list((await self.db.execute(secondary_stmt)).scalars().all())
        if not secondary_trips:
            return {
                "success": False,
                "message": "未找到可合并的次级行程",
            }

        all_starts = [t.start_date for t in ([primary] + secondary_trips) if t.start_date]
        all_ends = [t.end_date for t in ([primary] + secondary_trips) if t.end_date]
        if all_starts:
            primary.start_date = min(all_starts)
        if all_ends:
            primary.end_date = max(all_ends)

        participant_set = set(primary.participants or [])
        for sec in secondary_trips:
            participant_set.update(sec.participants or [])
        primary.participants = list(participant_set)
        primary.canonical_trip_id = None
        primary.is_active = True
        primary.updated_at = utc_now()

        superseded_ids: List[UUID] = []
        reason_text = (reason or "manual_or_semantic_merge").strip()
        for sec in secondary_trips:
            if sec.trip_id == primary_trip_id:
                continue
            sec.canonical_trip_id = primary_trip_id
            sec.is_active = False
            sec.updated_at = utc_now()
            extra = sec.extra_data if isinstance(sec.extra_data, dict) else {}
            extra["superseded_by_trip_id"] = str(primary_trip_id)
            extra["superseded_reason"] = reason_text
            extra["superseded_at"] = utc_now().isoformat()
            sec.extra_data = extra
            superseded_ids.append(sec.trip_id)

        if superseded_ids:
            from ...curation.models import CuratedEvent

            await self.db.execute(
                update(CuratedEvent)
                .where(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.trip_id.in_(superseded_ids),
                    CuratedEvent.is_active.is_(True),
                )
                .values(
                    trip_id=primary_trip_id,
                    dedup_reason=f"trip merge -> canonical {primary_trip_id}",
                )
            )

        await self.db.flush()
        return {
            "success": True,
            "primary_trip_id": str(primary_trip_id),
            "merged_trip_ids": [str(tid) for tid in superseded_ids],
            "merged_count": len(superseded_ids),
            "message": f"已合并 {len(superseded_ids)} 个行程到主行程",
        }

    @staticmethod
    def _sync_trip_end_date(trip: "TripPlan", max_day_number: int) -> None:
        """Extend trip.end_date if itinerary days exceed current range."""
        if not trip.start_date:
            return
        needed_end = trip.start_date + timedelta(days=max_day_number - 1)
        if trip.end_date is None or needed_end > trip.end_date:
            trip.end_date = needed_end

    @staticmethod
    def _itinerary_response(
        trip: "TripPlan",
        first_day: int,
        total_days_saved: int,
        updated: bool = False,
    ) -> Dict[str, Any]:
        """Build a rich response dict for itinerary mutations."""
        action = "更新" if updated else "添加"
        if total_days_saved == 1:
            message = f"已{action}第{first_day}天行程"
        else:
            message = f"已{action}{total_days_saved}天行程（第{first_day}-{first_day + total_days_saved - 1}天）"

        return {
            "success": True,
            "trip_id": str(trip.trip_id),
            "trip_name": trip.trip_name or trip.destination,
            "destination": trip.destination,
            "start_date": trip.start_date.isoformat() if trip.start_date else None,
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "days_saved": total_days_saved,
            "first_day_number": first_day,
            "message": message,
            "hint": f"后续添加请传入 trip_id=\"{trip.trip_id}\"",
        }

    async def create_trip_memory(
        self,
        user_id: UUID,
        family_id: UUID,
        trip: "TripPlan",
        action: str = "创建",
    ) -> None:
        """Create a ConversationMemory record for a trip so search_memory can find it."""
        try:
            from ...memory.repository import MemoryRepository

            dest = trip.destination or ""
            name = trip.trip_name or f"{dest}之旅"
            start_str = trip.start_date.isoformat() if trip.start_date else "待定"
            end_str = trip.end_date.isoformat() if trip.end_date else "待定"

            summary = f"{action}了{name}（{dest}，{start_str} ~ {end_str}）"
            content = (
                f"旅行计划: {name}\n"
                f"目的地: {dest}\n"
                f"日期: {start_str} ~ {end_str}\n"
                f"状态: {trip.status}"
            )
            if trip.notes:
                content += f"\n备注: {trip.notes}"

            tags = [dest, "旅行", name]
            entities = {
                "location": dest,
                "trip_id": str(trip.trip_id),
                "trip_name": name,
            }
            if trip.start_date:
                entities["start_date"] = start_str
            if trip.end_date:
                entities["end_date"] = end_str

            repo = MemoryRepository(self.db)
            await repo.create_memory(
                user_id=user_id,
                family_id=family_id,
                memory_type="schedule",
                content=content,
                summary=summary,
                entities=entities,
                tags=tags,
                importance=7,
                confidence=1.0,
                auto_commit=False,
            )
        except Exception as e:
            logger.warning("Failed to create trip memory: %s", e)
