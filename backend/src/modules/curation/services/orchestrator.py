"""Secretary orchestration layer -- structured day planning.

Transforms a flat list of curated events into a structured daily schedule
with buffer slots, gap warnings, secretary annotations, density scoring,
and a DayTheme that acts as the day's "attention navigator".

This is a **read-only** component: it never mutates curation data.
It runs at briefing time and produces an ``OrchestratedDay`` consumed
by the briefing/context layer.

Design doc: docs/secretary-intelligence-optimization.md section 3.2
"""

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_tz
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CuratedEvent, EventAssociation, FamilyPreference
from .context_enricher import ContextEnricher, EventContext
from .memory_engine import MemoryEngine
from .priority_engine import EnhancedPriorityScore, HybridPriorityEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures (all frozen / immutable)
# ---------------------------------------------------------------------------

_HIGH_INTENSITY_TYPES = frozenset({
    "meeting", "interview", "exam", "presentation", "business_trip",
})

# Meal windows: (start_hour, start_min, end_hour, end_min)
_MEAL_WINDOWS = [
    (12, 0, 13, 30),   # lunch
    (18, 0, 19, 30),   # dinner
]

# Days with fewer events than this are considered "light" (suitable for deferrals)
_LIGHT_DAY_THRESHOLD = 4

# Default buffer minutes (overridable via FamilyPreference.buffer_minutes)
_DEFAULT_BUFFERS = {
    "default": 15,
    "location_change": 45,
    "high_intensity": 20,
}


@dataclass(frozen=True)
class TimeSlot:
    """A block of time in the orchestrated day."""

    start: time
    end: time
    event_id: Optional[UUID] = None  # None for buffer / free slots
    slot_type: str = "event"         # event | buffer | travel | free | preparation
    note: Optional[str] = None       # secretary annotation


@dataclass(frozen=True)
class GapWarning:
    """A problematic gap between events."""

    gap_type: str  # no_buffer | impossible_commute | back_to_back | overloaded | meal_conflict
    affected_event_ids: Tuple[UUID, ...] = ()
    suggestion: Optional[str] = None


@dataclass(frozen=True)
class SecretaryAnnotation:
    """A contextual annotation attached to an event."""

    event_id: UUID
    text: str
    source: str = "context_enricher"  # context_enricher | priority_engine


@dataclass(frozen=True)
class PreparationItem:
    """A preparation task to schedule before an anchor event."""

    title: str
    duration_minutes: int
    note: Optional[str] = None


@dataclass(frozen=True)
class CascadeImpact:
    """Impact of a change on a single downstream event."""

    event_id: UUID
    event_title: str
    impact_type: str  # delayed | needs_reschedule | buffer_lost | cancelled | auto_cancel | auto_defer
    detail: str
    requires_user_decision: bool = False


@dataclass(frozen=True)
class CascadeAnalysis:
    """Result of analyzing a cascade of event changes."""

    changed_event_id: UUID
    change_type: str
    impacts: Tuple[CascadeImpact, ...] = ()
    summary: str = ""

    @property
    def requires_user_decision(self) -> bool:
        return any(i.requires_user_decision for i in self.impacts)


@dataclass(frozen=True)
class PreparationStep:
    """A single step in a preparation timeline."""

    text: str
    deadline: datetime
    suggested_start: datetime
    estimated_minutes: int
    note: Optional[str] = None


@dataclass(frozen=True)
class PreparationTimeline:
    """Reverse-engineered preparation schedule for an event."""

    anchor_event_id: UUID
    steps: Tuple[PreparationStep, ...] = ()


@dataclass(frozen=True)
class DayTheme:
    """Today's theme: determined by the headline event, organises others around it.

    Generated via pure rules (zero LLM cost) at orchestration time.
    Consumers should display ``title`` as the day banner and use
    ``focus`` / ``prep_note`` / ``evening_forward`` as supporting copy.
    """

    title: str                          # e.g. "上海客户拜访日"
    primary_event_id: Optional[UUID]    # anchor event UUID (may be None)
    focus: str                          # e.g. "下午3点与张总签约是关键节点"
    prep_note: Optional[str] = None     # e.g. "建议上午回顾合同要点"
    evening_forward: Optional[str] = None  # next-day warning, e.g. "明早6点航班"


@dataclass(frozen=True)
class DeferralSuggestion:
    """A suggestion to defer a low-priority event to reduce daily load (E5)."""

    event_id: UUID
    event_title: str
    reason: str
    suggested_new_date: Optional[date] = None
    priority_level: str = "P3"


@dataclass(frozen=True)
class OrchestratedDay:
    """The fully orchestrated schedule for a single day."""

    target_date: date
    slots: Tuple[TimeSlot, ...] = ()
    gaps: Tuple[GapWarning, ...] = ()
    annotations: Tuple[SecretaryAnnotation, ...] = ()
    density_score: float = 0.0       # 0-1, higher = busier
    suggested_reorder: Optional[Tuple[UUID, ...]] = None
    day_theme: Optional[DayTheme] = None  # Phase 4: attention navigation theme
    deferral_suggestions: Tuple[DeferralSuggestion, ...] = ()  # E5: active load reduction


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class SecretaryOrchestrator:
    """Transform flat event lists into structured daily schedules.

    Pure read-path component.  Integrates with:
    - ``HybridPriorityEngine`` for enhanced priority scores
    - ``ContextEnricher`` (previously unused) for secretary annotations

    Usage::

        orch = SecretaryOrchestrator(db, priority_engine)
        day = await orch.orchestrate_day(family_id, user_id, target, events, prefs)
    """

    def __init__(
        self,
        db: AsyncSession,
        priority_engine: HybridPriorityEngine,
    ):
        self._db = db
        self._priority_engine = priority_engine
        self._enricher = ContextEnricher(db, MemoryEngine(db))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def orchestrate_day(
        self,
        family_id: UUID,
        user_id: UUID,
        target_date: date,
        events: Sequence[CuratedEvent],
        family_prefs: Optional[FamilyPreference] = None,
        person_profiles_summary: str = "",
        next_day_events: Optional[List[CuratedEvent]] = None,
    ) -> OrchestratedDay:
        """Orchestrate a full day schedule.

        Steps:
        1. Score events via HybridPriorityEngine
        2. Sort by start time (priority-weighted for ties)
        3. Insert buffer / travel slots
        4. Detect gap problems
        5. Generate secretary annotations via ContextEnricher
        6. Compute density_score
        7. Suggest reorder when density > 0.8
        8. Generate DayTheme (pure rules, zero LLM cost)

        Args:
            next_day_events: Events from the following day used to generate
                ``evening_forward`` warnings (e.g. early-morning flights).
        """
        if not events:
            return OrchestratedDay(target_date=target_date)

        # Step 1: Score all events (parallel DB loads)
        association_counts, event_member_ids = await asyncio.gather(
            self._load_association_counts(events),
            self._load_event_member_ids(events),
        )
        event_dicts = [
            _event_to_dict(
                e,
                association_counts.get(e.id, 0),
                member_ids=event_member_ids.get(e.id),
            )
            for e in events
        ]
        scores = await self._priority_engine.score_batch(
            event_dicts,
            family_id,
            family_prefs=family_prefs,
            person_profiles_summary=person_profiles_summary,
        )
        scored = list(zip(events, scores))

        # Step 2: Sort by start time, break ties by composite score (desc)
        scored.sort(key=lambda pair: (
            pair[0].normalized_start or datetime.min.replace(tzinfo=None),
            -pair[1].composite,
        ))

        # Resolve buffer configuration (E5: apply fatigue multiplier)
        buffers = _resolve_buffers(family_prefs)
        fatigue_multiplier = self._compute_fatigue_multiplier(family_prefs)

        # Resolve meal windows (supports FamilyPreference-based personalisation)
        meal_windows = self._resolve_meal_windows(family_prefs)

        # Step 3: Build time slots with buffers
        slots: List[TimeSlot] = []
        gaps: List[GapWarning] = []

        for i, (event, enh_score) in enumerate(scored):
            ev_start = _extract_time(event.normalized_start)
            ev_end = _extract_time(event.normalized_end) or _default_end(ev_start)
            if ev_start is None:
                continue

            # Insert buffer between consecutive events
            if i > 0:
                prev_event, prev_score = scored[i - 1]
                prev_end = _extract_time(prev_event.normalized_end) or _default_end(
                    _extract_time(prev_event.normalized_start)
                )
                if prev_end is not None:
                    # E5: Count consecutive high-intensity events preceding
                    # this slot for buffer escalation
                    consecutive_hi = 0
                    for j in range(i - 1, -1, -1):
                        if scored[j][0].event_type in _HIGH_INTENSITY_TYPES:
                            consecutive_hi += 1
                        else:
                            break

                    gap_info = _compute_gap(
                        prev_event, event, prev_end, ev_start, buffers,
                        meal_windows, consecutive_high_intensity=consecutive_hi,
                        fatigue_multiplier=fatigue_multiplier,
                    )
                    if gap_info.buffer_slot is not None:
                        slots.append(gap_info.buffer_slot)
                    if gap_info.warning is not None:
                        gaps.append(gap_info.warning)

            # Event slot
            note = enh_score.secretary_note
            slots.append(TimeSlot(
                start=ev_start,
                end=ev_end,
                event_id=event.id,
                slot_type="event",
                note=note,
            ))

            # E5: Detect meal_conflict when an event fully spans a meal window
            if ev_end is not None:
                for meal_warn in _check_meal_conflicts(event, ev_start, ev_end, meal_windows):
                    gaps.append(meal_warn)

        # Step 4: Annotations via ContextEnricher (parallel) + priority engine
        annotations: List[SecretaryAnnotation] = []

        # Priority engine annotations (already available, no I/O)
        for event, enh_score in scored:
            if enh_score.secretary_note:
                annotations.append(SecretaryAnnotation(
                    event_id=event.id,
                    text=enh_score.secretary_note,
                    source="priority_engine",
                ))

        # Context enrichment in parallel
        async def _enrich_one(ev: CuratedEvent) -> List[SecretaryAnnotation]:
            try:
                ctx = await self._enricher.enrich_event(ev, family_id)
                return [
                    SecretaryAnnotation(event_id=ev.id, text=t, source="context_enricher")
                    for t in _extract_annotation_texts(ctx)
                ]
            except Exception:
                logger.debug("ContextEnricher failed for event %s", ev.id, exc_info=True)
                return []

        enrichment_results = await asyncio.gather(
            *[_enrich_one(ev) for ev, _ in scored],
            return_exceptions=True,
        )
        for result in enrichment_results:
            if isinstance(result, list):
                annotations.extend(result)

        # Step 5: Density score
        density = _compute_density(scored, target_date)

        # Step 6: Overload warnings + reorder suggestions
        if density > 0.8 and len(scored) > 3:
            gaps.append(GapWarning(
                gap_type="overloaded",
                affected_event_ids=tuple(e.id for e, _ in scored),
                suggestion="今天安排得很满，记得中间留时间吃饭休息，别把自己累坏了。",
            ))

        suggested_reorder = None
        if density > 0.8:
            suggested_reorder = _suggest_reorder(scored)

        # Step 6.5: Generate deferral suggestions for overloaded days (E5)
        deferral_suggestions: Tuple[DeferralSuggestion, ...] = ()
        if density > 0.7:
            deferral_suggestions = await self._generate_deferral_suggestions(
                scored, density, family_prefs,
                target_date=target_date,
                family_id=family_id,
            )

        # Step 7: Generate DayTheme (pure rules, no LLM)
        # Load fatigue state and stress for theme integration (PLAN-008)
        fatigue_state = None
        stress_score = 0.0
        if family_prefs is not None:
            fatigue_state = getattr(family_prefs, "fatigue_state", None) or {}
            if isinstance(fatigue_state, dict):
                stress_score = fatigue_state.get("stress_score_7d", 0.0)

        day_theme = self._generate_day_theme(
            events=list(events),
            scores=scores,
            density_score=density,
            next_day_events=next_day_events,
            fatigue_state=fatigue_state,
            stress_score=stress_score,
        )

        return OrchestratedDay(
            target_date=target_date,
            slots=tuple(slots),
            gaps=tuple(gaps),
            annotations=tuple(annotations),
            density_score=round(density, 3),
            suggested_reorder=suggested_reorder,
            day_theme=day_theme,
            deferral_suggestions=deferral_suggestions,
        )

    # ------------------------------------------------------------------
    # E5: Active load reduction (deferral suggestions + fatigue multiplier)
    # ------------------------------------------------------------------

    _UNDEFERRABLE_TYPES = frozenset({
        "pickup_child", "medical_appointment", "flight",
        "exam", "interview", "birthday", "anniversary",
    })

    async def _generate_deferral_suggestions(
        self,
        scored: List[Tuple[CuratedEvent, EnhancedPriorityScore]],
        density: float,
        family_prefs: Optional[FamilyPreference],
        target_date: Optional[date] = None,
        family_id: Optional[UUID] = None,
    ) -> Tuple[DeferralSuggestion, ...]:
        """Generate suggestions to defer low-priority events (E5).

        Pure rules, zero LLM cost.  Only called when ``density > 0.7``.
        Populates ``suggested_new_date`` via ``_find_next_light_day()``.
        """
        candidates = [
            (ev, sc) for ev, sc in scored
            if sc.priority_level in ("P2", "P3")
            and ev.event_type not in self._UNDEFERRABLE_TYPES
        ]

        if not candidates:
            return ()

        # Call _find_next_light_day once and reuse for all candidates
        suggested_new_date = None
        if target_date is not None and family_id is not None:
            exclude_event_ids = [ev.id for ev, _ in candidates]
            suggested_new_date = await self._find_next_light_day(
                target_date, family_id, exclude_event_ids=exclude_event_ids,
            )

        suggestions: List[DeferralSuggestion] = []
        for event, score in candidates[:2]:  # Max 2 suggestions per day
            suggestions.append(DeferralSuggestion(
                event_id=event.id,
                event_title=event.title,
                reason=f"今日日程较满(密度{density:.0%})，建议推迟",
                suggested_new_date=suggested_new_date,
                priority_level=score.priority_level,
            ))

        return tuple(suggestions)

    async def _find_next_light_day(
        self,
        target_date: date,
        family_id: UUID,
        exclude_event_ids: Optional[List[UUID]] = None,
    ) -> Optional[date]:
        """Find the next day with low event density for deferral (E5).

        Uses a single GROUP BY query to scan 7 days after ``target_date``.
        Returns the first day with fewer than ``_LIGHT_DAY_THRESHOLD``
        events, or ``None`` if no light day is found.
        """
        all_start = datetime.combine(
            target_date + timedelta(days=1), time.min, tzinfo=dt_tz.utc,
        )
        all_end = datetime.combine(
            target_date + timedelta(days=8), time.min, tzinfo=dt_tz.utc,
        )

        day_trunc = func.date_trunc(literal_column("'day'"), CuratedEvent.normalized_start)
        stmt = (
            select(
                day_trunc.label('day'),
                func.count(CuratedEvent.id).label('cnt'),
            )
            .where(
                CuratedEvent.family_id == family_id,
                CuratedEvent.normalized_start >= all_start,
                CuratedEvent.normalized_start < all_end,
                CuratedEvent.status != "cancelled",
            )
            .group_by(day_trunc)
        )
        if exclude_event_ids:
            stmt = stmt.where(CuratedEvent.id.not_in(exclude_event_ids))

        result = await self._db.execute(stmt)
        day_counts: Dict[date, int] = {}
        for row in result:
            day_key = row.day.date() if hasattr(row.day, 'date') else row.day
            day_counts[day_key] = row.cnt

        for offset in range(1, 8):
            candidate = target_date + timedelta(days=offset)
            if day_counts.get(candidate, 0) < _LIGHT_DAY_THRESHOLD:
                return candidate

        return None  # No light day found in the next 7 days

    @staticmethod
    def _compute_fatigue_multiplier(
        family_prefs: Optional[FamilyPreference],
    ) -> float:
        """Compute buffer expansion factor from fatigue state (E5).

        Pure rules, zero LLM cost.  Returns 1.0-1.5.
        """
        if family_prefs is None:
            return 1.0
        fatigue = getattr(family_prefs, "fatigue_state", None) or {}
        if not isinstance(fatigue, dict):
            return 1.0

        base = 1.0
        # Consecutive high-density days increase buffer
        consecutive_days = fatigue.get("consecutive_high_density_days", 0)
        if consecutive_days >= 3:
            base += 0.25
        # Recent health-negative signals increase buffer
        health_neg = fatigue.get("health_negative_7d", 0)
        if health_neg >= 2:
            base += 0.2

        return min(base, 1.5)  # Cap at 50% increase

    # ------------------------------------------------------------------
    # DayTheme generation (Phase 4 – pure rules, zero LLM cost)
    # ------------------------------------------------------------------

    def _generate_day_theme(
        self,
        events: List[CuratedEvent],
        scores: List[EnhancedPriorityScore],
        density_score: float,
        next_day_events: Optional[List[CuratedEvent]] = None,
        fatigue_state: Optional[Dict] = None,
        stress_score: float = 0.0,
    ) -> Optional[DayTheme]:
        """Generate today's theme via pure rules.

        Priority order:
        1. Trip day  → theme = trip name, anchor = highest-scored trip event
        2. P0/P1 event present → theme = event title, anchor = top event
        3. High density (>0.8) → theme = "高密度工作日"
        4. Otherwise → None (normal list display)

        Fatigue/stress sub-themes COMPLEMENT (not suppress) the primary theme:
        - 2+ consecutive high-intensity days → buffer time sub-theme (TC-9)
        - stress_score >= 0.6 → self-care sub-theme (PC-5)
        """
        if not events:
            return None

        evening_forward = self._build_evening_forward(next_day_events)

        # Build fatigue/stress sub-theme (NR-3: complement, not suppress)
        fatigue_sub_theme = self._build_fatigue_sub_theme(
            fatigue_state, stress_score,
        )

        scored_pairs = list(zip(events, scores))

        # Rule 1: Trip events take priority
        trip_pairs = [(e, s) for e, s in scored_pairs if e.trip_id is not None]
        if trip_pairs:
            best_event, best_score = max(trip_pairs, key=lambda p: p[1].composite)
            trip_name = best_event.trip_name or best_event.title
            prep_note = self._merge_prep_and_fatigue(
                self._build_prep_note(best_event, best_score), fatigue_sub_theme,
            )
            return DayTheme(
                title=trip_name,
                primary_event_id=best_event.id,
                focus=f"今天的重点：{best_event.title}，出门前检查一下东西带齐了没。",
                prep_note=prep_note,
                evening_forward=evening_forward,
            )

        # Rule 1.5: Family/life event day — birthday, anniversary, holiday
        family_event_types = {"birthday", "anniversary", "holiday"}
        family_pairs = [
            (e, s) for e, s in scored_pairs
            if e.event_type in family_event_types
        ]
        if family_pairs:
            best_event, best_score = max(family_pairs, key=lambda p: p[1].composite)
            focus = self._build_family_focus_text(best_event)
            prep_note = self._merge_prep_and_fatigue(
                self._build_prep_note(best_event, best_score), fatigue_sub_theme,
            )
            return DayTheme(
                title=best_event.title,
                primary_event_id=best_event.id,
                focus=focus,
                prep_note=prep_note,
                evening_forward=evening_forward,
            )

        # Rule 2: P0 or P1 event present
        top_pair = max(scored_pairs, key=lambda p: p[1].composite)
        top_event, top_score = top_pair
        if top_score.priority_level in ("P0", "P1"):
            prep_note = self._merge_prep_and_fatigue(
                self._build_prep_note(top_event, top_score), fatigue_sub_theme,
            )
            return DayTheme(
                title=top_event.title,
                primary_event_id=top_event.id,
                focus=self._build_focus_text(top_event, top_score),
                prep_note=prep_note,
                evening_forward=evening_forward,
            )

        # Rule 3: High-density day without a dominant event
        if density_score > 0.8:
            low_priority_pairs = sorted(
                [(e, s) for e, s in scored_pairs if s.priority_level in ("P2", "P3")],
                key=lambda p: p[1].composite,
            )
            low_priority_events = [e.title for e, _ in low_priority_pairs]
            focus = "今天事情比较多，先把重要的做完，不急的可以往后放放。"
            prep_note = "记得中间留时间吃饭、喝水，别一直忙着忘了照顾自己。"
            if low_priority_events:
                titles = "、".join(low_priority_events[:2])
                prep_note = f"「{titles}」不急的话可以改天再说，今天别把自己累着了。"
            prep_note = self._merge_prep_and_fatigue(prep_note, fatigue_sub_theme)
            return DayTheme(
                title="忙碌的一天",
                primary_event_id=None,
                focus=focus,
                prep_note=prep_note,
                evening_forward=evening_forward,
            )

        # Rule 4: Light/free day — encourage family time or self-care
        if len(events) <= 2 and density_score < 0.3:
            return DayTheme(
                title="轻松的一天",
                primary_event_id=None,
                focus="今天没什么紧急的事，趁机陪陪家人，或者给自己放松一下。",
                prep_note=fatigue_sub_theme,  # Only fatigue note if present
                evening_forward=evening_forward,
            )

        # If only evening_forward is present, still surface it without a theme
        if evening_forward:
            return DayTheme(
                title="明天有事要留意",
                primary_event_id=None,
                focus="今天日程平稳，看看明天的安排提前做好准备。",
                prep_note=None,
                evening_forward=evening_forward,
            )

        return None

    @staticmethod
    def _build_focus_text(event: CuratedEvent, score: EnhancedPriorityScore) -> str:
        """Build a concise focus sentence for a high-priority event."""
        if event.normalized_start:
            t = event.normalized_start.strftime("%H:%M")
            return f"{t} 有「{event.title}」，这是今天最重要的事，别忘了。"
        return f"「{event.title}」是今天最重要的事。"

    @staticmethod
    def _build_family_focus_text(event: CuratedEvent) -> str:
        """Build a warm focus sentence for family/life events."""
        event_type = event.event_type or ""
        if event_type == "birthday":
            return f"今天是{event.title}，记得送上祝福，让TA感受到你的心意。"
        if event_type == "anniversary":
            return f"今天是{event.title}，好好珍惜这个特别的日子。"
        if event_type == "holiday":
            return f"今天是{event.title}，和家人一起好好过节吧。"
        return f"今天有「{event.title}」，用心对待这个特别的日子。"

    @staticmethod
    def _build_prep_note(event: CuratedEvent, score: EnhancedPriorityScore) -> Optional[str]:
        """Build a preparation note if the event has estimated prep time."""
        event_type = event.event_type or ""
        hours = score.preparation_hours
        if hours and hours > 0:
            if hours >= 2:
                return f"记得提前 {int(hours)} 小时准备「{event.title}」的东西。"
            return f"提前 {int(hours * 60)} 分钟把「{event.title}」的事情准备好。"
        if event_type in ("meeting", "presentation", "interview"):
            return f"出发前把「{event.title}」相关的东西过一遍。"
        if event_type == "birthday":
            return "礼物和祝福准备好了吗？还来得及。"
        if event_type == "anniversary":
            return "想好怎么庆祝了吗？用点心，TA会很开心的。"
        if event_type in ("travel", "business_trip"):
            return "出门前检查一下证件和行李，别落东西。"
        return None

    @staticmethod
    def _build_evening_forward(
        next_day_events: Optional[List[CuratedEvent]],
    ) -> Optional[str]:
        """Return a warning string if tomorrow has early-morning events (before 08:00)."""
        if not next_day_events:
            return None
        early_events = [
            e for e in next_day_events
            if e.normalized_start and e.normalized_start.hour < 8
        ]
        if not early_events:
            return None
        earliest = min(early_events, key=lambda e: e.normalized_start)
        t = earliest.normalized_start.strftime("%H:%M")
        return f"明早 {t} 有「{earliest.title}」，今晚早点休息，东西提前收拾好。"

    # ------------------------------------------------------------------
    # Fatigue/stress sub-theme helpers (PLAN-008)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fatigue_sub_theme(
        fatigue_state: Optional[Dict],
        stress_score: float = 0.0,
    ) -> Optional[str]:
        """Build a fatigue/stress sub-theme string.

        Conditions (TC-9, PC-5):
        - 2+ consecutive high-intensity days -> buffer time advice
        - stress_score >= 0.6 -> self-care advice
        - Both -> combined theme
        """
        if fatigue_state is None:
            fatigue_state = {}

        consecutive_days = fatigue_state.get("consecutive_high_density_days", 0)
        has_fatigue = consecutive_days >= 2
        has_stress = stress_score >= 0.6

        if has_fatigue and has_stress:
            return "连续忙碌的日子，最近压力也不小，今天尽量留些时间照顾好自己。"
        if has_fatigue:
            return "连续忙碌的日子，今天尽量留些缓冲时间。"
        if has_stress:
            return "最近压力有点大，记得照顾好自己。"
        return None

    @staticmethod
    def _merge_prep_and_fatigue(
        prep_note: Optional[str],
        fatigue_sub_theme: Optional[str],
    ) -> Optional[str]:
        """Merge preparation note and fatigue sub-theme (NR-3: complement)."""
        if prep_note and fatigue_sub_theme:
            return f"{prep_note} {fatigue_sub_theme}"
        return prep_note or fatigue_sub_theme

    # ------------------------------------------------------------------
    # Meal window resolution (Phase 6 readiness)
    # ------------------------------------------------------------------

    def _resolve_meal_windows(
        self,
        family_prefs: Optional[Any],
    ) -> List[Tuple]:
        """Return personalised meal windows from FamilyPreference, or global defaults.

        The ``inferred_meal_windows`` JSONB field on FamilyPreference is expected to
        contain ``{"lunch": [start_h, start_m, end_h, end_m], "dinner": [...]}``
        once Phase 6 (meal_window_service) populates it.  Until then, the global
        ``_MEAL_WINDOWS`` constant acts as the cold-start fallback.
        """
        if (
            family_prefs is not None
            and hasattr(family_prefs, "inferred_meal_windows")
            and family_prefs.inferred_meal_windows
        ):
            windows: List[Tuple] = []
            lunch = family_prefs.inferred_meal_windows.get("lunch")
            dinner = family_prefs.inferred_meal_windows.get("dinner")
            if lunch:
                windows.append(tuple(lunch))
            if dinner:
                windows.append(tuple(dinner))
            if windows:
                return windows
        return list(_MEAL_WINDOWS)

    # ------------------------------------------------------------------
    # Association count loader
    # ------------------------------------------------------------------

    async def _load_association_counts(
        self,
        events: Sequence[CuratedEvent],
    ) -> Dict[UUID, int]:
        """Load association counts in one query to avoid async lazy-load issues."""
        event_ids = [e.id for e in events if e.id is not None]
        if not event_ids:
            return {}

        stmt = (
            select(
                EventAssociation.source_event_id,
                func.count(EventAssociation.id),
            )
            .where(EventAssociation.source_event_id.in_(event_ids))
            .group_by(EventAssociation.source_event_id)
        )
        result = await self._db.execute(stmt)
        rows = result.all()
        if inspect.isawaitable(rows):
            rows = await rows
        return {event_id: int(count) for event_id, count in rows}

    async def _load_event_member_ids(
        self,
        events: Sequence[CuratedEvent],
    ) -> Dict[UUID, List[str]]:
        """Load member IDs associated with events (target_type='person')."""
        event_ids = [e.id for e in events if e.id is not None]
        if not event_ids:
            return {}

        stmt = (
            select(
                EventAssociation.source_event_id,
                EventAssociation.target_id,
            )
            .where(
                EventAssociation.source_event_id.in_(event_ids),
                EventAssociation.target_type == "person",
            )
        )
        result = await self._db.execute(stmt)
        rows = result.all()
        if inspect.isawaitable(rows):
            rows = await rows
        mapping: Dict[UUID, List[str]] = {}
        for event_id, target_id in rows:
            mapping.setdefault(event_id, []).append(str(target_id))
        return mapping

    # ------------------------------------------------------------------
    # Cascade analysis
    # ------------------------------------------------------------------

    async def analyze_cascade(
        self,
        changed_event: CuratedEvent,
        change_type: str,
        change_detail: Dict[str, Any],
        affected_events: Sequence[CuratedEvent],
    ) -> CascadeAnalysis:
        """Analyze the downstream impact of an event change.

        E1 enhancement: priority-based routing. P0/P1 (critical/high) events
        require user decision; P2/P3 (normal/low) events are auto-handled.

        Args:
            changed_event: The event that changed.
            change_type: One of ``delayed``, ``cancelled``,
                ``location_changed``, ``time_changed``.
            change_detail: Extra info (e.g. ``{"delay_minutes": 120}``).
            affected_events: Events on the same day that might be impacted.
        """
        impacts: List[CascadeImpact] = []

        if change_type == "cancelled":
            for ev in affected_events:
                if ev.trip_id and ev.trip_id == changed_event.trip_id:
                    # Priority-based routing: P0/P1 need user decision,
                    # P2/P3 auto-handle
                    event_priority = getattr(ev, "priority", "normal")
                    requires_decision = event_priority in ("critical", "high")
                    if requires_decision:
                        impact_type = "needs_reschedule"
                        detail = (
                            f"同行程事件「{ev.title}」需要确认是否调整"
                        )
                    else:
                        impact_type = "auto_cancel"
                        detail = (
                            f"同行程事件「{ev.title}」已自动取消"
                        )
                    impacts.append(CascadeImpact(
                        event_id=ev.id,
                        event_title=ev.title,
                        impact_type=impact_type,
                        detail=detail,
                        requires_user_decision=requires_decision,
                    ))

        elif change_type == "delayed":
            delay_min = int(change_detail.get("delay_minutes", 0))
            if delay_min <= 0:
                return CascadeAnalysis(
                    changed_event_id=changed_event.id,
                    change_type=change_type,
                    summary="延误时间不明确",
                )

            ch_end = changed_event.normalized_end
            if ch_end is not None:
                new_end = ch_end + timedelta(minutes=delay_min)
                for ev in affected_events:
                    if ev.normalized_start and ev.normalized_start < new_end:
                        gap_min = (
                            ev.normalized_start - new_end
                        ).total_seconds() / 60
                        if gap_min < 0:
                            # Priority-based routing for overlapping events
                            event_priority = getattr(
                                ev, "priority", "normal",
                            )
                            requires_decision = event_priority in (
                                "critical", "high",
                            )
                            impacts.append(CascadeImpact(
                                event_id=ev.id,
                                event_title=ev.title,
                                impact_type=(
                                    "delayed" if requires_decision
                                    else "auto_defer"
                                ),
                                detail=(
                                    f"延误{delay_min}分钟后与"
                                    f"「{ev.title}」冲突，"
                                    f"重叠{abs(int(gap_min))}分钟"
                                ),
                                requires_user_decision=requires_decision,
                            ))
                        elif gap_min < 15:
                            impacts.append(CascadeImpact(
                                event_id=ev.id,
                                event_title=ev.title,
                                impact_type="buffer_lost",
                                detail=(
                                    f"延误后与「{ev.title}」"
                                    f"间隔仅{int(gap_min)}分钟"
                                ),
                                requires_user_decision=False,
                            ))

        elif change_type in ("location_changed", "time_changed"):
            for ev in affected_events:
                impacts.append(CascadeImpact(
                    event_id=ev.id,
                    event_title=ev.title,
                    impact_type="needs_reschedule",
                    detail=(
                        f"「{changed_event.title}」变更后，"
                        f"请确认「{ev.title}」是否受影响"
                    ),
                    requires_user_decision=True,
                ))

        n = len(impacts)
        summary = (
            f"「{changed_event.title}」{_change_type_label(change_type)}，"
            f"影响 {n} 个后续事件" if n else
            f"「{changed_event.title}」{_change_type_label(change_type)}，无级联影响"
        )

        return CascadeAnalysis(
            changed_event_id=changed_event.id,
            change_type=change_type,
            impacts=tuple(impacts),
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Preparation timeline
    # ------------------------------------------------------------------

    async def build_preparation_timeline(
        self,
        anchor_event: CuratedEvent,
        preparation_items: Sequence[PreparationItem],
    ) -> PreparationTimeline:
        """Build a reverse-engineered preparation timeline.

        Works backwards from the event start time, placing each preparation
        item at a suggested time with a 10-minute buffer between steps.
        """
        if not anchor_event.normalized_start:
            return PreparationTimeline(anchor_event_id=anchor_event.id)

        anchor_start = anchor_event.normalized_start
        steps: List[PreparationStep] = []
        cursor = anchor_start

        # Sort by duration descending so bigger tasks get earlier slots
        sorted_items = sorted(
            preparation_items,
            key=lambda p: p.duration_minutes,
            reverse=True,
        )

        for item in sorted_items:
            duration = item.duration_minutes or 30
            buffer = 10
            deadline = cursor - timedelta(minutes=buffer)
            suggested = deadline - timedelta(minutes=duration)
            steps.append(PreparationStep(
                text=item.title,
                deadline=deadline,
                suggested_start=suggested,
                estimated_minutes=duration,
                note=item.note,
            ))
            cursor = suggested

        # Reverse so the list reads earliest-first
        steps.reverse()
        return PreparationTimeline(
            anchor_event_id=anchor_event.id,
            steps=tuple(steps),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@dataclass
class _GapResult:
    buffer_slot: Optional[TimeSlot] = None
    warning: Optional[GapWarning] = None


def _resolve_buffers(family_prefs: Optional[FamilyPreference]) -> Dict[str, int]:
    """Merge default buffers with family preference overrides."""
    base = dict(_DEFAULT_BUFFERS)
    if family_prefs and family_prefs.buffer_minutes:
        base = {**base, **family_prefs.buffer_minutes}
    return base


def _event_to_dict(
    event: CuratedEvent,
    association_count: int,
    member_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convert a CuratedEvent ORM object to a dict for the priority engine."""
    return {
        "event_id": str(event.id),
        "title": event.title,
        "event_type": event.event_type,
        "normalized_start": event.normalized_start,
        "normalized_end": event.normalized_end,
        "location": event.location,
        "priority": event.priority,
        "association_count": association_count,
        "has_booking": event.event_type in ("flight", "business_trip", "travel"),
        "member_ids": member_ids or [],
    }


def _extract_time(dt: Optional[datetime]) -> Optional[time]:
    if dt is None:
        return None
    return dt.time()


def _default_end(start: Optional[time]) -> Optional[time]:
    """Assume 1-hour duration if end time is missing."""
    if start is None:
        return None
    dt = datetime.combine(date.today(), start) + timedelta(hours=1)
    return dt.time()


def _compute_gap(
    prev_event: CuratedEvent,
    next_event: CuratedEvent,
    prev_end: time,
    next_start: time,
    buffers: Dict[str, int],
    meal_windows: Optional[List[Tuple]] = None,
    consecutive_high_intensity: int = 0,
    fatigue_multiplier: float = 1.0,
) -> _GapResult:
    """Determine what buffer/warning to insert between two consecutive events."""
    gap_minutes = _time_diff_minutes(prev_end, next_start)

    # Determine required buffer
    location_changed = (
        prev_event.location and next_event.location
        and prev_event.location != next_event.location
    )
    prev_is_intense = prev_event.event_type in _HIGH_INTENSITY_TYPES

    if location_changed:
        required = buffers.get("location_change", 45)
        slot_type = "travel"
    elif prev_is_intense:
        required = buffers.get("high_intensity", 20)
        slot_type = "buffer"
    else:
        required = buffers.get("default", 15)
        slot_type = "buffer"

    # E5: Apply fatigue multiplier to expand buffers on fatigued days
    if fatigue_multiplier > 1.0:
        required = int(required * fatigue_multiplier)

    # E5: Consecutive high-intensity buffer escalation
    if consecutive_high_intensity >= 3:
        required = int(required * 1.5)
    elif consecutive_high_intensity >= 2:
        required = int(required * 1.3)

    if gap_minutes <= 0:
        # Events overlap or are back-to-back
        warning = GapWarning(
            gap_type="back_to_back",
            affected_event_ids=(prev_event.id, next_event.id),
            suggestion=f"「{prev_event.title}」和「{next_event.title}」之间没有间隔",
        )
        return _GapResult(warning=warning)

    if gap_minutes < required:
        note = f"{int(gap_minutes)}分钟间隔（建议{required}分钟）"
        buffer_slot = TimeSlot(
            start=prev_end,
            end=next_start,
            slot_type=slot_type,
            note=note,
        )
        gap_type = "impossible_commute" if location_changed else "no_buffer"
        suggestion = (
            f"「{prev_event.title}」到「{next_event.title}」"
            f"间隔{int(gap_minutes)}分钟不足（需{required}分钟）"
        )
        warning = GapWarning(
            gap_type=gap_type,
            affected_event_ids=(prev_event.id, next_event.id),
            suggestion=suggestion,
        )
        return _GapResult(buffer_slot=buffer_slot, warning=warning)

    # Sufficient gap -- insert a buffer slot
    buffer_end_dt = datetime.combine(date.today(), prev_end) + timedelta(minutes=required)
    buffer_end = buffer_end_dt.time()

    # Check if remaining free time overlaps a meal window
    effective_windows = meal_windows if meal_windows is not None else list(_MEAL_WINDOWS)
    note = f"{slot_type}: {required}分钟" if location_changed else None
    if buffer_end < next_start and _overlaps_meal_window(buffer_end, next_start, effective_windows):
        note = (note + "，" if note else "") + "建议利用此时段用餐"

    buffer_slot = TimeSlot(
        start=prev_end,
        end=buffer_end,
        slot_type=slot_type,
        note=note,
    )
    return _GapResult(buffer_slot=buffer_slot)


def _overlaps_meal_window(
    start: time,
    end: time,
    meal_windows: Optional[List[Tuple]] = None,
) -> bool:
    """Return True if [start, end) overlaps any meal window."""
    windows = meal_windows if meal_windows is not None else list(_MEAL_WINDOWS)
    for sh, sm, eh, em in windows:
        mw_start = time(sh, sm)
        mw_end = time(eh, em)
        if start < mw_end and end > mw_start:
            return True
    return False


_MEAL_WINDOW_NAMES = {
    (12, 0, 13, 30): "午餐",
    (18, 0, 19, 30): "晚餐",
}


def _check_meal_conflicts(
    event: CuratedEvent,
    ev_start: time,
    ev_end: time,
    meal_windows: Optional[List[Tuple]] = None,
) -> List[GapWarning]:
    """Return GapWarnings for each meal window fully spanned by the event.

    A meal conflict occurs when an event's time range completely covers
    a meal window (event starts at or before meal start AND ends at or
    after meal end), leaving no time for the meal.
    """
    windows = meal_windows if meal_windows is not None else list(_MEAL_WINDOWS)
    warnings: List[GapWarning] = []
    for window in windows:
        if len(window) < 4:
            continue
        sh, sm, eh, em = window[0], window[1], window[2], window[3]
        mw_start = time(sh, sm)
        mw_end = time(eh, em)
        if ev_start <= mw_start and ev_end >= mw_end:
            meal_name = _MEAL_WINDOW_NAMES.get(
                (sh, sm, eh, em),
                f"{sh}:{sm:02d}-{eh}:{em:02d}用餐",
            )
            warnings.append(GapWarning(
                gap_type="meal_conflict",
                affected_event_ids=(event.id,),
                suggestion=f"此事件占用了{meal_name}时间，建议调整",
            ))
    return warnings


def _time_diff_minutes(t1: time, t2: time) -> float:
    """Return (t2 - t1) in minutes. Negative if t2 is before t1."""
    d1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    d2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    return (d2 - d1).total_seconds() / 60.0


def _compute_density(
    scored: List[Tuple[CuratedEvent, EnhancedPriorityScore]],
    target_date: date,
) -> float:
    """Compute a 0-1 density score based on event count and time coverage.

    Factors:
    - Event count relative to a "full day" baseline (8 events = 1.0)
    - Total scheduled hours relative to a 12-hour work window
    """
    if not scored:
        return 0.0

    count_factor = min(1.0, len(scored) / 8.0)

    total_hours = 0.0
    for event, _ in scored:
        if event.normalized_start and event.normalized_end:
            delta = (event.normalized_end - event.normalized_start).total_seconds() / 3600.0
            total_hours += max(0.0, delta)
        else:
            total_hours += 1.0  # assume 1h for events without end time

    coverage_factor = min(1.0, total_hours / 12.0)

    return 0.5 * count_factor + 0.5 * coverage_factor


def _suggest_reorder(
    scored: List[Tuple[CuratedEvent, EnhancedPriorityScore]],
) -> Optional[Tuple[UUID, ...]]:
    """For overloaded days, suggest which events to keep (top by priority)."""
    if len(scored) <= 3:
        return None
    by_priority = sorted(scored, key=lambda p: -p[1].composite)
    # Suggest keeping only top-priority events
    keep = [e.id for e, _ in by_priority[:3]]
    defer = [e.id for e, _ in by_priority[3:]]
    return tuple(keep + defer)


def _extract_annotation_texts(ctx: EventContext) -> List[str]:
    """Extract non-empty annotation strings from an EventContext."""
    texts: List[str] = []
    if ctx.historical_summary:
        texts.append(ctx.historical_summary)
    if ctx.people_summary:
        texts.append(ctx.people_summary)
    if ctx.event_chain_summary:
        texts.append(ctx.event_chain_summary)
    return texts


def _change_type_label(change_type: str) -> str:
    labels = {
        "delayed": "延误",
        "cancelled": "取消",
        "location_changed": "地点变更",
        "time_changed": "时间变更",
    }
    return labels.get(change_type, change_type)
