"""Signal processing tests for ReactiveSessionActor.

Covers:
- Signal queue and eviction (_enqueue_signal)
- Signal dispatch routing (_dispatch_signal)
- Job ID mismatch rejection (_should_accept_signal)
- Signal dedup rejection
- Signal dedup deque properties
- _extract_signal_text helper
"""

from unittest.mock import AsyncMock

import pytest

from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionType,
)
from src.ai_engine.workers.reactive_session_actor import (
    _MAX_INTERVENTION_QUEUE,
    _SIGNAL_DEDUP_SIZE,
)

from tests.unit.reactive_actor_helpers import _make_signal


# ---------------------------------------------------------------------------
# Signal queue and eviction
# ---------------------------------------------------------------------------


class TestEnqueueSignal:
    @pytest.mark.asyncio
    async def test_cancel_always_enqueues(self, actor):
        signal = _make_signal(
            signal_type=InterventionType.CANCEL.value,
            priority=1,
        )
        await actor._enqueue_signal(signal)
        assert not actor._pending_interventions.empty()
        entry = actor._pending_interventions.get_nowait()
        enqueued = entry[2]  # PriorityQueue stores (priority, sequence, signal)
        assert enqueued.type == InterventionType.CANCEL.value

    @pytest.mark.asyncio
    async def test_evicts_lowest_priority_when_full(self, actor):
        # Fill queue with low-priority signals
        for i in range(_MAX_INTERVENTION_QUEUE):
            low_pri = _make_signal(
                signal_type=InterventionType.DIGRESSION.value,
                signal_id=f"low-{i}",
                priority=3,
            )
            await actor._enqueue_signal(low_pri)

        # Now enqueue a higher priority signal
        hi_pri = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id="high-priority",
            priority=2,
        )
        await actor._enqueue_signal(hi_pri)

        # Queue should contain the high-priority signal
        items = []
        while not actor._pending_interventions.empty():
            entry = actor._pending_interventions.get_nowait()
            items.append(entry[2])  # PriorityQueue stores (priority, sequence, signal)
        signal_ids = [s.signal_id for s in items]
        assert "high-priority" in signal_ids


# ---------------------------------------------------------------------------
# Signal dispatch routing
# ---------------------------------------------------------------------------


class TestDispatchSignal:
    @pytest.mark.asyncio
    async def test_dispatches_correction(self, actor):
        actor._do_correction = AsyncMock()
        signal = _make_signal(signal_type=InterventionType.CORRECTION.value)
        await actor._dispatch_signal(signal)
        actor._do_correction.assert_called_once_with(signal)
        assert actor._correction_count == 1
        assert actor._intervention_count == 1

    @pytest.mark.asyncio
    async def test_dispatches_cancel(self, actor):
        actor._do_cancel = AsyncMock()
        signal = _make_signal(signal_type=InterventionType.CANCEL.value)
        await actor._dispatch_signal(signal)
        actor._do_cancel.assert_called_once_with(signal)
        # CANCEL is exempt from budget -- counters should not increment
        assert actor._intervention_count == 0
        assert actor._correction_count == 0

    @pytest.mark.asyncio
    async def test_dispatches_additive(self, actor):
        actor._do_additive = AsyncMock()
        signal = _make_signal(signal_type=InterventionType.ADDITIVE.value)
        await actor._dispatch_signal(signal)
        actor._do_additive.assert_called_once_with(signal)

    @pytest.mark.asyncio
    async def test_dispatches_confirm(self, actor):
        actor._do_confirm = AsyncMock()
        signal = _make_signal(signal_type=InterventionType.CONFIRM.value)
        await actor._dispatch_signal(signal)
        actor._do_confirm.assert_called_once_with(signal)

    @pytest.mark.asyncio
    async def test_dispatches_digression(self, actor):
        actor._do_digression = AsyncMock()
        signal = _make_signal(signal_type=InterventionType.DIGRESSION.value)
        await actor._dispatch_signal(signal)
        actor._do_digression.assert_called_once_with(signal)

    @pytest.mark.asyncio
    async def test_dispatches_sidekick(self, actor):
        actor._do_sidekick = AsyncMock()
        signal = _make_signal(signal_type=InterventionType.SIDEKICK_INSIGHT.value)
        await actor._dispatch_signal(signal)
        actor._do_sidekick.assert_called_once_with(signal)

    @pytest.mark.asyncio
    async def test_unknown_type_logs_warning(self, actor):
        signal = _make_signal(signal_type="unknown_type")
        # Should not raise
        await actor._dispatch_signal(signal)

    @pytest.mark.asyncio
    async def test_budget_increments(self, actor):
        actor._do_additive = AsyncMock()
        actor._reset_session = AsyncMock()  # Prevent reset from clearing counters
        # Pre-handler budget check blocks signals at max (5), so only 5 are counted
        for i in range(6):
            signal = _make_signal(signal_type=InterventionType.ADDITIVE.value)
            await actor._dispatch_signal(signal)
        assert actor._intervention_count == actor._budget.max_interventions_per_session

    @pytest.mark.asyncio
    async def test_correction_budget_increments(self, actor):
        actor._do_correction = AsyncMock()
        actor._reset_session = AsyncMock()  # Prevent reset from clearing counters
        # Pre-handler budget check blocks at correction max (3), so only 3 counted
        for i in range(4):
            signal = _make_signal(signal_type=InterventionType.CORRECTION.value)
            await actor._dispatch_signal(signal)
        assert actor._correction_count == actor._budget.max_correction_per_session


# ---------------------------------------------------------------------------
# Boundary: Job ID mismatch rejection
# ---------------------------------------------------------------------------


class TestJobIdMismatchRejection:
    def test_signal_with_mismatched_job_id_is_rejected(self, actor):
        """Signal with non-matching job_id should be rejected by _should_accept_signal."""
        actor._current_job_id = "job-A"
        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            job_id="job-B",
        )
        assert actor._should_accept_signal(signal) is False

    def test_signal_with_matching_job_id_is_accepted(self, actor):
        """Signal with matching job_id should be accepted by _should_accept_signal."""
        actor._current_job_id = "job-A"
        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            job_id="job-A",
        )
        assert actor._should_accept_signal(signal) is True

    def test_signal_accepted_when_no_current_job(self, actor):
        """Signal should be accepted when no current_job_id is set."""
        actor._current_job_id = None
        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            job_id="any-job",
        )
        assert actor._should_accept_signal(signal) is True


# ---------------------------------------------------------------------------
# Boundary: Signal dedup rejection
# ---------------------------------------------------------------------------


class TestSignalDedupRejection:
    def test_duplicate_signal_id_rejected(self, actor):
        """Submitting the same signal_id twice: second should be rejected."""
        shared_id = "test-dedup-id-1"
        signal_a = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id=shared_id,
        )
        signal_b = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id=shared_id,
        )

        assert actor._should_accept_signal(signal_a) is True
        assert actor._should_accept_signal(signal_b) is False

    def test_different_signal_ids_both_accepted(self, actor):
        """Two distinct signal_ids should both be accepted."""
        signal_a = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id="id-1",
        )
        signal_b = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id="id-2",
        )

        assert actor._should_accept_signal(signal_a) is True
        assert actor._should_accept_signal(signal_b) is True
        # Both IDs should be in the dedup deque
        assert "id-1" in actor._signal_dedup
        assert "id-2" in actor._signal_dedup


# ---------------------------------------------------------------------------
# Signal dedup
# ---------------------------------------------------------------------------


class TestSignalDedup:
    def test_dedup_deque_initial_size(self, actor):
        assert len(actor._signal_dedup) == 0

    def test_dedup_maxlen(self, actor):
        assert actor._signal_dedup.maxlen == _SIGNAL_DEDUP_SIZE


# ---------------------------------------------------------------------------
# _extract_signal_text helper
# ---------------------------------------------------------------------------


class TestExtractSignalText:
    def test_prefers_corrected_input(self, actor):
        signal = _make_signal(payload={
            "corrected_input": "corrected",
            "additional_input": "additional",
            "text": "fallback",
        })
        assert actor._extract_signal_text(signal) == "corrected"

    def test_prefers_additional_input(self, actor):
        signal = _make_signal(payload={
            "additional_input": "additional",
            "text": "fallback",
        })
        assert actor._extract_signal_text(signal) == "additional"

    def test_prefers_new_input(self, actor):
        signal = _make_signal(payload={
            "new_input": "digression text",
            "text": "fallback",
        })
        assert actor._extract_signal_text(signal) == "digression text"

    def test_falls_back_to_text(self, actor):
        signal = _make_signal(payload={"text": "fallback"})
        assert actor._extract_signal_text(signal) == "fallback"

    def test_empty_payload_returns_empty(self, actor):
        signal = _make_signal(payload={})
        assert actor._extract_signal_text(signal) == ""

    def test_skips_empty_string_keys(self, actor):
        """Empty string values for specific keys should fall through."""
        signal = _make_signal(payload={
            "corrected_input": "",
            "additional_input": "",
            "text": "fallback",
        })
        assert actor._extract_signal_text(signal) == "fallback"
