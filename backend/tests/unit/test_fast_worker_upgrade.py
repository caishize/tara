"""Tests for Fast → Slow upgrade mechanism in FastWorker.

Covers:
- FastWorkerResult dataclass
- _should_upgrade_to_slow detection logic
- Agentic loop: normal completion (no upgrade)
- Agentic loop: max_turns exhausted + upgrade triggered
- Agentic loop: max_turns exhausted + no upgrade (simple case)
"""
import json
from dataclasses import FrozenInstanceError
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_engine.workers.fast_worker import FastWorker, FastWorkerResult


# ---------------------------------------------------------------------------
# FastWorkerResult dataclass tests
# ---------------------------------------------------------------------------

class TestFastWorkerResult:
    def test_complete_status(self):
        result = FastWorkerResult(status="complete", text="done")
        assert result.status == "complete"
        assert result.text == "done"
        assert result.partial_context == []
        assert result.reason == ""

    def test_upgrade_status(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = FastWorkerResult(
            status="upgrade_to_slow",
            partial_context=msgs,
            reason="tool_limit_exceeded",
        )
        assert result.status == "upgrade_to_slow"
        assert result.partial_context == msgs
        assert result.reason == "tool_limit_exceeded"
        assert result.text == ""

    def test_frozen(self):
        result = FastWorkerResult(status="complete")
        with pytest.raises(FrozenInstanceError):
            result.status = "upgrade_to_slow"

    def test_default_values(self):
        result = FastWorkerResult(status="complete")
        assert result.text == ""
        assert result.partial_context == []
        assert result.reason == ""

    def test_threshold_constant(self):
        assert FastWorkerResult.UPGRADE_UNIQUE_TOOLS_THRESHOLD == 3


# ---------------------------------------------------------------------------
# _should_upgrade_to_slow tests
# ---------------------------------------------------------------------------

class TestShouldUpgradeToSlow:
    def test_no_tool_calls_returns_false(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "hello") is False

    def test_one_tool_returns_false(self):
        messages = [
            {"role": "user", "content": "weather?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                ],
            },
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "weather?") is False

    def test_two_unique_tools_returns_false(self):
        messages = [
            {"role": "user", "content": "tasks and weather"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
                ],
            },
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "test") is False

    def test_three_unique_tools_returns_true(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
                    {"type": "tool_use", "id": "t3", "name": "query_trips", "input": {}},
                ],
            },
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "test") is True

    def test_three_tools_across_multiple_turns(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                ],
            },
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
                ],
            },
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "{}"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t3", "name": "query_trips", "input": {}},
                ],
            },
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "test") is True

    def test_duplicate_tools_not_counted_twice(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "get_weather", "input": {}},
                    {"type": "tool_use", "id": "t3", "name": "query_tasks", "input": {}},
                ],
            },
        ]
        # Only 2 unique tools: get_weather, query_tasks
        assert FastWorker._should_upgrade_to_slow(messages, "test") is False

    def test_non_list_content_ignored(self):
        messages = [
            {"role": "assistant", "content": "plain string content"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                ],
            },
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "test") is False

    def test_user_messages_ignored(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
                    {"type": "tool_use", "id": "t3", "name": "query_trips", "input": {}},
                ],
            },
        ]
        assert FastWorker._should_upgrade_to_slow(messages, "test") is False

    def test_empty_messages(self):
        assert FastWorker._should_upgrade_to_slow([], "test") is False

    def test_tool_use_without_name_ignored(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
                    {"type": "tool_use", "id": "t3", "input": {}},  # no name
                ],
            },
        ]
        # Only 2 named tools
        assert FastWorker._should_upgrade_to_slow(messages, "test") is False


# ---------------------------------------------------------------------------
# Integration: agentic loop upgrade detection
# ---------------------------------------------------------------------------

def _make_text_block(text: str):
    """Create a mock Anthropic text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_id: str, name: str, tool_input: dict = None):
    """Create a mock Anthropic tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = tool_input or {}
    return block


async def _collect(async_iter):
    items = []
    async for item in async_iter:
        items.append(item)
    return items


class TestAgenticUpgradeIntegration:
    """Test the agentic loop's max_turns exhaustion behavior."""

    @pytest.mark.asyncio
    async def test_normal_completion_no_upgrade(self):
        """When LLM returns end_turn (no tool calls), no upgrade signal."""
        worker = FastWorker(model="test-model")
        worker._fast_agentic_enabled = True
        worker._fast_agentic_max_turns = 3

        # Mock: LLM returns text only (no tool_use), so loop exits normally
        final_msg = MagicMock()
        final_msg.content = [_make_text_block("Here is the answer.")]

        mock_stream = AsyncMock()
        mock_stream.text_stream = _mock_text_stream(["Here is the answer."])
        mock_stream.get_final_message = AsyncMock(return_value=final_msg)
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        worker._client = mock_client

        worker._try_assemble_context = AsyncMock(return_value=None)

        from src.ai_engine.router.types import (
            ActionType, Difficulty, IntentCategory, IntentClassification, RouteType,
        )
        intent = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.WEATHER_QUERY,
            confidence=0.9,
            difficulty=Difficulty.IMMEDIATE,
            action=ActionType.WEATHER,
        )

        with patch("src.ai_engine.workers.fast_worker.get_db_session") as mock_db, \
             patch("src.ai_engine.workers.fast_worker.create_tool_bridge") as mock_bridge:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            bridge = MagicMock()
            bridge.get_tool_definitions = MagicMock(return_value=[])
            mock_bridge.return_value = bridge

            chunks = await _collect(worker._handle_agentic(
                user_input="hello",
                intent=intent,
                user_id="00000000-0000-0000-0000-000000000001",
                family_id="00000000-0000-0000-0000-000000000002",
                context=None,
                session_id="s1",
                path_type="fast",
            ))

        # Should NOT have upgrade_to_slow chunk
        upgrade_chunks = [c for c in chunks if c.get("type") == "upgrade_to_slow"]
        assert len(upgrade_chunks) == 0

        # Should have a final content chunk
        final_chunks = [c for c in chunks if c.get("type") == "content" and c.get("is_final")]
        assert len(final_chunks) >= 1

    @pytest.mark.asyncio
    async def test_max_turns_exhausted_with_upgrade(self):
        """When max_turns exhausted and 3+ unique tools used, emit upgrade signal."""
        worker = FastWorker(model="test-model")
        worker._fast_agentic_enabled = True
        worker._fast_agentic_max_turns = 1  # Only 1 turn, will exhaust

        # Mock: LLM returns 3 different tool_use blocks
        final_msg = MagicMock()
        final_msg.content = [
            _make_tool_use_block("t1", "get_weather", {"location": "Beijing"}),
            _make_tool_use_block("t2", "query_tasks", {}),
            _make_tool_use_block("t3", "query_trips", {}),
        ]

        mock_stream = AsyncMock()
        mock_stream.text_stream = _mock_text_stream([])
        mock_stream.get_final_message = AsyncMock(return_value=final_msg)
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        worker._client = mock_client

        worker._try_assemble_context = AsyncMock(return_value=None)

        # Mock tool execution to return quickly
        worker._execute_agentic_tool = AsyncMock(return_value={
            "is_error": False,
            "summary": "done",
            "duration_ms": 50,
            "tool_output": {"result": "ok"},
        })

        from src.ai_engine.router.types import (
            ActionType, Difficulty, IntentCategory, IntentClassification, RouteType,
        )
        intent = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.WEATHER_QUERY,
            confidence=0.9,
            difficulty=Difficulty.IMMEDIATE,
            action=ActionType.WEATHER,
        )

        with patch("src.ai_engine.workers.fast_worker.get_db_session") as mock_db, \
             patch("src.ai_engine.workers.fast_worker.create_tool_bridge") as mock_bridge:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            bridge = MagicMock()
            bridge.get_tool_definitions = MagicMock(return_value=[])
            mock_bridge.return_value = bridge

            chunks = await _collect(worker._handle_agentic(
                user_input="complex query",
                intent=intent,
                user_id="00000000-0000-0000-0000-000000000001",
                family_id="00000000-0000-0000-0000-000000000002",
                context=None,
                session_id="s1",
                path_type="fast",
            ))

        upgrade_chunks = [c for c in chunks if c.get("type") == "upgrade_to_slow"]
        assert len(upgrade_chunks) == 1
        assert upgrade_chunks[0]["reason"] == "tool_limit_exceeded"
        assert isinstance(upgrade_chunks[0]["partial_context"], list)

        # Should NOT have fallback content chunk
        fallback_chunks = [
            c for c in chunks
            if c.get("type") == "content"
            and c.get("is_final")
            and "换个问法" in (c.get("content") or "")
        ]
        assert len(fallback_chunks) == 0

    @pytest.mark.asyncio
    async def test_max_turns_exhausted_no_upgrade(self):
        """When max_turns exhausted but only 1 tool used, return fallback text."""
        worker = FastWorker(model="test-model")
        worker._fast_agentic_enabled = True
        worker._fast_agentic_max_turns = 1  # Only 1 turn

        # Mock: LLM returns only 1 tool_use block
        final_msg = MagicMock()
        final_msg.content = [
            _make_tool_use_block("t1", "get_weather", {"location": "Beijing"}),
        ]

        mock_stream = AsyncMock()
        mock_stream.text_stream = _mock_text_stream([])
        mock_stream.get_final_message = AsyncMock(return_value=final_msg)
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        worker._client = mock_client

        worker._try_assemble_context = AsyncMock(return_value=None)

        worker._execute_agentic_tool = AsyncMock(return_value={
            "is_error": False,
            "summary": "done",
            "duration_ms": 50,
            "tool_output": {"result": "ok"},
        })

        from src.ai_engine.router.types import (
            ActionType, Difficulty, IntentCategory, IntentClassification, RouteType,
        )
        intent = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.WEATHER_QUERY,
            confidence=0.9,
            difficulty=Difficulty.IMMEDIATE,
            action=ActionType.WEATHER,
        )

        with patch("src.ai_engine.workers.fast_worker.get_db_session") as mock_db, \
             patch("src.ai_engine.workers.fast_worker.create_tool_bridge") as mock_bridge:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            bridge = MagicMock()
            bridge.get_tool_definitions = MagicMock(return_value=[])
            mock_bridge.return_value = bridge

            chunks = await _collect(worker._handle_agentic(
                user_input="weather?",
                intent=intent,
                user_id="00000000-0000-0000-0000-000000000001",
                family_id="00000000-0000-0000-0000-000000000002",
                context=None,
                session_id="s1",
                path_type="fast",
            ))

        # Should NOT have upgrade signal
        upgrade_chunks = [c for c in chunks if c.get("type") == "upgrade_to_slow"]
        assert len(upgrade_chunks) == 0

        # Should have fallback content
        fallback_chunks = [
            c for c in chunks
            if c.get("type") == "content"
            and c.get("is_final")
            and "换个问法" in (c.get("content") or "")
        ]
        assert len(fallback_chunks) == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _mock_text_stream_gen(texts):
    for t in texts:
        yield t


def _mock_text_stream(texts):
    return _mock_text_stream_gen(texts)
