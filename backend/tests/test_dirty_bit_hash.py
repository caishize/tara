"""Tests for DirtyBitManager HASH-based implementation and patrol task.

Covers:
- HSET/HGETALL/HLEN operations (migrated from LIST)
- Natural deduplication via HASH field keys
- flush_dirty() returns deserialized entries
- get_queue_depth() uses HLEN
- get_stale_families() detects orphaned queues
- patrol_dirty_timers task dispatches curation for stale families
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.services.dirty_bit_manager import (
    DirtyBitManager,
    DirtyEntry,
)
from src.modules.curation.services.impact_arbitrator import (
    ExecutionMode,
    ImpactArbitrator,
    ImpactAssessment,
    ImpactLevel,
    TriggerContext,
)


# ---------------------------------------------------------------------------
# Fake async Redis client that simulates HASH operations
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal async Redis mock supporting HASH ops, SET NX, SCAN, EXISTS."""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._pipelines: List["FakePipeline"] = []

    async def hset(self, key: str, field: str, value: str) -> int:
        if key not in self._data:
            self._data[key] = {}
        is_new = field not in self._data[key]
        self._data[key][field] = value
        return 1 if is_new else 0

    async def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self._data.get(key, {}))

    async def hlen(self, key: str) -> int:
        return len(self._data.get(key, {}))

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                count += 1
        return count

    async def set(self, key: str, value: str, ex: Optional[int] = None, nx: bool = False) -> Optional[bool]:
        if nx and key in self._data:
            return None
        self._data[key] = value
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def scan(self, cursor: int = 0, match: str = "*", count: int = 100):
        import fnmatch
        matched = [k for k in self._data if fnmatch.fnmatch(k, match)]
        return (0, matched)

    def pipeline(self) -> "FakePipeline":
        pipe = FakePipeline(self)
        return pipe


class FakePipeline:
    """Fake pipeline that queues commands and executes them on .execute()."""

    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._cmds: List = []

    def hgetall(self, key: str) -> "FakePipeline":
        self._cmds.append(("hgetall", key))
        return self

    def delete(self, key: str) -> "FakePipeline":
        self._cmds.append(("delete", key))
        return self

    async def execute(self) -> List[Any]:
        results = []
        for cmd, key in self._cmds:
            if cmd == "hgetall":
                results.append(await self._redis.hgetall(key))
            elif cmd == "delete":
                results.append(await self._redis.delete(key))
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(trigger_type: str = "trip_updated", payload: Optional[dict] = None) -> TriggerContext:
    return TriggerContext(
        trigger_type=trigger_type,
        payload=payload or {"trip_id": "t1"},
        diff={},
    )


def _low_arbitrator() -> ImpactArbitrator:
    """Arbitrator that always returns LOW."""
    arb = ImpactArbitrator()
    arb.assess = MagicMock(return_value=ImpactAssessment(
        level=ImpactLevel.LOW,
        should_push=False,
        should_brief=False,
        execution_mode=ExecutionMode.T2_INCREMENTAL,
        reason="test_low",
    ))
    return arb


# ---------------------------------------------------------------------------
# Tests: HASH-based mark_dirty + flush
# ---------------------------------------------------------------------------

class TestDirtyBitHash:

    @pytest.mark.asyncio
    async def test_mark_dirty_uses_hset(self):
        """mark_dirty stores entry in HASH field '{trigger_type}:{entity_id}'."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        ctx = _make_context("trip_updated")
        await mgr.mark_dirty("fam-1", ctx, "entity-abc")

        queue_key = "curation:dirty:fam-1"
        assert queue_key in redis._data
        assert isinstance(redis._data[queue_key], dict)
        assert "trip_updated:entity-abc" in redis._data[queue_key]

        raw = redis._data[queue_key]["trip_updated:entity-abc"]
        parsed = json.loads(raw)
        assert parsed["trigger_type"] == "trip_updated"
        assert parsed["entity_id"] == "entity-abc"

    @pytest.mark.asyncio
    async def test_deduplication_on_same_entity(self):
        """Repeated mark_dirty for same trigger_type:entity_id overwrites (dedup)."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        ctx1 = _make_context("trip_updated", {"version": 1})
        ctx2 = _make_context("trip_updated", {"version": 2})

        await mgr.mark_dirty("fam-1", ctx1, "entity-1")
        await mgr.mark_dirty("fam-1", ctx2, "entity-1")

        # HASH should only have 1 field, not 2
        depth = await mgr.get_queue_depth("fam-1")
        assert depth == 1

        # Payload should be the latest
        raw = redis._data["curation:dirty:fam-1"]["trip_updated:entity-1"]
        parsed = json.loads(raw)
        assert parsed["payload"]["version"] == 2

    @pytest.mark.asyncio
    async def test_different_entities_create_different_fields(self):
        """Different entity_ids create distinct HASH fields."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        await mgr.mark_dirty("fam-1", _make_context("trip_updated"), "e1")
        await mgr.mark_dirty("fam-1", _make_context("memory_extracted"), "e2")

        depth = await mgr.get_queue_depth("fam-1")
        assert depth == 2

    @pytest.mark.asyncio
    async def test_flush_dirty_returns_entries_and_clears(self):
        """flush_dirty returns all entries and removes the HASH key."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        await mgr.mark_dirty("fam-1", _make_context("trip_updated"), "e1")
        await mgr.mark_dirty("fam-1", _make_context("memory_extracted"), "e2")

        entries = await mgr.flush_dirty("fam-1")
        assert len(entries) == 2
        assert all(isinstance(e, DirtyEntry) for e in entries)

        # Queue should be empty after flush
        depth = await mgr.get_queue_depth("fam-1")
        assert depth == 0

    @pytest.mark.asyncio
    async def test_batch_threshold_triggers_flush(self):
        """When queue depth reaches batch_threshold, on_batch_ready is called."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=2)

        batch_callback = AsyncMock()

        await mgr.mark_dirty("fam-1", _make_context("t1"), "e1", on_batch_ready=batch_callback)
        batch_callback.assert_not_called()

        await mgr.mark_dirty("fam-1", _make_context("t2"), "e2", on_batch_ready=batch_callback)
        batch_callback.assert_called_once()

        # Check the callback received the flushed entries
        args = batch_callback.call_args
        assert args[0][0] == "fam-1"
        entries = args[0][1]
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_get_queue_depth_uses_hlen(self):
        """get_queue_depth returns correct count based on HASH fields."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        assert await mgr.get_queue_depth("fam-1") == 0

        await mgr.mark_dirty("fam-1", _make_context("a"), "e1")
        assert await mgr.get_queue_depth("fam-1") == 1

        await mgr.mark_dirty("fam-1", _make_context("b"), "e2")
        assert await mgr.get_queue_depth("fam-1") == 2


# ---------------------------------------------------------------------------
# Tests: get_stale_families
# ---------------------------------------------------------------------------

class TestGetStaleFamilies:

    @pytest.mark.asyncio
    async def test_returns_family_without_timer(self):
        """Family with dirty queue but no timer key is stale."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        # Manually insert a dirty queue without timer
        await redis.hset("curation:dirty:fam-orphan", "trip:e1", '{"trigger_type":"trip","entity_id":"e1","impact_level":"low","timestamp":1.0,"payload":{}}')

        stale = await mgr.get_stale_families()
        assert "fam-orphan" in stale

    @pytest.mark.asyncio
    async def test_excludes_family_with_timer(self):
        """Family with both dirty queue and timer key is NOT stale."""
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator(), batch_threshold=10)

        # Insert queue + timer
        await redis.hset("curation:dirty:fam-ok", "trip:e1", '{}')
        await redis.set("dirty_timer:fam-ok", "1")

        stale = await mgr.get_stale_families()
        assert "fam-ok" not in stale

    @pytest.mark.asyncio
    async def test_empty_redis_returns_empty(self):
        redis = FakeRedis()
        mgr = DirtyBitManager(redis, arbitrator=_low_arbitrator())
        stale = await mgr.get_stale_families()
        assert stale == []


# ---------------------------------------------------------------------------
# Tests: DirtyEntry serialization
# ---------------------------------------------------------------------------

class TestDirtyEntrySerialization:

    def test_roundtrip(self):
        entry = DirtyEntry(
            trigger_type="trip_updated",
            entity_id="abc-123",
            impact_level="low",
            timestamp=1700000000.0,
            payload={"trip_id": "t1", "name": "Test"},
        )
        raw = entry.serialize()
        restored = DirtyEntry.deserialize(raw)
        assert restored == entry

    def test_deserialize_missing_payload(self):
        raw = json.dumps({
            "trigger_type": "x",
            "entity_id": "y",
            "impact_level": "low",
            "timestamp": 1.0,
        })
        entry = DirtyEntry.deserialize(raw)
        assert entry.payload == {}


# ---------------------------------------------------------------------------
# Tests: patrol_dirty_timers
# ---------------------------------------------------------------------------

class TestPatrolDirtyTimers:

    @pytest.mark.asyncio
    async def test_patrol_flushes_stale_families(self):
        """patrol_dirty_timers flushes orphaned queues and dispatches curation."""
        from src.modules.curation.tasks import _patrol_dirty_timers

        stale_family_id = "00000000-0000-0000-0000-000000000077"
        fake_redis = FakeRedis()
        # Pre-populate an orphaned dirty queue (no timer)
        await fake_redis.hset(
            f"curation:dirty:{stale_family_id}",
            "trip:e1",
            json.dumps({
                "trigger_type": "trip_updated",
                "entity_id": "e1",
                "impact_level": "low",
                "timestamp": time.time(),
                "payload": {},
            }),
        )

        # Build a fake RedisClient wrapper whose .client property returns
        # fake_redis (the underlying async redis object used by DirtyBitManager).
        class FakeRedisClient:
            def __init__(self):
                self._client = fake_redis

            @property
            def client(self):
                return self._client

            async def connect(self):
                pass

            async def disconnect(self):
                pass

        fake_redis_client = FakeRedisClient()

        with patch(
            "src.core.cache.RedisClient",
            return_value=fake_redis_client,
        ), patch(
            "src.modules.curation.tasks.trigger_curation_async",
            return_value=True,
        ) as mock_trigger:
            result = await _patrol_dirty_timers()

        assert result["status"] == "ok"
        assert result["flushed"] == 1
        mock_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_patrol_no_stale_families(self):
        """patrol returns flushed=0 when no stale families exist."""
        from src.modules.curation.tasks import _patrol_dirty_timers

        fake_redis = FakeRedis()

        class FakeRedisClient:
            def __init__(self):
                self._client = fake_redis

            @property
            def client(self):
                return self._client

            async def connect(self):
                pass

            async def disconnect(self):
                pass

        with patch(
            "src.core.cache.RedisClient",
            return_value=FakeRedisClient(),
        ):
            result = await _patrol_dirty_timers()

        assert result["status"] == "ok"
        assert result["flushed"] == 0

    @pytest.mark.asyncio
    async def test_patrol_skips_when_no_redis(self):
        """patrol gracefully skips when Redis is unavailable."""
        from src.modules.curation.tasks import _patrol_dirty_timers

        class FailingRedisClient:
            async def connect(self):
                raise ConnectionError("Redis unavailable")

            async def disconnect(self):
                pass

        with patch(
            "src.core.cache.RedisClient",
            return_value=FailingRedisClient(),
        ):
            result = await _patrol_dirty_timers()

        assert result["status"] == "skipped"
        assert result["reason"] == "no_redis"
