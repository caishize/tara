"""End-to-end integration test for the CORRECTION intervention flow.

Wires the real ReactiveSessionActor with a mock SDK client (no mocked
intermediate methods) and verifies the complete sequence:
  1. Actor is in GENERATING state processing a request
  2. A CORRECTION signal arrives
  3. Verify: interrupt() → partial_content emitted → bridging emitted → query()
"""

import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionType,
)
from src.ai_engine.workers.reactive_session_actor import ReactiveSessionActor

from tests.unit.reactive_actor_helpers import _make_pending_req, _make_signal


@pytest.mark.asyncio
async def test_correction_e2e_generating_state():
    """Full CORRECTION flow during GENERATING — real actor methods, mock SDK."""
    # --- Setup actor ---
    on_exit = AsyncMock()
    actor = ReactiveSessionActor(
        session_id="e2e-session-001",
        idle_seconds=60,
        on_exit=on_exit,
    )

    # Mock SDK client
    actor._pooled = MagicMock()
    actor._pooled.client = MagicMock()
    actor._pooled.client.interrupt = AsyncMock()
    actor._pooled.client.query = AsyncMock()

    # Mock Redis (for _save_stitching_context_from_obj background task)
    actor._signal_redis = AsyncMock()
    actor._signal_redis.setex = AsyncMock()

    # Track PubSub publish calls to capture emitted events
    published_events = []

    async def capture_publish(user_id, msg):
        published_events.append(msg)

    mock_pubsub = MagicMock()
    mock_pubsub.publish = AsyncMock(side_effect=capture_publish)

    # Create a pending request with accumulated partial text
    loop = asyncio.get_event_loop()
    request_future = loop.create_future()
    pending_req = _make_pending_req(
        future=request_future,
        user_input="帮我查一下北京的天气",
        all_text=["北京今天天气晴朗，温度"],
        session_id="e2e-session-001",
        pubsub=mock_pubsub,
    )

    # Set actor state: GENERATING with a pending request
    actor._set_state(GenerationState.GENERATING)
    actor._pending.append(pending_req)
    actor._current_generation_id = "gen-original-001"
    actor._current_job_id = "test-job"

    # --- Execute: send CORRECTION signal ---
    correction_signal = _make_signal(
        signal_type=InterventionType.CORRECTION.value,
        session_id="e2e-session-001",
        job_id="test-job",
        payload={"text": "不，查上海的天气"},
    )
    await actor._do_correction(correction_signal)

    # Allow background tasks (save stitch, increment gen count) to settle
    await asyncio.sleep(0.05)

    # --- Verify step 1: interrupt() was called ---
    actor._pooled.client.interrupt.assert_called_once()

    # --- Verify step 2: PARTIAL_CONTENT emitted ---
    partial_events = [
        e for e in published_events
        if e.message_type.value == "partial_content"
    ]
    assert len(partial_events) == 1, (
        f"Expected 1 PARTIAL_CONTENT event, got {len(partial_events)}"
    )
    partial_payload = partial_events[0].payload
    assert partial_payload["is_partial"] is True
    assert partial_payload["interrupted_by"] == "correction"
    assert partial_payload["generation_id"] == "gen-original-001"
    assert "北京今天天气晴朗" in partial_payload["content"]

    # --- Verify step 3: BRIDGING emitted ---
    bridging_events = [
        e for e in published_events
        if e.message_type.value == "bridging"
    ]
    assert len(bridging_events) == 1, (
        f"Expected 1 BRIDGING event, got {len(bridging_events)}"
    )
    bridging_payload = bridging_events[0].payload
    assert bridging_payload["signal_type"] == "correction"
    assert bridging_payload["continues_from"] == "gen-original-001"
    new_gen_id = bridging_payload["new_generation_id"]
    assert new_gen_id != "gen-original-001"

    # --- Verify step 4: query() called with correction prompt ---
    actor._pooled.client.query.assert_called_once()
    query_prompt = actor._pooled.client.query.call_args[0][0]
    assert "不，查上海的天气" in query_prompt
    # Should also contain prior partial text (stitching context)
    assert "北京今天天气晴朗" in query_prompt

    # --- Verify state transitions ---
    # After _query_sdk, state should be GENERATING
    assert actor._generation_state == GenerationState.GENERATING
    # Current generation_id should be updated to the new one
    assert actor._current_generation_id == new_gen_id

    # --- Verify stitching context was created and appended to history ---
    assert len(actor._stitch_history) == 1
    stitch = actor._stitch_history[0]
    assert stitch.reason == "correction"
    assert "北京今天天气晴朗" in stitch.partial_text

    # --- Cleanup ---
    tasks_to_cancel = []
    for task in list(getattr(actor, "_audit_tasks", set())):
        if not task.done():
            task.cancel()
            tasks_to_cancel.append(task)
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)


@pytest.mark.asyncio
async def test_additive_e2e_tool_executing_then_buffer_flush():
    """Full ADDITIVE flow: TOOL_EXECUTING merge → GENERATING buffer → IDLE flush.

    Sequence:
    1. Actor in TOOL_EXECUTING → ADDITIVE merges via query() with [SUPPLEMENTARY_INFO]
    2. Transition to GENERATING → second ADDITIVE is buffered (not queried)
    3. Simulate turn completion by transitioning to IDLE → flush sends combined query
    """
    # --- Setup actor ---
    on_exit = AsyncMock()
    actor = ReactiveSessionActor(
        session_id="e2e-additive-001",
        idle_seconds=60,
        on_exit=on_exit,
    )

    # Mock SDK client
    actor._pooled = MagicMock()
    actor._pooled.client = MagicMock()
    actor._pooled.client.interrupt = AsyncMock()
    actor._pooled.client.query = AsyncMock()

    # Mock Redis
    actor._signal_redis = AsyncMock()
    actor._signal_redis.setex = AsyncMock()

    # Track events
    published_events = []

    async def capture_publish(user_id, msg):
        published_events.append(msg)

    mock_pubsub = MagicMock()
    mock_pubsub.publish = AsyncMock(side_effect=capture_publish)

    # Create a pending request
    loop = asyncio.get_event_loop()
    request_future = loop.create_future()
    pending_req = _make_pending_req(
        future=request_future,
        user_input="帮我规划去日本的旅行",
        all_text=["好的，我来帮你规划日本旅行"],
        session_id="e2e-additive-001",
        pubsub=mock_pubsub,
    )
    actor._pending.append(pending_req)
    actor._current_generation_id = "gen-additive-001"
    actor._current_job_id = "test-job-additive"

    # --- Phase 1: TOOL_EXECUTING → ADDITIVE merges via query() ---
    actor._set_state(GenerationState.TOOL_EXECUTING)
    actor._active_tool = "query_trips"

    additive_1 = _make_signal(
        signal_type=InterventionType.ADDITIVE.value,
        session_id="e2e-additive-001",
        job_id="test-job-additive",
        payload={"additional_input": "预算控制在2万以内"},
    )
    result_1 = await actor._do_additive(additive_1)

    # During TOOL_EXECUTING, additive should inject directly via query()
    assert result_1 == "inject"
    actor._pooled.client.query.assert_called_once()
    first_call_arg = actor._pooled.client.query.call_args[0][0]
    assert "[SUPPLEMENTARY_INFO]" in first_call_arg
    assert "预算控制在2万以内" in first_call_arg
    assert len(actor._buffered_additives) == 0

    # --- Phase 2: GENERATING → second ADDITIVE is buffered ---
    actor._pooled.client.query.reset_mock()
    actor._set_state(GenerationState.GENERATING)

    additive_2 = _make_signal(
        signal_type=InterventionType.ADDITIVE.value,
        session_id="e2e-additive-001",
        job_id="test-job-additive",
        payload={"additional_input": "要去东京和大阪两个城市"},
    )
    result_2 = await actor._do_additive(additive_2)

    # During GENERATING, additive should buffer
    assert result_2 == "buffer"
    assert len(actor._buffered_additives) == 1
    actor._pooled.client.query.assert_not_called()

    # --- Phase 3: Simulate turn completion → IDLE → flush ---
    actor._set_state(GenerationState.IDLE)
    await actor._flush_buffered_additives()

    # Flush should send the buffered additive as a plain user message
    actor._pooled.client.query.assert_called_once()
    flush_call_arg = actor._pooled.client.query.call_args[0][0]
    assert "[SUPPLEMENTARY_INFO]" not in flush_call_arg
    assert "请回复用户" in flush_call_arg
    assert "要去东京和大阪两个城市" in flush_call_arg

    # Buffer should be empty after flush
    assert len(actor._buffered_additives) == 0

    # Additive counter should reflect both injections (1 direct + 1 flushed)
    assert actor._additive_this_turn == 2

    # --- Cleanup ---
    tasks_to_cancel = []
    for task in list(getattr(actor, "_audit_tasks", set())):
        if not task.done():
            task.cancel()
            tasks_to_cancel.append(task)
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)


@pytest.mark.asyncio
async def test_digression_e2e_generating_queue_process():
    """Full DIGRESSION flow: GENERATING → queue → turn complete → process.

    Sequence:
    1. Actor in GENERATING with a pending request
    2. DIGRESSION signal arrives → queued as new request (not immediate)
    3. Verify the digression is in the queue
    4. Verify client.query() was NOT called directly
    5. Verify the queued request has the digression text as user_input
    """
    # --- Setup actor ---
    on_exit = AsyncMock()
    actor = ReactiveSessionActor(
        session_id="e2e-digression-001",
        idle_seconds=60,
        on_exit=on_exit,
    )

    # Mock SDK client
    actor._pooled = MagicMock()
    actor._pooled.client = MagicMock()
    actor._pooled.client.interrupt = AsyncMock()
    actor._pooled.client.query = AsyncMock()

    # Mock Redis
    actor._signal_redis = AsyncMock()
    actor._signal_redis.setex = AsyncMock()

    # Track events
    published_events = []

    async def capture_publish(user_id, msg):
        published_events.append(msg)

    mock_pubsub = MagicMock()
    mock_pubsub.publish = AsyncMock(side_effect=capture_publish)

    # Create a pending request (actor is actively generating a response)
    loop = asyncio.get_event_loop()
    request_future = loop.create_future()
    pending_req = _make_pending_req(
        future=request_future,
        user_input="帮我查北京的天气",
        all_text=["北京今天天气晴朗"],
        session_id="e2e-digression-001",
        pubsub=mock_pubsub,
    )

    actor._set_state(GenerationState.GENERATING)
    actor._pending.append(pending_req)
    actor._current_generation_id = "gen-digression-001"
    actor._current_job_id = "test-job-digression"

    # --- Execute: send DIGRESSION signal ---
    digression_signal = _make_signal(
        signal_type=InterventionType.DIGRESSION.value,
        session_id="e2e-digression-001",
        job_id="test-job-digression",
        payload={"new_input": "算了，帮我订一张明天去上海的机票"},
    )
    result = await actor._do_digression(digression_signal)

    # --- Verify: digression was queued, not executed immediately ---
    assert result == "queue"

    # client.query() should NOT have been called
    actor._pooled.client.query.assert_not_called()

    # The queue should have the digression request
    assert not actor._queue.empty()

    # Dequeue and verify the request has the digression text
    queued_req = actor._queue.get_nowait()
    assert queued_req.task.user_input == "算了，帮我订一张明天去上海的机票"
    assert queued_req.task.session_id == "e2e-digression-001"

    # The original pending request should still be in _pending
    # (it hasn't been resolved since this is GENERATING, not WAITING_USER)
    assert len(actor._pending) == 1
    assert actor._pending[0] is pending_req

    # --- Cleanup ---
    tasks_to_cancel = []
    for task in list(getattr(actor, "_audit_tasks", set())):
        if not task.done():
            task.cancel()
            tasks_to_cancel.append(task)
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)


@pytest.mark.asyncio
async def test_sidekick_payload_compatibility():
    """Verify SidekickWorker's signal construction is compatible with Actor's _do_sidekick.

    Flow:
    1. Use SidekickWorker._build_signal() to construct a SIDEKICK signal
    2. Feed the signal to the Actor's _do_sidekick handler in IDLE state
    3. Verify the Actor reads injection_prompt, insight_text, urgency correctly
    4. Verify the injection_prompt is used in the SDK query
    """
    from src.ai_engine.workers.sidekick_worker import (
        INJECTION_PROMPT_TEMPLATE,
        SidekickWorker,
    )

    # --- Setup SidekickWorker and build signal ---
    worker = SidekickWorker()
    insight = {
        "insight_type": "trip_correlation",
        "insight_text": "你下周要去北京出差，张阿姨在北京，已经3个月没联系了",
        "urgency": "medium",
        "source_system": "A",
        "context_entities": ["北京", "张阿姨"],
    }
    signal = worker._build_signal(
        session_id="e2e-sidekick-001",
        job_id="test-job-sidekick",
        user_id="test-user",
        insight=insight,
    )

    # --- Verify signal structure ---
    assert signal.type == InterventionType.SIDEKICK_INSIGHT.value
    assert signal.session_id == "e2e-sidekick-001"
    assert signal.job_id == "test-job-sidekick"
    assert signal.user_id == "test-user"

    # Verify payload has the expected fields
    assert "injection_prompt" in signal.payload
    assert "insight_text" in signal.payload
    assert "urgency" in signal.payload
    assert signal.payload["urgency"] == "medium"
    assert signal.payload["insight_text"] == insight["insight_text"]

    # Verify injection_prompt follows the template
    expected_prompt = INJECTION_PROMPT_TEMPLATE.format(
        insight_text=insight["insight_text"]
    )
    assert signal.payload["injection_prompt"] == expected_prompt
    assert "[SYSTEM_INSIGHT]" in signal.payload["injection_prompt"]
    assert "[/SYSTEM_INSIGHT]" in signal.payload["injection_prompt"]
    assert "张阿姨" in signal.payload["injection_prompt"]

    # --- Setup actor and feed the signal ---
    on_exit = AsyncMock()
    actor = ReactiveSessionActor(
        session_id="e2e-sidekick-001",
        idle_seconds=60,
        on_exit=on_exit,
    )

    actor._pooled = MagicMock()
    actor._pooled.client = MagicMock()
    actor._pooled.client.query = AsyncMock()
    actor._pooled.client.interrupt = AsyncMock()

    # Provide minimal context so _build_signal_request() succeeds when
    # _query_sdk() is called with an empty _pending deque.
    mock_pubsub = MagicMock()
    mock_pubsub.publish = AsyncMock()
    mock_req = _make_pending_req(
        session_id="e2e-sidekick-001",
        job_id="test-job-sidekick",
        user_id="test-user",
        pubsub=mock_pubsub,
    )
    actor._build_signal_request = MagicMock(return_value=mock_req)

    # Set IDLE state — medium urgency should inject at IDLE
    actor._set_state(GenerationState.IDLE)

    result = await actor._do_sidekick(signal)

    # --- Verify: Actor used the injection_prompt in query ---
    assert result == "inject"
    actor._pooled.client.query.assert_called_once()
    query_arg = actor._pooled.client.query.call_args[0][0]

    # The Actor should use the pre-built injection_prompt (not re-wrap)
    assert query_arg == expected_prompt
    assert "[SYSTEM_INSIGHT]" in query_arg
    assert "张阿姨" in query_arg
    assert "北京" in query_arg

    # --- Verify rate limit counters updated ---
    assert actor._sidekick_count_session == 1
    assert actor._sidekick_count_turn == 1
    assert actor._last_sidekick_time is not None

    # --- Cleanup ---
    tasks_to_cancel = []
    for task in list(getattr(actor, "_audit_tasks", set())):
        if not task.done():
            task.cancel()
            tasks_to_cancel.append(task)
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
