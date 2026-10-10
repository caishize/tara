"""
Curation Service - AI-powered event deduplication and association discovery.

This service acts like a real secretary:
1. Collects events from multiple sources (travel, calendar, extracted schedules)
2. Uses LLM to semantically deduplicate and normalize events
3. Discovers meaningful associations between events and people/memories
4. Stores curated results for display in timeline and insight graph

The service is split across several mixin modules for maintainability:
- collector.py          -- raw event collection from DB
- dedup_service.py      -- LLM dedup, decompose, fallback heuristic
- association_service.py -- LLM + rule-engine association discovery
- storage_service.py    -- persist curated events and associations
- conflict_resolver.py  -- conflict detection and auto-resolution
- query_service.py      -- read-path: timeline and graph queries
- prompts.py            -- LLM prompt constants
- data_models.py        -- CurationResult, RawEvent data classes
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

from ....core.llm import openai_adapter
from ....config.logging import get_logger
from ....core.utils.timezone import (
    local_today,
    set_active_timezone,
    reset_active_timezone,
    utc_now,
)
from ..models import CuratedEvent, EventAssociation, CurationJob
from ...memory.models import ConversationMemory, MemoryType, MemoryStatus

from .data_models import CurationResult, RawEvent
from .collector import CurationCollectorMixin
from .dedup_service import CurationDedupMixin
from .association_service import CurationAssociationMixin
from .storage_service import CurationStorageMixin
from .conflict_resolver import CurationConflictMixin
from .query_service import CurationQueryMixin
from .rule_engine import RuleBasedAssociationEngine
from .context_enricher import ContextEnricher
from .curation_enricher import CurationEnricher
from .memory_engine import MemoryEngine
from .family_settings import get_family_curation_settings
from .family_preference_repository import FamilyPreferenceRepository
from .storage_service import compute_visibility_tier

logger = get_logger(__name__)


class SecretaryCurationService(
    CurationCollectorMixin,
    CurationDedupMixin,
    CurationAssociationMixin,
    CurationStorageMixin,
    CurationConflictMixin,
    CurationQueryMixin,
):
    """AI secretary curation service -- uses LLM for semantic dedup and association discovery."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = openai_adapter
        self.rule_engine = RuleBasedAssociationEngine(session)
        self.memory_engine = MemoryEngine(session)
        self.context_enricher = ContextEnricher(session, self.memory_engine)
        self._pref_repo = FamilyPreferenceRepository(session)
        self._last_collection_source_health: Dict[str, bool] = {}

    # --- Main Entry Points ---

    async def curate_family_events(
        self,
        family_id: UUID,
        date_range: Tuple[date, date],
        trigger_type: str = "manual",
        user_id: Optional[UUID] = None,
        existing_job_id: Optional[UUID] = None,
    ) -> CurationResult:
        """主整理流程。"""
        start_date, end_date = date_range
        tz_token = None

        job: Optional[CurationJob] = None
        if existing_job_id is not None:
            existing_stmt = select(CurationJob).where(
                and_(
                    CurationJob.id == existing_job_id,
                    CurationJob.family_id == family_id,
                )
            )
            existing_result = await self.session.execute(existing_stmt)
            job = existing_result.scalar_one_or_none()
            if job is None:
                logger.warning(
                    "Requested existing curation job %s not found for family %s; "
                    "creating a new job instead.",
                    existing_job_id,
                    family_id,
                )

        if job is None:
            job = CurationJob(
                family_id=family_id,
                trigger_type=trigger_type,
                status="running",
                date_range_start=start_date,
                date_range_end=end_date,
                started_at=utc_now(),
            )
            self.session.add(job)
        else:
            job.trigger_type = trigger_type
            job.status = "running"
            job.date_range_start = start_date
            job.date_range_end = end_date
            job.started_at = utc_now()
            job.completed_at = None
            job.error_message = None
            job.events_processed = 0
            job.events_curated = 0
            job.associations_created = 0

        await self.session.flush()

        try:
            async with self.session.begin_nested():
                family_settings = await get_family_curation_settings(self.session, family_id)
            tz_token = set_active_timezone(family_settings.timezone)
        except Exception as tz_err:
            logger.warning(
                "Failed to resolve family timezone for %s, using default: %s",
                family_id,
                tz_err,
            )

        # Load learned family preferences for personalized curation
        family_prefs = None
        try:
            async with self.session.begin_nested():
                family_prefs = await self._pref_repo.get_or_create_default(family_id)
        except Exception as pref_err:
            logger.debug(
                "Could not load FamilyPreference for %s: %s",
                family_id,
                pref_err,
            )

        try:
            raw_events = await self._collect_raw_events(family_id, date_range)
            source_health = getattr(self, "_last_collection_source_health", {}) or {}
            failed_sources = sorted(
                source for source, ok in source_health.items() if not ok
            )
            if failed_sources:
                logger.warning(
                    "Raw event collection had source failures for family %s: %s",
                    family_id,
                    ",".join(failed_sources),
                )
            job.events_processed = len(raw_events)

            if not raw_events:
                job.status = "completed"
                job.completed_at = utc_now()
                await self.session.commit()
                return CurationResult(
                    job_id=job.id,
                    events_processed=0,
                    events_curated=0,
                    associations_created=0,
                    unconfirmed_items=[],
                )

            curated_events, unconfirmed_items = await self._semantic_dedup_and_normalize(
                family_id, raw_events, user_id, family_prefs=family_prefs,
            )
            curated_events = await self._back_propagate_trip_merges(
                family_id, curated_events
            )
            curated_events = self._collapse_day_events_into_trips(curated_events)
            curated_events = self._decompose_multi_day_events(curated_events)
            curated_events = self._dedup_decomposed_events(curated_events)

            job.events_curated = len(curated_events)

            used_fallback = any(
                (e.dedup_reason or "").startswith("LLM\u5904\u7406\u5931\u8d25")
                for e in curated_events
            )
            if used_fallback:
                job.error_message = (
                    "LLM dedup failed; fell back to heuristic merge. "
                    "Results may have lower quality."
                )
            if failed_sources:
                source_fail_msg = (
                    "Partial source collection failed: " + ",".join(failed_sources)
                )
                if job.error_message:
                    job.error_message = f"{job.error_message} | {source_fail_msg}"
                else:
                    job.error_message = source_fail_msg

            curated_events = await self._store_curated_events(
                family_id,
                curated_events,
                date_range,
                failed_sources=failed_sources,
            )
            await self._mark_consumed_memories(family_id, curated_events)

            conflicts_detected = await self._detect_and_resolve_conflicts(
                family_id, curated_events, user_id,
                family_prefs=family_prefs,
            )

            associations = await self._discover_associations(
                family_id, curated_events, date_range,
                family_prefs=family_prefs,
            )
            job.associations_created = len(associations)

            await self._store_associations(associations)

            # Phase 2: Upgrade high-confidence associations to PendingAction drafts.
            # Flush first so association IDs are assigned before we reference them.
            try:
                await self.session.flush()
                actions_created = 0
                for event in curated_events:
                    event_user_id = event.user_id or user_id
                    if event_user_id is None:
                        continue
                    event_assocs = [
                        a for a in associations
                        if a.source_event_id == event.id
                    ]
                    if event_assocs:
                        actions_created += await self._generate_pending_actions_for_associations(
                            event_assocs, event, event_user_id, family_id,
                        )
                if actions_created:
                    logger.info(
                        "Created %d suggest_* PendingAction(s) for family %s",
                        actions_created, family_id,
                    )
            except Exception as exc:
                logger.warning(
                    "PendingAction generation skipped for family %s: %s",
                    family_id, exc,
                )

            # PLAN-002: Pre-generate warm content for enriched events via Haiku.
            # Runs after store + flush so event IDs are stable.  Each call is
            # individually guarded so a single LLM failure doesn't abort the job.
            if user_id and curated_events:
                enricher = CurationEnricher(
                    db=self.session,
                    user_id=user_id,
                    family_id=family_id,
                )
                for event in curated_events:
                    try:
                        await enricher.enrich(event)
                    except Exception as exc:
                        logger.warning(
                            "Enrichment failed for event %s: %s", event.id, exc,
                        )

            job.status = "completed"
            job.completed_at = utc_now()
            await self.session.commit()

            # Publish EventCurated for each curated event
            try:
                from ....core.events import get_event_bus
                from ....core.events.domain_events import EventCurated
                event_bus = get_event_bus()
                for ce in curated_events:
                    await event_bus.publish(EventCurated(
                        event_id=ce.id,
                        family_id=family_id,
                        event_type=ce.event_type or "",
                        priority=getattr(ce, "priority", "") or "",
                        title=ce.title or "",
                    ))
            except Exception as e:
                logger.warning("Failed to publish EventCurated events: %s", e)

            logger.info(
                f"Curation completed for family {family_id}: "
                f"{job.events_processed} processed, {job.events_curated} curated, "
                f"{job.associations_created} associations"
            )

            return CurationResult(
                job_id=job.id,
                events_processed=job.events_processed,
                events_curated=job.events_curated,
                associations_created=job.associations_created,
                unconfirmed_items=unconfirmed_items,
                conflicts_detected=conflicts_detected,
            )

        except Exception as e:
            logger.error(f"Curation failed for family {family_id}: {e}")
            await self.session.rollback()
            job.status = "failed"
            job.error_message = str(e)[:2000]
            job.completed_at = utc_now()
            try:
                self.session.add(job)
                await self.session.commit()
            except Exception as commit_err:
                logger.error(f"Failed to record curation failure: {commit_err}")
                await self.session.rollback()
            raise
        finally:
            reset_active_timezone(tz_token)

    async def trigger_curation(
        self,
        family_id: UUID,
        trigger_type: str = "manual",
        date_range: Optional[Tuple[date, date]] = None,
        user_id: Optional[UUID] = None,
        existing_job_id: Optional[UUID] = None,
    ) -> CurationJob:
        """触发整理任务。"""
        if date_range is None:
            family_settings = await get_family_curation_settings(self.session, family_id)
            start_date = local_today(family_settings.timezone)
            end_date = start_date + timedelta(days=family_settings.curation_days_ahead)
            date_range = (start_date, end_date)

        result = await self.curate_family_events(
            family_id=family_id,
            date_range=date_range,
            trigger_type=trigger_type,
            user_id=user_id,
            existing_job_id=existing_job_id,
        )

        job_stmt = select(CurationJob).where(CurationJob.id == result.job_id)
        job_result = await self.session.execute(job_stmt)
        return job_result.scalar_one()

    # --- Real-time Mini Curation ---

    async def mini_curate(
        self,
        family_id: UUID,
        user_id: UUID,
        title: str,
        event_type: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        source_type: str = "calendar",
        source_id: Optional[str] = None,
    ) -> Tuple[Optional[CuratedEvent], List[EventAssociation]]:
        """Synchronous mini-curation for a single new event.

        Unlike full curate_family_events(), this:
        - Skips LLM dedup (too slow for synchronous use)
        - Uses heuristic title/time overlap to merge with existing events
        - Creates a CuratedEvent immediately
        - Runs sync rule-engine probe for high-confidence associations
        - Fires full association discovery asynchronously

        Returns:
            Tuple of (curated_event, sync_hints) where sync_hints are
            strongly_recommend associations discovered synchronously.
        """
        # Three-level dedup matching:
        # Level 1: exact title + overlapping time (<5ms)
        # Level 2: semantic fingerprint match (<10ms)
        # Level 3: city + date unique match (<10ms)
        since = start_time - timedelta(hours=2)
        until = (end_time or start_time) + timedelta(hours=2)

        # Level 1: Exact title match
        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.title == title,
                CuratedEvent.normalized_start <= until,
                CuratedEvent.normalized_end >= since,
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        # Level 2: Semantic fingerprint match (works with or without location)
        if existing is None:
            from .storage_service import compute_mini_curate_fingerprint
            fp = compute_mini_curate_fingerprint(title, location, start_time, event_type)
            if fp:
                stmt2 = select(CuratedEvent).where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.semantic_fingerprint == fp,
                        CuratedEvent.normalized_start.between(since, until),
                    )
                ).limit(1)
                result2 = await self.session.execute(stmt2)
                existing = result2.scalar_one_or_none()

        # Level 3: City + date unique match (requires location)
        if existing is None and location:
            from .storage_service import extract_city
            city = extract_city(location)
            if city:
                stmt3 = select(CuratedEvent).where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.city == city,
                        CuratedEvent.normalized_start.between(since, until),
                        CuratedEvent.is_active.is_(True),
                    )
                ).limit(2)
                result3 = await self.session.execute(stmt3)
                candidates = list(result3.scalars().all())
                if len(candidates) == 1:
                    existing = candidates[0]  # Unique match

        if existing:
            # Merge: extend time range if needed
            if start_time < existing.normalized_start:
                existing.normalized_start = start_time
            if end_time and (not existing.normalized_end or end_time > existing.normalized_end):
                existing.normalized_end = end_time
            if source_id and source_id not in (existing.original_event_ids or []):
                existing.original_event_ids = (existing.original_event_ids or []) + [source_id]
                flag_modified(existing, "original_event_ids")
            await self.session.commit()
            logger.info("mini_curate: merged into existing event '%s'", title)
            return existing, []

        # Create new curated event
        from .storage_service import compute_mini_curate_fingerprint, extract_city

        tier = compute_visibility_tier({
            "normalized_start": start_time,
            "event_type": event_type,
            "priority": "normal",
        })
        curated = CuratedEvent(
            family_id=family_id,
            user_id=user_id,
            original_event_ids=[source_id] if source_id else [],
            source_types=[source_type],
            title=title,
            normalized_start=start_time,
            normalized_end=end_time,
            location=location,
            city=extract_city(location) if location else None,
            event_type=event_type,
            timeline_items=[],
            dedup_reason="mini_curate: 即时策展",
            confidence=0.9,
            visibility_tier=tier,
            semantic_fingerprint=compute_mini_curate_fingerprint(
                title, location, start_time, event_type
            ),
        )
        self.session.add(curated)
        await self.session.commit()
        await self.session.refresh(curated)

        logger.info("mini_curate: created new curated event '%s'", title)

        # 1. Synchronous: pure rule engine probe (4 SQL queries, <100ms)
        sync_hints: List[EventAssociation] = []
        try:
            all_associations = await self.rule_engine.discover_associations(
                family_id, curated
            )
            sync_hints = [
                a for a in all_associations
                if a.priority == "strongly_recommend"
            ]
            if sync_hints:
                for assoc in sync_hints:
                    self.session.add(assoc)
                await self.session.commit()
        except Exception:
            logger.debug(
                "Sync rule-engine probe failed, falling back to async-only",
                exc_info=True,
            )
            sync_hints = []

        # E3: Cache top association hints for Fast Path L1 injection
        if sync_hints:
            await self._cache_association_hints(
                family_id=family_id,
                hints=[
                    {
                        "title": h.title,
                        "reason": h.reason,
                        "priority": h.priority,
                        "target_name": h.target_id or "",
                    }
                    for h in sync_hints[:3]
                ],
            )

        # 2. Async: full association discovery including LLM (existing)
        try:
            from ..tasks import discover_associations_for_event_task
            discover_associations_for_event_task.delay(
                str(curated.id), str(family_id)
            )
        except Exception as e:
            logger.debug("Async association discovery not available: %s", e)

        return curated, sync_hints

    # --- Association Actions ---

    async def dismiss_association(
        self,
        association_id: str,
        family_id: UUID,
        correction: Optional[str] = None,
    ) -> bool:
        """Dismiss an association."""
        assoc_uuid = self._parse_uuid(association_id)
        if assoc_uuid is None:
            return False

        stmt = (
            select(EventAssociation)
            .where(
                and_(
                    EventAssociation.id == assoc_uuid,
                    EventAssociation.family_id == family_id,
                )
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        association = result.scalar_one_or_none()
        if not association:
            return False

        association.is_dismissed = True
        if correction:
            association.dismiss_reason = correction

        # Write preference signal (E2: replaces direct memory weight manipulation)
        source_event = await self.session.get(
            CuratedEvent, association.source_event_id,
        )
        signal_user_id = (
            source_event.user_id if source_event and source_event.user_id else None
        )
        if signal_user_id is not None:
            await self._record_preference_signal(
                user_id=signal_user_id,
                family_id=family_id,
                signal_type="dismiss",
                source_type="association",
                source_id=assoc_uuid,
                association=association,
                source_event=source_event,
            )

        # Record feedback for personalization learning
        await self._record_association_feedback(
            family_id, association.association_type, "dismiss"
        )

        try:
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            logger.warning(
                "Association %s was deleted by concurrent curation run",
                association_id,
            )
            return False
        return True

    async def confirm_association(
        self,
        association_id: str,
        family_id: UUID,
        scheduled_start: Optional[datetime] = None,
        create_placeholder: bool = True,
    ) -> bool:
        """Confirm an association, optionally creating a placeholder event (E8)."""
        assoc_uuid = self._parse_uuid(association_id)
        if assoc_uuid is None:
            return False

        stmt = (
            select(EventAssociation)
            .where(
                and_(
                    EventAssociation.id == assoc_uuid,
                    EventAssociation.family_id == family_id,
                )
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        association = result.scalar_one_or_none()
        if not association:
            return False

        association.is_confirmed = True

        source_event = await self.session.get(CuratedEvent, association.source_event_id)

        # Write preference signal for positive training data (E2)
        signal_user_id = (
            source_event.user_id if source_event and source_event.user_id else None
        )
        if signal_user_id is not None:
            await self._record_preference_signal(
                user_id=signal_user_id,
                family_id=family_id,
                signal_type="confirm",
                source_type="association",
                source_id=assoc_uuid,
                association=association,
                source_event=source_event,
            )

            # E2: Decay confidence of preference rules that were overridden
            if source_event is not None:
                await self.on_association_confirmed(
                    signal_user_id, source_event, association,
                )

        if (
            source_event
            and source_event.trip_id
            and source_event.event_type in ("business_trip", "travel")
        ):
            appointment_start = scheduled_start or source_event.normalized_start
            new_event = CuratedEvent(
                family_id=family_id,
                user_id=source_event.user_id,
                trip_id=source_event.trip_id,
                original_event_ids=[],
                source_types=["association_confirmed"],
                title=association.title,
                normalized_start=appointment_start,
                normalized_end=appointment_start,
                location=source_event.location,
                event_type="appointment",
                status="pending",
                confidence=association.confidence or 0.8,
                notes=association.reason,
            )
            self.session.add(new_event)
            logger.info(
                "Created appointment '%s' at %s from confirmed "
                "association on trip '%s'",
                association.title,
                appointment_start,
                source_event.title,
            )
        elif (
            create_placeholder
            and association.priority == "strongly_recommend"
            and association.source_event_id
        ):
            # E8: Create placeholder event for strongly_recommend confirmed
            # associations that are not trip-related appointments
            await self._create_placeholder_event(association, family_id)

        if association.target_type == "memory" and association.target_id:
            await self._mark_intent_fulfilled(association.target_id)

        # Record feedback for personalization learning
        await self._record_association_feedback(
            family_id, association.association_type, "confirm"
        )

        try:
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            logger.warning(
                "Association %s was deleted by concurrent curation run",
                association_id,
            )
            return False
        return True

    async def _create_placeholder_event(
        self,
        association: EventAssociation,
        family_id: UUID,
    ) -> None:
        """Create a placeholder event from a confirmed association (E8).

        Placeholder events have status='placeholder' and source_types
        ['association_confirmed']. They serve as visual reminders on the
        timeline (rendered with a dashed border on mobile) and can be
        promoted to full events by the user later.

        Uses _find_suitable_gap() to place the event in a free time slot
        rather than hardcoding at the source event's start time.
        """
        try:
            # C5: Idempotency check — skip if a matching placeholder already exists
            existing_stmt = select(CuratedEvent).where(
                and_(
                    CuratedEvent.status == "placeholder",
                    CuratedEvent.title == association.title,
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.source_types.contains(["association_confirmed"]),
                    CuratedEvent.original_event_ids.contains(
                        [str(association.source_event_id)]
                    ),
                )
            ).limit(1)
            existing_result = await self.session.execute(existing_stmt)
            if existing_result.scalar_one_or_none() is not None:
                logger.debug(
                    "Placeholder event already exists for association %s, skipping",
                    association.id,
                )
                return

            source_event = await self.session.get(
                CuratedEvent, association.source_event_id,
            )
            if source_event is None or not source_event.normalized_start:
                return

            # Try to find a suitable gap within the source event's day
            duration_minutes = 60
            day_start = source_event.normalized_start.replace(
                hour=9, minute=0, second=0, microsecond=0,
            )
            day_end = source_event.normalized_start.replace(
                hour=21, minute=0, second=0, microsecond=0,
            )

            gap = await self._find_suitable_gap(
                family_id=family_id,
                date_range=(day_start, day_end),
                duration_minutes=duration_minutes,
            )

            if gap is not None:
                placeholder_start = gap["start"]
                placeholder_end = gap["end"]
            else:
                # Fallback: use the source event's start time
                placeholder_start = source_event.normalized_start
                placeholder_end = placeholder_start + timedelta(minutes=duration_minutes)

            placeholder = CuratedEvent(
                family_id=family_id,
                user_id=source_event.user_id,
                title=association.title,
                normalized_start=placeholder_start,
                normalized_end=placeholder_end,
                status="placeholder",
                event_type="preparation",
                priority="normal",
                source_types=["association_confirmed"],
                original_event_ids=[str(source_event.id)],
                confidence=association.confidence or 0.8,
                notes=f"由关联确认创建：{association.reason}",
                visibility_tier="standard",
            )
            self.session.add(placeholder)
            logger.info(
                "Created placeholder event for confirmed association %s at %s",
                association.id,
                placeholder_start,
            )
        except Exception as exc:
            logger.warning("Failed to create placeholder event: %s", exc)

    # Default meal protection windows for gap finding.
    # These are conservative defaults (wider than exact meal times to be safe);
    # the orchestrator uses family-specific inferred_meal_windows from
    # FamilyPreference for more precise scheduling.
    _PROTECTED_MEAL_WINDOWS = [
        (11, 30, 13, 30),  # Lunch window (wider than exact to be safe)
        (17, 30, 19, 30),  # Dinner window
    ]

    async def _find_suitable_gap(
        self,
        family_id: UUID,
        date_range: tuple,
        duration_minutes: int = 60,
    ) -> Optional[dict]:
        """Find a free time slot within the date range (E8).

        Logic:
        1. Query CuratedEvents for this family within the date_range
        2. Look for gaps between consecutive events >= duration_minutes
        3. Skip meal times (conservative default windows; orchestrator uses
           family-specific inferred_meal_windows for precise scheduling)
        4. Prefer gaps during working hours (9:00-18:00)
        5. Return {"start": gap_start, "end": gap_end} or None
        """
        range_start, range_end = date_range
        duration = timedelta(minutes=duration_minutes)

        stmt = (
            select(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.normalized_start >= range_start,
                    CuratedEvent.normalized_start <= range_end,
                )
            )
            .order_by(CuratedEvent.normalized_start)
        )
        result = await self.session.execute(stmt)
        events = list(result.scalars().all())

        meal_windows = self._PROTECTED_MEAL_WINDOWS

        def _is_working_hours(dt: datetime) -> bool:
            """Check if the time is within working hours (9:00-18:00)."""
            return 9 <= dt.hour < 18

        def _gap_overlaps_meal(gap_start: datetime, gap_end: datetime) -> bool:
            """Check if the proposed gap overlaps with any protected meal window."""
            for start_h, start_m, end_h, end_m in meal_windows:
                meal_start = gap_start.replace(
                    hour=start_h, minute=start_m, second=0, microsecond=0,
                )
                meal_end = gap_start.replace(
                    hour=end_h, minute=end_m, second=0, microsecond=0,
                )
                if gap_start < meal_end and gap_end > meal_start:
                    return True
            return False

        def _shift_past_meal(candidate_start: datetime) -> Optional[datetime]:
            """Return a shifted start time past the overlapping meal window, or None."""
            for start_h, start_m, end_h, end_m in meal_windows:
                if (start_h < candidate_start.hour < end_h) or (
                    candidate_start.hour == start_h and candidate_start.minute >= start_m
                ) or (
                    candidate_start.hour == end_h and candidate_start.minute < end_m
                ):
                    return candidate_start.replace(
                        hour=end_h, minute=end_m, second=0, microsecond=0,
                    )
            return None

        # Build list of candidate gaps
        boundaries: List[tuple] = []

        # Gap before first event
        if events:
            first_start = events[0].normalized_start
            if first_start and first_start > range_start:
                boundaries.append((range_start, first_start))
        else:
            # No events at all: the entire range is free
            boundaries.append((range_start, range_end))

        # Gaps between consecutive events
        for i in range(len(events) - 1):
            current_end = events[i].normalized_end or events[i].normalized_start
            next_start = events[i + 1].normalized_start
            if current_end and next_start and next_start > current_end:
                boundaries.append((current_end, next_start))

        # Gap after last event
        if events:
            last_end = events[-1].normalized_end or events[-1].normalized_start
            if last_end and last_end < range_end:
                boundaries.append((last_end, range_end))

        # Score and pick the best gap
        best_gap: Optional[dict] = None
        best_score: int = -1

        for gap_start, gap_end in boundaries:
            available = gap_end - gap_start
            if available < duration:
                continue

            candidate_start = gap_start
            candidate_end = candidate_start + duration

            # Skip if it overlaps meal times
            if _gap_overlaps_meal(candidate_start, candidate_end):
                # Try shifting past meal time
                shifted = _shift_past_meal(candidate_start)
                if shifted is not None:
                    candidate_start = shifted
                candidate_end = candidate_start + duration
                if candidate_end > gap_end:
                    continue
                if _gap_overlaps_meal(candidate_start, candidate_end):
                    continue

            # Score: prefer working hours
            score = 2 if _is_working_hours(candidate_start) else 1

            if score > best_score:
                best_score = score
                best_gap = {"start": candidate_start, "end": candidate_end}

        return best_gap

    async def _mark_intent_fulfilled(self, target_id: str) -> None:
        """Mark a social intent as fulfilled when its association is confirmed."""
        from ..models import SocialIntent

        target_uuid = self._parse_uuid(target_id)
        if target_uuid is None:
            return

        intent = await self.session.get(SocialIntent, target_uuid)
        if intent and intent.is_active:
            intent.mark_fulfilled()
            logger.info("Marked SocialIntent %s as fulfilled", target_uuid)

            if intent.source_memory_id:
                memory = await self.session.get(
                    ConversationMemory, intent.source_memory_id
                )
                if memory and memory.status == MemoryStatus.ACTIVE.value:
                    memory.status = MemoryStatus.ARCHIVED.value
                    logger.info(
                        "Archived source memory %s for fulfilled intent",
                        intent.source_memory_id,
                    )
            return

        memory = await self.session.get(ConversationMemory, target_uuid)
        if memory and memory.status == MemoryStatus.ACTIVE.value:
            memory.status = MemoryStatus.ARCHIVED.value
            logger.info(
                "Archived memory %s (confirmed association fulfilled)",
                target_uuid,
            )

    async def _cache_association_hints(
        self,
        family_id: UUID,
        hints: list,
    ) -> None:
        """Cache association hints for ContextAssembler L1 injection (E3).

        Writes a compact JSON payload to Redis so the Fast Path can
        incorporate association context without any additional LLM calls.
        Key: ``assoc:hints:latest:{family_id}``
        TTL is 1 hour -- hints are refreshed on every mini_curate.
        """
        if not hints:
            return
        try:
            import json as _json

            from ....core.cache import redis_client

            client = redis_client.client
            if client is None:
                return

            payload = _json.dumps(hints, ensure_ascii=False)

            # Always write to the family-latest key so L1 can read without
            # knowing the location.
            latest_key = f"assoc:hints:latest:{family_id}"
            await client.set(latest_key, payload, ex=3600)

        except Exception as exc:
            logger.warning("Failed to cache association hints: %s", exc)

    async def _record_association_feedback(
        self, family_id: UUID, association_type: str, action: str,
    ) -> None:
        """Record association feedback for priority weight learning."""
        try:
            from ....core.cache import redis_client
            client = redis_client.client
            if client is None:
                return
            key = f"curation:feedback_stats:{family_id}"
            field = f"{association_type}:{action}_count"
            await client.hincrby(key, field, 1)
        except Exception:
            logger.debug("Failed to record association feedback", exc_info=True)

    async def _record_preference_signal(
        self,
        user_id: UUID,
        family_id: UUID,
        signal_type: str,
        source_type: str,
        source_id: UUID,
        association: "EventAssociation",
        source_event: Optional["CuratedEvent"] = None,
    ) -> None:
        """Record a preference signal for later batch extraction (E2)."""
        try:
            from ..models import PreferenceSignal

            event_type = ""
            location = None
            if source_event is not None:
                event_type = getattr(source_event, "event_type", "") or ""
                location = getattr(source_event, "location", None)

            person_id = None
            if association.target_type == "person" and association.target_id:
                person_id = association.target_id

            signal = PreferenceSignal(
                user_id=user_id,
                family_id=family_id,
                signal_type=signal_type,
                source_type=source_type,
                source_id=source_id,
                source_context={
                    "event_type": event_type,
                    "suggestion_type": association.association_type,
                    "person_id": person_id,
                    "location": location,
                },
                category_key=f"{event_type}:{association.association_type}",
            )
            self.session.add(signal)
        except Exception as exc:
            logger.warning("Failed to record preference signal: %s", exc)

    async def _update_association(
        self,
        association_id: str,
        family_id: UUID,
        is_dismissed: Optional[bool] = None,
        is_confirmed: Optional[bool] = None,
    ) -> bool:
        """Update association status (dismiss or confirm)."""
        assoc_uuid = self._parse_uuid(association_id)
        if assoc_uuid is None:
            return False

        stmt = select(EventAssociation).where(
            and_(
                EventAssociation.id == assoc_uuid,
                EventAssociation.family_id == family_id,
            )
        )
        result = await self.session.execute(stmt)
        association = result.scalar_one_or_none()

        if not association:
            return False

        if is_dismissed is not None:
            association.is_dismissed = is_dismissed
        if is_confirmed is not None:
            association.is_confirmed = is_confirmed

        await self.session.commit()
        return True

    async def _back_propagate_trip_merges(
        self,
        family_id: UUID,
        curated_events: List[CuratedEvent],
    ) -> List[CuratedEvent]:
        """Propagate semantic trip merges back to ``trips`` rows."""
        if not curated_events:
            return curated_events

        from ...trip.models.trip_plan import TripPlan
        from ...trip.services.trip_service import TripService
        from .dedup_service import _pick_best_trip

        trip_service = TripService(self.session)
        alias_map: Dict[UUID, UUID] = {}
        merged_total = 0

        for event in curated_events:
            if "trip_plan" not in set(event.source_types or []):
                continue

            candidate_trip_ids: Set[UUID] = set()
            for oid in event.original_event_ids or []:
                try:
                    candidate_trip_ids.add(UUID(str(oid)))
                except (TypeError, ValueError):
                    continue

            if len(candidate_trip_ids) < 2:
                continue

            stmt = select(TripPlan).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.trip_id.in_(list(candidate_trip_ids)),
                    TripPlan.canonical_trip_id.is_(None),
                    TripPlan.is_active.is_(True),
                    TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                )
            )
            plans = list((await self.session.execute(stmt)).scalars().all())
            if len(plans) < 2:
                continue

            canonical = _pick_best_trip(plans)
            merge_trip_ids = [p.trip_id for p in plans if p.trip_id != canonical.trip_id]
            if not merge_trip_ids:
                continue

            merge_result = await trip_service.merge_trips(
                family_id=family_id,
                primary_trip_id=canonical.trip_id,
                merge_trip_ids=merge_trip_ids,
                reason="curation_back_propagation",
            )
            if not merge_result.get("success"):
                continue

            merged_total += int(merge_result.get("merged_count", 0) or 0)
            for trip_id in merge_trip_ids:
                alias_map[trip_id] = canonical.trip_id
            event.trip_id = canonical.trip_id

        if alias_map:
            for event in curated_events:
                if event.trip_id in alias_map:
                    event.trip_id = alias_map[event.trip_id]
                    continue

                if "trip_plan" not in set(event.source_types or []) or event.trip_id is not None:
                    continue

                for oid in event.original_event_ids or []:
                    try:
                        oid_uuid = UUID(str(oid))
                    except (TypeError, ValueError):
                        continue
                    canonical_id = alias_map.get(oid_uuid)
                    if canonical_id is not None:
                        event.trip_id = canonical_id
                        break

        if merged_total > 0:
            logger.info(
                "Curation back-propagation merged %d trips for family %s",
                merged_total,
                family_id,
            )

        return curated_events

    # --- Utility Methods ---

    @staticmethod
    def _normalize_destination(dest: str) -> str:
        """Normalize destination for grouping."""
        from .trip_grouping import normalize_destination
        return normalize_destination(dest)

    def _parse_uuid(self, value: str) -> Optional[UUID]:
        """Parse a UUID string, returning None if invalid."""
        try:
            return UUID(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid UUID format: {value}")
            return None

    def _strip_markdown_json(self, text: str) -> str:
        """Strip markdown code block markers from JSON response."""
        text = text.strip()
        # Handle ```json ... ``` blocks (including trailing content)
        if "```" in text:
            parts = text.split("```")
            # Find the first code-block body (odd-indexed parts)
            for i in range(1, len(parts), 2):
                candidate = parts[i].strip()
                # Strip optional language tag (json, JSON, etc.)
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].lstrip()
                if candidate:
                    return candidate
        # Fallback: extract outermost JSON object/array by brace matching
        first_brace = min(
            (text.find(c) for c in "{[" if text.find(c) >= 0),
            default=-1,
        )
        if first_brace >= 0:
            last_brace = max(
                (text.rfind(c) for c in "}]" if text.rfind(c) >= 0),
                default=-1,
            )
            if last_brace > first_brace:
                return text[first_brace:last_brace + 1]
        return text

    def _sanitize_for_llm(self, data: Union[dict, list, str]) -> Union[dict, list, str]:
        """Sanitize user data before including in LLM prompts."""
        if isinstance(data, str):
            sanitized = data
            sanitized = sanitized.replace("```", "")
            for role in ["system:", "assistant:", "user:", "[INST]", "[/INST]"]:
                sanitized = sanitized.replace(role, "")
            return sanitized
        elif isinstance(data, dict):
            return {k: self._sanitize_for_llm(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_for_llm(item) for item in data]
        return data
