"""Hybrid priority engine: rule-based scoring (80%) + LLM calibration (20%).

The fast layer runs the existing ``compute_priority_score`` rules with
optional ``FamilyPreference`` weight overrides.  Only events that land in the
*ambiguous zone* (composite 0.42-0.58) or have high complexity (3+ associations)
are forwarded to a Haiku calibration call.

Phase 5: Intimate-relationship events (spouse / parent / child) are
unconditionally elevated to P0 for important date types, bypassing all
LLM calibration.

F3: Fuzzy band narrowed from [0.35, 0.65] to [0.42, 0.58] after adding
interaction_bonus (+0.15 max) and association_bonus (+0.10 max) to the
base scoring dimensions in ``compute_priority_score``.

Design doc: docs/secretary-intelligence-optimization.md section 3.1
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.cache import redis_client
from ....core.llm.haiku_client import get_haiku_client
from ....config.settings import settings
from ..models import FamilyPreference
from .family_context import FamilyRelationContext
from .priority_score import PriorityScore, compute_priority_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

CALIBRATION_CACHE_PREFIX = "cal:priority"
CALIBRATION_CACHE_TTL = 86400  # 24 hours
MAX_BATCH_SIZE = 5  # Haiku batch limit per call
MIN_CALIBRATION_CONFIDENCE = 0.6
COLD_RELATIONSHIP_BOOST_DELTA = 0.15  # irrecoverability boost for cold/frozen relations
COLD_INTIMACY_THRESHOLD = 2  # intimacy_level <= this = cold/frozen

# Phase 5: intimate relationship types that trigger unconditional P0
_INTIMATE_RELATION_TYPES = frozenset({
    "spouse", "partner",
    "father", "mother", "parent",
    "son", "daughter", "child",
    "father_in_law", "mother_in_law", "parent_in_law",
})

# Phase 5: event types considered "important dates" for intimate relations
_IMPORTANT_DATE_EVENT_TYPES = frozenset({
    "birthday", "anniversary", "family",
})

# Expanded P0 gate: intimate member + these event types -> P0 consideration
# Superset of _IMPORTANT_DATE_EVENT_TYPES, adding medical/health/milestone
_P0_INTIMATE_EVENT_TYPES = frozenset({
    "birthday", "anniversary", "family",
    "medical", "health_checkup", "milestone",
})

# Phase 5: human-readable event type labels for secretary notes
_EVENT_TYPE_CN: Dict[str, str] = {
    "birthday": "生日",
    "anniversary": "纪念日",
    "family": "家庭活动",
    "medical": "就医",
    "health_checkup": "体检",
    "milestone": "重要里程碑",
}

# Phase 5: preparation hours for intimate P0 events by event type
_INTIMATE_PREP_HOURS: Dict[str, float] = {
    "birthday": 48.0,
    "anniversary": 48.0,
    "family": 24.0,
    "medical": 24.0,
    "health_checkup": 24.0,
    "milestone": 48.0,
}


@dataclass(frozen=True)
class CalibrationResult:
    """LLM-calibrated dimension scores for one event."""

    event_id: str
    severity: float
    stakeholder: float
    irrecoverability: float
    preparation_hours: float
    secretary_note: Optional[str]
    confidence: float


@dataclass(frozen=True)
class EnhancedPriorityScore:
    """Extended priority score combining rule-based base with optional LLM calibration."""

    base: PriorityScore
    calibration: Optional[CalibrationResult] = None
    preparation_hours: float = 0.0
    secretary_note: Optional[str] = None
    fallback: bool = False

    @property
    def composite(self) -> float:
        """Return calibration-adjusted composite, or base composite."""
        if self.calibration is not None:
            # Blend calibrated dimensions with urgency from rule engine
            # (urgency is time-based and best handled by rules)
            wu = self.base.w_urgency_override if self.base.w_urgency_override is not None else PriorityScore.W_URGENCY
            ws = self.base.w_severity_override if self.base.w_severity_override is not None else PriorityScore.W_SEVERITY
            wst = self.base.w_stakeholder_override if self.base.w_stakeholder_override is not None else PriorityScore.W_STAKEHOLDER
            wi = self.base.w_irrecoverability_override if self.base.w_irrecoverability_override is not None else PriorityScore.W_IRRECOVERABLE
            return (
                self.base.urgency * wu
                + self.calibration.severity * ws
                + self.calibration.stakeholder * wst
                + self.calibration.irrecoverability * wi
            )
        return self.base.composite

    @property
    def priority_level(self) -> str:
        c = self.composite
        if c >= 0.8:
            return "P0"
        if c >= 0.6:
            return "P1"
        if c >= 0.3:
            return "P2"
        return "P3"

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "base": self.base.to_dict(),
            "composite": round(self.composite, 3),
            "priority_level": self.priority_level,
            "preparation_hours": self.preparation_hours,
            "secretary_note": self.secretary_note,
            "fallback": self.fallback,
            "calibrated": self.calibration is not None,
        }
        return result


# ---------------------------------------------------------------------------
# Calibration prompt
# ---------------------------------------------------------------------------

_CALIBRATION_SYSTEM_PROMPT = """你是一位贴心的生活管家，需要从关心家人的角度评估以下事件的重要性。

## 评估维度（每项 0-1）
- severity: 对用户和家人的生活、健康、感情的实际影响（家人的生日、健康检查和情感事件也很重要）
- stakeholder: 涉及的人和用户的关系有多亲近（家人 > 亲友 > 朋友 > 同事）
- irrecoverability: 错过之后还能不能补救（生日过了就过了，纪念日也是）
- preparation_hours: 需要多少准备时间（小时，0-24）
- secretary_note: 一句温馨提醒，像家人的叮嘱（可选，null 或字符串）

## 家庭偏好
{family_preference_rules}

## 人物关系
{person_profiles_summary}

## 事件列表
{events_json}

输出严格 JSON 数组，每个元素包含:
event_id, severity, stakeholder, irrecoverability, preparation_hours, secretary_note, confidence

示例:
[{{"event_id":"abc","severity":0.8,"stakeholder":0.6,"irrecoverability":0.9,"preparation_hours":2.0,"secretary_note":"记得提前订蛋糕，TA最喜欢巧克力口味","confidence":0.85}}]"""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class HybridPriorityEngine:
    """Dual-layer priority scoring: fast rules + LLM calibration for edge cases.

    Phase 5 adds an intimate-relationship fast-path that unconditionally
    elevates events involving spouses / parents / children to P0, completely
    bypassing LLM calibration for those events.

    Usage::

        engine = HybridPriorityEngine(db=db)
        score = await engine.score(event_data, member_context, family_id, family_prefs)
        scores = await engine.score_batch(events_list, family_id, family_prefs)
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        model: Optional[str] = None,
        calibration_enabled: bool = True,
    ):
        self._db = db
        self._model = model or settings.intent_router_model
        self._calibration_enabled = calibration_enabled
        # Per-run in-memory cache: {event_id -> CalibrationResult}
        self._run_cache: Dict[str, CalibrationResult] = {}
        # Set per-batch by score_batch(); used by _call_calibration_llm
        self._family_ctx: Optional[FamilyRelationContext] = None

    def clear_run_cache(self) -> None:
        """Clear per-curation-run in-memory calibration cache."""
        self._run_cache = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score(
        self,
        event_data: Dict[str, Any],
        member_context: Optional[Dict[str, Any]],
        family_id: UUID,
        family_prefs: Optional[FamilyPreference] = None,
        person_profiles_summary: str = "",
        family_ctx: Optional[FamilyRelationContext] = None,
    ) -> EnhancedPriorityScore:
        """Score a single event through the hybrid pipeline."""
        results = await self.score_batch(
            [event_data],
            family_id,
            family_prefs=family_prefs,
            member_contexts=[member_context],
            person_profiles_summary=person_profiles_summary,
            family_ctx=family_ctx,
        )
        return results[0]

    async def score_batch(
        self,
        events: Sequence[Dict[str, Any]],
        family_id: UUID,
        family_prefs: Optional[FamilyPreference] = None,
        member_contexts: Optional[Sequence[Optional[Dict[str, Any]]]] = None,
        person_profiles_summary: str = "",
        family_ctx: Optional[FamilyRelationContext] = None,
    ) -> List[EnhancedPriorityScore]:
        """Score a batch of events.

        Args:
            events: Event dicts (must include ``event_id`` or ``id`` key).
            family_id: Family UUID for cache keying and preference lookup.
            family_prefs: Optional learned family preferences.
            member_contexts: Parallel list of member context dicts (or None).
            person_profiles_summary: Aggregated person profiles for LLM prompt.
            family_ctx: Pre-loaded family relationship context (avoids N+1 queries).

        Returns:
            Parallel list of ``EnhancedPriorityScore`` objects.
        """
        if member_contexts is None:
            member_contexts = [None] * len(events)

        # Store family_ctx for use in _call_calibration_llm
        self._family_ctx = family_ctx

        weights = (family_prefs.priority_weights or {}) if family_prefs else {}
        severity_overrides = (family_prefs.event_type_severity or {}) if family_prefs else {}

        # Step 0: Phase 5 – intimate-relationship fast-path check (no LLM)
        # Uses FamilyRelationContext when available; falls back to DB query
        intimate_results: Dict[int, EnhancedPriorityScore] = {}
        for i, event_data in enumerate(events):
            intimate_note = self._check_intimate_via_ctx(
                event_data, family_ctx,
            ) if family_ctx is not None else None

            # Fallback to DB query if no family_ctx provided
            if intimate_note is None and self._db is not None and family_ctx is None:
                intimate_note = await self._check_intimate_relationship_boost(
                    event_data, family_id,
                )

            if intimate_note is not None:
                p0_base = PriorityScore(
                    urgency=1.0,
                    severity=1.0,
                    stakeholder_weight=1.0,
                    irrecoverability=0.9,
                )
                intimate_results[i] = EnhancedPriorityScore(
                    base=p0_base,
                    calibration=None,
                    preparation_hours=_INTIMATE_PREP_HOURS.get(
                        event_data.get("event_type", ""), 24.0
                    ),
                    secretary_note=intimate_note,
                    fallback=False,
                )

        # Step 1: Rule-based fast scoring (skip intimate events)
        base_scores: List[PriorityScore] = []
        for i, (event_data, member_ctx) in enumerate(zip(events, member_contexts)):
            if i in intimate_results:
                # Placeholder; will be replaced by intimate result
                base_scores.append(intimate_results[i].base)
                continue
            enriched = _apply_severity_override(event_data, severity_overrides)
            base = compute_priority_score(enriched, member_ctx, weights=weights)
            base_scores.append(base)

        # Step 1.5: Cold-relationship irrecoverability boost (no LLM)
        # For intimate relations, remove composite >= 0.3 requirement (PLAN-002)
        if self._db is not None:
            for i, (base, event_data) in enumerate(zip(base_scores, events)):
                if i in intimate_results:
                    continue
                cold_boost = await self._check_cold_relationship_boost(
                    event_data, family_id,
                )
                if cold_boost is not None:
                    # Check if any member is intimate -- if so, skip composite gate
                    member_ids = event_data.get("member_ids") or []
                    is_intimate_event = (
                        family_ctx.has_any_intimate(member_ids)
                        if family_ctx is not None
                        else False
                    )
                    # Intimate relations: always boost; non-intimate: require composite >= 0.3
                    if is_intimate_event or base.composite >= 0.3:
                        boosted = PriorityScore(
                            urgency=base.urgency,
                            severity=base.severity,
                            stakeholder_weight=base.stakeholder_weight,
                            irrecoverability=min(1.0, base.irrecoverability + cold_boost),
                            w_urgency_override=base.w_urgency_override,
                            w_severity_override=base.w_severity_override,
                            w_stakeholder_override=base.w_stakeholder_override,
                            w_irrecoverability_override=base.w_irrecoverability_override,
                        )
                        base_scores[i] = boosted

        # Step 2: Identify events needing calibration (skip intimate events)
        needs_cal: List[int] = []
        if self._calibration_enabled:
            for i, (base, event_data) in enumerate(zip(base_scores, events)):
                if i in intimate_results:
                    continue
                if self._needs_calibration(base, event_data):
                    needs_cal.append(i)

        # Step 3: Batch-calibrate ambiguous events
        calibrations: Dict[int, CalibrationResult] = {}
        if needs_cal:
            cal_events = [events[i] for i in needs_cal]
            cal_results = await self._calibrate_batch(
                cal_events, family_id, family_prefs, person_profiles_summary,
            )
            for idx, cal in zip(needs_cal, cal_results):
                if cal is not None:
                    calibrations[idx] = cal

        # Step 4: Assemble enhanced scores
        results: List[EnhancedPriorityScore] = []
        for i, base in enumerate(base_scores):
            # Intimate fast-path takes absolute precedence
            if i in intimate_results:
                results.append(intimate_results[i])
                continue

            cal = calibrations.get(i)
            if cal is not None and cal.confidence >= MIN_CALIBRATION_CONFIDENCE:
                results.append(EnhancedPriorityScore(
                    base=base,
                    calibration=cal,
                    preparation_hours=cal.preparation_hours,
                    secretary_note=cal.secretary_note,
                    fallback=False,
                ))
            else:
                results.append(EnhancedPriorityScore(
                    base=base,
                    calibration=None,
                    preparation_hours=0.0,
                    secretary_note=None,
                    fallback=(i in needs_cal),
                ))

        return results

    # ------------------------------------------------------------------
    # Phase 5: Intimate-relationship unconditional P0 boost
    # ------------------------------------------------------------------

    async def _check_intimate_relationship_boost(
        self,
        event_data: Dict[str, Any],
        family_id: UUID,
    ) -> Optional[str]:
        """Check if event involves an intimate-relation member on an important date.

        Returns a secretary_note string when the event should be forced to P0,
        or None if the event proceeds through the normal scoring pipeline.

        An event qualifies when ALL of the following hold:
        1. ``event_type`` is in _IMPORTANT_DATE_EVENT_TYPES
           ("birthday", "anniversary", "family")
        2. ``member_ids`` in event_data contains at least one member whose
           MemberRelation.relation_type is in _INTIMATE_RELATION_TYPES

        The DB check is only attempted when a session is available; if not,
        None is returned so normal scoring applies.
        """
        event_type = event_data.get("event_type", "")
        if event_type not in _IMPORTANT_DATE_EVENT_TYPES:
            return None

        member_ids = event_data.get("member_ids") or []
        if not member_ids:
            return None

        # Normalise member_ids to a list of UUID strings
        member_id_list: List[str] = []
        for mid in member_ids:
            try:
                member_id_list.append(str(UUID(str(mid))))
            except (ValueError, AttributeError):
                pass

        if not member_id_list:
            return None

        try:
            intimate_info = await self._query_intimate_members(
                member_id_list, family_id,
            )
        except Exception:
            logger.warning(
                "Intimate relationship DB check failed for family %s", family_id,
                exc_info=True,
            )
            return None

        if not intimate_info:
            return None

        # Pick the highest-priority relationship type for the note
        relation_type, member_name = intimate_info[0]
        event_type_cn = _EVENT_TYPE_CN.get(event_type, event_type)
        note = _build_intimate_note(relation_type, event_type_cn, member_name)
        return note

    @staticmethod
    def _check_intimate_via_ctx(
        event_data: Dict[str, Any],
        family_ctx: FamilyRelationContext,
    ) -> Optional[str]:
        """Check intimate P0 using pre-loaded FamilyRelationContext.

        Uses the expanded _P0_INTIMATE_EVENT_TYPES set (PLAN-002).
        Returns a secretary_note when the event should be forced to P0.
        """
        event_type = event_data.get("event_type", "")
        if event_type not in _P0_INTIMATE_EVENT_TYPES:
            return None

        member_ids = event_data.get("member_ids") or []
        if not member_ids:
            return None

        intimate_info = family_ctx.first_intimate(member_ids)
        if intimate_info is None:
            return None

        event_type_cn = _EVENT_TYPE_CN.get(event_type, event_type)
        return _build_intimate_note(
            intimate_info.relation_type,
            event_type_cn,
            intimate_info.member_name,
        )

    async def _query_intimate_members(
        self,
        member_ids: List[str],
        family_id: UUID,
    ) -> List[tuple]:
        """Query MemberRelation for intimate-relation members.

        Returns list of (relation_type_value, member_name) tuples for matched
        members, sorted by a rough intimacy priority order.
        """
        # Late import to avoid circular dependencies at module load time
        from ...member.models.member import MemberRelation
        from ...member.models import Member

        uuid_list = [UUID(mid) for mid in member_ids]

        stmt = (
            select(MemberRelation.relation_type, Member.name)
            .join(Member, Member.id == MemberRelation.to_member_id)
            .where(
                MemberRelation.family_id == family_id,
                MemberRelation.to_member_id.in_(uuid_list),
                MemberRelation.relation_type.in_(list(_INTIMATE_RELATION_TYPES)),
            )
            .order_by(MemberRelation.intimacy_level.desc())
        )
        result = await self._db.execute(stmt)
        rows = result.all()
        return [
            (row[0].value if hasattr(row[0], "value") else str(row[0]), row[1] or "")
            for row in rows
        ]

    async def _check_cold_relationship_boost(
        self,
        event_data: Dict[str, Any],
        family_id: UUID,
    ) -> Optional[float]:
        """Check if event involves cold-relationship members warranting irrecoverability boost.

        Returns an irrecoverability boost delta (e.g. 0.15) when the event
        involves a cold/frozen-relationship member, or None otherwise.
        """
        member_ids = event_data.get("member_ids") or []
        if not member_ids:
            return None

        try:
            from ...member.models.member import MemberRelation
            from ...member.models import Member

            uuid_list = []
            for mid in member_ids:
                try:
                    uuid_list.append(UUID(str(mid)))
                except (ValueError, AttributeError):
                    pass
            if not uuid_list:
                return None

            # Check if any associated member has cold/frozen relationship
            stmt = (
                select(MemberRelation.relation_type, MemberRelation.intimacy_level)
                .where(
                    MemberRelation.family_id == family_id,
                    MemberRelation.to_member_id.in_(uuid_list),
                )
            )
            result = await self._db.execute(stmt)
            rows = result.all()
            for relation_type, intimacy_level in rows:
                rel_str = relation_type.value if hasattr(relation_type, "value") else str(relation_type)
                # Skip intimate relations (already handled by P0 fast-path)
                if rel_str in _INTIMATE_RELATION_TYPES:
                    continue
                # For non-intimate cold/frozen relations, boost irrecoverability
                if intimacy_level is not None and intimacy_level <= COLD_INTIMACY_THRESHOLD:
                    return COLD_RELATIONSHIP_BOOST_DELTA
            return None
        except Exception:
            logger.debug(
                "Cold relationship boost check failed for family %s",
                family_id, exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Calibration decision
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_calibration(score: PriorityScore, event_data: Dict[str, Any]) -> bool:
        """Return True if the event falls in the ambiguous zone or is highly connected.

        F3: Narrowed fuzzy band from [0.35, 0.65] to [0.42, 0.58] after
        adding interaction_bonus and association_bonus to the composite,
        reducing unnecessary LLM calibration calls.
        """
        composite = score.composite
        if 0.42 <= composite <= 0.58:
            return True
        if int(event_data.get("association_count", 0)) >= 3:
            return True
        return False

    # ------------------------------------------------------------------
    # LLM calibration
    # ------------------------------------------------------------------

    async def _calibrate_batch(
        self,
        events: Sequence[Dict[str, Any]],
        family_id: UUID,
        family_prefs: Optional[FamilyPreference],
        person_profiles_summary: str,
    ) -> List[Optional[CalibrationResult]]:
        """Calibrate events via Haiku, respecting batch size limits and caching."""
        results: List[Optional[CalibrationResult]] = [None] * len(events)

        # Check caches first (run cache)
        uncached_indices: List[int] = []
        for i, event in enumerate(events):
            eid = _event_id(event)
            cached = self._check_caches(eid, event, family_id)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)

        if not uncached_indices:
            return results

        # Try Redis for run-cache misses
        redis_hits: List[int] = []
        for i in uncached_indices:
            cached = await self._read_redis_cache(events[i], family_id)
            if cached is not None:
                eid = _event_id(events[i])
                results[i] = cached
                self._run_cache[eid] = cached
                redis_hits.append(i)
        for idx in redis_hits:
            uncached_indices.remove(idx)

        if not uncached_indices:
            return results

        # Batch into groups of MAX_BATCH_SIZE
        uncached_events = [events[i] for i in uncached_indices]
        for batch_start in range(0, len(uncached_events), MAX_BATCH_SIZE):
            batch = uncached_events[batch_start:batch_start + MAX_BATCH_SIZE]
            batch_indices = uncached_indices[batch_start:batch_start + MAX_BATCH_SIZE]
            cal_results = await self._call_calibration_llm(
                batch, family_prefs, person_profiles_summary,
            )
            for j, cal in enumerate(cal_results):
                global_idx = batch_indices[j]
                results[global_idx] = cal
                if cal is not None:
                    eid = _event_id(events[global_idx])
                    self._run_cache[eid] = cal
                    await self._write_redis_cache(
                        eid, events[global_idx], family_id, cal,
                    )

        return results

    def _check_caches(
        self, event_id: str, event_data: Dict[str, Any], family_id: UUID,
    ) -> Optional[CalibrationResult]:
        """Check per-run in-memory cache (Redis check is async, done separately)."""
        return self._run_cache.get(event_id)

    async def _read_redis_cache(
        self, event_data: Dict[str, Any], family_id: UUID,
    ) -> Optional[CalibrationResult]:
        """Try reading a cached calibration from Redis."""
        key = _redis_cache_key(event_data, family_id)
        raw = await redis_client.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return CalibrationResult(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    async def _write_redis_cache(
        self,
        event_id: str,
        event_data: Dict[str, Any],
        family_id: UUID,
        cal: CalibrationResult,
    ) -> None:
        """Cache calibration result in Redis with 24h TTL."""
        key = _redis_cache_key(event_data, family_id)
        payload = {
            "event_id": cal.event_id,
            "severity": cal.severity,
            "stakeholder": cal.stakeholder,
            "irrecoverability": cal.irrecoverability,
            "preparation_hours": cal.preparation_hours,
            "secretary_note": cal.secretary_note,
            "confidence": cal.confidence,
        }
        try:
            await redis_client.set(key, payload, ttl=CALIBRATION_CACHE_TTL)
        except Exception:
            logger.warning("Failed to write calibration cache for %s", event_id, exc_info=True)

    async def _call_calibration_llm(
        self,
        events: Sequence[Dict[str, Any]],
        family_prefs: Optional[FamilyPreference],
        person_profiles_summary: str,
    ) -> List[Optional[CalibrationResult]]:
        """Make a single Haiku call to calibrate up to MAX_BATCH_SIZE events.

        Returns a list parallel to *events*. ``None`` entries indicate
        parsing failures for that event (the rest are still usable).
        """
        events_for_prompt = []
        for e in events:
            entry: Dict[str, Any] = {
                "event_id": _event_id(e),
                "title": e.get("title", ""),
                "event_type": e.get("event_type", ""),
                "normalized_start": str(e.get("normalized_start", "")),
                "location": e.get("location", ""),
                "association_count": int(e.get("association_count", 0)),
                "priority": e.get("priority", "normal"),
            }
            # Enrich with relationship context (TC-3)
            member_ids = e.get("member_ids") or []
            if member_ids and self._family_ctx is not None:
                intimate_info = self._family_ctx.first_intimate(member_ids)
                if intimate_info is not None:
                    entry["is_family_member"] = True
                    entry["relationship_type"] = intimate_info.relation_type
                    entry["intimacy_level"] = intimate_info.intimacy_level
                else:
                    # Check if any member is known at all
                    for mid in member_ids:
                        rel = self._family_ctx.relation_type(
                            UUID(str(mid)) if isinstance(mid, str) else mid
                        )
                        if rel is not None:
                            entry["is_family_member"] = True
                            entry["relationship_type"] = rel
                            entry["intimacy_level"] = self._family_ctx.intimacy_level(
                                UUID(str(mid)) if isinstance(mid, str) else mid
                            )
                            break
            events_for_prompt.append(entry)

        pref_rules = _format_preference_rules(family_prefs)

        system_prompt = _CALIBRATION_SYSTEM_PROMPT.format(
            family_preference_rules=pref_rules,
            person_profiles_summary=person_profiles_summary or "无可用人物画像",
            events_json=json.dumps(events_for_prompt, ensure_ascii=False),
        )

        try:
            client = get_haiku_client()
            response = await client.messages.create(
                model=self._model,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": "请评估以上事件。"}],
            )

            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if not text_parts:
                raise ValueError("No TextBlock in calibration response")

            raw_text = text_parts[0].strip()
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
            raw_text = raw_text.strip()

            parsed = json.loads(raw_text)
            if not isinstance(parsed, list):
                parsed = [parsed]

            # Build lookup by event_id
            by_id: Dict[str, dict] = {}
            for item in parsed:
                eid = item.get("event_id", "")
                if eid:
                    by_id[eid] = item

            results: List[Optional[CalibrationResult]] = []
            for event in events:
                eid = _event_id(event)
                item = by_id.get(eid)
                if item is not None:
                    results.append(_parse_calibration(item))
                else:
                    results.append(None)

            return results

        except Exception:
            logger.warning(
                "Calibration LLM call failed for %d events, falling back to rules",
                len(events),
                exc_info=True,
            )
            return [None] * len(events)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_intimate_note(
    relation_type: str,
    event_type_cn: str,
    member_name: str,
) -> str:
    """Build a secretary note for an intimate-relationship P0 event."""
    name_part = f"「{member_name}」的" if member_name else "的"
    # Medical/health events get a different template
    if event_type_cn in ("就医", "体检"):
        if relation_type in ("spouse", "partner"):
            return f"配偶{name_part}{event_type_cn}，记得陪同并关注结果"
        if relation_type in ("father", "mother", "parent", "father_in_law", "mother_in_law", "parent_in_law"):
            return f"父母{name_part}{event_type_cn}，建议陪同前往并记录医嘱"
        if relation_type in ("son", "daughter", "child"):
            return f"子女{name_part}{event_type_cn}，记得全程陪伴"
        return f"亲密关系成员{name_part}{event_type_cn}，请关注并提供支持"
    if relation_type in ("spouse", "partner"):
        return f"配偶{name_part}{event_type_cn}，建议提前准备并预留陪伴时间"
    if relation_type in ("father", "mother", "parent", "father_in_law", "mother_in_law", "parent_in_law"):
        return f"父母{name_part}{event_type_cn}，建议提前安排礼物或祝福"
    if relation_type in ("son", "daughter", "child"):
        return f"子女{name_part}{event_type_cn}，建议全程陪伴"
    # Generic intimate relation fallback
    return f"亲密关系成员{name_part}{event_type_cn}，请优先关注"


def _event_id(event_data: Dict[str, Any]) -> str:
    """Extract a stable event identifier."""
    return str(event_data.get("event_id") or event_data.get("id", "unknown"))


def _redis_cache_key(event_data: Dict[str, Any], family_id: UUID) -> str:
    """Build Redis cache key including event_id and event_date for uniqueness.

    Previous key ``cal:priority:type:{event_type}:family:{id}`` caused cache
    poisoning when two events of the same type existed in the same family
    (e.g. two birthday events).  The new key adds ``event_id`` and
    ``event_date`` to guarantee per-event isolation.
    """
    event_type = event_data.get("event_type", "unknown")
    event_id = _event_id(event_data)
    raw_start = event_data.get("normalized_start") or event_data.get("event_date", "")
    event_date = str(raw_start)[:10] if raw_start else "nodate"
    return (
        f"{CALIBRATION_CACHE_PREFIX}:type:{event_type}"
        f":family:{family_id}:evt:{event_id}:d:{event_date}"
    )


def _apply_severity_override(
    event_data: Dict[str, Any], severity_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Return event_data with severity boosted if FamilyPreference overrides exist."""
    event_type = event_data.get("event_type")
    if event_type and event_type in severity_overrides:
        override_val = severity_overrides[event_type]
        # Translate FamilyPreference severity (0-1) into the priority string
        # that _score_severity() understands, boosting important types.
        if override_val >= 0.9:
            return {**event_data, "priority": "critical"}
        if override_val >= 0.7:
            return {**event_data, "priority": "high"}
    return event_data


def _format_preference_rules(family_prefs: Optional[FamilyPreference]) -> str:
    """Format FamilyPreference into a concise text block for the LLM prompt."""
    if family_prefs is None:
        return "无特殊偏好"

    parts: List[str] = []

    pw = family_prefs.priority_weights or {}
    if pw:
        parts.append(f"优先级权重: {json.dumps(pw, ensure_ascii=False)}")

    ets = family_prefs.event_type_severity or {}
    if ets:
        parts.append(f"事件类型严重度: {json.dumps(ets, ensure_ascii=False)}")

    bm = family_prefs.buffer_minutes or {}
    if bm:
        parts.append(f"缓冲时间偏好: {json.dumps(bm, ensure_ascii=False)}")

    st = family_prefs.suppressed_types or []
    if st:
        parts.append(f"已屏蔽推荐类型: {', '.join(st)}")

    return "\n".join(parts) if parts else "无特殊偏好"


def _parse_calibration(item: dict) -> Optional[CalibrationResult]:
    """Parse a single calibration result dict into a ``CalibrationResult``."""
    try:
        return CalibrationResult(
            event_id=str(item.get("event_id", "")),
            severity=_clamp(float(item.get("severity", 0.5))),
            stakeholder=_clamp(float(item.get("stakeholder", 0.5))),
            irrecoverability=_clamp(float(item.get("irrecoverability", 0.5))),
            preparation_hours=max(0.0, min(24.0, float(item.get("preparation_hours", 0)))),
            secretary_note=item.get("secretary_note"),
            confidence=_clamp(float(item.get("confidence", 0.5))),
        )
    except (TypeError, ValueError):
        logger.warning("Failed to parse calibration item: %s", item)
        return None


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
