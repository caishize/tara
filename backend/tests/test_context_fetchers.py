"""Tests for ai_engine/context_fetchers.py.

Tests cover:
- Each fetcher returns proper ContextItem lists
- Fetcher graceful failure (returns [] on exception)
- Workers construct assembler with fetchers injected
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.ai_engine.context_assembler import ContextAssembler, ContextItem
from src.ai_engine.context_fetchers import (
    decompose_query,
    extract_person_ids_from_l4,
    fetch_l1_notes,
    fetch_l2_messages,
    fetch_l3_summaries,
    fetch_l4_memories,
    fetch_l5_orchestration,
)


USER_ID = uuid4()
FAMILY_ID = uuid4()
SESSION_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Helpers: mock model objects
# ---------------------------------------------------------------------------

def _make_mock_note(
    note_id: Optional[UUID] = None,
    title: str = "Test Note",
    content: str = "Note content",
    priority: int = 7,
    category: str = "preference",
    life_type: str = "permanent",
    confidence: float = 0.9,
    status: str = "active",
) -> MagicMock:
    note = MagicMock()
    note.id = note_id or uuid4()
    note.user_id = USER_ID
    note.family_id = FAMILY_ID
    note.title = title
    note.content = content
    note.priority = priority
    note.category = category
    note.life_type = life_type
    note.confidence = confidence
    note.status = status
    note.updated_at = datetime.now(timezone.utc)
    return note


def _make_mock_message(
    role: str = "user",
    content: str = "Hello",
    is_superseded: bool = False,
) -> MagicMock:
    msg = MagicMock()
    msg.id = uuid4()
    msg.session_id = UUID(SESSION_ID)
    msg.role = role
    msg.content = content
    msg.is_superseded = is_superseded
    msg.created_at = datetime.now(timezone.utc)
    return msg


def _make_mock_summary(
    title: str = "Summary",
    content: str = "Summary content",
    summary_type: str = "person_profile",
    importance: int = 6,
) -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.user_id = USER_ID
    s.family_id = FAMILY_ID
    s.title = title
    s.content = content
    s.summary_type = summary_type
    s.importance = importance
    s.period_start = None
    s.period_end = None
    s.last_updated_at = datetime.now(timezone.utc)
    return s


def _make_mock_memory(
    content: str = "Memory content",
    summary: str = "Memory summary",
    importance: int = 5,
    feedback_weight: float = 1.0,
    memory_type: str = "general",
    sensitivity_level: str = "public",
    entities: Optional[Dict[str, Any]] = None,
) -> MagicMock:
    m = MagicMock()
    m.id = uuid4()
    m.user_id = USER_ID
    m.content = content
    m.summary = summary
    m.importance = importance
    m.feedback_weight = feedback_weight
    m.memory_type = memory_type
    m.sensitivity_level = sensitivity_level
    m.entities = entities or {}
    m.created_at = datetime.now(timezone.utc)
    return m


# ---------------------------------------------------------------------------
# fetch_l1_notes
# ---------------------------------------------------------------------------

class TestFetchL1Notes:
    @pytest.mark.asyncio
    async def test_returns_context_items(self):
        notes = [_make_mock_note(title="Pref A"), _make_mock_note(title="Pref B")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = notes

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "src.ai_engine.context_fetchers.get_db_session"
        ) as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await fetch_l1_notes(USER_ID, FAMILY_ID)

        assert len(items) == 2
        assert all(isinstance(i, ContextItem) for i in items)
        assert all(i.layer == "l1" for i in items)
        assert all(i.source == "secretary_note" for i in items)
        assert "[Pref A]" in items[0].content
        assert items[0].tokens > 0

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        with patch(
            "src.ai_engine.context_fetchers.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            items = await fetch_l1_notes(USER_ID, FAMILY_ID)

        assert items == []


# ---------------------------------------------------------------------------
# fetch_l2_messages
# ---------------------------------------------------------------------------

class TestFetchL2Messages:
    @pytest.mark.asyncio
    async def test_returns_context_items(self):
        msgs = [
            _make_mock_message(role="user", content="How are you?"),
            _make_mock_message(role="assistant", content="I'm fine."),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = msgs

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "src.ai_engine.context_fetchers.get_db_session"
        ) as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await fetch_l2_messages(USER_ID, SESSION_ID)

        assert len(items) == 2
        assert all(i.layer == "l2" for i in items)
        assert all(i.source == "conversation" for i in items)

    @pytest.mark.asyncio
    async def test_empty_session_id(self):
        items = await fetch_l2_messages(USER_ID, "")
        assert items == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        with patch(
            "src.ai_engine.context_fetchers.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            items = await fetch_l2_messages(USER_ID, SESSION_ID)

        assert items == []


# ---------------------------------------------------------------------------
# fetch_l3_summaries
# ---------------------------------------------------------------------------

class TestFetchL3Summaries:
    @pytest.mark.asyncio
    async def test_returns_context_items(self):
        summaries = [_make_mock_summary(title="Person A")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = summaries

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch(
            "src.ai_engine.context_fetchers.get_db_session"
        ) as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await fetch_l3_summaries(USER_ID, FAMILY_ID, set())

        assert len(items) == 1
        assert items[0].layer == "l3"
        assert "[Person A]" in items[0].content

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        with patch(
            "src.ai_engine.context_fetchers.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            items = await fetch_l3_summaries(USER_ID, FAMILY_ID, set())

        assert items == []


# ---------------------------------------------------------------------------
# fetch_l4_memories
# ---------------------------------------------------------------------------

class TestFetchL4Memories:
    @pytest.mark.asyncio
    async def test_returns_context_items(self):
        memories = [_make_mock_memory(summary="Trip to Tokyo")]
        mock_repo = MagicMock()
        mock_repo.full_text_search = AsyncMock(return_value=memories)
        mock_repo.get_recent_memories = AsyncMock(return_value=[])

        mock_session = AsyncMock()

        with patch(
            "src.ai_engine.context_fetchers.get_db_session"
        ) as mock_ctx, patch(
            "src.modules.memory.repository.MemoryRepository",
            return_value=mock_repo,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await fetch_l4_memories(USER_ID, "Tokyo trip")

        assert len(items) == 1
        assert items[0].layer == "l4"
        assert items[0].source == "memory"
        assert "Trip to Tokyo" in items[0].content

    @pytest.mark.asyncio
    async def test_empty_message_returns_empty(self):
        items = await fetch_l4_memories(USER_ID, "")
        assert items == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        with patch(
            "src.ai_engine.context_fetchers.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            items = await fetch_l4_memories(USER_ID, "test query")

        assert items == []

    @pytest.mark.asyncio
    async def test_supplements_with_recent_memories(self):
        """When FTS returns few results, recent memories fill the gap."""
        fts_memories = [_make_mock_memory(summary="Only one FTS result")]
        recent_memories = [
            _make_mock_memory(summary="Recent memory 1"),
            _make_mock_memory(summary="Recent memory 2"),
        ]
        mock_repo = MagicMock()
        mock_repo.full_text_search = AsyncMock(return_value=fts_memories)
        mock_repo.get_recent_memories = AsyncMock(return_value=recent_memories)

        mock_session = AsyncMock()

        with patch(
            "src.ai_engine.context_fetchers.get_db_session"
        ) as mock_ctx, patch(
            "src.modules.memory.repository.MemoryRepository",
            return_value=mock_repo,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await fetch_l4_memories(USER_ID, "search query")

        # 1 FTS + 2 recent = 3 items
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_semantic_queries_run_in_single_session(self):
        """After session consolidation, all sub-queries share one session and repo."""
        created_repos: List[MagicMock] = []

        def _repo_factory(_db):
            repo = MagicMock()
            repo.full_text_search = AsyncMock(return_value=[])
            repo.get_recent_memories = AsyncMock(return_value=[])
            created_repos.append(repo)
            return repo

        run_semantic_mock = AsyncMock(return_value=[])

        def _make_session_ctx():
            @asynccontextmanager
            async def _ctx():
                yield AsyncMock()
            return _ctx()

        with patch(
            "src.ai_engine.context_fetchers.get_db_session",
            side_effect=_make_session_ctx,
        ), patch(
            "src.modules.memory.repository.MemoryRepository",
            side_effect=_repo_factory,
        ), patch(
            "src.ai_engine.context_fetchers.decompose_query",
            return_value=["广州住宿", "广州酒店"],
        ), patch(
            "src.ai_engine.context_fetchers._run_semantic_search",
            run_semantic_mock,
        ):
            await fetch_l4_memories(USER_ID, "关于广州行程住宿安排")

        # After session consolidation (ROOT-002), only 1 repo is created
        assert len(created_repos) == 1
        assert run_semantic_mock.await_count == 2

        # All semantic sub-queries share the same repo
        repos_used_by_semantic = [
            call.args[0] for call in run_semantic_mock.await_args_list
        ]
        assert all(repo is created_repos[0] for repo in repos_used_by_semantic)

        # FTS also uses the same repo
        assert created_repos[0].full_text_search.await_count == 1


# ---------------------------------------------------------------------------
# fetch_l5_orchestration
# ---------------------------------------------------------------------------

class TestFetchL5Orchestration:
    @pytest.mark.asyncio
    async def test_returns_orchestration_context_for_today_events(self):
        event = MagicMock()
        event.id = uuid4()
        event.title = "晨会"
        event.normalized_start = datetime.now(timezone.utc)
        event.normalized_end = datetime.now(timezone.utc)

        mock_tz_result = MagicMock()
        mock_tz_result.scalar_one_or_none.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [event]
        mock_session = AsyncMock()
        mock_session.execute.side_effect = [mock_tz_result, mock_result]

        slot = SimpleNamespace(
            slot_type="event",
            event_id=event.id,
            start=time(9, 0),
            end=time(10, 0),
            note=None,
        )
        day = SimpleNamespace(
            density_score=0.56,
            slots=[slot],
            gaps=[],
            annotations=[],
            day_theme=None,
        )

        mock_pref_repo = MagicMock()
        mock_pref_repo.get_by_family_id = AsyncMock(return_value=None)

        mock_orchestrator = MagicMock()
        mock_orchestrator.orchestrate_day = AsyncMock(return_value=day)

        with patch(
            "src.modules.curation.services.family_preference_repository.FamilyPreferenceRepository",
            return_value=mock_pref_repo,
        ), patch(
            "src.modules.curation.services.orchestrator.SecretaryOrchestrator",
            return_value=mock_orchestrator,
        ), patch(
            "src.modules.curation.services.priority_engine.HybridPriorityEngine",
            return_value=MagicMock(),
        ):
            items = await fetch_l5_orchestration(USER_ID, FAMILY_ID, db=mock_session)

        assert len(items) == 1
        assert items[0].layer == "l5"
        assert items[0].source == "orchestration"
        assert "今日日程概览" in items[0].content
        assert "09:00-10:00 晨会" in items[0].content

        mock_orchestrator.orchestrate_day.assert_awaited_once()
        assert mock_session.execute.await_count == 2

        stmt = mock_session.execute.await_args_list[1].args[0]
        sql = str(stmt)
        assert "curated_events.is_active" in sql
        assert "curated_events.status" in sql
        assert "curated_events.normalized_start" in sql
        assert "curated_events.normalized_end" in sql
        assert "target_date" not in sql
        assert "is_archived" not in sql

# ---------------------------------------------------------------------------
# Worker fetcher injection
# ---------------------------------------------------------------------------

class TestWorkerFetcherInjection:
    def test_agent_worker_assembler_has_fetchers(self):
        """AgentWorker.context_assembler should have all 4 fetchers injected."""
        with patch("src.ai_engine.workers.agent_worker.settings") as mock_settings:
            mock_settings.effective_anthropic_model = "claude-sonnet-4-20250514"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.anthropic_base_url = ""

            mock_db = MagicMock()
            from src.ai_engine.workers.agent_worker import AgentWorker
            worker = AgentWorker(db=mock_db, model="claude-sonnet-4-20250514")

            assembler = worker.context_assembler

        # L1 fetcher is now a combined fetcher that wraps fetch_l1_notes + fetch_curation_hints
        assert callable(assembler._l1_fetcher)
        assert assembler._l2_fetcher is fetch_l2_messages
        assert assembler._l3_fetcher is fetch_l3_summaries
        assert assembler._l4_fetcher is fetch_l4_memories

    def test_fast_worker_assembler_has_fetchers(self):
        """FastWorker._try_assemble_context should create assembler with fetchers."""
        with patch("src.ai_engine.workers.fast_worker.settings") as mock_settings:
            mock_settings.fast_worker_model = "claude-haiku-4-20250414"
            mock_settings.effective_anthropic_model = "claude-haiku-4-20250414"
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.anthropic_base_url = ""
            mock_settings.fast_agentic_enabled = False
            mock_settings.fast_agentic_max_turns = 3
            mock_settings.fast_agentic_max_tool_calls = 5
            mock_settings.fast_agentic_tool_timeout_seconds = 10
            mock_settings.fast_weather_tool_timeout_seconds = 10
            mock_settings.agentic_tool_timeout_seconds = 30

            from src.ai_engine.workers.fast_worker import FastWorker
            worker = FastWorker(model="claude-haiku-4-20250414")

            # Patch ContextAssembler at source module (it's imported lazily
            # inside the method body from ..context_assembler)
            with patch(
                "src.ai_engine.context_assembler.ContextAssembler"
            ) as MockAssembler:
                mock_instance = MagicMock()
                mock_instance.assemble = AsyncMock(return_value=("text", MagicMock()))
                MockAssembler.return_value = mock_instance

                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        worker._try_assemble_context(
                            str(USER_ID), str(FAMILY_ID), SESSION_ID, "test", None
                        )
                    )
                finally:
                    loop.close()

                MockAssembler.assert_called_once()
                call_kwargs = MockAssembler.call_args
                # L1 fetcher is now a combined fetcher wrapping fetch_l1_notes + fetch_curation_hints
                assert callable(call_kwargs.kwargs.get("l1_fetcher"))
                assert call_kwargs.kwargs.get("l2_fetcher") is fetch_l2_messages
                assert call_kwargs.kwargs.get("l3_fetcher") is fetch_l3_summaries
                assert call_kwargs.kwargs.get("l4_fetcher") is fetch_l4_memories


# ---------------------------------------------------------------------------
# ContextAssembler integration with fetchers
# ---------------------------------------------------------------------------

class TestAssemblerWithFetchers:
    @pytest.mark.asyncio
    async def test_assembler_collects_from_injected_fetchers(self):
        """ContextAssembler should call fetchers and produce non-empty output."""
        async def mock_l1(user_id, family_id):
            return [ContextItem(layer="l1", source="secretary_note", content="Fact A", tokens=10)]

        async def mock_l2(user_id, session_id):
            return [ContextItem(layer="l2", source="conversation", content="Msg A", tokens=10)]

        async def mock_l3(user_id, family_id, resolved_ids, **kwargs):
            return [ContextItem(layer="l3", source="person_profile", content="Profile A", tokens=10)]

        async def mock_l4(user_id, user_message):
            return [ContextItem(layer="l4", source="memory", content="Memory A", tokens=10)]

        assembler = ContextAssembler(
            l1_fetcher=mock_l1,
            l2_fetcher=mock_l2,
            l3_fetcher=mock_l3,
            l4_fetcher=mock_l4,
        )

        async def _no_cache_get(*args, **kwargs):
            return None

        async def _no_cache_set(*args, **kwargs):
            return None

        # Mock metrics to avoid import dependency in test env
        mock_counter = MagicMock()
        mock_counter.labels.return_value.inc = MagicMock()
        mock_histogram = MagicMock()
        mock_histogram.observe = MagicMock()

        with patch.object(assembler, "_cache_get", side_effect=_no_cache_get), \
             patch.object(assembler, "_cache_set", side_effect=_no_cache_set), \
             patch(
                 "src.core.observability.metrics.context_cache_ops",
                 mock_counter,
             ), \
             patch(
                 "src.core.observability.metrics.context_assembly_seconds",
                 mock_histogram,
             ):
            prompt_text, metadata = await assembler.assemble(
                user_id=USER_ID,
                family_id=FAMILY_ID,
                session_id=SESSION_ID,
                user_message="Hello",
            )

        assert "Fact A" in prompt_text
        assert "Msg A" in prompt_text
        assert "Profile A" in prompt_text
        assert "Memory A" in prompt_text
        assert metadata.total_tokens_used > 0

    @pytest.mark.asyncio
    async def test_assembler_graceful_fetcher_failure(self):
        """If one fetcher raises, the assembler should still succeed with other layers."""
        async def failing_l1(user_id, family_id):
            raise RuntimeError("DB exploded")

        async def mock_l2(user_id, session_id):
            return [ContextItem(layer="l2", source="conversation", content="Msg B", tokens=10)]

        assembler = ContextAssembler(
            l1_fetcher=failing_l1,
            l2_fetcher=mock_l2,
        )

        async def _no_cache_get(*args, **kwargs):
            return None

        async def _no_cache_set(*args, **kwargs):
            return None

        mock_counter = MagicMock()
        mock_counter.labels.return_value.inc = MagicMock()
        mock_histogram = MagicMock()
        mock_histogram.observe = MagicMock()

        with patch.object(assembler, "_cache_get", side_effect=_no_cache_get), \
             patch.object(assembler, "_cache_set", side_effect=_no_cache_set), \
             patch(
                 "src.core.observability.metrics.context_cache_ops",
                 mock_counter,
             ), \
             patch(
                 "src.core.observability.metrics.context_assembly_seconds",
                 mock_histogram,
             ):
            prompt_text, metadata = await assembler.assemble(
                user_id=USER_ID,
                family_id=FAMILY_ID,
                session_id=SESSION_ID,
                user_message="Hello",
            )

        # L1 failed but L2 succeeded
        assert "Msg B" in prompt_text
        assert metadata.l1_tokens == 0
        assert metadata.l2_tokens > 0


# ---------------------------------------------------------------------------
# Context hash versioning (Task #6)
# ---------------------------------------------------------------------------

class TestContextHashVersioning:
    def test_hash_differs_with_different_facts_version(self):
        """Hash should change when facts_version changes."""
        h1 = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
            facts_version="100", exclusion_version="100",
        )
        h2 = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
            facts_version="101", exclusion_version="100",
        )
        assert h1 != h2

    def test_hash_differs_with_different_exclusion_version(self):
        """Hash should change when exclusion_version changes."""
        h1 = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
            facts_version="100", exclusion_version="100",
        )
        h2 = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
            facts_version="100", exclusion_version="101",
        )
        assert h1 != h2

    def test_hash_same_within_same_bucket(self):
        """Hash should be identical when all inputs including versions match."""
        h1 = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
            facts_version="200", exclusion_version="200",
        )
        h2 = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
            facts_version="200", exclusion_version="200",
        )
        assert h1 == h2

    def test_hash_backward_compatible_with_empty_versions(self):
        """Empty version strings should still produce a valid hash."""
        h = ContextAssembler._compute_context_hash(
            USER_ID, FAMILY_ID, SESSION_ID, "hello",
        )
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest length


# ---------------------------------------------------------------------------
# Query decomposition (Enhancement 3.7.3)
# ---------------------------------------------------------------------------

class TestDecomposeQuery:
    def test_empty_returns_empty(self):
        assert decompose_query("") == []
        assert decompose_query(None) == []

    def test_short_message_returns_as_is(self):
        result = decompose_query("你好")
        assert result == ["你好"]

    def test_simple_message_unchanged(self):
        result = decompose_query("hello")
        assert result == ["hello"]

    def test_long_chinese_produces_sub_queries(self):
        """A complex Chinese sentence should be decomposed into sub-queries."""
        msg = "妈妈上次去北京出差的时候买了什么礼物给爸爸"
        result = decompose_query(msg)
        assert len(result) >= 1
        assert result[0] == msg  # original always first
        # Should not exceed max_queries
        assert len(result) <= 3

    def test_max_queries_respected(self):
        msg = "妈妈上次去北京出差的时候买了什么礼物给爸爸"
        result = decompose_query(msg, max_queries=1)
        assert len(result) == 1

    def test_no_duplicates(self):
        msg = "记得上次和妈妈一起去北京旅游的事情"
        result = decompose_query(msg)
        assert len(result) == len(set(result))

    def test_returns_list_of_strings(self):
        msg = "帮我查一下上周和张三讨论的项目进展情况"
        result = decompose_query(msg)
        assert all(isinstance(q, str) for q in result)
        assert all(len(q) > 0 for q in result)


# ---------------------------------------------------------------------------
# Extract person IDs from L4 (Enhancement 3.7.2)
# ---------------------------------------------------------------------------

class TestExtractPersonIdsFromL4:
    def test_empty_items_returns_empty(self):
        assert extract_person_ids_from_l4([]) == set()

    def test_extracts_from_entity_ids(self):
        items = [
            ContextItem(layer="l4", source="memory", content="test",
                        entity_ids=("uuid-1", "uuid-2")),
        ]
        result = extract_person_ids_from_l4(items)
        assert result == {"uuid-1", "uuid-2"}

    def test_extracts_from_metadata_person_id(self):
        items = [
            ContextItem(layer="l4", source="memory", content="test",
                        metadata={"person_id": "uuid-3"}),
        ]
        result = extract_person_ids_from_l4(items)
        assert "uuid-3" in result

    def test_deduplicates(self):
        items = [
            ContextItem(layer="l4", source="memory", content="a",
                        entity_ids=("uuid-1",)),
            ContextItem(layer="l4", source="memory", content="b",
                        entity_ids=("uuid-1", "uuid-2")),
        ]
        result = extract_person_ids_from_l4(items)
        assert result == {"uuid-1", "uuid-2"}

    def test_skips_empty_entity_ids(self):
        items = [
            ContextItem(layer="l4", source="memory", content="test",
                        entity_ids=("", )),
        ]
        result = extract_person_ids_from_l4(items)
        assert result == set()  # empty string skipped

    def test_mixed_sources(self):
        items = [
            ContextItem(layer="l4", source="memory", content="a",
                        entity_ids=("uuid-1",),
                        metadata={"person_id": "uuid-2"}),
            ContextItem(layer="l4", source="memory", content="b"),
        ]
        result = extract_person_ids_from_l4(items)
        assert result == {"uuid-1", "uuid-2"}


# ---------------------------------------------------------------------------
# L3 cross-layer boost (Enhancement 3.7.2)
# ---------------------------------------------------------------------------

class TestL3CrossLayerBoost:
    @pytest.mark.asyncio
    async def test_boost_increases_importance(self):
        """Summaries matching boost_person_ids should have higher importance."""
        mock_summary = MagicMock()
        mock_summary.id = uuid4()
        mock_summary.user_id = USER_ID
        mock_summary.family_id = FAMILY_ID
        mock_summary.summary_type = "person_profile"
        mock_summary.title = "Profile A"
        mock_summary.content = "About person A"
        mock_summary.importance = 5
        mock_summary.period_start = None
        mock_summary.period_end = None
        mock_summary.last_updated_at = datetime.now(timezone.utc)
        mock_summary.consolidated_entities = {"person_id": "uuid-person-1"}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_summary]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Without boost
        items_no_boost = await fetch_l3_summaries(
            USER_ID, FAMILY_ID, set(), db=mock_session,
        )
        assert len(items_no_boost) == 1
        base_importance = items_no_boost[0].importance

        # With boost matching the entity
        mock_session.execute = AsyncMock(return_value=mock_result)
        items_boosted = await fetch_l3_summaries(
            USER_ID, FAMILY_ID, set(), db=mock_session,
            boost_person_ids={"uuid-person-1"},
        )
        assert len(items_boosted) == 1
        assert items_boosted[0].importance > base_importance
        assert items_boosted[0].metadata.get("l4_boosted") is True

    @pytest.mark.asyncio
    async def test_no_boost_without_match(self):
        """Summaries not matching boost IDs should keep original importance."""
        mock_summary = MagicMock()
        mock_summary.id = uuid4()
        mock_summary.user_id = USER_ID
        mock_summary.family_id = FAMILY_ID
        mock_summary.summary_type = "topic_summary"
        mock_summary.title = "Topic B"
        mock_summary.content = "About topic B"
        mock_summary.importance = 5
        mock_summary.period_start = None
        mock_summary.period_end = None
        mock_summary.last_updated_at = datetime.now(timezone.utc)
        mock_summary.consolidated_entities = {"topic": "cooking"}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_summary]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        items = await fetch_l3_summaries(
            USER_ID, FAMILY_ID, set(), db=mock_session,
            boost_person_ids={"uuid-person-1"},
        )
        assert len(items) == 1
        assert items[0].importance == 0.5  # 5/10 unchanged
        assert "l4_boosted" not in items[0].metadata

    @pytest.mark.asyncio
    async def test_boost_capped_at_1(self):
        """Importance after boost should never exceed 1.0."""
        mock_summary = MagicMock()
        mock_summary.id = uuid4()
        mock_summary.user_id = USER_ID
        mock_summary.family_id = FAMILY_ID
        mock_summary.summary_type = "person_profile"
        mock_summary.title = "Important person"
        mock_summary.content = "Very important"
        mock_summary.importance = 9  # 0.9 base
        mock_summary.period_start = None
        mock_summary.period_end = None
        mock_summary.last_updated_at = datetime.now(timezone.utc)
        mock_summary.consolidated_entities = {"person_id": "uuid-p"}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_summary]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        items = await fetch_l3_summaries(
            USER_ID, FAMILY_ID, set(), db=mock_session,
            boost_person_ids={"uuid-p"},
        )
        assert items[0].importance <= 1.0

    @pytest.mark.asyncio
    async def test_none_consolidated_entities_no_crash(self):
        """Summaries with None consolidated_entities should not crash."""
        mock_summary = MagicMock()
        mock_summary.id = uuid4()
        mock_summary.user_id = USER_ID
        mock_summary.family_id = FAMILY_ID
        mock_summary.summary_type = "topic_summary"
        mock_summary.title = "Topic"
        mock_summary.content = "Content"
        mock_summary.importance = 5
        mock_summary.period_start = None
        mock_summary.period_end = None
        mock_summary.last_updated_at = datetime.now(timezone.utc)
        mock_summary.consolidated_entities = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_summary]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        items = await fetch_l3_summaries(
            USER_ID, FAMILY_ID, set(), db=mock_session,
            boost_person_ids={"uuid-1"},
        )
        assert len(items) == 1
        assert items[0].importance == 0.5  # no boost


# ---------------------------------------------------------------------------
# Integration: L4→L3 cross-layer in assembler _collect
# ---------------------------------------------------------------------------

class TestCrossLayerCollect:
    @pytest.mark.asyncio
    async def test_l3_receives_boost_from_l4(self):
        """When L4 returns items with entity_ids, L3 fetcher should receive boost_person_ids."""
        received_kwargs = {}

        async def mock_l1(user_id, family_id):
            return [ContextItem(layer="l1", source="note", content="Note", tokens=10)]

        async def mock_l2(user_id, session_id):
            return [ContextItem(layer="l2", source="conv", content="Conv", tokens=10)]

        async def mock_l3(user_id, family_id, resolved_ids, **kwargs):
            received_kwargs.update(kwargs)
            return [ContextItem(layer="l3", source="profile", content="Profile", tokens=10)]

        async def mock_l4(user_id, user_message):
            return [
                ContextItem(layer="l4", source="memory", content="Memory",
                            tokens=10, entity_ids=("person-uuid-1", "person-uuid-2")),
            ]

        assembler = ContextAssembler(
            l1_fetcher=mock_l1,
            l2_fetcher=mock_l2,
            l3_fetcher=mock_l3,
            l4_fetcher=mock_l4,
        )

        async def _no_cache_get(*a, **kw):
            return None

        async def _no_cache_set(*a, **kw):
            return None

        mock_counter = MagicMock()
        mock_counter.labels.return_value.inc = MagicMock()
        mock_histogram = MagicMock()
        mock_histogram.observe = MagicMock()

        with patch.object(assembler, "_cache_get", side_effect=_no_cache_get), \
             patch.object(assembler, "_cache_set", side_effect=_no_cache_set), \
             patch("src.core.observability.metrics.context_cache_ops", mock_counter), \
             patch("src.core.observability.metrics.context_assembly_seconds", mock_histogram):
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, "test message")

        # L3 fetcher should have received boost_person_ids from L4
        assert "boost_person_ids" in received_kwargs
        assert received_kwargs["boost_person_ids"] == {"person-uuid-1", "person-uuid-2"}

    @pytest.mark.asyncio
    async def test_l3_no_boost_when_l4_empty(self):
        """When L4 returns no items, L3 should get boost_person_ids=None."""
        received_kwargs = {}

        async def mock_l3(user_id, family_id, resolved_ids, **kwargs):
            received_kwargs.update(kwargs)
            return []

        async def mock_l4(user_id, user_message):
            return []

        assembler = ContextAssembler(
            l3_fetcher=mock_l3,
            l4_fetcher=mock_l4,
        )

        async def _no_cache_get(*a, **kw):
            return None

        async def _no_cache_set(*a, **kw):
            return None

        mock_counter = MagicMock()
        mock_counter.labels.return_value.inc = MagicMock()
        mock_histogram = MagicMock()
        mock_histogram.observe = MagicMock()

        with patch.object(assembler, "_cache_get", side_effect=_no_cache_get), \
             patch.object(assembler, "_cache_set", side_effect=_no_cache_set), \
             patch("src.core.observability.metrics.context_cache_ops", mock_counter), \
             patch("src.core.observability.metrics.context_assembly_seconds", mock_histogram):
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, "test")

        # No boost when L4 returns nothing
        assert received_kwargs.get("boost_person_ids") is None
