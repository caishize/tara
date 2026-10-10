"""Tests for context hash cache in ContextAssembler.

Covers: cache miss, cache hit, invalidation, TTL, separate user caches,
and graceful fallback when Redis is unavailable.
"""

from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.ai_engine.context_assembler import (
    CONTEXT_CACHE_PREFIX,
    CONTEXT_CACHE_TTL,
    ContextAssembler,
    ContextItem,
    ContextMetadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = uuid4()
FAMILY_ID = uuid4()
SESSION_ID = "sess-001"
MESSAGE = "今天天气怎么样"


def _make_l1_fetcher(items: Optional[List[ContextItem]] = None):
    """Return an async callable that yields L1 items."""
    async def fetcher(user_id, family_id):
        return items or [
            ContextItem(layer="l1", source="note", content="系统事实", tokens=10),
        ]
    return fetcher


def _make_l2_fetcher(items: Optional[List[ContextItem]] = None):
    async def fetcher(user_id, session_id):
        return items or [
            ContextItem(layer="l2", source="conversation", content="对话历史", tokens=10),
        ]
    return fetcher


def _make_assembler(**kwargs) -> ContextAssembler:
    defaults = dict(
        l1_fetcher=_make_l1_fetcher(),
        l2_fetcher=_make_l2_fetcher(),
    )
    defaults.update(kwargs)
    return ContextAssembler(**defaults)


class FakeRedisClient:
    """In-memory Redis-like client for testing cache logic."""

    def __init__(self):
        self._store: Dict[str, Tuple[str, Optional[int]]] = {}  # key -> (value, ttl)
        self.client = self  # expose self as .client for scan_iter

    async def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        return entry[0]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, ex: Optional[int] = None) -> bool:
        self._store[key] = (value, ttl or ex)
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    async def scan_iter(self, match: str = "*", count: int = 100):
        """Yield keys matching a simple glob pattern (supports trailing *)."""
        import fnmatch
        for key in list(self._store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key


def _patch_redis(fake: FakeRedisClient):
    """Patch _get_redis_client to return our fake."""
    return patch.object(
        ContextAssembler,
        "_get_redis_client",
        new=AsyncMock(return_value=fake),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComputeContextHash:
    def test_deterministic(self):
        h1 = ContextAssembler._compute_context_hash(USER_ID, FAMILY_ID, SESSION_ID, MESSAGE)
        h2 = ContextAssembler._compute_context_hash(USER_ID, FAMILY_ID, SESSION_ID, MESSAGE)
        assert h1 == h2

    def test_different_message_different_hash(self):
        h1 = ContextAssembler._compute_context_hash(USER_ID, FAMILY_ID, SESSION_ID, "hello")
        h2 = ContextAssembler._compute_context_hash(USER_ID, FAMILY_ID, SESSION_ID, "world")
        assert h1 != h2

    def test_different_user_different_hash(self):
        h1 = ContextAssembler._compute_context_hash(USER_ID, FAMILY_ID, SESSION_ID, MESSAGE)
        h2 = ContextAssembler._compute_context_hash(uuid4(), FAMILY_ID, SESSION_ID, MESSAGE)
        assert h1 != h2

    def test_returns_hex_string(self):
        h = ContextAssembler._compute_context_hash(USER_ID, FAMILY_ID, SESSION_ID, MESSAGE)
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest length
        int(h, 16)  # Must be valid hex


@pytest.mark.asyncio
class TestCacheMiss:
    async def test_cache_miss_runs_full_pipeline(self):
        """On cache miss, the full pipeline runs and result is cached."""
        fake = FakeRedisClient()
        assembler = _make_assembler()

        with _patch_redis(fake):
            prompt, metadata = await assembler.assemble(
                USER_ID, FAMILY_ID, SESSION_ID, MESSAGE,
            )

        assert "系统事实" in prompt
        assert "对话历史" in prompt
        assert metadata.total_tokens_used > 0

        # Verify something was stored in the fake cache
        assert len(fake._store) == 1
        key = list(fake._store.keys())[0]
        assert key.startswith(CONTEXT_CACHE_PREFIX)
        assert str(USER_ID) in key


@pytest.mark.asyncio
class TestCacheHit:
    async def test_cache_hit_skips_pipeline(self):
        """On cache hit, fetchers are NOT called."""
        fake = FakeRedisClient()
        call_count = 0

        async def counting_l1_fetcher(user_id, family_id):
            nonlocal call_count
            call_count += 1
            return [ContextItem(layer="l1", source="note", content="fact", tokens=5)]

        assembler = _make_assembler(l1_fetcher=counting_l1_fetcher)

        with _patch_redis(fake):
            # First call: cache miss
            prompt1, meta1 = await assembler.assemble(
                USER_ID, FAMILY_ID, SESSION_ID, MESSAGE,
            )
            assert call_count == 1

            # Second call: cache hit
            prompt2, meta2 = await assembler.assemble(
                USER_ID, FAMILY_ID, SESSION_ID, MESSAGE,
            )
            # Fetcher should NOT be called again
            assert call_count == 1

        assert prompt1 == prompt2
        assert meta1.total_tokens_used == meta2.total_tokens_used

    async def test_different_message_is_cache_miss(self):
        """Different user_message produces a different hash -> cache miss."""
        fake = FakeRedisClient()
        call_count = 0

        async def counting_l1_fetcher(user_id, family_id):
            nonlocal call_count
            call_count += 1
            return [ContextItem(layer="l1", source="note", content="fact", tokens=5)]

        assembler = _make_assembler(l1_fetcher=counting_l1_fetcher)

        with _patch_redis(fake):
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, "message A")
            assert call_count == 1

            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, "message B")
            assert call_count == 2


@pytest.mark.asyncio
class TestCacheInvalidation:
    async def test_invalidate_removes_user_keys(self):
        """invalidate_context_cache deletes all cache keys for the given user."""
        fake = FakeRedisClient()
        assembler = _make_assembler()

        with _patch_redis(fake):
            # Populate cache with two different messages
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, "msg1")
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, "msg2")
            assert len(fake._store) == 2

            deleted = await ContextAssembler.invalidate_context_cache(USER_ID)

        assert deleted == 2
        # Only the invalidation marker remains (ctx_invalidated:{user_id})
        cache_keys = [k for k in fake._store if k.startswith(CONTEXT_CACHE_PREFIX)]
        assert len(cache_keys) == 0

    async def test_invalidate_only_affects_target_user(self):
        """Invalidation for user A does not remove user B's cache."""
        fake = FakeRedisClient()
        user_a = uuid4()
        user_b = uuid4()

        assembler = _make_assembler()

        with _patch_redis(fake):
            await assembler.assemble(user_a, FAMILY_ID, SESSION_ID, MESSAGE)
            await assembler.assemble(user_b, FAMILY_ID, SESSION_ID, MESSAGE)
            assert len(fake._store) == 2

            await ContextAssembler.invalidate_context_cache(user_a)

        # user_b cache + user_a invalidation marker
        cache_keys = [k for k in fake._store if k.startswith(CONTEXT_CACHE_PREFIX)]
        assert len(cache_keys) == 1
        assert str(user_b) in cache_keys[0]


@pytest.mark.asyncio
class TestCacheTTL:
    async def test_cache_uses_configured_ttl(self):
        """Cached entries are stored with the configured TTL."""
        fake = FakeRedisClient()
        custom_ttl = 120
        assembler = _make_assembler(cache_ttl=custom_ttl)

        with _patch_redis(fake):
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, MESSAGE)

        assert len(fake._store) == 1
        _, ttl = list(fake._store.values())[0]
        assert ttl == custom_ttl

    async def test_default_ttl_is_300(self):
        """Default TTL matches CONTEXT_CACHE_TTL (300s)."""
        fake = FakeRedisClient()
        assembler = _make_assembler()

        with _patch_redis(fake):
            await assembler.assemble(USER_ID, FAMILY_ID, SESSION_ID, MESSAGE)

        _, ttl = list(fake._store.values())[0]
        assert ttl == CONTEXT_CACHE_TTL
        assert ttl == 300


@pytest.mark.asyncio
class TestSeparateUserCaches:
    async def test_two_users_same_message(self):
        """Two users sending the same message get separate cache entries."""
        fake = FakeRedisClient()
        user_a = uuid4()
        user_b = uuid4()

        assembler = _make_assembler()

        with _patch_redis(fake):
            await assembler.assemble(user_a, FAMILY_ID, SESSION_ID, MESSAGE)
            await assembler.assemble(user_b, FAMILY_ID, SESSION_ID, MESSAGE)

        assert len(fake._store) == 2
        keys = list(fake._store.keys())
        assert str(user_a) in keys[0] or str(user_a) in keys[1]
        assert str(user_b) in keys[0] or str(user_b) in keys[1]


@pytest.mark.asyncio
class TestRedisUnavailable:
    async def test_no_redis_runs_pipeline_normally(self):
        """When Redis is unavailable, the pipeline runs without caching."""
        assembler = _make_assembler()

        with patch.object(
            ContextAssembler,
            "_get_redis_client",
            new=AsyncMock(return_value=None),
        ):
            prompt, metadata = await assembler.assemble(
                USER_ID, FAMILY_ID, SESSION_ID, MESSAGE,
            )

        assert "系统事实" in prompt
        assert metadata.total_tokens_used > 0

    async def test_redis_error_falls_back_gracefully(self):
        """When Redis raises an exception, the pipeline still runs."""
        broken_redis = MagicMock()
        broken_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        assembler = _make_assembler()

        with patch.object(
            ContextAssembler,
            "_get_redis_client",
            new=AsyncMock(return_value=broken_redis),
        ):
            prompt, metadata = await assembler.assemble(
                USER_ID, FAMILY_ID, SESSION_ID, MESSAGE,
            )

        assert metadata.total_tokens_used > 0

    async def test_invalidate_with_no_redis_returns_zero(self):
        """invalidate_context_cache returns 0 when Redis is unavailable."""
        with patch.object(
            ContextAssembler,
            "_get_redis_client",
            new=AsyncMock(return_value=None),
        ):
            deleted = await ContextAssembler.invalidate_context_cache(USER_ID)

        assert deleted == 0


@pytest.mark.asyncio
class TestMetadataDeserialization:
    async def test_cached_metadata_round_trips(self):
        """ContextMetadata survives JSON serialization via to_dict()."""
        original = ContextMetadata(
            total_tokens_used=100,
            l1_tokens=10,
            l2_tokens=20,
            l3_tokens=30,
            l4_tokens=40,
            memories_included=5,
            memories_filtered=2,
            assembly_time_ms=12.34,
            budget_total=6000,
        )
        serialized = original.to_dict()
        # Filter like _cache_get does
        filtered = {
            k: v for k, v in serialized.items()
            if k in ContextMetadata.__dataclass_fields__
        }
        restored = ContextMetadata(**filtered)

        assert restored.total_tokens_used == original.total_tokens_used
        assert restored.l1_tokens == original.l1_tokens
        assert restored.l2_tokens == original.l2_tokens
        assert restored.l3_tokens == original.l3_tokens
        assert restored.l4_tokens == original.l4_tokens
        assert restored.memories_included == original.memories_included
        assert restored.memories_filtered == original.memories_filtered
        assert restored.budget_total == original.budget_total
