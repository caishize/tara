"""Trip domain tool executor — data tools for trip management.

NOTE: plan_smart_trip and search_travel_info have been replaced by Skills
(travel_planning and travel_search). The main agent now uses WebSearch
directly, guided by Skill prompt injection, and calls the data tools
below to persist results.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from ....config.logging import get_logger
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


class TripToolExecutor(BaseToolExecutor):
    """Handles add_trip_event, add_trip_itinerary, query_trips,
    update_trip, cancel_trip, query_trip_bookings, query_external_calendar."""

    def __init__(self, db, session_id=None):
        super().__init__(db, session_id)

    async def add_trip_event(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.trip.services.trip_service import TripService
        from ....modules.curation.tasks import trigger_curation_if_enabled

        try:
            service = TripService(self.db)
            # Map tool definition params to service params:
            # tool has: event_date, location, category, description
            # service expects: destination, start_date_str, end_date_str, event_type, notes
            result = await service.add_event(
                family_id=family_id,
                user_id=user_id,
                title=args.get("title"),
                destination=args.get("location", args.get("destination", "")),
                start_date_str=args.get("event_date", args.get("start_date")),
                end_date_str=args.get("event_date", args.get("end_date")),
                event_type=args.get("category", args.get("event_type", "trip")),
                notes=args.get("description", args.get("notes")),
            )

            if result.get("success"):
                trip_id_str = result.get("trip_id", "")
                await trigger_curation_if_enabled(
                    family_id,
                    "auto_curate_on_trip_create",
                    "trip_created",
                    payload={"trip_id": trip_id_str},
                    db=self.db,
                )
                # Check memory triggers for the destination
                from ....modules.memory.tasks import (
                    trigger_memory_check_for_trip,
                )
                trigger_memory_check_for_trip(
                    family_id=str(family_id),
                    user_id=str(user_id),
                    destination=args.get("location", args.get("destination", "")),
                    trip_id=trip_id_str,
                    start_date=args.get("event_date", args.get("start_date", "")),
                    end_date=args.get("event_date", args.get("end_date", "")),
                )

            return result
        except Exception as e:
            logger.error(f"Add trip event failed: {e}")
            await self.db.rollback()
            return tool_error(ToolErrorType.INTERNAL, f"添加行程失败: {str(e)}")

    async def add_trip_itinerary(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.trip.services.trip_service import TripService
        from ....modules.curation.tasks import trigger_curation_if_enabled

        try:
            service = TripService(self.db)

            # --- Resolve or create trip -----------------------------------
            trip_id = args.get("trip_id")
            if not trip_id:
                destination = (args.get("destination") or "").strip()
                if not destination:
                    return tool_error(
                        ToolErrorType.VALIDATION,
                        "创建新行程需要提供 destination（目的地）",
                    )

                # Calculate end_date based on days array length
                days_raw = args.get("days")
                num_days = len(days_raw) if days_raw and isinstance(days_raw, list) else 1
                event_date = args.get("event_date")
                if event_date and num_days > 1:
                    start_dt = datetime.strptime(event_date, "%Y-%m-%d")
                    end_date_str = (start_dt + timedelta(days=num_days - 1)).strftime("%Y-%m-%d")
                else:
                    end_date_str = event_date

                trip_result = await service.add_event(
                    family_id=family_id,
                    user_id=user_id,
                    title=args.get("trip_name"),
                    destination=destination,
                    start_date_str=event_date,
                    end_date_str=end_date_str,
                    event_type="trip",
                )
                if not trip_result.get("success"):
                    return trip_result
                trip_id = trip_result["trip_id"]

            # --- Batch mode: ``days`` array --------------------------------
            days_raw = args.get("days")
            if days_raw and isinstance(days_raw, list):
                days_formatted = [
                    {
                        "day_number": d.get("day_number"),
                        "schedule": self._format_activities(
                            d.get("activities", d.get("schedule", []))
                        ),
                    }
                    for d in days_raw
                ]
                result = await service.add_itinerary(
                    family_id=family_id,
                    user_id=user_id,
                    args={"trip_id": trip_id, "days": days_formatted},
                )
            else:
                # --- Single-day mode --------------------------------------
                activities = args.get("activities", [])
                schedule = self._format_activities(activities)

                itinerary_args: Dict[str, Any] = {
                    "trip_id": trip_id,
                    "schedule": schedule,
                }
                # Only pass day_number when explicitly provided
                day_number = args.get("day_number")
                if day_number is not None:
                    itinerary_args["day_number"] = day_number

                result = await service.add_itinerary(
                    family_id=family_id,
                    user_id=user_id,
                    args=itinerary_args,
                )

            if result.get("success"):
                await trigger_curation_if_enabled(
                    family_id,
                    "auto_curate_on_trip_create",
                    "itinerary_updated",
                    payload={"trip_id": str(trip_id)},
                    db=self.db,
                )
                # Check memory triggers when a new trip is created via itinerary
                destination = (args.get("destination") or "").strip()
                if destination and trip_id == result.get("trip_id", trip_id):
                    from ....modules.memory.tasks import (
                        trigger_memory_check_for_trip,
                    )
                    trigger_memory_check_for_trip(
                        family_id=str(family_id),
                        user_id=str(user_id),
                        destination=destination,
                        trip_id=str(trip_id),
                        start_date=args.get("event_date", ""),
                    )

            return result
        except Exception as e:
            logger.error(f"Add trip itinerary failed: {e}")
            await self.db.rollback()
            return tool_error(ToolErrorType.INTERNAL, f"添加行程失败: {str(e)}")

    @staticmethod
    def _format_activities(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalise activity dicts into the schedule format."""
        return [
            {
                "time": act.get("start_time", ""),
                "end_time": act.get("end_time", ""),
                "title": act.get("title", ""),
                "location": act.get("location", ""),
                "category": act.get("category", ""),
                "description": act.get("description", ""),
            }
            for act in (activities or [])
        ]

    async def query_trips(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import select, and_, or_
        from sqlalchemy.orm import selectinload
        from ....modules.trip.models.trip_plan import TripPlan
        from ....modules.trip.services.trip_query_policy import (
            resolve_trip_query_policy,
        )

        status = args.get("status", "all")
        destination = args.get("destination")
        policy = resolve_trip_query_policy(args)
        query_scene = policy.scene
        include_history = policy.include_history

        try:
            conditions = [TripPlan.family_id == family_id]
            today = date.today()

            if status and status != "all":
                if status == "upcoming":
                    conditions.append(TripPlan.start_date > today)
                    conditions.append(TripPlan.status.notin_(["cancelled", "completed"]))
                elif status == "ongoing":
                    conditions.append(TripPlan.start_date <= today)
                    conditions.append(TripPlan.end_date >= today)
                elif status == "completed":
                    conditions.append(TripPlan.status == "completed")

            start_date_str = args.get("start_date")
            end_date_str = args.get("end_date")
            
            if start_date_str:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                conditions.append(TripPlan.end_date >= start_dt)
            if end_date_str:
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                conditions.append(TripPlan.start_date <= end_dt)

            if policy.date_scope == "past_only":
                conditions.append(TripPlan.end_date < today)
            elif policy.date_scope == "current_or_future":
                conditions.append(TripPlan.end_date >= today)

            if policy.status_include:
                conditions.append(TripPlan.status.in_(list(policy.status_include)))
            if policy.status_exclude:
                conditions.append(TripPlan.status.notin_(list(policy.status_exclude)))

            if not include_history:
                conditions.append(TripPlan.canonical_trip_id.is_(None))
                conditions.append(TripPlan.is_active.is_(True))

            if destination:
                from ..shared.sql_utils import escape_like
                escaped = escape_like(destination)
                conditions.append(
                    or_(
                        TripPlan.destination.ilike(f"%{escaped}%", escape="\\"),
                        TripPlan.trip_name.ilike(f"%{escaped}%", escape="\\"),
                    )
                )

            stmt = (
                select(TripPlan)
                .options(selectinload(TripPlan.itineraries))
                .where(and_(*conditions))
                .order_by(TripPlan.start_date.desc())
                .limit(10)
            )

            result = await self.db.execute(stmt)
            trips = list(result.scalars().all())

            if not trips:
                return {
                    "success": True,
                    "trips": [],
                    "total_count": 0,
                    "include_history": include_history,
                    "query_scene": query_scene,
                    "message": f"暂无{'去' + destination if destination else ''}旅行计划",
                }

            from ....modules.trip.services.trip_status import (
                compute_trip_status,
                get_status_display,
            )

            trip_list = []
            for trip in trips:
                effective = compute_trip_status(
                    trip.status, trip.start_date, trip.end_date,
                )
                trip_info = {
                    "id": str(trip.trip_id),
                    "title": trip.trip_name or trip.destination,
                    "location": trip.destination,
                    "start_date": trip.start_date.isoformat() if trip.start_date else None,
                    "end_date": trip.end_date.isoformat() if trip.end_date else None,
                    "status": effective,
                    "status_label": get_status_display(effective),
                    "description": trip.description,
                    "canonical_trip_id": (
                        str(trip.canonical_trip_id) if trip.canonical_trip_id else None
                    ),
                    "is_active": bool(getattr(trip, "is_active", True)),
                    "is_canonical": trip.canonical_trip_id is None,
                }

                if trip.itineraries:
                    itinerary_days = []
                    for itin in sorted(trip.itineraries, key=lambda x: x.day_number):
                        day_info = {"day_number": itin.day_number}
                        schedule = itin.schedule or []
                        day_info["activity_count"] = len(schedule)
                        if schedule:
                            day_info["activities"] = [
                                {
                                    "time": act.get("time", ""),
                                    "title": act.get("title", ""),
                                    "type": act.get("activity_type", "other"),
                                    "location": act.get("location", ""),
                                }
                                for act in schedule
                            ]
                        itinerary_days.append(day_info)
                    trip_info["itinerary"] = itinerary_days
                    trip_info["itinerary_days"] = len(itinerary_days)

                trip_list.append(trip_info)

            return {
                "success": True,
                "trips": trip_list,
                "total_count": len(trip_list),
                "include_history": include_history,
                "query_scene": query_scene,
                "message": f"找到 {len(trip_list)} 个{'去' + destination if destination else ''}旅行计划",
            }

        except Exception as e:
            logger.error(f"Query trips failed: {e}")
            return {"success": False, "message": f"查询旅行计划失败: {str(e)}"}

    async def merge_trips(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.trip.services.trip_service import TripService
        from ....modules.curation.tasks import trigger_curation_if_enabled

        primary_raw = args.get("primary_trip_id")
        merge_raw = args.get("merge_trip_ids") or []
        reason = args.get("reason")

        if not primary_raw:
            return tool_error(ToolErrorType.VALIDATION, "请提供 primary_trip_id")
        if not isinstance(merge_raw, list) or not merge_raw:
            return tool_error(ToolErrorType.VALIDATION, "请提供 merge_trip_ids（数组）")

        try:
            primary_trip_id = UUID(str(primary_raw))
            merge_trip_ids = [UUID(str(item)) for item in merge_raw]
        except Exception:
            return tool_error(ToolErrorType.VALIDATION, "trip_id 格式无效，请使用 UUID")

        try:
            service = TripService(self.db)
            result = await service.merge_trips(
                family_id=family_id,
                primary_trip_id=primary_trip_id,
                merge_trip_ids=merge_trip_ids,
                reason=reason,
            )
            if not result.get("success"):
                return result

            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "trip_updated",
                payload={"trip_id": str(primary_trip_id)},
                db=self.db,
            )
            return result
        except Exception as e:
            logger.error("Merge trips failed: %s", e)
            await self.db.rollback()
            return tool_error(ToolErrorType.INTERNAL, f"合并行程失败: {str(e)}")

    async def save_trip_plan(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import select, and_
        from ....modules.trip.models.trip_plan import TripPlan

        trip_id = args.get("trip_id")
        if not trip_id:
            return tool_error(
                ToolErrorType.VALIDATION,
                "请提供旅行计划ID (trip_id)",
            )

        try:
            stmt = select(TripPlan).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.trip_id == trip_id,
                )
            )
            result = await self.db.execute(stmt)
            trip = result.scalar_one_or_none()

            if not trip:
                return tool_error(
                    ToolErrorType.NOT_FOUND,
                    f"未找到行程 (trip_id={trip_id})，请先通过 query_trips 确认行程ID",
                )

            notes = args.get("notes")
            status = args.get("status")
            updated_fields = []

            if notes is not None:
                trip.description = notes
                updated_fields.append("备注")
            if status and status in ("planning", "confirmed", "completed"):
                trip.status = status
                updated_fields.append(f"状态→{status}")

            if not updated_fields:
                return {
                    "success": True,
                    "trip_id": str(trip.trip_id),
                    "trip_name": trip.trip_name,
                    "destination": trip.destination,
                    "status": trip.status,
                    "message": "行程无需更新",
                }

            await self.db.commit()

            try:
                from ....modules.curation.tasks import trigger_curation_if_enabled
                await trigger_curation_if_enabled(
                    family_id,
                    "auto_curate_on_trip_create",
                    "trip_updated",
                    payload={"trip_id": str(trip.trip_id)},
                    db=self.db,
                )
            except Exception:
                logger.debug("Curation trigger after save_trip_plan skipped")

            return {
                "success": True,
                "trip_id": str(trip.trip_id),
                "trip_name": trip.trip_name,
                "destination": trip.destination,
                "status": trip.status,
                "message": f"已更新行程「{trip.trip_name}」: {', '.join(updated_fields)}",
            }
        except Exception as e:
            logger.error(f"Save trip plan failed: {e}")
            return tool_error(ToolErrorType.INTERNAL, f"保存行程失败: {str(e)}")

    async def cancel_trip(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import select, and_, or_
        from ....modules.curation.models import CuratedEvent
        from ....modules.trip.models.trip_plan import TripPlan
        from ....modules.curation.tasks import trigger_curation_if_enabled

        trip_id = args.get("trip_id", "")
        trip_name = args.get("trip_name", "")
        reason = args.get("reason", "用户取消")
        keep_related_events = args.get("keep_related_events", False)

        if not trip_id and not trip_name:
            return tool_error(
                ToolErrorType.VALIDATION,
                "请提供要取消的行程ID或名称（建议先通过 query_trips 获取行程列表）",
            )

        try:
            if trip_id:
                trip_stmt = select(TripPlan).where(
                    and_(
                        TripPlan.family_id == family_id,
                        TripPlan.trip_id == trip_id,
                        TripPlan.status.notin_(["cancelled", "completed"]),
                    )
                )
            else:
                from ..shared.sql_utils import escape_like
                escaped_name = escape_like(trip_name)
                trip_stmt = (
                    select(TripPlan)
                    .where(
                        and_(
                            TripPlan.family_id == family_id,
                            TripPlan.status.notin_(["cancelled", "completed"]),
                            or_(
                                TripPlan.trip_name.ilike(f"%{escaped_name}%", escape="\\"),
                                TripPlan.trip_name.ilike(f"{escaped_name}%", escape="\\"),
                            ),
                        )
                    )
                    .order_by(TripPlan.start_date)
                )

            trip_result = await self.db.execute(trip_stmt)
            trips = list(trip_result.scalars().all())

            search_label = trip_id or trip_name

            if not trips:
                fallback_conditions = [
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.event_type.in_(["business_trip", "trip"]),
                    CuratedEvent.status.notin_(["cancelled", "completed"]),
                ]

                if trip_id:
                    fallback_conditions.append(CuratedEvent.trip_id == trip_id)
                else:
                    from ..shared.sql_utils import escape_like
                    escaped_fallback = escape_like(trip_name)
                    fallback_conditions.append(
                        or_(
                            CuratedEvent.title.ilike(f"%{escaped_fallback}%", escape="\\"),
                            CuratedEvent.title.ilike(f"{escaped_fallback}%", escape="\\"),
                        )
                    )

                event_stmt = select(CuratedEvent).where(and_(*fallback_conditions))
                event_result = await self.db.execute(event_stmt)
                events = list(event_result.scalars().all())

                if not events:
                    return tool_error(ToolErrorType.NOT_FOUND, f"未找到匹配「{search_label}」的行程")

                cancelled_titles = []
                for event in events:
                    event.status = "cancelled"
                    event.is_active = False
                    if event.notes:
                        event.notes = f"{event.notes}\n[取消原因: {reason}]"
                    else:
                        event.notes = f"[取消原因: {reason}]"
                    cancelled_titles.append(event.title)

                await self.db.commit()

                # Fallback path: trigger curation for each unique trip_id
                fallback_trip_ids = list(dict.fromkeys(
                    str(e.trip_id) for e in events if e.trip_id
                ))
                for tid in fallback_trip_ids:
                    await trigger_curation_if_enabled(
                        family_id,
                        "auto_curate_on_trip_create",
                        "trip_cancelled",
                        payload={"trip_id": tid},
                        db=self.db,
                    )

                return {
                    "success": True,
                    "cancelled_trip": cancelled_titles[0] if cancelled_titles else search_label,
                    "cancelled_events": len(cancelled_titles),
                    "message": (
                        f"已取消行程「{cancelled_titles[0]}」及其{len(cancelled_titles)}个相关事件"
                        if len(cancelled_titles) > 1
                        else f"已取消行程「{cancelled_titles[0]}」"
                    ),
                    "secretary_hint": "行程已取消，我会帮您重新整理相关安排",
                    "should_recurate": True,
                }

            cancelled_trips = []
            total_cancelled_events = 0

            for trip in trips:
                trip.status = "cancelled"
                trip.is_active = False
                cancelled_trips.append(trip.trip_name or trip.destination)

                if not keep_related_events:
                    related_stmt = select(CuratedEvent).where(
                        and_(
                            CuratedEvent.family_id == family_id,
                            CuratedEvent.trip_id == trip.trip_id,
                            CuratedEvent.is_active.is_(True),
                        )
                    )
                    related_result = await self.db.execute(related_stmt)
                    related_events = list(related_result.scalars().all())

                    for event in related_events:
                        event.status = "cancelled"
                        event.is_active = False
                        total_cancelled_events += 1

            await self.db.commit()

            # Pass trip_ids for proper curation lifecycle handling
            cancelled_trip_ids = [
                str(t.trip_id) for t in trips
            ]
            for tid in cancelled_trip_ids:
                await trigger_curation_if_enabled(
                    family_id,
                    "auto_curate_on_trip_create",
                    "trip_cancelled",
                    payload={"trip_id": tid},
                    db=self.db,
                )

            if len(cancelled_trips) == 1:
                if total_cancelled_events > 0:
                    message = f"已取消行程「{cancelled_trips[0]}」及其{total_cancelled_events}个相关事件"
                else:
                    message = f"已取消行程「{cancelled_trips[0]}」"
            else:
                trips_str = "、".join(cancelled_trips[:3])
                if len(cancelled_trips) > 3:
                    trips_str += f" 等{len(cancelled_trips)}个行程"
                message = f"已取消: {trips_str}（共{total_cancelled_events}个相关事件）"

            return {
                "success": True,
                "cancelled_trips": cancelled_trips,
                "cancelled_events": total_cancelled_events,
                "message": message,
                "secretary_hint": "行程已取消，我会帮您重新整理相关安排",
                "should_recurate": True,
            }

        except Exception as e:
            logger.error(f"Cancel trip failed: {e}")
            await self.db.rollback()
            return tool_error(ToolErrorType.INTERNAL, f"取消行程失败: {str(e)}")

    async def query_trip_bookings(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            from ....modules.data_connection.services.external_data_service import ExternalDataService
            from ....core.utils.timezone import utc_now

            start_str = args.get("start_date")
            end_str = args.get("end_date")
            booking_type = args.get("booking_type", "all")

            start_date = (
                datetime.strptime(start_str, "%Y-%m-%d")
                if start_str
                else utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
            )
            end_date = (
                datetime.strptime(end_str, "%Y-%m-%d")
                if end_str
                else start_date + timedelta(days=90)
            )

            service = ExternalDataService(self.db)
            bookings = await service.get_travel_bookings(
                family_id=family_id,
                start_date=start_date,
                end_date=end_date,
                booking_type=booking_type if booking_type != "all" else None,
            )

            if not bookings:
                return {
                    "success": True,
                    "bookings": [],
                    "message": "未找到行程预订信息。可能尚未连接邮箱服务，或该时间段没有预订。",
                    "hint": "您可以在【数据连接中心】添加 Gmail 或 Outlook 邮箱连接，系统会自动解析机票、酒店预订邮件。",
                }

            booking_list = []
            for b in bookings:
                booking_info: Dict[str, Any] = {
                    "booking_type": b.booking_type,
                    "confirmation_number": b.booking_id,
                    "status": b.status,
                    "source": b.source,
                }

                if b.booking_type == "flight":
                    booking_info.update({
                        "title": f"{b.airline or ''} {b.flight_number or ''}: {b.departure_city or ''} → {b.arrival_city or ''}",
                        "departure_time": b.departure_time.strftime("%Y-%m-%d %H:%M") if b.departure_time else None,
                        "arrival_time": b.arrival_time.strftime("%Y-%m-%d %H:%M") if b.arrival_time else None,
                        "passenger": b.passenger_name,
                    })
                elif b.booking_type == "hotel":
                    booking_info.update({
                        "title": b.hotel_name or "酒店预订",
                        "check_in": b.check_in_date.strftime("%Y-%m-%d") if b.check_in_date else None,
                        "check_out": b.check_out_date.strftime("%Y-%m-%d") if b.check_out_date else None,
                        "city": b.city,
                        "guest_name": b.guest_name,
                    })
                else:
                    booking_info["title"] = "行程预订"

                booking_list.append(booking_info)

            return {
                "success": True,
                "bookings": booking_list,
                "total": len(booking_list),
                "period": f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                "message": f"找到 {len(booking_list)} 个行程预订",
            }

        except ImportError:
            return {"success": False, "message": "数据连接模块未启用"}
        except Exception as e:
            logger.error(f"Query trip bookings failed: {e}")
            return {"success": False, "message": f"查询行程预订失败: {str(e)}"}

    async def query_external_calendar(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            from ....modules.data_connection.services.external_data_service import ExternalDataService
            from ....core.utils.timezone import utc_now

            start_str = args.get("start_date")
            end_str = args.get("end_date")

            start_date = (
                datetime.strptime(start_str, "%Y-%m-%d")
                if start_str
                else utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
            )
            end_date = (
                datetime.strptime(end_str, "%Y-%m-%d")
                if end_str
                else start_date + timedelta(days=7)
            )

            service = ExternalDataService(self.db)
            events = await service.get_calendar_events(
                family_id=family_id,
                start_date=start_date,
                end_date=end_date,
                usage_type="assistant_query",
            )

            if not events:
                return {
                    "success": True,
                    "events": [],
                    "message": "未找到外部日历事件。可能尚未连接日历服务，或该时间段没有日程。",
                    "hint": "您可以在【数据连接中心】添加 Google Calendar 或 Outlook 日历连接。",
                }

            event_list = [
                {
                    "title": e.title,
                    "description": e.description,
                    "start_time": e.start_time.strftime("%Y-%m-%d %H:%M") if e.start_time else None,
                    "end_time": e.end_time.strftime("%Y-%m-%d %H:%M") if e.end_time else None,
                    "location": e.location,
                    "is_all_day": e.is_all_day,
                    "source": e.source,
                    "organizer": e.organizer,
                }
                for e in events
            ]

            return {
                "success": True,
                "events": event_list,
                "total": len(event_list),
                "period": f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                "message": f"找到 {len(event_list)} 个外部日历事件",
            }

        except ImportError:
            return {"success": False, "message": "数据连接模块未启用"}
        except Exception as e:
            logger.error(f"Query external calendar failed: {e}")
            return {"success": False, "message": f"查询外部日历失败: {str(e)}"}
