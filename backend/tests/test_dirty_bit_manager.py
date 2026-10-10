"""Tests for DirtyBitManager — Redis-based accumulation queue with anti-starvation.

Covers:
- DirtyEntry serialization / deserialization
- Routing: SILENT → on_silent, HIGH → on_immediate, LOW/MEDIUM → queue
- Batch threshold triggering flush + on_batch_ready callback
- Anti-starvation timer (NX+EX behaviour)
- flush_dirty atomic get-and-clear
- get_queue_depth / has_timer observability helpers
- Redis unavailable fallback (immediate dispatch)
- Callback error handling (exceptions swallowed)
- _get_raw_client with/without .client attribute
"""
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.services.impact_arbitrator import (
    ExecutionMode,
    ImpactArbitrator,
    ImpactAssessment,
    ImpactLevel,
    TriggerContext,
)
from src.modules.curation.services.dirty_bit_manager import (
    DirtyBitManager,
    DirtyEntry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(
    trigger_type: str = "trip_updated",
    payload: dict = None,
    diff: dict = None,
) -> TriggerContext:
    return TriggerContext(
        trigger_type=trigger_type,
        payload=payload or {},
        diff=diff or {},
    )


def _make_entry(
    trigger_type: str = "trip_updated",
    entity_id: str = "entity-1",
    impact_level: str = "low",
    timestamp: float = 1000000.0,
    payload: dict = None,
) -> DirtyEntry:
    return DirtyEntry(
        trigger_type=trigger_type,
        entity_id=entity_id,
        impact_level=impact_level,
        timestamp=timestamp,
        payload=payload or {},
    )


class FakeRedisPipeline:
    """Minimal fake pipeline that records commands and returns preset results."""

    def __init__(self, results):
        self._results = results

    def lrange(self, key, start, end):
        pass

    def hgetall(self, key):
        pass

    def delete(self, key):
        pass

    async def execute(self):
        return self._results


def _make_redis_client(
    rpush_return=1,
    llen_return=1,
    set_return=True,
    exists_return=0,
    pipeline_results=None,
    hset_return=1,
    hlen_return=1,
    hgetall_return=None,
):
    """Create a mock async Redis client with configurable return values."""
    client = AsyncMock()
    client.rpush = AsyncMock(return_value=rpush_return)
    client.llen = AsyncMock(return_value=llen_return)
    client.set = AsyncMock(return_value=set_return)
    client.exists = AsyncMock(return_value=exists_return)
    # HASH-based operations (used by v8 DirtyBitManager)
    client.hset = AsyncMock(return_value=hset_return)
    client.hlen = AsyncMock(return_value=hlen_return)
    client.hgetall = AsyncMock(return_value=hgetall_return or {})

    if pipeline_results is not None:
        pipe = FakeRedisPipeline(pipeline_results)
        client.pipeline = MagicMock(return_value=pipe)
    else:
        pipe = FakeRedisPipeline([{}, 1, 1])
        client.pipeline = MagicMock(return_value=pipe)

    return client


def _wrap_with_client_attr(raw_client):
    """Wrap a raw client in an object with a .client property (like RedisClient)."""
    wrapper = MagicMock()
    wrapper.client = raw_client
    return wrapper


# ---------------------------------------------------------------------------
# DirtyEntry tests
# ---------------------------------------------------------------------------

class TestDirtyEntrySerialization:
    def test_serialize_roundtrip(self):
        entry = _make_entry(
            trigger_type="memory_extracted",
            entity_id="mem-42",
            impact_level="low",
            timestamp=1234567890.5,
            payload={"key": "value", "nested": {"a": 1}},
        )
        raw = entry.serialize()
        restored = DirtyEntry.deserialize(raw)
        assert restored == entry

    def test_serialize_produces_valid_json(self):
        entry = _make_entry()
        data = json.loads(entry.serialize())
        assert data["trigger_type"] == "trip_updated"
        assert data["entity_id"] == "entity-1"
        assert data["impact_level"] == "low"
        assert data["timestamp"] == 1000000.0
        assert data["payload"] == {}

    def test_deserialize_missing_payload_defaults_to_empty(self):
        raw = json.dumps({
            "trigger_type": "test",
            "entity_id": "e1",
            "impact_level": "medium",
            "timestamp": 999.0,
        })
        entry = DirtyEntry.deserialize(raw)
        assert entry.payload == {}

    def test_serialize_unicode(self):
        entry = _make_entry(payload={"name": "家庭旅行"})
        raw = entry.serialize()
        assert "家庭旅行" in raw
        restored = DirtyEntry.deserialize(raw)
        assert restored.payload["name"] == "家庭旅行"

    def test_deserialize_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            DirtyEntry.deserialize("not-json{{{")

    def test_frozen_immutability(self):
        entry = _make_entry()
        with pytest.raises(AttributeError):
            entry.trigger_type = "something_else"


# ---------------------------------------------------------------------------
# DirtyBitManager init
# ---------------------------------------------------------------------------

class TestDirtyBitManagerInit:
    def test_defaults(self):
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)
        assert mgr._batch_threshold == 5
        assert mgr._debounce_window_seconds == 300
        assert isinstance(mgr._arbitrator, ImpactArbitrator)

    def test_custom_params(self):
        redis = _make_redis_client()
        arb = ImpactArbitrator()
        mgr = DirtyBitManager(
            redis, arbitrator=arb, batch_threshold=10, debounce_window_seconds=60,
        )
        assert mgr._batch_threshold == 10
        assert mgr._debounce_window_seconds == 60
        assert mgr._arbitrator is arb

    def test_batch_threshold_min_clamp(self):
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis, batch_threshold=0)
        assert mgr._batch_threshold == 1

    def test_debounce_window_min_clamp(self):
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis, debounce_window_seconds=-5)
        assert mgr._debounce_window_seconds == 1


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    def test_family_queue_key(self):
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)
        assert mgr._family_queue_key("fam-1") == "curation:dirty:fam-1"

    def test_family_timer_key(self):
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)
        assert mgr._family_timer_key("fam-1") == "dirty_timer:fam-1"

    def test_queue_key_property(self):
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)
        assert mgr._queue_key == "curation:dirty"


# ---------------------------------------------------------------------------
# _get_raw_client
# ---------------------------------------------------------------------------

class TestGetRawClient:
    def test_with_client_attribute(self):
        raw = AsyncMock()
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)
        assert mgr._get_raw_client() is raw

    def test_without_client_attribute(self):
        raw = AsyncMock()
        # Remove the .client attribute so hasattr returns False
        raw_plain = MagicMock(spec=[])
        mgr = DirtyBitManager(raw_plain)
        assert mgr._get_raw_client() is raw_plain


# ---------------------------------------------------------------------------
# mark_dirty — SILENT routing
# ---------------------------------------------------------------------------

class TestMarkDirtySilent:
    @pytest.mark.asyncio
    async def test_silent_calls_on_silent_callback(self):
        """SILENT level triggers → on_silent callback, no queue."""
        ctx = _make_context(
            trigger_type="trip_updated",
            diff={"notes": {"old": "a", "new": "b"}},
        )
        on_silent = AsyncMock()
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_silent=on_silent,
        )

        assert result.level == ImpactLevel.SILENT
        on_silent.assert_awaited_once_with("fam-1", ctx)
        redis.rpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_silent_no_callback_still_returns(self):
        """SILENT level without callback still returns assessment."""
        ctx = _make_context(diff={"notes": {"old": "a", "new": "b"}})
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)

        result = await mgr.mark_dirty("fam-1", ctx, "ent-1")
        assert result.level == ImpactLevel.SILENT

    @pytest.mark.asyncio
    async def test_silent_callback_error_swallowed(self):
        """Exception in on_silent does not propagate."""
        ctx = _make_context(diff={"notes": {"old": "a", "new": "b"}})
        on_silent = AsyncMock(side_effect=RuntimeError("boom"))
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_silent=on_silent,
        )
        assert result.level == ImpactLevel.SILENT


# ---------------------------------------------------------------------------
# mark_dirty — HIGH routing
# ---------------------------------------------------------------------------

class TestMarkDirtyHigh:
    @pytest.mark.asyncio
    async def test_high_calls_on_immediate_callback(self):
        """HIGH level triggers → on_immediate callback, no queue."""
        ctx = _make_context(trigger_type="trip_created")
        on_immediate = AsyncMock()
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_immediate=on_immediate,
        )

        assert result.level == ImpactLevel.HIGH
        assert on_immediate.await_count == 1
        call_args = on_immediate.call_args[0]
        assert call_args[0] == "fam-1"
        assert call_args[1] is ctx
        assert isinstance(call_args[2], ImpactAssessment)
        redis.rpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_high_no_callback_still_returns(self):
        ctx = _make_context(trigger_type="trip_created")
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)

        result = await mgr.mark_dirty("fam-1", ctx, "ent-1")
        assert result.level == ImpactLevel.HIGH

    @pytest.mark.asyncio
    async def test_high_callback_error_swallowed(self):
        ctx = _make_context(trigger_type="trip_created")
        on_immediate = AsyncMock(side_effect=ValueError("fail"))
        redis = _make_redis_client()
        mgr = DirtyBitManager(redis)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_immediate=on_immediate,
        )
        assert result.level == ImpactLevel.HIGH


# ---------------------------------------------------------------------------
# mark_dirty — LOW/MEDIUM queueing
# ---------------------------------------------------------------------------

class TestMarkDirtyQueueing:
    @pytest.mark.asyncio
    async def test_low_queued_in_redis(self):
        """LOW impact → entry queued via HSET in Redis hash."""
        ctx = _make_context(trigger_type="some_update", diff={})
        raw = _make_redis_client(hset_return=1, hlen_return=1, set_return=True)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper, batch_threshold=5)

        result = await mgr.mark_dirty("fam-1", ctx, "ent-1")

        assert result.level == ImpactLevel.LOW
        raw.hset.assert_awaited_once()
        key_arg = raw.hset.call_args[0][0]
        assert key_arg == "curation:dirty:fam-1"
        # Timer should be set since we're below threshold
        raw.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_medium_queued_in_redis(self):
        """MEDIUM impact → entry queued via HSET in Redis hash."""
        ctx = _make_context(
            trigger_type="trip_updated",
            diff={"location": {"old": "A", "new": "B"}},
        )
        raw = _make_redis_client(hset_return=1, hlen_return=1, set_return=True)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper, batch_threshold=5)

        result = await mgr.mark_dirty("fam-1", ctx, "ent-1")

        assert result.level == ImpactLevel.MEDIUM
        raw.hset.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_threshold_triggers_flush_and_callback(self):
        """When queue depth reaches threshold, flush + on_batch_ready called."""
        ctx = _make_context(trigger_type="some_update", diff={})
        entry_data = _make_entry().serialize()
        # Pipeline returns hash data: {field: serialized_entry, ...}
        hash_data = {f"k{i}".encode(): entry_data for i in range(5)}

        raw = _make_redis_client(
            hset_return=1,
            hlen_return=5,
            pipeline_results=[hash_data, 1, 1],
        )
        wrapper = _wrap_with_client_attr(raw)
        on_batch_ready = AsyncMock()
        mgr = DirtyBitManager(wrapper, batch_threshold=5)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_batch_ready=on_batch_ready,
        )

        assert result.level == ImpactLevel.LOW
        on_batch_ready.assert_awaited_once()
        call_args = on_batch_ready.call_args[0]
        assert call_args[0] == "fam-1"
        assert len(call_args[1]) == 5

    @pytest.mark.asyncio
    async def test_batch_threshold_no_callback(self):
        """Threshold reached but no on_batch_ready → no error."""
        ctx = _make_context(trigger_type="some_update", diff={})
        entry_data = _make_entry().serialize()
        hash_data = {f"k{i}".encode(): entry_data for i in range(5)}

        raw = _make_redis_client(
            hset_return=1,
            hlen_return=5,
            pipeline_results=[hash_data, 1, 1],
        )
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper, batch_threshold=5)

        result = await mgr.mark_dirty("fam-1", ctx, "ent-1")
        assert result.level == ImpactLevel.LOW

    @pytest.mark.asyncio
    async def test_batch_callback_error_swallowed(self):
        """Exception in on_batch_ready does not propagate."""
        ctx = _make_context(trigger_type="some_update", diff={})
        entry_data = _make_entry().serialize()
        hash_data = {f"k{i}".encode(): entry_data for i in range(5)}

        raw = _make_redis_client(
            hset_return=1,
            hlen_return=5,
            pipeline_results=[hash_data, 1, 1],
        )
        wrapper = _wrap_with_client_attr(raw)
        on_batch_ready = AsyncMock(side_effect=RuntimeError("batch fail"))
        mgr = DirtyBitManager(wrapper, batch_threshold=5)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_batch_ready=on_batch_ready,
        )
        assert result.level == ImpactLevel.LOW

    @pytest.mark.asyncio
    async def test_below_threshold_sets_timer(self):
        """Below threshold → anti-starvation timer set via SET NX EX."""
        ctx = _make_context(trigger_type="some_update", diff={})
        raw = _make_redis_client(hset_return=1, hlen_return=2, set_return=True)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(
            wrapper, batch_threshold=5, debounce_window_seconds=120,
        )

        await mgr.mark_dirty("fam-1", ctx, "ent-1")

        raw.set.assert_awaited_once_with(
            "dirty_timer:fam-1", "1", ex=120, nx=True,
        )


# ---------------------------------------------------------------------------
# mark_dirty — Redis unavailable fallback
# ---------------------------------------------------------------------------

class TestMarkDirtyRedisFallback:
    @pytest.mark.asyncio
    async def test_redis_none_falls_back_to_immediate(self):
        """When Redis client is None, falls back to on_immediate."""
        ctx = _make_context(trigger_type="some_update", diff={})
        on_immediate = AsyncMock()

        # Create a redis_client where _get_raw_client returns None
        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_immediate=on_immediate,
        )

        assert result.level == ImpactLevel.LOW
        on_immediate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_none_fallback_error_swallowed(self):
        """Fallback immediate dispatch error is swallowed."""
        ctx = _make_context(trigger_type="some_update", diff={})
        on_immediate = AsyncMock(side_effect=RuntimeError("redis down"))

        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        result = await mgr.mark_dirty(
            "fam-1", ctx, "ent-1", on_immediate=on_immediate,
        )
        assert result.level == ImpactLevel.LOW

    @pytest.mark.asyncio
    async def test_redis_none_no_callback_returns_assessment(self):
        """Redis unavailable + no callback → returns assessment without error."""
        ctx = _make_context(trigger_type="some_update", diff={})
        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        result = await mgr.mark_dirty("fam-1", ctx, "ent-1")
        assert result.level == ImpactLevel.LOW


# ---------------------------------------------------------------------------
# flush_dirty
# ---------------------------------------------------------------------------

class TestFlushDirty:
    @pytest.mark.asyncio
    async def test_flush_returns_deserialized_entries(self):
        entries = [
            _make_entry(entity_id="e1", timestamp=100.0),
            _make_entry(entity_id="e2", timestamp=200.0),
        ]
        # hgetall returns dict {field: value}
        raw_data = {
            b"key:e1": entries[0].serialize(),
            b"key:e2": entries[1].serialize(),
        }

        raw = _make_redis_client(pipeline_results=[raw_data, 1, 1])
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        result = await mgr.flush_dirty("fam-1")

        assert len(result) == 2
        entity_ids = {r.entity_id for r in result}
        assert "e1" in entity_ids
        assert "e2" in entity_ids

    @pytest.mark.asyncio
    async def test_flush_empty_queue(self):
        raw = _make_redis_client(pipeline_results=[{}, 0, 0])
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        result = await mgr.flush_dirty("fam-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_flush_none_result(self):
        raw = _make_redis_client(pipeline_results=[None, 0, 0])
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        result = await mgr.flush_dirty("fam-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_flush_skips_corrupted_entries(self):
        """Corrupted entries are skipped with a warning, not crashing."""
        good_entry = _make_entry(entity_id="good").serialize()
        bad_entry = "not-valid-json{{{"

        raw = _make_redis_client(
            pipeline_results=[{b"good": good_entry, b"bad": bad_entry}, 1, 1],
        )
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        result = await mgr.flush_dirty("fam-1")
        assert len(result) == 1
        assert result[0].entity_id == "good"

    @pytest.mark.asyncio
    async def test_flush_redis_unavailable(self):
        """Redis unavailable → returns empty list."""
        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        result = await mgr.flush_dirty("fam-1")
        assert result == []


# ---------------------------------------------------------------------------
# get_queue_depth
# ---------------------------------------------------------------------------

class TestGetQueueDepth:
    @pytest.mark.asyncio
    async def test_returns_queue_length(self):
        raw = _make_redis_client(hlen_return=7)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        depth = await mgr.get_queue_depth("fam-1")
        assert depth == 7
        raw.hlen.assert_awaited_once_with("curation:dirty:fam-1")

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_zero(self):
        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        depth = await mgr.get_queue_depth("fam-1")
        assert depth == 0


# ---------------------------------------------------------------------------
# has_timer
# ---------------------------------------------------------------------------

class TestHasTimer:
    @pytest.mark.asyncio
    async def test_timer_active(self):
        raw = _make_redis_client(exists_return=1)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        assert await mgr.has_timer("fam-1") is True
        raw.exists.assert_awaited_once_with("dirty_timer:fam-1")

    @pytest.mark.asyncio
    async def test_timer_not_active(self):
        raw = _make_redis_client(exists_return=0)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        assert await mgr.has_timer("fam-1") is False

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_false(self):
        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        assert await mgr.has_timer("fam-1") is False


# ---------------------------------------------------------------------------
# _ensure_timeout_flush
# ---------------------------------------------------------------------------

class TestEnsureTimeoutFlush:
    @pytest.mark.asyncio
    async def test_new_timer_set(self):
        """First dirty bit sets timer → returns True."""
        raw = _make_redis_client(set_return=True)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(
            wrapper, debounce_window_seconds=60,
        )

        result = await mgr._ensure_timeout_flush("fam-1")
        assert result is True
        raw.set.assert_awaited_once_with(
            "dirty_timer:fam-1", "1", ex=60, nx=True,
        )

    @pytest.mark.asyncio
    async def test_timer_already_exists(self):
        """Timer already set → SET NX returns None/False → returns False."""
        raw = _make_redis_client(set_return=None)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper)

        result = await mgr._ensure_timeout_flush("fam-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_false(self):
        redis_wrapper = MagicMock()
        redis_wrapper.client = None
        mgr = DirtyBitManager(redis_wrapper)

        result = await mgr._ensure_timeout_flush("fam-1")
        assert result is False


# ---------------------------------------------------------------------------
# Integration-style: full flow
# ---------------------------------------------------------------------------

class TestFullFlow:
    @pytest.mark.asyncio
    async def test_accumulate_then_flush_on_threshold(self):
        """Simulate accumulating entries until threshold triggers batch flush."""
        on_batch_ready = AsyncMock()
        on_silent = AsyncMock()

        # We need a stateful fake Redis to track actual queue depth (HASH-based)
        queue_data = {}

        raw = AsyncMock()

        async def fake_hset(key, field, value):
            queue_data[field] = value
            return 1

        async def fake_hlen(key):
            return len(queue_data)

        raw.hset = AsyncMock(side_effect=fake_hset)
        raw.hlen = AsyncMock(side_effect=fake_hlen)
        raw.set = AsyncMock(return_value=True)

        # Pipeline for flush (hgetall-based)
        def make_pipeline():
            pipe = MagicMock()
            pipe.hgetall = MagicMock()
            pipe.delete = MagicMock()

            async def execute():
                data = dict(queue_data)
                queue_data.clear()
                return [data, 1, 1]

            pipe.execute = execute
            return pipe

        raw.pipeline = MagicMock(side_effect=make_pipeline)

        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper, batch_threshold=3)

        # First two entries: below threshold
        ctx1 = _make_context(trigger_type="some_update", diff={})
        await mgr.mark_dirty("fam-1", ctx1, "e1", on_batch_ready=on_batch_ready)
        assert on_batch_ready.await_count == 0
        assert len(queue_data) == 1

        ctx2 = _make_context(trigger_type="some_update", diff={})
        await mgr.mark_dirty("fam-1", ctx2, "e2", on_batch_ready=on_batch_ready)
        assert on_batch_ready.await_count == 0
        assert len(queue_data) == 2

        # Third entry: reaches threshold → flush + callback
        ctx3 = _make_context(trigger_type="some_update", diff={})
        await mgr.mark_dirty("fam-1", ctx3, "e3", on_batch_ready=on_batch_ready)
        assert on_batch_ready.await_count == 1
        # Queue should be cleared after flush
        assert len(queue_data) == 0

    @pytest.mark.asyncio
    async def test_different_families_independent_queues(self):
        """Different families use independent queue keys."""
        raw = _make_redis_client(hset_return=1, hlen_return=1, set_return=True)
        wrapper = _wrap_with_client_attr(raw)
        mgr = DirtyBitManager(wrapper, batch_threshold=5)

        ctx = _make_context(trigger_type="some_update", diff={})
        await mgr.mark_dirty("fam-A", ctx, "e1")
        await mgr.mark_dirty("fam-B", ctx, "e2")

        hset_calls = raw.hset.call_args_list
        keys_used = [call[0][0] for call in hset_calls]
        assert "curation:dirty:fam-A" in keys_used
        assert "curation:dirty:fam-B" in keys_used
