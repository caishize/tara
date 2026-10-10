"""Trip Completeness Service - LLM-semantic gap detection for trip planning.

Replaces keyword-based gap detection with Claude Haiku semantic understanding.
Uses a cache table (trip_completeness_checks) to avoid redundant LLM calls
when trip events have not changed.

Fallback: if LLM is unavailable, returns None to signal the caller to use
the existing keyword-based logic (EventHygieneService.detect_trip_gaps).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now
from ....db.session import Base
from ...trip.models.trip_itinerary import TripItinerary
from ..models import CuratedEvent, PreparationItem

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Inline ORM model for the cache table
# ---------------------------------------------------------------------------

_COMPLETENESS_CHECK_TIMEOUT_SECS = 15


class TripCompletenessCheck(Base):
    """Cache table for LLM-based trip completeness checks.

    Created by migration 108.  Accessed with a try/except to gracefully
    handle environments where the migration has not yet been applied.
    """

    __tablename__ = "trip_completeness_checks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    input_hash = Column(String(64), nullable=False)
    result = Column(JSONB, nullable=False, default=dict)
    checked_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "trip_id", "input_hash",
            name="uq_trip_completeness_trip_hash",
        ),
        Index("ix_trip_completeness_checks_trip_id", "trip_id"),
        Index("ix_trip_completeness_checks_family_id", "family_id"),
    )


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TripCompletenessResult:
    """Immutable result of a completeness check."""

    trip_id: UUID
    has_departure: bool
    has_return: bool
    return_type: str  # "explicit" | "same_day" | "missing"
    has_accommodation: bool
    accommodation_type: str  # "booked" | "private" | "missing"
    gaps: list = field(default_factory=list)
    input_hash: str = ""


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
你是行程完整性审核员。
任务：分析以下行程信息和事件列表，判断行程是否完整。

判断规则（语义级别，不依赖关键字）：
- 出发：任何表示用户离开当前城市的事件（含"飞""坐高铁""开车去""驱车前往"等）
- 返程：任何表示用户回到出发城市的事件，OR 行程标注为"当天往返"
- 自驾/驾车：当行程或事件中包含"自驾""驾车""开车往返""自驾往返"等信息时，\
视为出发和返程均已安排（无需单独的机票/火车票），has_departure和has_return均为true
- 交通已安排：有明确的交通方式（自驾/高铁/飞机），且来回都有 → 不报 gap
- 住宿已安排：明确的酒店/民宿预订 OR 用户明确说明住处（朋友家/公寓/公司安排/活动提供）
- 住宿不需要：当天往返行程

请综合行程的 notes、description、transportation_mode，各事件的 notes、\
secretary_note，以及每日行程安排（schedule）中的活动详情来判断，不要只看标题。

输出严格JSON（不要包含Markdown代码块），格式：
{
  "has_departure": true,
  "has_return": false,
  "return_type": "explicit|same_day|missing",
  "has_accommodation": false,
  "accommodation_type": "booked|private|missing",
  "gaps": [{"gap_type": "no_return|no_accommodation", "suggestion": "...", "urgency": "high|medium"}],
  "reasoning": "一句话说明判断依据"
}"""


def _build_user_prompt(
    trip_json: dict,
    events_json: list[dict],
    itineraries_json: Optional[list[dict]] = None,
) -> str:
    parts = [
        f"行程信息：{json.dumps(trip_json, ensure_ascii=False)}",
        f"\n\n行程关联事件（共{len(events_json)}条）：{json.dumps(events_json, ensure_ascii=False)}",
    ]
    if itineraries_json:
        parts.append(f"\n\n每日行程安排（共{len(itineraries_json)}天）：{json.dumps(itineraries_json, ensure_ascii=False)}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TripCompletenessService:
    """Checks trip completeness using LLM semantic analysis.

    When llm_provider is None the service returns None from check_completeness,
    signalling the caller to fall back to keyword-based detection.
    """

    def __init__(self, db: AsyncSession, llm_provider=None):
        self._db = db
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_completeness(
        self, trip_id: UUID, family_id: UUID
    ) -> Optional[TripCompletenessResult]:
        """Detect completeness gaps for a single trip.

        Returns None when:
        - No LLM provider is configured (caller should fallback to keywords)
        - The trip has no associated curated events
        - Same-day round-trip (no gaps by definition)

        Uses input_hash caching to avoid duplicate LLM calls.
        """
        from ...trip.models.trip_plan import TripPlan

        trip = await self._db.get(TripPlan, trip_id)
        if trip is None:
            logger.debug("TripCompletenessService: trip %s not found", trip_id)
            return None

        events = await self._load_trip_events(trip_id, family_id)
        if not events:
            return None

        itineraries = await self._load_trip_itineraries(trip_id)
        input_hash = _compute_input_hash(trip, events, itineraries or None)

        cached = await self._load_cached_result(trip_id, family_id, input_hash)
        if cached is not None:
            logger.debug(
                "TripCompletenessService: cache hit for trip %s (hash=%s)",
                trip_id, input_hash,
            )
            await self._cleanup_stale_prep_items(events, cached)
            return cached

        if self._llm is None:
            return None

        llm_raw = await self._call_llm_check(trip, events, itineraries)
        if llm_raw is None:
            return None

        result = _parse_llm_result(trip_id, llm_raw, input_hash)

        await self._save_check_result(trip_id, family_id, input_hash, llm_raw)

        await self._cleanup_stale_prep_items(events, result)

        if result.gaps:
            await self._create_prep_items_for_gaps(trip, events, result)

        return result

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    async def _call_llm_check(
        self, trip, events: list, itineraries: Optional[list] = None
    ) -> Optional[dict]:
        """Call Claude Haiku for semantic completeness analysis.

        On any failure returns None so the caller can degrade gracefully.
        Conservative fallback: treat trip as complete (avoid false positives).

        Uses self._llm (injected via __init__) which may be an AsyncAnthropic
        client or another provider. Falls back to creating a new AsyncAnthropic
        client only if self._llm lacks the expected .messages.create interface.
        """
        try:
            from ....config.settings import settings

            trip_json = _serialize_trip(trip)
            events_json = [_serialize_event(e) for e in events]
            itineraries_json = (
                [_serialize_itinerary(i) for i in itineraries]
                if itineraries else None
            )
            user_prompt = _build_user_prompt(trip_json, events_json, itineraries_json)

            client = self._llm
            # If the injected provider does not expose .messages.create
            # (e.g. a different adapter), fall back to a fresh AsyncAnthropic.
            if not hasattr(client, "messages"):
                from ....core.llm.haiku_client import get_haiku_client
                client = get_haiku_client()

            response = await client.messages.create(
                model=settings.fast_worker_model,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=_COMPLETENESS_CHECK_TIMEOUT_SECS,
            )

            raw_text = response.content[0].text.strip()
            return json.loads(raw_text)

        except json.JSONDecodeError as exc:
            logger.warning(
                "TripCompletenessService: LLM returned invalid JSON: %s", exc
            )
            return None
        except Exception as exc:
            logger.warning(
                "TripCompletenessService: LLM call failed for trip %s: %s",
                trip.trip_id, exc,
            )
            return None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _load_cached_result(
        self, trip_id: UUID, family_id: UUID, input_hash: str
    ) -> Optional[TripCompletenessResult]:
        try:
            stmt = (
                select(TripCompletenessCheck)
                .where(
                    TripCompletenessCheck.trip_id == trip_id,
                    TripCompletenessCheck.family_id == family_id,
                    TripCompletenessCheck.input_hash == input_hash,
                )
                .limit(1)
            )
            result = await self._db.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _parse_llm_result(trip_id, row.result, input_hash)
        except Exception as exc:
            logger.debug(
                "TripCompletenessService: cache lookup failed (table may not exist): %s",
                exc,
            )
            return None

    async def _save_check_result(
        self,
        trip_id: UUID,
        family_id: UUID,
        input_hash: str,
        llm_result: dict,
    ) -> None:
        try:
            check = TripCompletenessCheck(
                trip_id=trip_id,
                family_id=family_id,
                input_hash=input_hash,
                result=llm_result,
                checked_at=utc_now(),
            )
            self._db.add(check)
            await self._db.flush()
        except Exception as exc:
            logger.debug(
                "TripCompletenessService: failed to save check result "
                "(table may not exist): %s",
                exc,
            )

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _load_trip_events(
        self, trip_id: UUID, family_id: UUID
    ) -> list:
        stmt = (
            select(CuratedEvent)
            .where(
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
            )
            .order_by(CuratedEvent.normalized_start)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _load_trip_itineraries(self, trip_id: UUID) -> list:
        stmt = (
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.day_number)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Stale prep item cleanup
    # ------------------------------------------------------------------

    async def _cleanup_stale_prep_items(
        self,
        events: list,
        result: TripCompletenessResult,
    ) -> None:
        """Remove hygiene_auto PreparationItems whose gaps no longer exist."""
        if not events:
            return
        anchor_event = events[0]

        current_suggestions = {
            gap.get("suggestion", "") for gap in result.gaps if gap.get("suggestion")
        }

        stmt = (
            select(PreparationItem)
            .where(
                PreparationItem.event_id == anchor_event.id,
                PreparationItem.source == "hygiene_auto",
                PreparationItem.done.is_(False),
            )
        )
        existing = await self._db.execute(stmt)
        for item in existing.scalars().all():
            if item.text not in current_suggestions:
                await self._db.delete(item)

    # ------------------------------------------------------------------
    # PreparationItem creation
    # ------------------------------------------------------------------

    async def _create_prep_items_for_gaps(
        self,
        trip,
        events: list,
        result: TripCompletenessResult,
    ) -> None:
        """Create PreparationItem rows for each detected gap."""
        anchor_event = events[0] if events else None
        if anchor_event is None:
            return

        for gap in result.gaps:
            suggestion = gap.get("suggestion", "")
            if not suggestion:
                continue
            await self._upsert_prep_item(anchor_event.id, suggestion)

    async def _upsert_prep_item(self, event_id: UUID, suggestion: str) -> None:
        """Insert a PreparationItem if one with the same text does not exist."""
        existing_stmt = (
            select(PreparationItem)
            .where(
                PreparationItem.event_id == event_id,
                PreparationItem.source == "hygiene_auto",
                PreparationItem.text == suggestion,
            )
            .limit(1)
        )
        existing = await self._db.execute(existing_stmt)
        if existing.scalar_one_or_none() is not None:
            return

        prep = PreparationItem(
            event_id=event_id,
            text=suggestion,
            source="hygiene_auto",
            done=False,
        )
        self._db.add(prep)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def _compute_input_hash(
    trip, events: list, itineraries: Optional[list] = None
) -> str:
    """Compute a stable MD5 hash over trip metadata + event + itinerary details.

    Includes notes and extra_data so that user edits (e.g. adding "自驾")
    invalidate cached results and trigger a fresh LLM check.
    """
    extra_data_str = ""
    if getattr(trip, "extra_data", None) and isinstance(trip.extra_data, dict):
        extra_data_str = json.dumps(trip.extra_data, sort_keys=True)
    parts = [
        str(trip.trip_id),
        str(trip.start_date),
        str(trip.end_date),
        trip.destination or "",
        trip.notes or "",
        extra_data_str,
    ]
    for ev in events:
        parts.append(
            f"{ev.id}|{ev.title}|{ev.event_type}|{ev.location}|{ev.notes or ''}"
        )
    if itineraries:
        for itin in sorted(itineraries, key=lambda i: getattr(i, "day_number", 0)):
            schedule_str = json.dumps(
                getattr(itin, "schedule", []) or [],
                ensure_ascii=False, sort_keys=True,
            )
            parts.append(f"itin:{itin.day_number}|{schedule_str}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _serialize_trip(trip) -> dict:
    result = {
        "trip_id": str(trip.trip_id),
        "trip_name": trip.trip_name,
        "destination": trip.destination,
        "start_date": str(trip.start_date),
        "end_date": str(trip.end_date),
        "duration_days": trip.duration_days,
        "status": trip.status,
        "category": trip.category,
        "notes": trip.notes,
    }
    extra_data = getattr(trip, "extra_data", None)
    if extra_data and isinstance(extra_data, dict):
        transport = (
            extra_data.get("transportation_mode")
            or extra_data.get("transportation")
        )
        if transport:
            result["transportation_mode"] = transport
    description = getattr(trip, "description", None)
    if description:
        result["description"] = str(description)[:300]
    return result


def _serialize_itinerary(itinerary) -> dict:
    result = {"day_number": itinerary.day_number}
    schedule = getattr(itinerary, "schedule", None)
    if schedule and isinstance(schedule, list):
        result["schedule"] = schedule  # Already JSONB, pass through
    return result


def _serialize_event(event) -> dict:
    result = {
        "id": str(event.id),
        "title": event.title,
        "event_type": event.event_type,
        "location": event.location,
        "normalized_start": str(event.normalized_start) if event.normalized_start else None,
        "normalized_end": str(event.normalized_end) if event.normalized_end else None,
        "status": event.status,
    }
    if getattr(event, "notes", None):
        result["notes"] = event.notes[:200]
    if getattr(event, "secretary_note", None):
        result["secretary_note"] = event.secretary_note[:200]
    enrichments = getattr(event, "enrichments", None)
    if enrichments and isinstance(enrichments, dict):
        transport = (
            enrichments.get("transportation")
            or enrichments.get("transport_mode")
        )
        if transport:
            result["transportation"] = transport
    return result


def _parse_llm_result(
    trip_id: UUID, raw: dict, input_hash: str
) -> TripCompletenessResult:
    """Convert raw LLM JSON dict into a TripCompletenessResult."""
    return TripCompletenessResult(
        trip_id=trip_id,
        has_departure=bool(raw.get("has_departure", True)),
        has_return=bool(raw.get("has_return", True)),
        return_type=str(raw.get("return_type", "explicit")),
        has_accommodation=bool(raw.get("has_accommodation", True)),
        accommodation_type=str(raw.get("accommodation_type", "booked")),
        gaps=list(raw.get("gaps", [])),
        input_hash=input_hash,
    )
