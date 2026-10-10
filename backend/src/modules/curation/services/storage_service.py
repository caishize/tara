"""Storage methods for the curation service.

Contains _store_curated_events, _link_events_to_trips,
_populate_trip_context, _store_associations, _mark_consumed_memories.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, select, update

from ....config.logging import get_logger
from ....core.utils.timezone import local_today, get_user_timezone
from ..models import CuratedEvent, EventAssociation
from ...memory.models import ConversationMemory, MemoryType, MemoryStatus
from ...trip.models.trip_plan import TripPlan
from .priority_score import compute_priority_score

logger = get_logger(__name__)


def _md5(text: str) -> str:
    """Compute MD5 hex digest of text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Mini-curate semantic dedup helpers
# ---------------------------------------------------------------------------

from .constants import MAJOR_CITIES as _MAJOR_CITIES


def extract_city(location: Optional[str]) -> Optional[str]:
    """Extract city name from location string like '上海虹桥' -> '上海'."""
    if not location:
        return None
    location = location.strip()
    if not location:
        return None
    for city in _MAJOR_CITIES:
        if city in location:
            return city
    # Fallback: return first 2 chars if Chinese
    if len(location) >= 2 and '\u4e00' <= location[0] <= '\u9fff':
        return location[:2]
    return location


def compute_mini_curate_fingerprint(
    title: str,
    location: Optional[str] = None,
    start_time: Optional[datetime] = None,
    event_type: Optional[str] = None,
) -> Optional[str]:
    """Compute semantic fingerprint for mini-curate dedup: MD5(city|start_date|event_type).

    NOTE: Fingerprint schema v2 (2026-02): changed from MD5(city|date) to
    MD5(city|date|event_type). Existing rows with old-format fingerprints will
    not match via Level 2 dedup; Level 1 (exact title) and Level 3 (city+date
    unique) provide fallback coverage during the transition period.

    Returns ``None`` when there is not enough information to build a
    meaningful fingerprint.
    """
    city = extract_city(location) if location else None
    if not city and not start_time:
        return None
    date_str = start_time.strftime("%Y-%m-%d") if start_time else ""
    etype = event_type or ""
    raw = "{city}|{date}|{etype}".format(city=city or "", date=date_str, etype=etype)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def compute_event_stable_key(event: CuratedEvent) -> str:
    """Build a deterministic identity key from event type + entity IDs.

    Compose from event_type + sorted original_event_ids + trip_id so that
    the same logical event always produces the same key across re-curations.
    """
    parts = [
        str(event.family_id or ""),
        (event.event_type or "").strip().lower(),
    ]
    source_ids = sorted(str(oid) for oid in (event.original_event_ids or []) if oid)
    parts.extend(source_ids)
    if event.trip_id:
        parts.append(str(event.trip_id))
    return "|".join(parts)


def compute_raw_event_fingerprint(raw) -> str:
    """MD5 of raw event data for quick change detection during reconciliation.

    Operates on raw event objects (with attrs like title, start_time, etc.)
    before they become CuratedEvents.
    """
    parts = [
        str(getattr(raw, 'title', '') or ''),
        str(getattr(raw, 'start_time', '') or ''),
        str(getattr(raw, 'end_time', '') or ''),
        str(getattr(raw, 'location', '') or ''),
        str(getattr(raw, 'description', '') or ''),
    ]
    return _md5("|".join(parts))


def compute_event_source_fingerprint(event: CuratedEvent) -> str:
    """MD5 of the raw source data that produced this event."""
    source_ids = sorted(str(oid) for oid in (event.original_event_ids or []) if oid)
    source_types = sorted(str(s) for s in (event.source_types or []) if s)
    text = "|".join(source_ids + source_types)
    return _md5(text)


def compute_event_semantic_fingerprint(event: CuratedEvent) -> str:
    """MD5 of the semantic content (title+start+end+location+type)."""
    parts = [
        (event.title or "").strip(),
        event.normalized_start.isoformat() if event.normalized_start else "",
        event.normalized_end.isoformat() if event.normalized_end else "",
        (event.location or "").strip(),
        (event.event_type or "").strip().lower(),
        (event.city or "").strip(),
        (event.priority or "").strip().lower(),
    ]
    return _md5("|".join(parts))


def compute_association_stable_key(assoc: EventAssociation) -> str:
    """Build a deterministic identity key for an association."""
    return "|".join([
        str(assoc.source_event_id or ""),
        (assoc.target_id or "").strip(),
        (assoc.target_type or "").strip().lower(),
        (assoc.association_type or "").strip().lower(),
    ])


def compute_association_source_fingerprint(assoc: EventAssociation) -> str:
    """MD5 of the source data that produced this association."""
    text = "|".join([
        str(assoc.source_event_id or ""),
        str(assoc.family_id or ""),
        (assoc.target_id or "").strip(),
    ])
    return _md5(text)


def compute_association_semantic_fingerprint(assoc: EventAssociation) -> str:
    """MD5 of the semantic content of this association."""
    parts = [
        (assoc.title or "").strip(),
        (assoc.reason or "").strip(),
        (assoc.priority or "").strip().lower(),
        str(assoc.confidence or 0),
    ]
    return _md5("|".join(parts))


def compute_visibility_tier(event_data: dict) -> str:
    """Compute visibility tier based on PriorityScore composite.

    composite >= 0.6 -> "focus" (important: business trip, wedding, birthday)
    composite >= 0.3 -> "standard" (routine: dentist, haircut, meeting)
    composite < 0.3  -> "detail" (trivial: groceries, utilities)
    """
    score = compute_priority_score(event_data)
    composite = score.composite
    if composite >= 0.6:
        return "focus"
    if composite >= 0.3:
        return "standard"
    return "detail"


class CurationStorageMixin:
    """Mixin providing storage methods for SecretaryCurationService."""

    @staticmethod
    def _stamp_event_fingerprints(event: CuratedEvent) -> None:
        """Compute and set fingerprint fields on a CuratedEvent."""
        event.stable_key = compute_event_stable_key(event)
        event.source_fingerprint = compute_event_source_fingerprint(event)
        event.semantic_fingerprint = compute_event_semantic_fingerprint(event)

    @staticmethod
    def _stamp_association_fingerprints(assoc: EventAssociation) -> None:
        """Compute and set fingerprint fields on an EventAssociation."""
        assoc.stable_key = compute_association_stable_key(assoc)
        assoc.source_fingerprint = compute_association_source_fingerprint(assoc)
        assoc.semantic_fingerprint = compute_association_semantic_fingerprint(assoc)

    async def _store_curated_events(
        self,
        family_id: UUID,
        curated_events: List[CuratedEvent],
        date_range: Tuple[datetime, datetime],
        failed_sources: Optional[List[str]] = None,
    ) -> List[CuratedEvent]:
        """Store curated events via diff/upsert (idempotent, no replace-all)."""
        start_date, end_date = date_range

        job_start_utc = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        job_end_utc = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        event_starts = [e.normalized_start for e in curated_events if e.normalized_start]
        raw_start = min([job_start_utc] + event_starts)
        scope_start = datetime.combine(raw_start.date(), datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=1)
        scope_end = max([job_end_utc] + event_starts)

        incoming_trip_ids = {e.trip_id for e in curated_events if e.trip_id is not None}
        incoming_source_ids = sorted({
            str(oid)
            for event in curated_events
            for oid in (event.original_event_ids or [])
            if oid
        })
        curated_events = self._dedup_decomposed_events(curated_events)

        # Stamp fingerprints and compute visibility tier on all incoming events.
        for event in curated_events:
            self._stamp_event_fingerprints(event)
            event.visibility_tier = compute_visibility_tier({
                "normalized_start": event.normalized_start,
                "event_type": event.event_type,
                "priority": event.priority,
            })

        existing_events = await self._load_mutable_events_for_diff(
            family_id=family_id,
            scope_start=scope_start,
            scope_end=scope_end,
            trip_ids=incoming_trip_ids,
            source_ids=incoming_source_ids,
        )

        user_tz = get_user_timezone()
        existing_by_key: Dict[tuple, List[CuratedEvent]] = {}
        existing_by_stable_key: Dict[str, CuratedEvent] = {}
        failed_source_set = {
            source for source in (failed_sources or [])
            if isinstance(source, str) and source.strip()
        }
        for existing in existing_events:
            key = self._event_identity_key(existing, user_tz)
            existing_by_key.setdefault(key, []).append(existing)
            if existing.stable_key:
                existing_by_stable_key[existing.stable_key] = existing

        # Reuse historical rows (including inactive/cancelled) by stable_key
        # to avoid unique-key collisions on re-curation.
        incoming_stable_keys = sorted({
            event.stable_key
            for event in curated_events
            if isinstance(event.stable_key, str) and event.stable_key.strip()
        })
        if incoming_stable_keys:
            stable_stmt = select(CuratedEvent).where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.stable_key.in_(incoming_stable_keys),
                )
            )
            stable_result = await self.session.execute(stable_stmt)
            for existing in stable_result.scalars().all():
                if "user_created" in (existing.source_types or []):
                    continue
                if existing.stable_key:
                    existing_by_stable_key.setdefault(existing.stable_key, existing)

        matched_ids: Set[UUID] = set()
        persisted_events: List[CuratedEvent] = []
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for incoming in curated_events:
            # 1. Try stable_key lookup first (fingerprint-based).
            existing: Optional[CuratedEvent] = None
            if incoming.stable_key:
                existing = existing_by_stable_key.get(incoming.stable_key)
                if existing and existing.id in matched_ids:
                    existing = None

            # 2. Fall back to legacy identity-key matching.
            if existing is None:
                key = self._event_identity_key(incoming, user_tz)
                existing = self._pop_matching_event(existing_by_key, key, matched_ids)
            if existing is None:
                existing = self._find_source_overlap_match(
                    incoming,
                    existing_events,
                    matched_ids,
                )

            if existing is None:
                self.session.add(incoming)
                persisted_events.append(incoming)
                created_count += 1
                continue

            matched_ids.add(existing.id)

            # Fingerprint short-circuit: skip if semantic content unchanged.
            if (
                existing.semantic_fingerprint
                and incoming.semantic_fingerprint
                and existing.semantic_fingerprint == incoming.semantic_fingerprint
            ):
                # No-op: content identical. Keep existing row as-is.
                incoming.id = existing.id
                persisted_events.append(existing)
                skipped_count += 1
                continue

            # Keep downstream steps (conflict/association discovery) aligned with
            # the persisted row identity.
            incoming.id = existing.id
            if self._apply_event_patch(existing, incoming):
                # Bump fingerprints on the persisted row.
                existing.stable_key = incoming.stable_key
                existing.source_fingerprint = incoming.source_fingerprint
                existing.semantic_fingerprint = incoming.semantic_fingerprint
                updated_count += 1
            persisted_events.append(existing)

        stale_ids: List[UUID] = []
        for existing in existing_events:
            if existing.id in matched_ids:
                continue
            if failed_source_set and (set(existing.source_types or []) & failed_source_set):
                continue
            if existing.status == "confirmed":
                continue

            # NEW LOGIC: Only consider an event stale if it falls completely within the core job timeframe.
            # If it's outside [job_start_utc, job_end_utc], its source might not have been collected by the job,
            # meaning it was falsely deduced to be deleted by diff_apply.
            if existing.normalized_start:
                if existing.normalized_start < job_start_utc or existing.normalized_start > job_end_utc:
                    continue

            if existing.is_active:
                existing.is_active = False
            if existing.status not in ("cancelled", "completed"):
                existing.status = "cancelled"
            existing.dedup_reason = "diff_apply: source removed or out of scope"
            stale_ids.append(existing.id)

        if stale_ids:
            await self._expire_pending_reschedule_actions(family_id, stale_ids)
            await self._dismiss_open_associations(stale_ids)

        # Safety net: deactivate stale auto-curated events beyond 1 year.
        far_future_cutoff = datetime.combine(
            local_today() + timedelta(days=365),
            datetime.max.time(),
            tzinfo=timezone.utc,
        )
        orphan_stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.normalized_start > far_future_cutoff,
            )
        )
        orphan_result = await self.session.execute(orphan_stmt)
        far_future_ids: List[UUID] = []
        for event in orphan_result.scalars().all():
            if "user_created" in (event.source_types or []):
                continue
            if event.status == "confirmed":
                continue
            event.is_active = False
            if event.status not in ("cancelled", "completed"):
                event.status = "cancelled"
            event.dedup_reason = "diff_apply: far-future safety deactivate"
            far_future_ids.append(event.id)

        if far_future_ids:
            logger.warning(
                "Deactivated %d far-future events (beyond %s) for family %s",
                len(far_future_ids),
                far_future_cutoff.date(),
                family_id,
            )
            await self._expire_pending_reschedule_actions(family_id, far_future_ids)
            await self._dismiss_open_associations(far_future_ids)

        await self.session.flush()

        if persisted_events:
            await self._link_events_to_trips(persisted_events)
            await self._populate_trip_context(persisted_events)

        logger.info(
            "DiffApply curated_events for family %s: %d created, %d updated, "
            "%d skipped (fingerprint match), %d deactivated",
            family_id,
            created_count,
            updated_count,
            skipped_count,
            len(stale_ids) + len(far_future_ids),
        )
        return persisted_events

    async def _load_mutable_events_for_diff(
        self,
        family_id: UUID,
        scope_start: datetime,
        scope_end: datetime,
        trip_ids: Set[UUID],
        source_ids: List[str],
    ) -> List[CuratedEvent]:
        scope_condition = and_(
            CuratedEvent.normalized_start >= scope_start,
            CuratedEvent.normalized_start <= scope_end,
        )
        extra_conditions = [scope_condition]
        if trip_ids:
            extra_conditions.append(CuratedEvent.trip_id.in_(trip_ids))
        if source_ids:
            extra_conditions.extend(
                CuratedEvent.original_event_ids.contains([source_id])
                for source_id in source_ids
            )

        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                or_(*extra_conditions),
            )
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        return [
            event
            for event in events
            if "user_created" not in (event.source_types or [])
        ]

    def _event_identity_key(self, event: CuratedEvent, user_tz) -> tuple:
        title = (event.title or "").strip()
        is_day_event = title.startswith("Day ")
        day_marker = ""
        if is_day_event and event.normalized_start:
            day_marker = event.normalized_start.astimezone(user_tz).date().isoformat()

        if event.trip_id:
            return ("trip", str(event.trip_id), day_marker)

        source_ids = tuple(sorted(str(oid) for oid in (event.original_event_ids or [])))
        if source_ids:
            source_types = tuple(sorted(str(s) for s in (event.source_types or [])))
            return ("source", source_types, source_ids, day_marker)

        normalized_title = title.lower()
        normalized_location = (
            self._normalize_destination(event.location or "")
            or (event.location or "").strip().lower()
        )
        normalized_day = ""
        if event.normalized_start:
            normalized_day = event.normalized_start.astimezone(user_tz).date().isoformat()
        return (
            "semantic",
            normalized_title,
            normalized_day,
            (event.event_type or "").strip().lower(),
            normalized_location,
        )

    @staticmethod
    def _pop_matching_event(
        existing_by_key: Dict[tuple, List[CuratedEvent]],
        key: tuple,
        matched_ids: Set[UUID],
    ) -> Optional[CuratedEvent]:
        candidates = existing_by_key.get(key, [])
        while candidates:
            candidate = candidates.pop(0)
            if candidate.id in matched_ids:
                continue
            return candidate
        return None

    @staticmethod
    def _find_source_overlap_match(
        incoming: CuratedEvent,
        existing_events: List[CuratedEvent],
        matched_ids: Set[UUID],
    ) -> Optional[CuratedEvent]:
        incoming_sources = {str(oid) for oid in (incoming.original_event_ids or [])}
        if not incoming_sources:
            return None

        best_match: Optional[CuratedEvent] = None
        best_score = -1
        for existing in existing_events:
            if existing.id in matched_ids:
                continue
            existing_sources = {str(oid) for oid in (existing.original_event_ids or [])}
            if not existing_sources:
                continue

            overlap = len(incoming_sources & existing_sources)
            if overlap <= 0:
                continue

            score = overlap
            if incoming.trip_id and existing.trip_id and incoming.trip_id == existing.trip_id:
                score += 2
            if (incoming.event_type or "") == (existing.event_type or ""):
                score += 1

            if score > best_score:
                best_match = existing
                best_score = score

        return best_match

    def _apply_event_patch(self, target: CuratedEvent, source: CuratedEvent) -> bool:
        changed = False

        merged_original_ids = sorted({
            str(oid) for oid in (target.original_event_ids or [])
        } | {
            str(oid) for oid in (source.original_event_ids or [])
        })
        merged_source_types = sorted({
            str(st) for st in (target.source_types or [])
        } | {
            str(st) for st in (source.source_types or [])
        })

        field_values = {
            "user_id": source.user_id,
            "trip_id": source.trip_id,
            "original_event_ids": merged_original_ids,
            "source_types": merged_source_types,
            "title": source.title,
            "normalized_start": source.normalized_start,
            "normalized_end": source.normalized_end,
            "location": source.location,
            "city": source.city,
            "event_type": source.event_type,
            "timeline_items": source.timeline_items,
            "dedup_reason": source.dedup_reason,
            "enrichments": source.enrichments,
            "confidence": source.confidence,
            "priority": source.priority,
            "notes": source.notes,
            "trip_name": source.trip_name,
            "trip_day_label": source.trip_day_label,
            "visibility_tier": source.visibility_tier,
        }

        for field, new_value in field_values.items():
            if getattr(target, field) != new_value:
                setattr(target, field, new_value)
                changed = True

        if not target.is_active:
            target.is_active = True
            changed = True

        desired_status = source.status or "pending"
        if target.status != "confirmed" and target.status != desired_status:
            target.status = desired_status
            changed = True

        return changed

    async def _expire_pending_reschedule_actions(
        self,
        family_id: UUID,
        event_ids: List[UUID],
    ) -> None:
        if not event_ids:
            return

        try:
            from ...conversation.pending_action import (
                ActionStatus,
                ActionType,
                PendingAction,
            )

            stale_actions_stmt = select(PendingAction).where(
                and_(
                    PendingAction.family_id == family_id,
                    PendingAction.action_type == ActionType.RESCHEDULE_EVENT.value,
                    PendingAction.status == ActionStatus.PENDING.value,
                )
            )
            stale_result = await self.session.execute(stale_actions_stmt)
            stale_ids = {str(eid) for eid in event_ids}
            for action in stale_result.scalars():
                event_id = (action.payload or {}).get("event_id")
                if event_id and str(event_id) in stale_ids:
                    action.status = ActionStatus.EXPIRED.value
        except Exception as e:
            logger.warning("Failed to expire stale pending actions: %s", e)

    async def _dismiss_open_associations(self, event_ids: List[UUID]) -> None:
        if not event_ids:
            return

        stmt = select(EventAssociation).where(
            and_(
                EventAssociation.source_event_id.in_(event_ids),
                EventAssociation.is_confirmed.is_(False),
                EventAssociation.is_dismissed.is_(False),
            )
        )
        result = await self.session.execute(stmt)
        for association in result.scalars().all():
            association.is_dismissed = True
            if not association.dismiss_reason:
                association.dismiss_reason = "auto: source event deactivated by diff_apply"

    async def _link_events_to_trips(
        self,
        curated_events: List[CuratedEvent],
    ) -> None:
        """Associate events that fall within a trip's date range."""
        trip_events = [
            e for e in curated_events
            if e.trip_id is not None
            and e.event_type in ("business_trip", "travel")
            and e.normalized_start
            and e.normalized_end
        ]

        if not trip_events:
            return

        for trip_event in trip_events:
            plan_start = datetime.combine(
                trip_event.normalized_start.date(),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            plan_end = datetime.combine(
                trip_event.normalized_end.date(),
                datetime.max.time(),
                tzinfo=timezone.utc,
            )

            for event in curated_events:
                if event.id == trip_event.id:
                    continue
                if event.trip_id is not None:
                    continue

                if (
                    event.normalized_start
                    and plan_start <= event.normalized_start <= plan_end
                ):
                    event.trip_id = trip_event.trip_id
                    logger.info(
                        f"Linked event '{event.title}' to trip '{trip_event.title}'"
                    )

        await self.session.flush()

    async def _populate_trip_context(
        self,
        curated_events: List[CuratedEvent],
    ) -> None:
        """Populate trip_name and trip_day_label for events linked to a trip."""
        trip_ids = {e.trip_id for e in curated_events if e.trip_id}
        if not trip_ids:
            return

        stmt = select(TripPlan).where(TripPlan.trip_id.in_(trip_ids))
        result = await self.session.execute(stmt)
        plans_by_id = {plan.trip_id: plan for plan in result.scalars().all()}

        for event in curated_events:
            if not event.trip_id:
                continue

            plan = plans_by_id.get(event.trip_id)
            if not plan:
                continue

            trip_name = (plan.trip_name or "").strip() or f"{plan.destination}\u884c\u7a0b"
            event.trip_name = trip_name[:200]

            if event.normalized_start and plan.start_date:
                event_date = event.normalized_start.date()
                day_num = (event_date - plan.start_date).days + 1
                if day_num >= 1:
                    event.trip_day_label = f"{trip_name} \u00b7 Day {day_num}"[:100]
                else:
                    event.trip_day_label = trip_name[:100]

        await self.session.flush()

    async def _store_associations(
        self,
        associations: List[EventAssociation],
    ) -> None:
        """Store associations via key-based upsert; keep user feedback stable."""
        if not associations:
            return

        valid_associations: List[EventAssociation] = []
        dropped_missing_source = 0
        for assoc in associations:
            if not assoc.source_event_id:
                dropped_missing_source += 1
                logger.warning(
                    "Dropping association without source_event_id: title=%r target=%r type=%r",
                    assoc.title,
                    assoc.target_id,
                    assoc.target_type,
                )
                continue
            valid_associations.append(assoc)

        if dropped_missing_source:
            logger.warning(
                "Dropped %d association(s) missing source_event_id before upsert",
                dropped_missing_source,
            )

        if not valid_associations:
            return

        source_ids = {assoc.source_event_id for assoc in valid_associations if assoc.source_event_id}
        if not source_ids:
            return

        source_event_stmt = select(CuratedEvent.id).where(CuratedEvent.id.in_(source_ids))
        source_event_result = await self.session.execute(source_event_stmt)
        existing_source_ids = {row[0] for row in source_event_result.all()}
        if not existing_source_ids:
            logger.warning("Skipping association upsert: none of %d source events exist", len(source_ids))
            return

        associations = [
            assoc for assoc in valid_associations
            if assoc.source_event_id in existing_source_ids
        ]
        dropped_missing_source_event = len(valid_associations) - len(associations)
        if dropped_missing_source_event:
            logger.warning(
                "Dropped %d association(s) referencing non-existent source events",
                dropped_missing_source_event,
            )

        if not associations:
            return

        # Stamp fingerprints on all incoming associations.
        for assoc in associations:
            self._stamp_association_fingerprints(assoc)

        source_ids = {assoc.source_event_id for assoc in associations if assoc.source_event_id}
        existing_stmt = select(EventAssociation).where(
            EventAssociation.source_event_id.in_(source_ids)
        )
        existing_result = await self.session.execute(existing_stmt)
        existing_list = existing_result.scalars().all()

        existing_by_key: Dict[tuple, List[EventAssociation]] = {}
        existing_by_stable_key: Dict[str, EventAssociation] = {}
        for existing in existing_list:
            key = self._association_identity_key(existing)
            existing_by_key.setdefault(key, []).append(existing)
            if existing.stable_key:
                existing_by_stable_key[existing.stable_key] = existing

        incoming_by_key: Dict[tuple, EventAssociation] = {}
        for assoc in associations:
            key = self._association_identity_key(assoc)
            previous = incoming_by_key.get(key)
            if previous is None or (assoc.confidence or 0) > (previous.confidence or 0):
                incoming_by_key[key] = assoc

        created = 0
        updated = 0
        skipped = 0
        auto_dismissed = 0
        matched_keys: Set[tuple] = set()

        for key, incoming in incoming_by_key.items():
            existing_candidates = existing_by_key.get(key, [])
            if not existing_candidates:
                self.session.add(incoming)
                created += 1
                continue

            existing = existing_candidates[0]
            matched_keys.add(key)

            # Collapse duplicate rows for the same identity key.
            for duplicate in existing_candidates[1:]:
                if duplicate.is_confirmed or duplicate.is_dismissed:
                    continue
                duplicate.is_dismissed = True
                duplicate.dismiss_reason = "auto: duplicate association suppressed by diff_apply"
                auto_dismissed += 1

            # Preserve explicit dismiss feedback unless user later confirms.
            if existing.is_dismissed and not existing.is_confirmed:
                continue

            # Fingerprint short-circuit: skip if semantic content unchanged.
            if (
                existing.semantic_fingerprint
                and incoming.semantic_fingerprint
                and existing.semantic_fingerprint == incoming.semantic_fingerprint
            ):
                skipped += 1
                continue

            if self._apply_association_patch(existing, incoming):
                existing.stable_key = incoming.stable_key
                existing.source_fingerprint = incoming.source_fingerprint
                existing.semantic_fingerprint = incoming.semantic_fingerprint
                updated += 1

        for key, existing_candidates in existing_by_key.items():
            if key in matched_keys:
                continue
            for existing in existing_candidates:
                if existing.is_confirmed or existing.is_dismissed:
                    continue
                existing.is_dismissed = True
                existing.dismiss_reason = "auto: not suggested in latest curation"
                auto_dismissed += 1

        await self.session.flush()
        logger.info(
            "DiffApply associations: %d created, %d updated, "
            "%d skipped (fingerprint match), %d auto-dismissed",
            created,
            updated,
            skipped,
            auto_dismissed,
        )

    @staticmethod
    def _association_identity_key(assoc: EventAssociation) -> tuple:
        target_ref = (assoc.target_id or "").strip()
        if not target_ref:
            target_ref = (assoc.title or "").strip().lower()
        return (
            str(assoc.source_event_id),
            target_ref,
            (assoc.target_type or "").strip().lower(),
            (assoc.association_type or "").strip().lower(),
        )

    @staticmethod
    def _apply_association_patch(
        target: EventAssociation,
        source: EventAssociation,
    ) -> bool:
        changed = False
        fields = (
            "family_id",
            "target_id",
            "target_type",
            "association_type",
            "title",
            "reason",
            "priority",
            "confidence",
        )
        for field in fields:
            new_value = getattr(source, field)
            if getattr(target, field) != new_value:
                setattr(target, field, new_value)
                changed = True
        return changed

    async def _mark_consumed_memories(
        self,
        family_id: UUID,
        curated_events: List[CuratedEvent],
    ) -> None:
        """Mark SCHEDULE memories that have been curated into events as ARCHIVED."""
        all_original_ids: List[str] = []
        for event in curated_events:
            all_original_ids.extend(event.original_event_ids or [])

        if not all_original_ids:
            return

        from uuid import UUID as PyUUID

        valid_uuids = []
        for oid in all_original_ids:
            try:
                valid_uuids.append(PyUUID(oid))
            except (ValueError, TypeError):
                continue

        if not valid_uuids:
            return

        update_stmt = (
            update(ConversationMemory)
            .where(
                and_(
                    ConversationMemory.family_id == family_id,
                    ConversationMemory.id.in_(valid_uuids),
                    ConversationMemory.memory_type == MemoryType.SCHEDULE.value,
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                )
            )
            .values(status=MemoryStatus.ARCHIVED.value)
        )
        result = await self.session.execute(update_stmt)
        if result.rowcount > 0:
            logger.info(
                f"Archived {result.rowcount} consumed SCHEDULE memories for family {family_id}"
            )

    async def upsert_curated_event(
        self,
        family_id: UUID,
        trip_id: UUID,
        defaults: dict,
    ) -> Tuple[CuratedEvent, bool]:
        """Create or update a CuratedEvent matched by family_id + trip_id.

        If a matching active CuratedEvent with the given trip_id exists,
        update its fields from ``defaults``. Otherwise create a new one.

        Returns:
            (curated_event, created) — the event and whether it was newly created.
        """
        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.is_active.is_(True),
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            for key, value in defaults.items():
                if hasattr(existing, key) and key not in ("id", "family_id", "trip_id"):
                    setattr(existing, key, value)
            self._stamp_event_fingerprints(existing)
            await self.session.flush()
            return existing, False

        curated = CuratedEvent(family_id=family_id, trip_id=trip_id, **defaults)
        self._stamp_event_fingerprints(curated)
        self.session.add(curated)
        await self.session.flush()
        return curated, True
