"""InsightContextAssembler - assembles person/memory/emotion context for insight
generation. NOT curation.services.context_enricher.ContextEnricher (event-level)."""

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from ...core.utils.xml_escape import escape_xml, escape_like
from ..member.models import PersonProfile, ProfileStatus
from ..memory.models import MemorySummary

logger = get_logger(__name__)


@dataclass(frozen=True)
class InsightContext:
    """Assembled context data for insight generation."""

    person_profiles: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    memory_summaries: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    emotional_trend: Optional[Dict[str, Any]] = None
    preference_rules: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "person_profiles", tuple(self.person_profiles))
        object.__setattr__(self, "memory_summaries", tuple(self.memory_summaries))
        object.__setattr__(self, "preference_rules", tuple(self.preference_rules))

    def to_prompt_xml(self) -> str:
        """Serialize assembled context into XML for LLM prompt injection."""
        sections: List[str] = []

        if self.person_profiles:
            items = []
            for p in self.person_profiles:
                fields = [_tag("name", p.get("name", ""))]
                _opt(fields, "relationship", p)
                _opt(fields, "location", p)
                if p.get("preferences", {}).get("likes"):
                    fields.append(_tag("likes", ", ".join(str(v) for v in p["preferences"]["likes"][:5])))
                for k in ("favor_balance", "importance", "days_since_contact"):
                    if p.get(k) is not None:
                        fields.append(_tag(k, str(p[k])))
                items.append(_wrap("person", fields))
            sections.append(_wrap_list("person_profiles", items))

        if self.memory_summaries:
            items = []
            for s in self.memory_summaries:
                fields = [_tag("type", s.get("summary_type", "")), _tag("title", s.get("title", "")), _tag("content", s.get("content", ""))]
                if s.get("importance") is not None:
                    fields.append(_tag("importance", str(s["importance"])))
                items.append(_wrap("summary", fields))
            sections.append(_wrap_list("memory_summaries", items))

        if self.emotional_trend and self.emotional_trend.get("trend") != "unknown":
            et = self.emotional_trend
            fields = [_tag("trend", et.get("trend", "")),
                      _tag("negative_count", str(et.get("negative_count", 0)), indent=2),
                      _tag("positive_count", str(et.get("positive_count", 0)), indent=2),
                      _tag("suggested_tone", et.get("suggested_tone", ""))]
            sections.append("<emotional_trend>\n" + "\n".join(fields) + "\n</emotional_trend>")

        if self.preference_rules:
            items = []
            for r in self.preference_rules:
                fields: List[str] = []
                _opt(fields, "action", r)
                _opt(fields, "explanation", r)
                if r.get("condition_event_type"):
                    fields.append(_tag("event_type", r["condition_event_type"]))
                if r.get("condition_person_id"):
                    fields.append(_tag("person_id", str(r["condition_person_id"])))
                items.append(_wrap("rule", fields))
            sections.append(_wrap_list("preference_rules", items))

        if not sections:
            return ""
        return "<insight_context>\n" + "\n".join(sections) + "\n</insight_context>"


def _tag(name: str, value: str, indent: int = 4) -> str:
    """Build an XML tag with escaped value."""
    pad = " " * indent
    return f"{pad}<{name}>{escape_xml(str(value))}</{name}>"


def _opt(fields: List[str], key: str, data: Dict[str, Any]) -> None:
    """Append a tag to fields if the key exists and is truthy."""
    if data.get(key):
        fields.append(_tag(key, data[key]))


def _wrap(tag: str, fields: List[str], indent: int = 2) -> str:
    """Wrap fields in an element."""
    pad = " " * indent
    return f"{pad}<{tag}>\n" + "\n".join(fields) + f"\n{pad}</{tag}>"


def _wrap_list(tag: str, items: List[str]) -> str:
    """Wrap a list of item elements in a container tag."""
    return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"


class InsightContextAssembler:
    """Assembles person/memory/emotion context for insight generation.

    Fetches PersonProfiles, MemorySummaries, EmotionalTrend, and preference
    rules in parallel via asyncio.gather(), then bundles them into an
    InsightContext with XML serialization.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._static_cache: Dict[Tuple, Dict[str, Any]] = {}

    async def assemble_static(
        self, user_id: UUID, family_id: UUID,
    ) -> InsightContext:
        """Assemble context fields that are stable within a single daily run.

        Caches memory_summaries, emotional_trend, and preference_rules in memory.
        Call this once per run and reuse the result for multiple events/persons.
        """
        cache_key = (user_id, family_id)
        if cache_key not in self._static_cache:
            results = await asyncio.gather(
                self._fetch_memory_summaries(user_id, family_id),
                self._fetch_emotional_trend(user_id),
                self._fetch_preference_rules(user_id, family_id),
                return_exceptions=True,
            )
            self._static_cache[cache_key] = {
                "memory_summaries": results[0] if not isinstance(results[0], BaseException) else [],
                "emotional_trend": results[1] if not isinstance(results[1], BaseException) else None,
                "preference_rules": results[2] if not isinstance(results[2], BaseException) else [],
            }
        static = self._static_cache[cache_key]
        return InsightContext(
            person_profiles=(),
            memory_summaries=static["memory_summaries"],
            emotional_trend=static["emotional_trend"],
            preference_rules=static["preference_rules"],
        )

    async def assemble(
        self, user_id: UUID, family_id: UUID,
        person_names: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        date_context: Optional[date] = None,
    ) -> InsightContext:
        """Full assembly: cached static context + per-entity person profiles.

        Static fields (memory_summaries, emotional_trend, preference_rules) are
        fetched once per (user_id, family_id) pair and cached for the assembler's
        lifetime. Person profiles are always fetched fresh since they vary by
        name/location query.
        """
        static_ctx = await self.assemble_static(user_id, family_id)
        person_profiles = await self._fetch_person_profiles(
            user_id, family_id, person_names, locations,
        )
        return InsightContext(
            person_profiles=person_profiles,
            memory_summaries=static_ctx.memory_summaries,
            emotional_trend=static_ctx.emotional_trend,
            preference_rules=static_ctx.preference_rules,
        )

    async def _fetch_person_profiles(
        self, user_id: UUID, family_id: UUID,
        person_names: Optional[List[str]], locations: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Fetch PersonProfiles by name/alias or location match."""
        from sqlalchemy import func, or_

        filters: List[Any] = []
        if person_names:
            for name in person_names:
                filters.append(func.lower(PersonProfile.name) == name.lower())
                filters.append(PersonProfile.aliases.contains([name]))
        if locations:
            for loc in locations:
                filters.append(PersonProfile.location.ilike(f"%{escape_like(loc)}%"))
        if not filters:
            return []

        stmt = (
            select(PersonProfile)
            .where(and_(
                PersonProfile.user_id == user_id,
                PersonProfile.family_id == family_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
                or_(*filters),
            ))
            .order_by(PersonProfile.importance.desc()).limit(10)
        )
        result = await self.db.execute(stmt)
        now = utc_now()
        return [
            {"name": p.name, "relationship": p.relationship, "location": p.location,
             "preferences": p.preferences or {}, "favor_balance": p.favor_balance,
             "importance": p.importance,
             "days_since_contact": (now - p.last_mentioned_at).days if p.last_mentioned_at else None}
            for p in result.scalars().all()
        ]

    async def _fetch_memory_summaries(
        self, user_id: UUID, family_id: UUID, limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fetch recent MemorySummary entries (last 30 days)."""
        stmt = (
            select(MemorySummary)
            .where(and_(
                MemorySummary.user_id == user_id, MemorySummary.family_id == family_id,
                MemorySummary.created_at >= utc_now() - timedelta(days=30),
            ))
            .order_by(MemorySummary.importance.desc(), MemorySummary.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            {"summary_type": s.summary_type, "title": s.title, "content": s.content,
             "importance": s.importance, "tags": s.tags or []}
            for s in result.scalars().all()
        ]

    async def _fetch_emotional_trend(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Compute emotional trend via the shared service."""
        from ..memory.emotional_trend_service import compute_emotional_trend
        trend = await compute_emotional_trend(self.db, user_id)
        if trend.trend == "unknown":
            return None
        return {"trend": trend.trend, "negative_count": trend.negative_count,
                "positive_count": trend.positive_count, "neutral_count": trend.neutral_count,
                "total_count": trend.total_count, "suggested_tone": trend.suggested_tone}

    async def _fetch_preference_rules(
        self, user_id: UUID, family_id: UUID, limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch active, non-expired user preference rules."""
        from ..curation.models import UserPreferenceRule
        stmt = (
            select(UserPreferenceRule)
            .where(and_(
                UserPreferenceRule.user_id == user_id, UserPreferenceRule.family_id == family_id,
                UserPreferenceRule.is_active.is_(True), UserPreferenceRule.expires_at > utc_now(),
            ))
            .order_by(UserPreferenceRule.created_at.desc()).limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            {"action": r.action, "explanation": r.explanation,
             "condition_event_type": r.condition_event_type,
             "condition_suggestion_type": r.condition_suggestion_type,
             "condition_person_id": str(r.condition_person_id) if r.condition_person_id else None,
             "condition_location": r.condition_location, "scope": r.scope, "confidence": r.confidence}
            for r in result.scalars().all()
        ]
