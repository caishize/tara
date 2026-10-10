"""
Tests for the Redis Sorted Set scheduler core.

Uses an in-memory mock Redis to test schedule/unschedule/pop_due
and calculate_next_run without a real Redis instance.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.scheduler.redis_scheduler import (
    RedisScheduleStore,
    SyncRedisScheduleStore,
    TaskScheduleConfig,
    ScheduleType,
    calculate_next_run,
    _key,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


class FakeAsyncRedis:
    """In-memory Redis mock for sorted set operations."""

    def __init__(self):
        self._sets: dict[str, dict[str, float]] = {}
        self._script_sha = "fake_sha"

    async def zadd(self, key, mapping, nx=False):
        if key not in self._sets:
            self._sets[key] = {}
        added = 0
        for member, score in mapping.items():
            if nx and member in self._sets[key]:
                continue
            if member not in self._sets[key]:
                added += 1
            self._sets[key][member] = score
        return added

    async def zrem(self, key, *members):
        if key not in self._sets:
            return 0
        removed = 0
        for m in members:
            if m in self._sets[key]:
                del self._sets[key][m]
                removed += 1
        return removed

    async def zscore(self, key, member):
        return self._sets.get(key, {}).get(member)

    async def zcard(self, key):
        return len(self._sets.get(key, {}))

    async def zcount(self, key, min_score, max_score):
        items = self._sets.get(key, {})
        return sum(1 for s in items.values() if min_score <= s <= max_score)

    async def zrangebyscore(self, key, min_score, max_score, start=0, num=None, withscores=False):
        items = self._sets.get(key, {})
        if isinstance(max_score, str) and max_score == "+inf":
            max_score = float("inf")
        filtered = [(m, s) for m, s in items.items() if float(min_score) <= s <= float(max_score)]
        filtered.sort(key=lambda x: x[1])
        if num is not None:
            filtered = filtered[start:start + num]
        else:
            filtered = filtered[start:]
        if withscores:
            return filtered
        return [m for m, _ in filtered]

    async def script_load(self, script):
        return self._script_sha

    async def evalsha(self, sha, numkeys, *args):
        # Simulate the Lua pop script: ZRANGEBYSCORE + ZREM
        key = args[0]
        now_ts = float(args[1])
        batch = int(args[2])
        items = await self.zrangebyscore(key, 0, now_ts, start=0, num=batch)
        if items:
            await self.zrem(key, *items)
        return items


class FakeSyncRedis:
    """In-memory sync Redis mock."""

    def __init__(self):
        self._sets: dict[str, dict[str, float]] = {}

    def zadd(self, key, mapping, nx=False):
        if key not in self._sets:
            self._sets[key] = {}
        added = 0
        for member, score in mapping.items():
            if nx and member in self._sets[key]:
                continue
            if member not in self._sets[key]:
                added += 1
            self._sets[key][member] = score
        return added

    def zrem(self, key, *members):
        if key not in self._sets:
            return 0
        removed = 0
        for m in members:
            if m in self._sets[key]:
                del self._sets[key][m]
                removed += 1
        return removed


@pytest.fixture
def fake_redis():
    return FakeAsyncRedis()


@pytest.fixture
def store(fake_redis):
    return RedisScheduleStore(fake_redis)


@pytest.fixture
def sync_store():
    return SyncRedisScheduleStore(FakeSyncRedis())


# ─── RedisScheduleStore Tests ────────────────────────────────────────────────


class TestRedisScheduleStore:

    @pytest.mark.asyncio
    async def test_schedule_and_get_next_run(self, store):
        next_run = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        result = await store.schedule("briefing", "user-1", next_run)
        assert result is True

        got = await store.get_next_run("briefing", "user-1")
        assert got is not None
        assert abs((got - next_run).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_schedule_overwrites_existing(self, store):
        t1 = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)

        await store.schedule("briefing", "user-1", t1)
        await store.schedule("briefing", "user-1", t2)

        got = await store.get_next_run("briefing", "user-1")
        assert abs((got - t2).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_schedule_nx_does_not_overwrite(self, store):
        t1 = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)

        await store.schedule("briefing", "user-1", t1)
        result = await store.schedule_nx("briefing", "user-1", t2)
        assert result is False

        got = await store.get_next_run("briefing", "user-1")
        assert abs((got - t1).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_schedule_nx_adds_if_missing(self, store):
        t1 = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        result = await store.schedule_nx("briefing", "user-1", t1)
        assert result is True

    @pytest.mark.asyncio
    async def test_unschedule(self, store):
        t = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        await store.schedule("briefing", "user-1", t)

        result = await store.unschedule("briefing", "user-1")
        assert result is True

        got = await store.get_next_run("briefing", "user-1")
        assert got is None

    @pytest.mark.asyncio
    async def test_unschedule_nonexistent(self, store):
        result = await store.unschedule("briefing", "no-such-user")
        assert result is False

    @pytest.mark.asyncio
    async def test_pop_due(self, store):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)
        future = now + timedelta(hours=1)

        await store.schedule("briefing", "user-past", past)
        await store.schedule("briefing", "user-future", future)

        due = await store.pop_due("briefing", batch_size=10)
        assert "user-past" in due
        assert "user-future" not in due

        # After pop, the past entry should be removed
        got = await store.get_next_run("briefing", "user-past")
        assert got is None

        # Future entry should still be there
        got = await store.get_next_run("briefing", "user-future")
        assert got is not None

    @pytest.mark.asyncio
    async def test_pop_due_respects_batch_size(self, store):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)

        for i in range(10):
            await store.schedule("briefing", f"user-{i}", past)

        due = await store.pop_due("briefing", batch_size=3)
        assert len(due) == 3

    @pytest.mark.asyncio
    async def test_pop_due_empty(self, store):
        due = await store.pop_due("briefing")
        assert due == []

    @pytest.mark.asyncio
    async def test_get_stats(self, store):
        now = datetime.now(timezone.utc)
        await store.schedule("briefing", "u1", now - timedelta(minutes=5))
        await store.schedule("briefing", "u2", now + timedelta(hours=1))
        await store.schedule("briefing", "u3", now + timedelta(hours=2))

        stats = await store.get_stats("briefing")
        assert stats["task_name"] == "briefing"
        assert stats["total_scheduled"] == 3
        assert stats["overdue"] == 1
        assert stats["next_run"] is not None


class TestSyncRedisScheduleStore:

    def test_schedule_and_unschedule(self, sync_store):
        t = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        sync_store.schedule("briefing", "user-1", t)
        result = sync_store.unschedule("briefing", "user-1")
        assert result is True

    def test_schedule_nx(self, sync_store):
        t1 = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)

        r1 = sync_store.schedule_nx("briefing", "user-1", t1)
        assert r1 is True

        r2 = sync_store.schedule_nx("briefing", "user-1", t2)
        assert r2 is False


# ─── calculate_next_run Tests ────────────────────────────────────────────────


class TestCalculateNextRun:

    def test_daily_next_day_if_past(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="user",
            schedule_type=ScheduleType.DAILY,
            default_hour=8, default_minute=30,
        )
        now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)  # 10:00, past 8:30
        result = calculate_next_run(config, now=now)
        assert result.day == 2
        assert result.hour == 8
        assert result.minute == 30

    def test_daily_same_day_if_before(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="user",
            schedule_type=ScheduleType.DAILY,
            default_hour=20, default_minute=0,
        )
        now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        result = calculate_next_run(config, now=now)
        assert result.day == 1
        assert result.hour == 20

    def test_weekly(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="user",
            schedule_type=ScheduleType.WEEKLY,
            default_day_of_week=6,  # Sunday
            default_hour=3,
        )
        # 2026-03-01 is a Sunday (weekday=6)
        now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)  # past 3:00
        result = calculate_next_run(config, now=now)
        assert result.weekday() == 6  # Next Sunday
        assert result > now

    def test_interval(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="family",
            schedule_type=ScheduleType.INTERVAL,
            default_interval_minutes=60,
        )
        now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        result = calculate_next_run(config, now=now)
        assert result == now + timedelta(minutes=60)

    def test_interval_custom(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="family",
            schedule_type=ScheduleType.INTERVAL,
            default_interval_minutes=60,
        )
        now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        result = calculate_next_run(config, now=now, custom_interval=30)
        assert result == now + timedelta(minutes=30)

    def test_once(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="reminder",
            schedule_type=ScheduleType.ONCE,
        )
        now = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        result = calculate_next_run(config, now=now)
        assert result == now

    def test_custom_hour_overrides_default(self):
        config = TaskScheduleConfig(
            task_name="test", entity_type="user",
            schedule_type=ScheduleType.DAILY,
            default_hour=8, default_minute=30,
        )
        now = datetime(2026, 3, 1, 5, 0, tzinfo=timezone.utc)
        result = calculate_next_run(config, now=now, custom_hour=10)
        assert result.hour == 10
        assert result.minute == 30


# ─── Key format ───────────────────────────────────────────────────────────────


class TestKeyFormat:

    def test_key(self):
        assert _key("briefing") == "schedule:briefing"
        assert _key("secretary.curate_family") == "schedule:secretary.curate_family"
