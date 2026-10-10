"""Deduplication and normalization methods for the curation service.

Contains semantic dedup (LLM-based), batch processing, day event
collapse/decompose, and fallback heuristic dedup logic.
"""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict
from uuid import UUID

from ....config.logging import get_logger
from ....config.settings import settings
from ....core.interfaces.llm_provider import LLMMessage
from ....core.utils.timezone import local_today, get_user_timezone, utc_now
from ..models import CuratedEvent
from ..schemas import (
    LLMDeduplicationResponse,
    UnconfirmedItem,
)
from .data_models import RawEvent
from .event_type_utils import normalize_event_type
from .prompts import (
    DEDUP_SYSTEM_PROMPT,
    DEFAULT_LLM_TEMPERATURE,
    FALLBACK_CONFIDENCE,
)

logger = get_logger(__name__)


_IMPORTANT_DATE_EVENT_TYPES = {
    "birthday",
    "anniversary",
    "holiday",
    "holiday_solar_term",
    "solar_term",
    "reminder",
}

_IMPORTANT_DATE_TYPE_PRIORITY = {
    # Preserve the most semantically specific calendar intent on ties.
    "birthday": 60,
    "anniversary": 50,
    "holiday_solar_term": 40,
    "solar_term": 35,
    "holiday": 30,
    "reminder": 20,
    "other": 10,
}


def _low_importance_event_types() -> set[str]:
    """Load low-importance event types from settings."""
    return {
        str(event_type).strip().lower()
        for event_type in (settings.curation_low_importance_event_types or [])
        if str(event_type).strip()
    }


def _infer_priority(event_type: Optional[str]) -> str:
    """Infer CuratedEvent.priority from event_type during curation.

    The secretary assigns priority intelligently so downstream views
    can filter without hardcoding event type lists.
    """
    normalized_type = (event_type or "").strip().lower()
    if normalized_type in _low_importance_event_types():
        return "low"
    if event_type == "birthday":
        return "high"
    return "normal"


def _pick_preferred_source_event_type(source_event_types: List[str]) -> Optional[str]:
    """Pick a stable source event type based on frequency + semantic specificity."""
    normalized_types = [
        normalize_event_type(event_type)
        for event_type in source_event_types
        if event_type
    ]
    if not normalized_types:
        return None

    counts = Counter(normalized_types)
    return max(
        counts.items(),
        key=lambda item: (
            item[1],
            _IMPORTANT_DATE_TYPE_PRIORITY.get(item[0], 0),
        ),
    )[0]


def _align_event_type_with_sources(
    llm_event_type: Optional[str],
    *,
    source_types: List[str],
    merged_raw_events: List[RawEvent],
) -> str:
    """Align LLM classification with source semantics to avoid type drift.

    Important-date records (birthday/anniversary/holidays/solar-terms) are
    source-of-truth metadata. We let LLM dedup text and timing, but keep the
    source calendar type to avoid generic reclassification (e.g. solar_term
    drifting into holiday).
    """
    normalized_llm_type = normalize_event_type(llm_event_type)
    if not merged_raw_events:
        return normalized_llm_type

    normalized_source_types = {
        str(source_type).strip().lower()
        for source_type in source_types
        if str(source_type).strip()
    }
    if normalized_source_types != {"important_date"}:
        return normalized_llm_type

    source_event_types = [
        normalize_event_type(event.event_type)
        for event in merged_raw_events
        if event.event_type
    ]
    preferred_source_type = _pick_preferred_source_event_type(source_event_types)
    if not preferred_source_type:
        return normalized_llm_type

    if preferred_source_type not in _IMPORTANT_DATE_EVENT_TYPES:
        return normalized_llm_type

    if normalized_llm_type == preferred_source_type:
        return normalized_llm_type

    # If LLM moved away from source calendar semantics, restore source type.
    if normalized_llm_type not in _IMPORTANT_DATE_EVENT_TYPES:
        return preferred_source_type
    if normalized_llm_type in {"holiday", "reminder", "other"}:
        return preferred_source_type
    return preferred_source_type


# ---------------------------------------------------------------------------
# Trip clustering helpers (pure functions, no DB access)
# ---------------------------------------------------------------------------

_STATUS_PRIORITY = {"confirmed": 3, "in_progress": 2, "planning": 1}


def _cluster_by_date_proximity(
    plans: list,
    proximity_days: int,
) -> List[list]:
    """Group plans whose date ranges overlap or are within *proximity_days*.

    Uses a sweep-line approach: sort by start_date, then greedily extend the
    cluster envelope.  Two plans are in the same cluster when
    ``plan.start_date <= cluster_end + proximity_days``.
    """
    sorted_plans = sorted(plans, key=lambda p: (p.start_date or date.min))
    clusters: List[list] = []

    for plan in sorted_plans:
        s = plan.start_date or date.min
        e = plan.end_date or s
        if clusters:
            cluster_end = clusters[-1][0]
            if s <= cluster_end + timedelta(days=proximity_days):
                # Extend cluster envelope
                clusters[-1][0] = max(cluster_end, e)
                clusters[-1][1].append(plan)
                continue
        clusters.append([e, [plan]])

    return [c[1] for c in clusters]


def _pick_best_trip(cluster: list) -> object:
    """Pick the best trip from a cluster to survive dedup.

    Priority:
    1. Highest status (confirmed > in_progress > planning)
    2. Longest date range
    3. Most itinerary data (description length)
    4. Most recently updated
    """
    return max(
        cluster,
        key=lambda p: (
            _STATUS_PRIORITY.get(p.status, 0),
            (p.end_date or date.min) - (p.start_date or date.min),
            len(p.description or ""),
            p.updated_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
    )


class CurationDedupMixin:
    """Mixin providing dedup/normalize methods for SecretaryCurationService."""

    async def _semantic_dedup_and_normalize(
        self,
        family_id: UUID,
        raw_events: List[RawEvent],
        user_id: Optional[UUID] = None,
        family_prefs=None,
    ) -> Tuple[List[CuratedEvent], List[UnconfirmedItem]]:
        """使用LLM进行语义去重和规范化。"""
        if not raw_events:
            return [], []

        max_batch_size = 50
        if len(raw_events) > max_batch_size:
            return await self._batch_semantic_dedup(
                family_id, raw_events, user_id, max_batch_size
            )

        return await self._single_batch_dedup(family_id, raw_events, user_id)

    async def _batch_semantic_dedup(
        self,
        family_id: UUID,
        raw_events: List[RawEvent],
        user_id: Optional[UUID],
        max_batch_size: int,
    ) -> Tuple[List[CuratedEvent], List[UnconfirmedItem]]:
        """Split large event sets into date-sorted batches and process each with LLM."""
        sorted_events = sorted(raw_events, key=lambda e: e.start_time)

        batches: List[List[RawEvent]] = []
        current_batch: List[RawEvent] = []
        for event in sorted_events:
            current_batch.append(event)
            if len(current_batch) >= max_batch_size:
                batches.append(current_batch)
                current_batch = []
        if current_batch:
            batches.append(current_batch)

        logger.info(
            f"Splitting {len(raw_events)} events into {len(batches)} batches "
            f"for LLM dedup (max {max_batch_size} per batch)"
        )

        all_curated: List[CuratedEvent] = []
        all_unconfirmed: List[UnconfirmedItem] = []

        for i, batch in enumerate(batches):
            try:
                curated, unconfirmed = await self._single_batch_dedup(
                    family_id, batch, user_id
                )
                all_curated.extend(curated)
                all_unconfirmed.extend(unconfirmed)
                logger.info(
                    f"Batch {i + 1}/{len(batches)}: {len(batch)} events → "
                    f"{len(curated)} curated"
                )
            except Exception as e:
                logger.error(f"Batch {i + 1}/{len(batches)} failed: {e}")
                all_curated.extend(
                    self._fallback_heuristic_dedup(family_id, batch, user_id)
                )

        return all_curated, all_unconfirmed

    async def _single_batch_dedup(
        self,
        family_id: UUID,
        raw_events: List[RawEvent],
        user_id: Optional[UUID],
    ) -> Tuple[List[CuratedEvent], List[UnconfirmedItem]]:
        """Process a single batch of events through LLM dedup."""
        raw_events_data = self._sanitize_for_llm([e.to_dict() for e in raw_events])
        events_json = json.dumps(
            raw_events_data,
            ensure_ascii=False,
            indent=2,
        )

        today_str = local_today(get_user_timezone()).isoformat()
        user_prompt = f"""今天是 {today_str}。

请分析以下事件列表，进行语义去重和规范化：

{events_json}

请输出JSON格式的结果。"""

        try:
            response = await self.llm.chat(
                messages=[
                    LLMMessage(role="system", content=DEDUP_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                temperature=DEFAULT_LLM_TEMPERATURE,
                max_tokens=settings.curation_dedup_max_tokens,
            )

            response_text = self._strip_markdown_json(response.text)
            parsed = json.loads(response_text)
            llm_response = LLMDeduplicationResponse(**parsed)

            curated_events = []
            raw_events_by_id = {event.id: event for event in raw_events}
            for llm_event in llm_response.curated_events:
                start_time = datetime.fromisoformat(llm_event.start_time.replace("Z", "+00:00"))
                end_time = None
                if llm_event.end_time:
                    end_time = datetime.fromisoformat(llm_event.end_time.replace("Z", "+00:00"))

                timeline_items = [
                    {
                        "time": ti.time,
                        "item": ti.item,
                        "confirmed": ti.confirmed,
                        "note": ti.note,
                    }
                    for ti in llm_event.timeline_items
                ]

                merged_raw_events = [
                    raw_events_by_id[event_id]
                    for event_id in llm_event.merged_from
                    if event_id in raw_events_by_id
                ]
                source_types_set = {
                    event.source_type
                    for event in merged_raw_events
                    if event.source_type
                }
                source_types = sorted(source_types_set) if source_types_set else ["unknown"]

                trip_id = None
                if llm_event.trip_source_id:
                    raw_match = raw_events_by_id.get(llm_event.trip_source_id)
                    if raw_match and raw_match.source_type != "trip_plan":
                        raw_match = None
                    if raw_match:
                        try:
                            trip_id = UUID(raw_match.id)
                        except (ValueError, TypeError):
                            pass

                if trip_id is None:
                    trip_id = self._extract_trip_id(raw_events, llm_event.merged_from)

                normalized_event_type = _align_event_type_with_sources(
                    llm_event.event_type,
                    source_types=source_types,
                    merged_raw_events=merged_raw_events,
                )
                curated_event = CuratedEvent(
                    family_id=family_id,
                    user_id=user_id,
                    original_event_ids=llm_event.merged_from,
                    source_types=source_types,
                    title=llm_event.title,
                    normalized_start=start_time,
                    normalized_end=end_time,
                    city=llm_event.city,
                    location=llm_event.location,
                    event_type=normalized_event_type,
                    timeline_items=timeline_items,
                    dedup_reason=llm_event.dedup_reason,
                    confidence=llm_event.confidence,
                    trip_id=trip_id,
                    notes=llm_event.secretary_notes,
                    priority=_infer_priority(normalized_event_type),
                )
                curated_events.append(curated_event)

            return curated_events, llm_response.unconfirmed_items

        except json.JSONDecodeError as e:
            raw_text = ""
            try:
                raw_text = response.text[:1000]
            except Exception:
                pass
            logger.error(
                "Failed to parse LLM dedup response for family %s "
                "(%d events): %s | raw_response (truncated): %s",
                family_id, len(raw_events), e, raw_text,
            )
            return self._fallback_heuristic_dedup(family_id, raw_events, user_id), []
        except Exception as e:
            logger.error(
                "LLM dedup failed for family %s (%d events): %s",
                family_id, len(raw_events), e,
                exc_info=True,
            )
            return self._fallback_heuristic_dedup(family_id, raw_events, user_id), []

    @staticmethod
    def _collapse_day_events_into_trips(
        curated_events: List[CuratedEvent],
    ) -> List[CuratedEvent]:
        """Collapse LLM-generated "Day N ..." events back into a single trip event."""
        trip_groups: Dict[str, List[CuratedEvent]] = {}
        non_day_events: List[CuratedEvent] = []

        for ev in curated_events:
            title = ev.title or ""
            if not title.startswith("Day ") or " \u00b7 " not in title:
                non_day_events.append(ev)
                continue

            if ev.trip_id:
                key = str(ev.trip_id)
            elif ev.original_event_ids:
                key = str(ev.original_event_ids[0])
            else:
                non_day_events.append(ev)
                continue

            trip_groups.setdefault(key, []).append(ev)

        if not trip_groups:
            return curated_events

        for key, day_events in trip_groups.items():
            day_events.sort(key=lambda e: e.normalized_start or datetime.min.replace(tzinfo=timezone.utc))
            base = day_events[0]

            base_title = (base.title or "").split(" \u00b7 ", 1)[-1]

            earliest_start = min(e.normalized_start for e in day_events if e.normalized_start)
            latest_end = max(
                (e.normalized_end or e.normalized_start) for e in day_events
                if e.normalized_start
            )

            merged = CuratedEvent(
                family_id=base.family_id,
                user_id=base.user_id,
                original_event_ids=base.original_event_ids,
                source_types=base.source_types,
                title=base_title,
                normalized_start=earliest_start,
                normalized_end=latest_end,
                city=base.city,
                location=base.location,
                event_type=normalize_event_type(base.event_type, default="travel"),
                timeline_items=[],
                dedup_reason="LLM拆解事件已合并回原始行程",
                confidence=base.confidence,
                trip_id=base.trip_id,
                notes=base.notes,
            )
            non_day_events.append(merged)

        return non_day_events

    @staticmethod
    def _decompose_multi_day_events(
        curated_events: List[CuratedEvent],
    ) -> List[CuratedEvent]:
        """Decompose non-trip multi-day events into daily events."""
        skip_types = {"holiday"}
        trip_types = {"business_trip", "travel"}
        result: List[CuratedEvent] = []

        for ev in curated_events:
            if (
                ev.event_type in skip_types
                or ev.event_type in trip_types
                or ev.trip_id is not None
                or not ev.normalized_start
                or not ev.normalized_end
                or (ev.title or "").startswith("Day ")
            ):
                result.append(ev)
                continue

            user_tz = get_user_timezone()
            local_start = ev.normalized_start.astimezone(user_tz)
            local_end = ev.normalized_end.astimezone(user_tz)
            start_d = local_start.date()
            end_d = local_end.date()
            num_days = (end_d - start_d).days + 1

            if num_days < 2:
                result.append(ev)
                continue

            for day_idx in range(num_days):
                day_date = start_d + timedelta(days=day_idx)
                day_start = datetime(
                    day_date.year, day_date.month, day_date.day,
                    9, 0, 0, tzinfo=user_tz,
                )
                day_end = datetime(
                    day_date.year, day_date.month, day_date.day,
                    18, 0, 0, tzinfo=user_tz,
                )

                day_event = CuratedEvent(
                    family_id=ev.family_id,
                    user_id=ev.user_id,
                    original_event_ids=ev.original_event_ids,
                    source_types=ev.source_types,
                    title=f"Day {day_idx + 1} \u00b7 {ev.title}",
                    normalized_start=day_start,
                    normalized_end=day_end,
                    city=ev.city,
                    location=ev.location,
                    event_type=normalize_event_type(ev.event_type),
                    timeline_items=[],
                    dedup_reason=f"从{ev.title}拆解: 第{day_idx + 1}天日程",
                    confidence=ev.confidence * 0.9,
                    trip_id=ev.trip_id,
                    trip_name=ev.trip_name,
                    trip_day_label=f"{ev.title} \u00b7 Day {day_idx + 1}",
                    notes=ev.notes,
                )
                result.append(day_event)

            logger.info(
                f"Decomposed multi-day event '{ev.title}' ({num_days} days) "
                f"into {num_days} daily events"
            )

        return result

    @staticmethod
    def _dedup_decomposed_events(
        curated_events: List[CuratedEvent],
    ) -> List[CuratedEvent]:
        """Post-decomposition dedup by (date, location)."""
        from .trip_grouping import normalize_destination
        normalize_dest = normalize_destination
        user_tz = get_user_timezone()

        day_events: List[CuratedEvent] = []
        other_events: List[CuratedEvent] = []
        for ev in curated_events:
            if (ev.title or "").startswith("Day ") and ev.normalized_start:
                day_events.append(ev)
            else:
                other_events.append(ev)

        if not day_events:
            return curated_events

        groups: Dict[tuple, List[CuratedEvent]] = {}
        for ev in day_events:
            cal_date = ev.normalized_start.astimezone(user_tz).date()
            norm_loc = normalize_dest(ev.location or "")
            if norm_loc:
                group_key = f"loc:{norm_loc}"
            elif ev.trip_id:
                group_key = f"trip:{ev.trip_id}"
            else:
                title = ev.title or ""
                group_key = title.split(" \u00b7 ", 1)[1] if " \u00b7 " in title else title
            key = (cal_date, group_key)
            groups.setdefault(key, []).append(ev)

        deduped_days: List[CuratedEvent] = []
        for key, group in groups.items():
            if len(group) == 1:
                deduped_days.append(group[0])
            else:
                best = max(
                    group,
                    key=lambda e: (
                        len(e.title or ""),
                        len(getattr(e, "notes", "") or ""),
                        e.confidence or 0,
                    ),
                )
                deduped_days.append(best)
                logger.info(
                    f"Deduped {len(group)} Day events on {key[0]} "
                    f"for group '{key[1]}', kept '{best.title}'"
                )

        return other_events + deduped_days

    @staticmethod
    def _decompose_surviving_multi_day(
        surviving_events: List[CuratedEvent],
    ) -> List[CuratedEvent]:
        """Decompose surviving (user_created/confirmed) multi-day events into daily events."""
        skip_types = {"holiday"}
        trip_types = {"business_trip", "travel"}
        new_events: List[CuratedEvent] = []

        for ev in surviving_events:
            if not ev.normalized_start or not ev.normalized_end:
                continue
            if ev.event_type in skip_types:
                continue
            if ev.event_type in trip_types:
                continue
            if (ev.title or "").startswith("Day "):
                continue

            user_tz = get_user_timezone()
            local_start = ev.normalized_start.astimezone(user_tz)
            local_end = ev.normalized_end.astimezone(user_tz)
            start_d = local_start.date()
            end_d = local_end.date()
            num_days = (end_d - start_d).days + 1
            if num_days < 2:
                continue

            ev.is_active = False

            for day_idx in range(num_days):
                day_date = start_d + timedelta(days=day_idx)
                day_event = CuratedEvent(
                    family_id=ev.family_id,
                    user_id=ev.user_id,
                    original_event_ids=ev.original_event_ids or [],
                    source_types=ev.source_types or [],
                    title=f"Day {day_idx + 1} \u00b7 {ev.title}",
                    normalized_start=datetime(
                        day_date.year, day_date.month, day_date.day,
                        9, 0, 0, tzinfo=user_tz,
                    ),
                    normalized_end=datetime(
                        day_date.year, day_date.month, day_date.day,
                        18, 0, 0, tzinfo=user_tz,
                    ),
                    location=ev.location,
                    event_type=normalize_event_type(ev.event_type, default="travel"),
                    timeline_items=[],
                    dedup_reason=f"从{ev.title}拆解: 第{day_idx + 1}天日程",
                    confidence=ev.confidence * 0.9,
                    trip_id=ev.trip_id,
                    status=ev.status,
                    notes=ev.notes,
                )
                new_events.append(day_event)

            logger.info(
                f"Decomposed surviving multi-day event '{ev.title}' "
                f"({num_days} days) into {num_days} daily events"
            )

        return new_events

    def _fallback_heuristic_dedup(
        self,
        family_id: UUID,
        raw_events: List[RawEvent],
        user_id: Optional[UUID] = None,
    ) -> List[CuratedEvent]:
        """Fallback when LLM fails: keep each raw event as an independent atomic event."""
        curated_events = []
        for raw in raw_events:
            trip_id = None
            if raw.source_type == "trip_plan":
                try:
                    trip_id = UUID(raw.id)
                except (ValueError, TypeError):
                    pass

            default_type = "travel" if raw.source_type == "trip_plan" else "other"
            normalized_event_type = normalize_event_type(raw.event_type, default=default_type)
            curated_events.append(CuratedEvent(
                family_id=family_id,
                user_id=user_id,
                original_event_ids=[raw.id],
                source_types=[raw.source_type],
                title=raw.title,
                normalized_start=raw.start_time,
                normalized_end=raw.end_time,
                location=raw.location,
                event_type=normalized_event_type,
                trip_id=trip_id,
                confidence=FALLBACK_CONFIDENCE,
                dedup_reason="LLM处理失败，使用原始数据",
                priority=_infer_priority(normalized_event_type),
            ))

        return curated_events

    async def _dedup_overlapping_trips(
        self,
        travels: list,
        proximity_days: int = 3,
    ) -> list:
        """Deduplicate overlapping/near-overlapping trips in the DB.

        For each destination, clusters trips whose date ranges overlap or are
        within ``proximity_days`` of each other.  The best trip in each cluster
        survives (date range extended to cover all merged trips); the rest are
        cancelled in the database and their curated_events deactivated.

        Confirmed/in_progress trips are always kept and act as merge targets
        (they absorb planning-status duplicates).
        """
        from .trip_grouping import normalize_destination

        if not travels:
            return []

        # Group all trips by normalized destination
        by_dest: Dict[str, list] = defaultdict(list)
        for t in travels:
            by_dest[normalize_destination(t.destination or "")].append(t)

        keep: list = []
        cancelled_ids: list = []

        for _dest, plans in by_dest.items():
            clusters = _cluster_by_date_proximity(plans, proximity_days)

            for cluster in clusters:
                if len(cluster) == 1:
                    keep.append(cluster[0])
                    continue

                best = _pick_best_trip(cluster)

                # Extend best trip's date range to cover the whole cluster
                all_starts = [p.start_date for p in cluster if p.start_date]
                all_ends = [p.end_date for p in cluster if p.end_date]
                if all_starts:
                    best.start_date = min(all_starts)
                if all_ends:
                    best.end_date = max(all_ends)
                best.updated_at = utc_now()

                # Cancel the losers
                for plan in cluster:
                    if plan is not best:
                        plan.status = "cancelled"
                        if hasattr(plan, "canonical_trip_id"):
                            plan.canonical_trip_id = best.trip_id
                        if hasattr(plan, "is_active"):
                            plan.is_active = False
                        plan.updated_at = utc_now()
                        cancelled_ids.append(plan.trip_id)
                        logger.info(
                            "Cancelled duplicate trip %s (%s %s~%s) in favour of %s",
                            plan.trip_id,
                            plan.destination,
                            plan.start_date,
                            plan.end_date,
                            best.trip_id,
                        )

                keep.append(best)
                if hasattr(best, "canonical_trip_id"):
                    best.canonical_trip_id = None
                if hasattr(best, "is_active"):
                    best.is_active = True

        # Deactivate curated_events that reference cancelled trips
        if cancelled_ids:
            from ..models import CuratedEvent as CE
            from sqlalchemy import update

            await self.session.execute(
                update(CE)
                .where(
                    CE.trip_id.in_(cancelled_ids),
                    CE.is_active.is_(True),
                )
                .values(is_active=False, status="cancelled")
            )

        if cancelled_ids:
            await self.session.flush()
            logger.info(
                "Deduped trips: cancelled %d, kept %d",
                len(cancelled_ids),
                len(keep),
            )

        return keep

    @staticmethod
    def _extract_trip_id(raw_events: List[RawEvent], merged_ids: List[str]) -> Optional[UUID]:
        """Extract trip_id from merged raw events that originated from a trip_plan."""
        for eid in merged_ids:
            raw = next((e for e in raw_events if e.id == eid and e.source_type == "trip_plan"), None)
            if raw:
                try:
                    return UUID(raw.id)
                except (ValueError, TypeError):
                    continue
        return None
