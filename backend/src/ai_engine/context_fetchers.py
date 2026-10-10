"""Concrete data-fetcher functions for the ContextAssembler pipeline.

Each fetcher is an async callable that:
  1. Opens its own DB session (via get_db_session context manager)
  2. Queries the relevant model(s)
  3. Returns a list of ContextItem instances for one layer
  4. Catches all exceptions and returns [] on failure (resilient)

These are injected into ContextAssembler at construction time so the
assembler remains testable without real DB sessions.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from ..db.session import get_db_session
from .context_assembler import ContextItem, estimate_tokens

logger = logging.getLogger(__name__)

# Default limits
_L1_NOTE_LIMIT = 50
_L2_MESSAGE_LIMIT = 20
_L3_SUMMARY_LIMIT = 30
_L4_MEMORY_LIMIT = 15


async def fetch_l1_notes(
    user_id: UUID,
    family_id: UUID,
    db: Optional[Any] = None,
) -> List[ContextItem]:
    """Fetch active SecretaryNotes as L1 context items (fact base).

    Args:
        db: Optional shared DB session (C3). When provided, uses it
            directly instead of opening a new session.
    """
    try:
        from sqlalchemy import and_, select

        from ..modules.memory.secretary_note_model import SecretaryNote

        async def _query(session: Any) -> list:
            stmt = (
                select(SecretaryNote)
                .where(
                    and_(
                        SecretaryNote.user_id == user_id,
                        SecretaryNote.family_id == family_id,
                        SecretaryNote.status == "active",
                    )
                )
                .order_by(SecretaryNote.priority.desc(), SecretaryNote.updated_at.desc())
                .limit(_L1_NOTE_LIMIT)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

        if db is not None:
            notes = await _query(db)
        else:
            async with get_db_session() as session:
                notes = await _query(session)

        items: List[ContextItem] = []
        for note in notes:
            content = note.content or ""
            if note.title:
                content = f"[{note.title}] {content}"
            items.append(
                ContextItem(
                    layer="l1",
                    source="secretary_note",
                    content=content,
                    tokens=estimate_tokens(content),
                    importance=float(note.priority or 5) / 10.0,
                    metadata={
                        "note_id": str(note.id),
                        "category": note.category,
                        "life_type": note.life_type,
                        "confidence": note.confidence,
                    },
                )
            )
        return items

    except Exception:
        logger.warning("fetch_l1_notes failed, returning empty", exc_info=True)
        return []


async def fetch_l2_messages(
    user_id: UUID,
    session_id: str,
    db: Optional[Any] = None,
) -> List[ContextItem]:
    """Fetch recent conversation messages as L2 context items (active window).

    Args:
        db: Optional shared DB session (C3). When provided, uses it
            directly instead of opening a new session.
    """
    try:
        if not session_id:
            return []

        from sqlalchemy import select

        from ..modules.conversation.models import ConversationMessage

        session_uuid = UUID(session_id)

        async def _query(sess: Any) -> list:
            stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == session_uuid,
                    ConversationMessage.is_superseded.is_(False),
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(_L2_MESSAGE_LIMIT)
            )
            result = await sess.execute(stmt)
            return list(result.scalars().all())

        if db is not None:
            messages = await _query(db)
        else:
            async with get_db_session() as sess:
                messages = await _query(sess)

        # Reverse to chronological order for the LLM
        messages.reverse()

        items: List[ContextItem] = []
        for msg in messages:
            role = msg.role or "user"
            content = msg.content or ""
            prefix = f"[{role}] " if role != "assistant" else "[assistant] "
            formatted = f"{prefix}{content}"
            created_at = msg.created_at if isinstance(msg.created_at, datetime) else None
            metadata = {}
            if created_at is not None:
                metadata["created_at"] = created_at

            items.append(
                ContextItem(
                    layer="l2",
                    source="conversation",
                    content=formatted,
                    tokens=estimate_tokens(formatted),
                    metadata=metadata,
                )
            )
        return items

    except Exception:
        logger.warning("fetch_l2_messages failed, returning empty", exc_info=True)
        return []


async def fetch_l3_summaries(
    user_id: UUID,
    family_id: UUID,
    resolved_ids: Set[UUID],
    db: Optional[Any] = None,
    boost_person_ids: Optional[Set[str]] = None,
) -> List[ContextItem]:
    """Fetch memory summaries as L3 context items (person profiles / topic summaries).

    Args:
        db: Optional shared DB session (C3). When provided, uses it
            directly instead of opening a new session.
        boost_person_ids: Entity IDs extracted from L4 results. Summaries
            whose ``consolidated_entities`` reference these IDs receive an
            importance boost so they rank higher in budget allocation.
    """
    try:
        from sqlalchemy import and_, select

        from ..modules.memory.models import MemorySummary

        async def _query(sess: Any) -> list:
            stmt = (
                select(MemorySummary)
                .where(
                    and_(
                        MemorySummary.user_id == user_id,
                        MemorySummary.family_id == family_id,
                    )
                )
                .order_by(MemorySummary.importance.desc(), MemorySummary.last_updated_at.desc())
                .limit(_L3_SUMMARY_LIMIT)
            )
            result = await sess.execute(stmt)
            return list(result.scalars().all())

        if db is not None:
            summaries = await _query(db)
        else:
            async with get_db_session() as sess:
                summaries = await _query(sess)

        _boost_ids = boost_person_ids or set()

        items: List[ContextItem] = []
        for summary in summaries:
            content = summary.content or ""
            if summary.title:
                content = f"[{summary.title}] {content}"
            source = summary.summary_type or "topic_summary"

            metadata: Dict[str, Any] = {}
            if summary.period_start is not None:
                metadata["period_start"] = summary.period_start
            if summary.period_end is not None:
                metadata["period_end"] = summary.period_end

            _recency_days = 0.0
            if summary.last_updated_at and isinstance(summary.last_updated_at, datetime):
                from ..core.utils.timezone import utc_now
                delta = utc_now() - summary.last_updated_at
                _recency_days = max(0.0, delta.total_seconds() / 86400.0)

            # Cross-layer boost: if L4 memories reference entities that
            # match this summary's consolidated_entities, raise importance.
            base_importance = float(summary.importance or 5) / 10.0
            boosted = False
            if _boost_ids and summary.consolidated_entities:
                entity_values = {
                    str(v) for v in summary.consolidated_entities.values() if v
                }
                if entity_values & _boost_ids:
                    base_importance = min(1.0, base_importance + 0.2)
                    boosted = True
            if boosted:
                metadata["l4_boosted"] = True

            items.append(
                ContextItem(
                    layer="l3",
                    source=source,
                    content=content,
                    tokens=estimate_tokens(content),
                    importance=base_importance,
                    recency_days=_recency_days,
                    metadata=metadata,
                )
            )
        return items

    except Exception:
        logger.warning("fetch_l3_summaries failed, returning empty", exc_info=True)
        return []


async def _run_semantic_search(
    repo: Any,
    user_id: UUID,
    query_text: str,
    limit: int,
) -> List[Tuple[Any, float]]:
    """Generate embedding and run semantic search. Returns (memory, similarity) pairs."""
    from ..modules.memory.embedding_service import EmbeddingService

    service = EmbeddingService()
    query_embedding = await service.get_embedding(query_text)
    if not query_embedding:
        return []

    from ..modules.memory.config import memory_config

    return await repo.semantic_search(
        user_id=user_id,
        query_embedding=query_embedding,
        similarity_threshold=memory_config.semantic_similarity_threshold,
        limit=limit,
    )


def _score_memory(
    mem: Any,
    semantic_similarity: Optional[float],
    now: datetime,
) -> float:
    """Compute hybrid retrieval score: semantic × 0.6 + importance × 0.3 + recency × 0.1."""
    importance_norm = float(mem.importance or 5) / 10.0

    recency_score = 0.5
    if mem.created_at and isinstance(mem.created_at, datetime):
        days_old = max(0.0, (now - mem.created_at).total_seconds() / 86400.0)
        recency_score = max(0.0, 1.0 - days_old / 90.0)

    if semantic_similarity is not None:
        return semantic_similarity * 0.6 + importance_norm * 0.3 + recency_score * 0.1

    return importance_norm * 0.7 + recency_score * 0.3


def decompose_query(user_message: str, max_queries: int = 3) -> List[str]:
    """Decompose a user message into multiple search queries using jieba.

    For complex messages containing multiple semantic dimensions (e.g.
    "妈妈上次去北京出差买的礼物"), splits into sub-queries that each target
    a different retrieval angle. Short or simple messages return as-is.

    Returns a list of 1..max_queries query strings (always includes original).
    """
    if not user_message or len(user_message.strip()) < 10:
        return [user_message] if user_message else []

    stripped = user_message.strip()
    queries: List[str] = [stripped]

    try:
        import jieba
        import jieba.analyse

        # Extract top keywords by TF-IDF to form sub-queries
        keywords = jieba.analyse.extract_tags(stripped, topK=6)

        # Group keywords into sub-query clusters of 2-3 words
        if len(keywords) >= 4:
            mid = len(keywords) // 2
            sub_q1 = "".join(keywords[:mid])
            sub_q2 = "".join(keywords[mid:])
            if sub_q1 != stripped:
                queries.append(sub_q1)
            if sub_q2 != stripped:
                queries.append(sub_q2)
        elif len(keywords) >= 2:
            sub_q = "".join(keywords)
            if sub_q != stripped:
                queries.append(sub_q)

    except ImportError:
        # jieba not available: extract Chinese bigrams as fallback
        cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', stripped)
        if len(cn_words) >= 4:
            mid = len(cn_words) // 2
            queries.append("".join(cn_words[:mid]))
            queries.append("".join(cn_words[mid:]))

    # Deduplicate while preserving order, cap at max_queries
    seen: Set[str] = set()
    unique: List[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique[:max_queries]


def extract_person_ids_from_l4(l4_items: List[ContextItem]) -> Set[str]:
    """Extract person/entity IDs from L4 memory results.

    Scans entity_ids and metadata for person references that can be used
    to boost L3 person profile selection.
    """
    person_ids: Set[str] = set()
    for item in l4_items:
        for eid in item.entity_ids:
            if eid:
                person_ids.add(str(eid))
        # Also check metadata for explicit person references
        meta_person = item.metadata.get("person_id")
        if meta_person:
            person_ids.add(str(meta_person))
    return person_ids


async def fetch_l4_memories(
    user_id: UUID,
    user_message: str,
) -> List[ContextItem]:
    """Fetch relevant memories via hybrid retrieval as L4 context items (long-term memory).

    Strategy:
    1. Decompose user message into sub-queries (jieba TF-IDF)
    2. If query >= 10 chars: run semantic search per sub-query in parallel with FTS
    3. Merge and deduplicate by memory id (keep best similarity)
    4. Score by (semantic_similarity * 0.6 + importance * 0.3 + recency * 0.1)
    5. Falls back to FTS-only if embedding generation fails
    """
    try:
        if not user_message or not user_message.strip():
            return []

        from ..modules.memory.repository import MemoryRepository

        # Decompose into sub-queries for broader retrieval
        sub_queries = decompose_query(user_message)

        semantic_results: List[Tuple[Any, float]] = []
        fts_results: List[Any] = []

        async with get_db_session() as db:
            repo = MemoryRepository(db)

            use_semantic = len(user_message.strip()) >= 10

            if use_semantic:
                # Run semantic sub-queries sequentially within the same
                # session to avoid opening extra DB sessions (ROOT-002).
                for q in sub_queries:
                    try:
                        sub_result = await _run_semantic_search(
                            repo, user_id, q, _L4_MEMORY_LIMIT,
                        )
                        semantic_results.extend(sub_result)
                    except Exception:
                        logger.debug(
                            "L4 semantic search failed for sub-query",
                            exc_info=True,
                        )

                # FTS also runs within the same session
                fts_results = await repo.full_text_search(
                    user_id=user_id,
                    query_text=user_message,
                    limit=_L4_MEMORY_LIMIT,
                )
            else:
                fts_results = await repo.full_text_search(
                    user_id=user_id,
                    query_text=user_message,
                    limit=_L4_MEMORY_LIMIT,
                )

            # Merge and deduplicate (keep best similarity across sub-queries)
            seen_ids: Dict[UUID, Tuple[Any, Optional[float]]] = {}

            for mem, similarity in semantic_results:
                existing = seen_ids.get(mem.id)
                if existing is None or (similarity or 0) > (existing[1] or 0):
                    seen_ids[mem.id] = (mem, similarity)

            for mem in fts_results:
                if mem.id not in seen_ids:
                    seen_ids[mem.id] = (mem, None)

            # Supplement with recent memories if results are sparse
            if len(seen_ids) < 5:
                recent = await repo.get_recent_memories(
                    user_id=user_id,
                    days=14,
                    limit=_L4_MEMORY_LIMIT - len(seen_ids),
                )
                for m in recent:
                    if m.id not in seen_ids:
                        seen_ids[m.id] = (m, None)

        # Score and sort
        from ..core.utils.timezone import utc_now

        now = utc_now()
        scored: List[Tuple[Any, float, Optional[float]]] = []
        for mem, similarity in seen_ids.values():
            score = _score_memory(mem, similarity, now)
            scored.append((mem, score, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:_L4_MEMORY_LIMIT]

        items: List[ContextItem] = []
        for mem, _score, _sim in scored:
            content = mem.summary or mem.content or ""
            if not content.strip():
                continue

            _recency_days = 0.0
            if mem.created_at and isinstance(mem.created_at, datetime):
                delta = now - mem.created_at
                _recency_days = max(0.0, delta.total_seconds() / 86400.0)

            entity_ids: Tuple[str, ...] = ()
            if mem.entities:
                entity_ids = tuple(
                    str(v) for v in mem.entities.values()
                    if isinstance(v, (str, int, UUID))
                )

            items.append(
                ContextItem(
                    layer="l4",
                    source="memory",
                    content=content,
                    tokens=estimate_tokens(content),
                    importance=float(mem.importance or 5) / 10.0,
                    feedback_weight=float(mem.feedback_weight or 1.0),
                    recency_days=_recency_days,
                    entity_ids=entity_ids,
                    sensitivity_level=mem.sensitivity_level or "public",
                    metadata={
                        "memory_id": str(mem.id),
                        "memory_type": mem.memory_type,
                    },
                )
            )
        return items

    except Exception:
        logger.warning("fetch_l4_memories failed, returning empty", exc_info=True)
        return []


async def fetch_l5_orchestration(
    user_id: UUID,
    family_id: UUID,
    db: Optional[Any] = None,
    scope: str = "today_only",
) -> List[ContextItem]:
    """Fetch orchestrated schedule as L5 context items.

    Queries curated events, runs them through SecretaryOrchestrator,
    and serializes the OrchestratedDay (time slots, annotations, gaps, density)
    into a compact prompt section so the Agent naturally references the schedule.

    Args:
        scope: Injection scope controlling how much data is loaded.
            "skip"       -- return [] immediately (e.g. weather/chat tasks).
            "today_only" -- load today's events only (default, backward-compatible).
            "full_window" -- load today + next 7 days; orchestrate today,
                            append a compact future-events summary.

    This is a read-only path with no LLM calls. Typical latency: <200ms.
    """
    if scope == "skip":
        return []

    try:
        from zoneinfo import ZoneInfo

        from sqlalchemy import and_, or_, select

        from ..core.utils.timezone import (
            DEFAULT_TIMEZONE,
            local_date_range_to_utc,
            local_today,
        )
        from ..modules.curation.models import CuratedEvent
        from ..modules.insight.insight_settings_model import UserInsightSettings
        from ..modules.curation.services.family_preference_repository import (
            FamilyPreferenceRepository,
        )
        from ..modules.curation.services.orchestrator import SecretaryOrchestrator
        from ..modules.curation.services.priority_engine import HybridPriorityEngine

        _FULL_WINDOW_DAYS = 7

        async def _run(sess: Any) -> List[ContextItem]:
            # Resolve user's preferred timezone; fall back to DEFAULT_TIMEZONE.
            user_tz = DEFAULT_TIMEZONE
            try:
                tz_stmt = select(UserInsightSettings.timezone).where(
                    UserInsightSettings.user_id == user_id
                )
                tz_result = await sess.execute(tz_stmt)
                tz_name = tz_result.scalar_one_or_none()
                if isinstance(tz_name, str) and tz_name.strip():
                    try:
                        user_tz = ZoneInfo(tz_name.strip())
                    except Exception:
                        logger.debug(
                            "Invalid timezone '%s' for user %s, falling back to default",
                            tz_name,
                            user_id,
                        )
            except Exception:
                logger.debug("Failed to resolve user timezone for %s", user_id, exc_info=True)

            today = local_today(user_tz)
            day_start_utc, day_end_utc = local_date_range_to_utc(today, today, user_tz)

            # Determine query date range based on scope
            if scope == "full_window":
                window_end_date = today + timedelta(days=_FULL_WINDOW_DAYS)
                _, query_end_utc = local_date_range_to_utc(
                    window_end_date, window_end_date, user_tz,
                )
            else:
                query_end_utc = day_end_utc

            # Load curated events for the query range
            stmt = (
                select(CuratedEvent)
                .where(and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status != "cancelled",
                    or_(
                        and_(
                            CuratedEvent.normalized_start >= day_start_utc,
                            CuratedEvent.normalized_start <= query_end_utc,
                        ),
                        and_(
                            CuratedEvent.normalized_start <= day_start_utc,
                            CuratedEvent.normalized_end >= day_start_utc,
                        ),
                    ),
                ))
                .order_by(CuratedEvent.normalized_start.asc())
            )
            result = await sess.execute(stmt)
            all_events = list(result.scalars().all())

            if not all_events:
                return []

            # Separate today's events from future events
            today_events = [
                ev for ev in all_events
                if (ev.normalized_start is not None and ev.normalized_start <= day_end_utc)
                or (ev.normalized_end is not None and ev.normalized_end >= day_start_utc
                    and ev.normalized_start is not None and ev.normalized_start <= day_start_utc)
            ]
            future_events = [
                ev for ev in all_events
                if ev.normalized_start is not None and ev.normalized_start > day_end_utc
            ] if scope == "full_window" else []

            # Load family preferences
            pref_repo = FamilyPreferenceRepository(sess)
            family_prefs = await pref_repo.get_by_family_id(family_id)

            # Build orchestrated day (today only)
            lines: List[str] = []

            if today_events:
                priority_engine = HybridPriorityEngine()
                orchestrator = SecretaryOrchestrator(sess, priority_engine)
                day = await orchestrator.orchestrate_day(
                    family_id=family_id,
                    user_id=user_id,
                    target_date=today,
                    events=today_events,
                    family_prefs=family_prefs,
                )

                # Serialize today's schedule
                lines.append(f"今日日程概览 ({today.isoformat()}):")
                lines.append(f"忙碌度: {'较高' if day.density_score > 0.7 else '适中' if day.density_score > 0.4 else '轻松'} ({day.density_score:.0%})")

                if day.slots:
                    lines.append("")
                    for slot in day.slots:
                        if slot.slot_type == "event":
                            ev_title = ""
                            for ev in today_events:
                                if ev.id == slot.event_id:
                                    ev_title = ev.title or ""
                                    break
                            time_str = f"{slot.start.strftime('%H:%M')}-{slot.end.strftime('%H:%M')}"
                            line = f"  {time_str} {ev_title}"
                            if slot.note:
                                line += f" [{slot.note}]"
                            lines.append(line)
                        elif slot.slot_type in ("buffer", "travel"):
                            time_str = f"{slot.start.strftime('%H:%M')}-{slot.end.strftime('%H:%M')}"
                            note = slot.note or slot.slot_type
                            lines.append(f"  {time_str} ({note})")

                if day.gaps:
                    lines.append("")
                    lines.append("注意事项:")
                    for gap in day.gaps:
                        if gap.suggestion:
                            lines.append(f"  - {gap.suggestion}")

                if day.annotations:
                    seen_texts: Set[str] = set()
                    annotation_lines: List[str] = []
                    for ann in day.annotations:
                        if ann.text not in seen_texts:
                            seen_texts.add(ann.text)
                            annotation_lines.append(f"  - {ann.text}")
                    if annotation_lines:
                        lines.append("")
                        lines.append("秘书批注:")
                        lines.extend(annotation_lines)

                if day.day_theme is not None:
                    lines.append("")
                    lines.append(f"今日主题: {day.day_theme.title}")
                    lines.append(f"聚焦: {day.day_theme.focus}")
                    if day.day_theme.prep_note:
                        lines.append(f"准备提示: {day.day_theme.prep_note}")
                    if day.day_theme.evening_forward:
                        lines.append(f"明日预警: {day.day_theme.evening_forward}")

                density_score = day.density_score
            else:
                lines.append(f"今日日程概览 ({today.isoformat()}):")
                lines.append("忙碌度: 轻松 (0%)")
                density_score = 0.0

            # Append future events summary for full_window scope
            if future_events:
                lines.append("")
                lines.append(f"未来 {_FULL_WINDOW_DAYS} 天事件概要:")
                # Group future events by date for a compact summary
                date_events: Dict[str, List[str]] = {}
                for ev in future_events:
                    if ev.normalized_start is not None:
                        ev_local = ev.normalized_start.astimezone(user_tz)
                        date_key = ev_local.strftime("%m-%d")
                        title = ev.title or "未命名事件"
                        time_str = ev_local.strftime("%H:%M")
                        date_events.setdefault(date_key, []).append(
                            f"{time_str} {title}"
                        )
                for date_key in sorted(date_events.keys()):
                    ev_list = date_events[date_key]
                    lines.append(f"  [{date_key}] {'; '.join(ev_list)}")

            content = "\n".join(lines)
            metadata: Dict[str, Any] = {
                "target_date": today.isoformat(),
                "density": density_score,
                "scope": scope,
            }
            if future_events:
                metadata["future_event_count"] = len(future_events)

            return [ContextItem(
                layer="l5",
                source="orchestration",
                content=content,
                tokens=estimate_tokens(content),
                importance=0.9,
                metadata=metadata,
            )]

        if db is not None:
            return await _run(db)
        async with get_db_session() as sess:
            return await _run(sess)

    except Exception:
        logger.warning("fetch_l5_orchestration failed, returning empty", exc_info=True)
        return []


async def fetch_curation_hints(
    user_id: UUID,
    family_id: UUID,
    db: Optional[Any] = None,
) -> List[ContextItem]:
    """L1 layer: recent high-confidence curation associations and proactive triggers.

    Data sources:
    1. EventAssociation: is_dismissed=False, is_confirmed=False,
       priority='strongly_recommend', created_at > now()-24h, limit 5
    2. Redis key curation:proactive:{family_id}: recent proactive triggers
    3. (E3) Redis key assoc:hints:latest:{family_id}: mini_curate association
       hints cached for Fast Path fusion

    Latency: <50ms (pure DB/Redis, no LLM)
    """
    items: List[ContextItem] = []

    # Source 1: DB - recent strong associations
    try:
        from sqlalchemy import and_, select

        from ..modules.curation.models import EventAssociation

        from ..core.utils.timezone import utc_now
        cutoff = utc_now() - timedelta(hours=24)

        async def _query_assoc(sess: Any) -> list:
            stmt = (
                select(EventAssociation)
                .where(and_(
                    EventAssociation.family_id == family_id,
                    EventAssociation.is_dismissed.is_(False),
                    EventAssociation.is_confirmed.is_(False),
                    EventAssociation.priority == "strongly_recommend",
                    EventAssociation.created_at >= cutoff,
                ))
                .order_by(EventAssociation.confidence.desc())
                .limit(5)
            )
            result = await sess.execute(stmt)
            return list(result.scalars().all())

        if db is not None:
            associations = await _query_assoc(db)
        else:
            async with get_db_session() as sess:
                associations = await _query_assoc(sess)

        for assoc in associations:
            text = f"{assoc.title}: {assoc.reason}" if assoc.title and assoc.reason else (assoc.title or assoc.reason or "")
            if not text.strip():
                continue
            items.append(ContextItem(
                layer="l1",
                source="curation_hint",
                content="[秘书发现] %s" % text,
                tokens=estimate_tokens(text) + 10,
                importance=0.9,
            ))
    except Exception:
        logger.warning("fetch_curation_hints: DB query failed", exc_info=True)

    # Source 2: Redis - recent proactive triggers
    try:
        import json

        from ..core.cache import redis_client

        key = "curation:proactive:%s" % str(family_id)
        client = redis_client.client
        if client is not None:
            raw_items = await client.lrange(key, 0, 4)
            for raw in (raw_items or []):
                data = json.loads(raw)
                text = data.get("text", "")
                if not text:
                    continue
                priority = data.get("priority", "P2")
                items.append(ContextItem(
                    layer="l1",
                    source="proactive_trigger",
                    content="[秘书提醒] %s" % text,
                    tokens=estimate_tokens(text) + 10,
                    importance=0.95 if priority in ("P0", "P1") else 0.7,
                ))
    except Exception:
        logger.warning("fetch_curation_hints: Redis query failed", exc_info=True)

    # Source 3 (E3): Redis - mini_curate association hints for Fast Path fusion
    try:
        import json

        from ..core.cache import redis_client

        _PRIORITY_RANK = {"strongly_recommend": 0, "convenient": 1, "optional": 2}
        latest_key = "assoc:hints:latest:%s" % str(family_id)
        _client = redis_client.client
        if _client is not None:
            raw = await _client.get(latest_key)
            if raw:
                hints = json.loads(raw)
                if hints:
                    # Take top-1 highest priority hint to avoid info overload
                    top = sorted(
                        hints,
                        key=lambda h: _PRIORITY_RANK.get(
                            h.get("priority", "optional"), 2,
                        ),
                    )[0]
                    text = "%s：%s" % (
                        top.get("title", ""),
                        top.get("reason", ""),
                    )
                    text = text.strip("：").strip()
                    if text:
                        items.append(ContextItem(
                            layer="l1",
                            source="association_hint",
                            content="[关联提示] %s" % text,
                            tokens=estimate_tokens(text) + 10,
                            importance=0.9,
                        ))
    except Exception:
        logger.warning("fetch_curation_hints: association hint read failed", exc_info=True)

    return items


# Feedback weight threshold below which a memory is considered "dismissed"
_FEEDBACK_WEIGHT_THRESHOLD = 0.3


async def aggregate_dismissed_entities(
    user_id: UUID,
    family_id: UUID,
) -> Set[str]:
    """Aggregate entity IDs that should be excluded from context assembly.

    Sources:
        1. insight_feedbacks WHERE feedback_type IN ('not_useful', 'not_relevant',
           'incorrect') — extracts entity IDs from the related source memory
        2. conversation_memories WHERE feedback_weight < 0.3 — low-weight memories
           indicate the user has repeatedly dismissed this content
        3. ExclusionRepository — persisted exclusion rules with optional cooldown

    Returns a set of entity ID strings for the ExclusionFilter.
    """
    dismissed: Set[str] = set()
    try:
        from sqlalchemy import and_, select

        from ..modules.insight.models import Insight, InsightEntity, InsightFeedback
        from ..modules.memory.models import ConversationMemory

        async with get_db_session() as db:
            # Source 1: insight_feedbacks with dismiss-like feedback types
            dismiss_types = ("not_useful", "not_relevant", "incorrect")
            fb_stmt = (
                select(InsightFeedback.source_memory_id)
                .where(
                    and_(
                        InsightFeedback.user_id == user_id,
                        InsightFeedback.feedback_type.in_(dismiss_types),
                        InsightFeedback.source_memory_id.isnot(None),
                    )
                )
            )
            fb_result = await db.execute(fb_stmt)
            dismissed_memory_ids = {row[0] for row in fb_result.fetchall() if row[0] is not None}

            # For each dismissed memory, extract its entity IDs
            if dismissed_memory_ids:
                mem_stmt = (
                    select(ConversationMemory.entities)
                    .where(ConversationMemory.id.in_(dismissed_memory_ids))
                )
                mem_result = await db.execute(mem_stmt)
                for (entities,) in mem_result.fetchall():
                    if entities and isinstance(entities, dict):
                        for val in entities.values():
                            if isinstance(val, (str, int)):
                                dismissed.add(str(val))
                            elif isinstance(val, list):
                                for item in val:
                                    if isinstance(item, (str, int)):
                                        dismissed.add(str(item))

            # Also extract person entity IDs from unified insights that
            # were dismissed by this user (via InsightEntity associations).
            dismissed_insight_stmt = (
                select(InsightEntity.entity_id)
                .join(Insight, InsightEntity.insight_id == Insight.id)
                .where(
                    and_(
                        Insight.user_id == user_id,
                        Insight.status == "dismissed",
                        InsightEntity.entity_type == "person",
                    )
                )
            )
            dismissed_insight_result = await db.execute(dismissed_insight_stmt)
            for (entity_id,) in dismissed_insight_result.fetchall():
                if entity_id is not None:
                    dismissed.add(str(entity_id))

            # Source 2: low feedback_weight memories → extract entity_ids
            low_weight_stmt = (
                select(ConversationMemory.entities)
                .where(
                    and_(
                        ConversationMemory.user_id == user_id,
                        ConversationMemory.family_id == family_id,
                        ConversationMemory.feedback_weight < _FEEDBACK_WEIGHT_THRESHOLD,
                        ConversationMemory.entities.isnot(None),
                    )
                )
                .limit(200)
            )
            low_result = await db.execute(low_weight_stmt)
            for (entities,) in low_result.fetchall():
                if entities and isinstance(entities, dict):
                    for val in entities.values():
                        if isinstance(val, (str, int)):
                            dismissed.add(str(val))
                        elif isinstance(val, list):
                            for item in val:
                                if isinstance(item, (str, int)):
                                    dismissed.add(str(item))

            # Source 3: persisted exclusion rules (ExclusionRepository)
            from .exclusion_repository import ExclusionRepository

            exclusion_repo = ExclusionRepository(db)
            excluded_ids = await exclusion_repo.get_active_entity_ids(
                user_id=user_id,
                family_id=family_id,
            )
            dismissed.update(excluded_ids)

    except Exception:
        logger.warning("aggregate_dismissed_entities failed, returning empty", exc_info=True)

    return dismissed
