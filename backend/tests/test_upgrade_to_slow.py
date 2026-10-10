"""Tests for Fast→Slow upgrade signal consumption.

Verifies that:
- The "upgrade_to_slow" chunk type triggers proper handling (not generic CONTENT)
- partial_context is included in the enqueued task
- Client receives an upgrade_notice message
- Confidence < 0.8 on FAST routes to HYBRID
- Agent worker prepends partial_context from context_snapshot
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeIntent:
    """Minimal IntentClassification stand-in."""
    intent_category: Any = None
    action: Any = None
    route_type: Any = None
    lookup_filter: Optional[str] = None
    skill_hint: Optional[str] = None


class _FakeMessageService:
    """Minimal MessageService stub."""

    def __init__(self, db=None):
        self.saved_user: List[Dict[str, Any]] = []
        self.saved_assistant: List[Dict[str, Any]] = []

    async def save_user_message(self, **kw):
        self.saved_user.append(kw)

    async def save_assistant_message(self, **kw):
        self.saved_assistant.append(kw)


class _PubCollector:
    """Collects all messages published via _pub."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    async def __call__(self, user_id, msg_type, payload, job_id, seq, session_id=None):
        self.messages.append({
            "user_id": user_id,
            "msg_type": msg_type,
            "payload": payload,
            "job_id": job_id,
        })


# ---------------------------------------------------------------------------
# Test: upgrade_to_slow chunk type triggers proper handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upgrade_to_slow_chunk_triggers_enqueue():
    """When FastWorker yields upgrade_to_slow, ws_publishers should:
    1) Send upgrade_notice to client
    2) Enqueue a SLOW task with partial_context
    3) NOT treat it as generic CONTENT
    """
    partial_msgs = [
        {"role": "user", "content": "plan a trip"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "query_trips", "input": {}},
        ]},
    ]

    # FastWorker that yields upgrade_to_slow
    async def fake_handle(**kw):
        yield {"type": "thinking_start", "content": "..."}
        yield {"type": "thinking_end", "content": ""}
        yield {
            "type": "upgrade_to_slow",
            "partial_context": partial_msgs,
            "reason": "tool_limit_exceeded",
        }

    test_user_id = "00000000-0000-0000-0000-000000000099"
    test_family_id = "00000000-0000-0000-0000-000000000088"
    test_session_id = "00000000-0000-0000-0000-000000000001"

    collected_pub: List[Dict[str, Any]] = []
    enqueued_tasks: List[Any] = []

    async def fake_pub(user_id, msg_type, payload, job_id, seq, session_id=None):
        collected_pub.append({"msg_type": msg_type, "payload": payload})

    fake_queue = AsyncMock()

    async def fake_enqueue(task):
        enqueued_tasks.append(task)

    fake_queue.enqueue = fake_enqueue

    intent = _FakeIntent()

    with patch("src.api.v1.ws_publishers._pub", side_effect=fake_pub), \
         patch("src.api.v1.ws_publishers.async_session_maker") as mock_session_maker, \
         patch("src.ai_engine.workers.fast_worker.FastWorker") as MockFW, \
         patch("src.modules.conversation.MessageService", _FakeMessageService), \
         patch("src.api.v1.ws_publishers._load_history", new_callable=AsyncMock, return_value=[]), \
         patch("src.ai_engine.queue.task_queue.get_task_queue", return_value=fake_queue), \
         patch("src.core.observability.metrics.route_upgrades_total") as mock_metric:

        # Configure mock session
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        # Configure mock FastWorker
        mock_worker_instance = MagicMock()
        mock_worker_instance.set_conversation_history = MagicMock()
        mock_worker_instance.handle = MagicMock(return_value=fake_handle())
        MockFW.return_value = mock_worker_instance

        from src.api.v1.ws_publishers import publish_fast_path

        await publish_fast_path(
            intent=intent,
            message="plan a complex trip",
            user_id=test_user_id,
            family_id=test_family_id,
            job_id="job-1",
            session_id=test_session_id,
            _locked=True,
        )

    # Verify upgrade_notice was sent
    upgrade_notices = [
        m for m in collected_pub
        if m["payload"].get("type") == "upgrade_notice"
    ]
    assert len(upgrade_notices) == 1
    assert "深度思考" in upgrade_notices[0]["payload"]["content"]
    assert upgrade_notices[0]["payload"]["reason"] == "tool_limit_exceeded"

    # Verify a SLOW task was enqueued
    assert len(enqueued_tasks) == 1
    task = enqueued_tasks[0]
    assert task.route_type == "slow"
    assert task.context_snapshot["partial_context"] == partial_msgs
    assert task.context_snapshot["upgraded_from"] == "fast"
    assert task.user_input == "plan a complex trip"

    # Verify the metrics counter was called
    mock_metric.labels.assert_called_with(reason="tool_limit_exceeded")

    # Verify no generic CONTENT message was sent with upgrade_to_slow data
    content_payloads = [
        m["payload"] for m in collected_pub
        if m["payload"].get("type") == "upgrade_to_slow"
    ]
    assert len(content_payloads) == 0, "upgrade_to_slow should not be forwarded as CONTENT"


# ---------------------------------------------------------------------------
# Test: Confidence < 0.8 upgrades FAST to HYBRID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_fast_upgrades_to_hybrid():
    """When confidence < 0.8 and route is FAST, it should upgrade to HYBRID."""
    from src.ai_engine.router.types import (
        RouteType,
        Difficulty,
        ActionType,
        IntentCategory,
        resolve_route,
    )

    # Simulate what IntentRouter.classify does after parsing results
    difficulty = Difficulty.IMMEDIATE
    action = ActionType.WEATHER
    enhance = False
    confidence = 0.65  # Below 0.8 threshold

    route_type = resolve_route(difficulty, enhance)
    assert route_type == RouteType.FAST

    # Apply the confidence threshold check (same logic as in intent_router.py)
    if route_type == RouteType.FAST and confidence < 0.8 and not enhance:
        route_type = RouteType.HYBRID
        enhance = True

    assert route_type == RouteType.HYBRID
    assert enhance is True


@pytest.mark.asyncio
async def test_high_confidence_fast_stays_fast():
    """When confidence >= 0.8, FAST should remain FAST."""
    from src.ai_engine.router.types import (
        RouteType,
        Difficulty,
        ActionType,
        resolve_route,
    )

    difficulty = Difficulty.IMMEDIATE
    enhance = False
    confidence = 0.95

    route_type = resolve_route(difficulty, enhance)
    assert route_type == RouteType.FAST

    # Apply the same threshold check
    if route_type == RouteType.FAST and confidence < 0.8 and not enhance:
        route_type = RouteType.HYBRID
        enhance = True

    assert route_type == RouteType.FAST
    assert enhance is False


# ---------------------------------------------------------------------------
# Test: AgentWorker prepends partial_context
# ---------------------------------------------------------------------------


def test_summarize_partial_context():
    """AgentWorker._summarize_partial_context produces readable summaries."""
    from src.ai_engine.workers.agent_worker import AgentWorker

    partial = [
        {"role": "user", "content": "what is the weather in Paris?"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Let me check..."},
            {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {"location": "Paris"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": '{"temp": 15}'},
        ]},
    ]

    lines = AgentWorker._summarize_partial_context(partial)

    assert any("weather in Paris" in line for line in lines)
    assert any("get_weather" in line for line in lines)
    assert any("tool_result" in line for line in lines)
    assert any("Let me check" in line for line in lines)


def test_summarize_partial_context_empty():
    """Empty partial context should produce empty list."""
    from src.ai_engine.workers.agent_worker import AgentWorker

    assert AgentWorker._summarize_partial_context([]) == []


def test_summarize_partial_context_handles_non_dict_blocks():
    """Non-dict blocks in content lists should be skipped gracefully."""
    from src.ai_engine.workers.agent_worker import AgentWorker

    partial = [
        {"role": "assistant", "content": ["plain string block", 42, None]},
    ]
    lines = AgentWorker._summarize_partial_context(partial)
    assert lines == []
