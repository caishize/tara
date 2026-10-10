"""Conflict detection and resolution methods for the curation service.

Contains _ensure_pending_actions, _detect_and_resolve_conflicts,
and _notify_conflicts.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Set
from uuid import UUID

from sqlalchemy import select, and_

from ....config.logging import get_logger
from ....config.settings import settings
from ....core.utils.timezone import local_today, format_local_datetime
from ..models import CuratedEvent

logger = get_logger(__name__)


class CurationConflictMixin:
    """Mixin providing conflict detection methods for SecretaryCurationService."""

    async def _ensure_pending_actions(
        self,
        conflicts: list,
        family_id: UUID,
        user_id: Optional[UUID],
        core_event: "CuratedEvent",
    ) -> None:
        """Ensure every conflict has a PendingAction for user interaction."""
        try:
            from ...conversation.pending_action import (
                PendingAction,
                ActionType,
                ActionStatus,
            )
            from .conflict_detection import _create_reschedule_action
            from ..schemas import ConflictAlert

            stmt = select(PendingAction).where(
                and_(
                    PendingAction.family_id == family_id,
                    PendingAction.action_type == ActionType.RESCHEDULE_EVENT.value,
                    PendingAction.status == ActionStatus.PENDING.value,
                )
            )
            result = await self.session.execute(stmt)
            pending_actions = list(result.scalars().all())

            event_to_action: Dict[str, str] = {}
            for action in pending_actions:
                event_id = (action.payload or {}).get("event_id")
                if not event_id:
                    continue
                exists = await self.session.get(CuratedEvent, event_id)
                if exists and exists.is_active:
                    event_to_action[event_id] = str(action.id)
                else:
                    action.status = ActionStatus.EXPIRED.value
                    logger.info(
                        "Expired stale pending action %s (event %s no longer exists)",
                        action.id, event_id,
                    )

            for i, conflict in enumerate(conflicts):
                if conflict.auto_resolved:
                    continue

                matched_action_id = None
                for eid in conflict.conflicting_event_ids:
                    if eid in event_to_action:
                        matched_action_id = event_to_action[eid]
                        break

                if matched_action_id:
                    conflicts[i] = ConflictAlert(
                        **{
                            **conflict.model_dump(),
                            "pending_action_id": matched_action_id,
                        }
                    )
                elif user_id:
                    other_event_id = next(
                        (eid for eid in conflict.conflicting_event_ids
                         if eid != str(core_event.id)),
                        None,
                    )
                    if other_event_id:
                        other_event = await self.session.get(
                            CuratedEvent, other_event_id,
                        )
                        if other_event:
                            action_id = await _create_reschedule_action(
                                self.session, user_id, family_id,
                                core_event, other_event,
                                conflict.suggestion,
                            )
                            if action_id:
                                conflicts[i] = ConflictAlert(
                                    **{
                                        **conflict.model_dump(),
                                        "pending_action_id": action_id,
                                    }
                                )

            await self.session.commit()
        except Exception as e:
            logger.error("Failed to ensure pending actions: %s", e)

    async def _detect_and_resolve_conflicts(
        self,
        family_id: UUID,
        curated_events: List[CuratedEvent],
        user_id: Optional[UUID],
        family_prefs=None,
    ) -> int:
        """Detect and resolve schedule conflicts during curation (write path).

        Returns:
            Total number of conflicts detected.
        """
        from .conflict_detection import (
            detect_conflicts,
            detect_spatial_conflicts,
            classify_conflict_importance,
            _aggregate_by_trip,
            _pick_event_to_adjust,
            _create_reschedule_action,
            _snap_to_weekend_if_needed,
            CONFLICT_EVENT_TYPES,
        )
        from ..schemas import ConflictAlert

        max_horizon = datetime.combine(
            local_today() + timedelta(days=365),
            datetime.max.time(),
            tzinfo=timezone.utc,
        )
        all_events_stmt = (
            select(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status != "cancelled",
                    CuratedEvent.event_type.in_(list(CONFLICT_EVENT_TYPES)),
                    CuratedEvent.normalized_start.isnot(None),
                    CuratedEvent.normalized_start <= max_horizon,
                )
            )
            .order_by(CuratedEvent.normalized_start)
        )
        result = await self.session.execute(all_events_stmt)
        all_db_events = list(result.scalars().all())

        if not all_db_events:
            return 0

        trip_day_events: Dict[str, List[CuratedEvent]] = {}
        for e in all_db_events:
            key = str(e.trip_id) if e.trip_id else str(e.id)
            trip_day_events.setdefault(key, []).append(e)

        aggregated = _aggregate_by_trip(all_db_events)

        all_conflicts: List[ConflictAlert] = []
        resolved_trip_keys: Set[str] = set()

        for conflict_event in aggregated:
            trip_key = str(conflict_event.trip_id) if conflict_event.trip_id else str(conflict_event.id)

            if trip_key in resolved_trip_keys:
                continue

            same_trip_ids: Set[UUID] = set()
            if conflict_event.trip_id:
                same_trip_ids = {
                    e.id for e in all_db_events
                    if e.trip_id == conflict_event.trip_id
                    and e.id != conflict_event.id
                }

            conflicts = await detect_conflicts(
                self.session,
                family_id,
                conflict_event,
                user_id=user_id,
                exclude_event_ids=same_trip_ids or None,
                read_only=True,
            )

            if not conflicts:
                continue

            for conflict in conflicts:
                other_event_ids = [
                    eid for eid in conflict.conflicting_event_ids
                    if eid != str(conflict_event.id)
                ]

                other_aggregated = None
                other_trip_key = None
                for agg in aggregated:
                    if str(agg.id) in other_event_ids:
                        other_aggregated = agg
                        other_trip_key = str(agg.trip_id) if agg.trip_id else str(agg.id)
                        break

                if not other_aggregated:
                    all_conflicts.append(conflict)
                    continue

                if other_trip_key in resolved_trip_keys:
                    continue

                resolution = classify_conflict_importance(conflict_event, other_aggregated)

                if resolution == "auto_resolve":
                    event_to_adjust = _pick_event_to_adjust(conflict_event, other_aggregated)
                    adjust_trip_key = str(event_to_adjust.trip_id) if event_to_adjust.trip_id else str(event_to_adjust.id)
                    anchor = conflict_event if adjust_trip_key != trip_key else other_aggregated
                    anchor_end = anchor.normalized_end or anchor.normalized_start

                    max_offset_days = max(1, int(settings.curation_max_auto_resolve_offset_days))
                    buffer_days = max(0, int(settings.curation_auto_resolve_buffer_days))
                    real_days = trip_day_events.get(adjust_trip_key, [])
                    new_trip_start = None
                    if real_days:
                        original_trip_start = min(
                            e.normalized_start for e in real_days if e.normalized_start
                        )
                        new_trip_start = anchor_end + timedelta(days=buffer_days)
                        new_trip_start = _snap_to_weekend_if_needed(
                            event_to_adjust.title, new_trip_start,
                        )
                        new_trip_start = new_trip_start.replace(
                            hour=original_trip_start.hour,
                            minute=original_trip_start.minute,
                            second=original_trip_start.second,
                            microsecond=original_trip_start.microsecond,
                        )
                        offset = new_trip_start - original_trip_start

                        if abs(offset.days) > max_offset_days:
                            logger.warning(
                                "Auto-resolve offset too large (%d days) for trip '%s'; "
                                "skipping auto-resolve — will require user confirmation.",
                                offset.days, event_to_adjust.title,
                            )
                            resolution = "user_confirm"
                        else:
                            for day_event in real_days:
                                if day_event.normalized_start:
                                    day_event.normalized_start = day_event.normalized_start + offset
                                if day_event.normalized_end:
                                    day_event.normalized_end = day_event.normalized_end + offset

                            await self.session.flush()
                            resolved_trip_keys.add(adjust_trip_key)

                            logger.info(
                                "Auto-resolved conflict: moved trip '%s' (%d days) by %d days",
                                event_to_adjust.title, len(real_days), offset.days,
                            )
                    else:
                        resolution = "user_confirm"

                    if resolution != "user_confirm" and new_trip_start is not None:
                        conflict = ConflictAlert(
                            **{
                                **conflict.model_dump(),
                                "auto_resolved": True,
                                "resolution_note": (
                                    f"\u5df2\u81ea\u52a8\u8c03\u6574{event_to_adjust.title}\u81f3"
                                    f"{format_local_datetime(new_trip_start, format_str='%m.%d')}\u540e"
                                ),
                            }
                        )

                if resolution == "user_confirm" and user_id is not None:
                    pending_action_id = await _create_reschedule_action(
                        self.session, user_id, family_id,
                        conflict_event, other_aggregated,
                        conflict.suggestion,
                    )
                    if pending_action_id:
                        conflict = ConflictAlert(
                            **{
                                **conflict.model_dump(),
                                "pending_action_id": pending_action_id,
                            }
                        )

                all_conflicts.append(conflict)

        # Spatial conflict detection: same-day different-city events
        spatial_conflicts = await detect_spatial_conflicts(
            self.session, family_id, all_db_events,
        )
        all_conflicts.extend(spatial_conflicts)

        if all_conflicts:
            await self._notify_conflicts(all_conflicts, user_id)

        if all_conflicts:
            logger.info(
                "Detected %d conflicts (%d spatial) during curation for family %s",
                len(all_conflicts), len(spatial_conflicts), family_id,
            )

        return len(all_conflicts)

    async def _notify_conflicts(
        self,
        conflicts: list,
        user_id: Optional[UUID],
    ) -> None:
        """Push notifications for detected conflicts."""
        if not user_id:
            return

        try:
            from ....core.pubsub.redis_pubsub import get_pubsub_manager
            from uuid import uuid4

            pubsub = get_pubsub_manager()
            user_id_str = str(user_id)

            for conflict in conflicts:
                if conflict.pending_action_id:
                    trace_id = str(uuid4())
                    await pubsub.publish_confirm_card(
                        user_id=user_id_str,
                        action_id=conflict.pending_action_id,
                        action_type="reschedule_event",
                        display_data={
                            "title": conflict.title,
                            "details": [
                                {"label": "\u51b2\u7a81\u8be6\u60c5", "value": conflict.description},
                                {"label": "\u5efa\u8bae", "value": conflict.suggestion},
                            ],
                        },
                        trace_id=trace_id,
                    )
        except Exception as e:
            logger.error("Failed to push conflict notifications: %s", e)
