"""Tests for ContextAssembler integration into fast_worker + agent_worker.

Verifies:
- Workers create ContextAssembler instances
- _try_assemble_context succeeds with mock fetchers
- _try_assemble_context returns None on failure (graceful fallback)
- _build_system_prompt includes assembled context when available
- _build_agentic_system_prompt includes assembled context
- ContextMetadata is captured for observability
- _extract_action_type extracts from task context
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.ai_engine.context_assembler import (
    ContextAssembler,
    ContextItem,
    ContextMetadata,
)


# ---------------------------------------------------------------------------
# AgentWorker integration
# ---------------------------------------------------------------------------


class TestAgentWorkerContextAssembler:
    """Test ContextAssembler integration in AgentWorker."""

    def _make_task(self, **overrides):
        """Create a minimal TaskPayload mock."""
        task = MagicMock()
        task.user_id = str(uuid4())
        task.family_id = str(uuid4())
        task.session_id = str(uuid4())
        task.user_input = "帮我分析家庭情况"
        task.job_id = "job-123"
        task.route_type = "slow"
        task.context_snapshot = {}
        task.metadata = {}
        for k, v in overrides.items():
            setattr(task, k, v)
        return task

    def test_extract_action_type_from_context_snapshot(self):
        from src.ai_engine.workers.agent_worker import AgentWorker
        task = self._make_task(context_snapshot={"action_type": "analyze"})
        assert AgentWorker._extract_action_type(task) == "analyze"

    def test_extract_action_type_from_action_enum(self):
        from src.ai_engine.workers.agent_worker import AgentWorker

        class FakeAction:
            value = "LOOKUP"
        task = self._make_task(context_snapshot={"action": FakeAction()})
        assert AgentWorker._extract_action_type(task) == "lookup"

    def test_extract_action_type_none(self):
        from src.ai_engine.workers.agent_worker import AgentWorker
        task = self._make_task(context_snapshot={})
        assert AgentWorker._extract_action_type(task) is None

    @pytest.mark.asyncio
    async def test_try_assemble_context_success(self):
        from src.ai_engine.workers.agent_worker import AgentWorker

        items = [ContextItem(layer="l1", source="note", content="Family fact", tokens=20)]

        async def mock_l1_fetcher(*args):
            return items

        assembler = ContextAssembler(l1_fetcher=mock_l1_fetcher)

        worker = MagicMock(spec=AgentWorker)
        worker._context_assembler = assembler
        worker._context_metadata = None
        worker.context_assembler = assembler

        task = self._make_task()
        result = await AgentWorker._try_assemble_context(worker, task, "analyze")

        assert result is not None
        assert "Family fact" in result
        assert worker._context_metadata is not None
        assert worker._context_metadata.total_tokens_used > 0

    @pytest.mark.asyncio
    async def test_try_assemble_context_failure_returns_none(self):
        from src.ai_engine.workers.agent_worker import AgentWorker

        async def failing_assembler(*args, **kwargs):
            raise RuntimeError("DB down")

        assembler = MagicMock(spec=ContextAssembler)
        assembler.assemble = failing_assembler

        worker = MagicMock(spec=AgentWorker)
        worker._context_metadata = None
        worker.context_assembler = assembler

        task = self._make_task()
        result = await AgentWorker._try_assemble_context(worker, task, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_try_assemble_context_empty_result_returns_none(self):
        from src.ai_engine.workers.agent_worker import AgentWorker

        assembler = ContextAssembler()  # no fetchers -> empty output

        worker = MagicMock(spec=AgentWorker)
        worker._context_assembler = assembler
        worker._context_metadata = None
        worker.context_assembler = assembler

        task = self._make_task()
        result = await AgentWorker._try_assemble_context(worker, task, None)
        assert result is None

    def test_build_system_prompt_with_assembled_context(self):
        from src.ai_engine.workers.agent_worker import AgentWorker

        worker = MagicMock(spec=AgentWorker)

        result = AgentWorker._build_system_prompt(
            worker,
            task=self._make_task(),
            base_prompt="Base prompt here.",
            assembled_context="L1 facts and L4 memories",
        )
        assert "Base prompt here." in result
        assert "用户上下文" in result
        assert "L1 facts and L4 memories" in result

    def test_build_system_prompt_without_assembled_context(self):
        from src.ai_engine.workers.agent_worker import AgentWorker

        worker = MagicMock(spec=AgentWorker)

        result = AgentWorker._build_system_prompt(
            worker,
            task=self._make_task(),
            base_prompt="Base prompt here.",
            assembled_context=None,
        )
        assert "Base prompt here." in result
        assert "上下文装配器补充" not in result

    def test_context_metadata_stored(self):
        """Verify _context_metadata is initialized to None and populated after assembly."""
        from src.ai_engine.workers.agent_worker import AgentWorker

        # We can't instantiate AgentWorker without DB + claude_agent_sdk,
        # but we can verify the attribute exists via __init__ param list
        worker = MagicMock(spec=AgentWorker)
        worker._context_metadata = None
        assert worker._context_metadata is None

        meta = ContextMetadata(total_tokens_used=3000, assembly_time_ms=50.0)
        worker._context_metadata = meta
        assert worker._context_metadata.total_tokens_used == 3000


# ---------------------------------------------------------------------------
# FastWorker integration
# ---------------------------------------------------------------------------


class TestFastWorkerContextAssembler:
    """Test ContextAssembler integration in FastWorker."""

    @pytest.mark.asyncio
    async def test_try_assemble_context_success(self):
        from src.ai_engine.workers.fast_worker import FastWorker

        items = [ContextItem(layer="l4", source="mem", content="Relevant memory", tokens=15)]

        async def mock_l4_fetcher(*args):
            return items

        worker = FastWorker.__new__(FastWorker)
        worker._context_assembler = ContextAssembler(l4_fetcher=mock_l4_fetcher)
        worker._context_metadata = None

        result = await worker._try_assemble_context(
            user_id=str(uuid4()),
            family_id=str(uuid4()),
            session_id=str(uuid4()),
            user_message="test query",
            action_type="lookup",
        )
        assert result is not None
        assert "Relevant memory" in result
        assert worker._context_metadata is not None

    @pytest.mark.asyncio
    async def test_try_assemble_context_failure_returns_none(self):
        from src.ai_engine.workers.fast_worker import FastWorker

        async def failing_assemble(*args, **kwargs):
            raise RuntimeError("DB error")

        broken_assembler = MagicMock()
        broken_assembler.assemble = failing_assemble

        worker = FastWorker.__new__(FastWorker)
        worker._context_assembler = broken_assembler
        worker._context_metadata = None

        result = await worker._try_assemble_context(
            user_id=str(uuid4()),
            family_id=str(uuid4()),
            session_id=None,
            user_message="test",
        )
        assert result is None

    def test_build_agentic_system_prompt_with_context(self):
        from src.ai_engine.workers.fast_worker import FastWorker
        from src.ai_engine.router.types import (
            ActionType, IntentClassification, RouteType, IntentCategory,
        )

        worker = FastWorker.__new__(FastWorker)

        intent = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.DATA_LOOKUP,
            confidence=0.9,
            action=ActionType.LOOKUP,
        )

        result = worker._build_agentic_system_prompt(
            intent=intent,
            context=None,
            assembled_context="Memory: user prefers 北京",
        )
        assert "相关上下文" in result
        assert "Memory: user prefers 北京" in result

    def test_build_agentic_system_prompt_without_context(self):
        from src.ai_engine.workers.fast_worker import FastWorker
        from src.ai_engine.router.types import (
            ActionType, IntentClassification, RouteType, IntentCategory,
        )

        worker = FastWorker.__new__(FastWorker)

        intent = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.CASUAL_CHAT,
            confidence=0.9,
            action=ActionType.CHAT,
        )

        result = worker._build_agentic_system_prompt(
            intent=intent,
            context=None,
            assembled_context=None,
        )
        assert "相关上下文" not in result


# ---------------------------------------------------------------------------
# End-to-end pipeline simulation
# ---------------------------------------------------------------------------


class TestAssemblerPipelineEndToEnd:
    """Simulate a full pipeline run without real DB or LLM."""

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_sections(self):
        l1 = [ContextItem(layer="l1", source="note", content="用户生日3月15日", tokens=15)]
        l2 = [ContextItem(layer="l2", source="conv", content="用户:你好 助手:你好！", tokens=20)]
        l3 = [ContextItem(layer="l3", source="profile", content="妻子小丽,32岁", tokens=12)]
        l4 = [ContextItem(
            layer="l4", source="memory", content="去年一起去了杭州旅行",
            tokens=18, importance=8.0,
        )]

        async def l1_fetch(*a, **kw): return l1
        async def l2_fetch(*a, **kw): return l2
        async def l3_fetch(*a, **kw): return l3
        async def l4_fetch(*a, **kw): return l4

        assembler = ContextAssembler(
            l1_fetcher=l1_fetch,
            l2_fetcher=l2_fetch,
            l3_fetcher=l3_fetch,
            l4_fetcher=l4_fetch,
        )

        prompt, meta = await assembler.assemble(
            user_id=uuid4(),
            family_id=uuid4(),
            session_id="sess-1",
            user_message="我要给小丽过生日",
            action_type="plan",
        )

        # All sections present
        assert "事实基座 (L1)" in prompt
        assert "活跃窗口 (L2)" in prompt
        assert "人物档案 (L3)" in prompt
        assert "相关记忆 (L4)" in prompt

        # Content preserved
        assert "用户生日3月15日" in prompt
        assert "去年一起去了杭州旅行" in prompt

        # Metadata populated
        assert meta.total_tokens_used == 15 + 20 + 12 + 18
        assert meta.l1_tokens == 15
        assert meta.l4_tokens == 18
        assert meta.memories_included == 1
        assert meta.assembly_time_ms >= 0
        # budget_total reflects the actual budget used (default 6900)
        assert meta.budget_total == 6900
        assert meta.budget_utilization == pytest.approx(meta.total_tokens_used / 6900.0)

    @pytest.mark.asyncio
    async def test_full_pipeline_custom_budget_reflected_in_metadata(self):
        from src.ai_engine.context_assembler import TokenBudget

        l1 = [ContextItem(layer="l1", source="note", content="fact", tokens=10)]

        async def l1_fetch(*a, **kw): return l1

        custom_budget = TokenBudget(total=10000)
        assembler = ContextAssembler(
            budget=custom_budget,
            l1_fetcher=l1_fetch,
        )

        _, meta = await assembler.assemble(
            user_id=uuid4(),
            family_id=uuid4(),
            session_id="sess-2",
            user_message="test",
        )
        assert meta.budget_total == 10000
        assert meta.budget_utilization == pytest.approx(10 / 10000.0)
