"""Tests for embedding_service two-tier cache (L1 in-process + L2 Redis).

Covers:
- Cache miss -> API call -> both L1 and L2 populated
- L1 cache hit -> no API call, no Redis read
- L2 cache hit -> promotes to L1, no API call
- Cache invalidation clears both tiers
- Redis down gracefully falls back to API
- Batch embedding caching
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from src.modules.memory import embedding_service as emb_module
from src.modules.memory.embedding_service import (
    EmbeddingService,
    _l1_cache,
    _l1_get,
    _l1_put,
    _l1_delete,
    _l2_get,
    _l2_put,
    _l2_delete,
    _cache_key,
    _redis_key,
    _REDIS_PREFIX,
    _CACHE_TTL,
)


@pytest.fixture(autouse=True)
def clear_l1_cache():
    """Clear the L1 cache before and after each test."""
    _l1_cache.clear()
    yield
    _l1_cache.clear()


SAMPLE_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]
SAMPLE_TEXT = "Hello, world!"


# ---------------------------------------------------------------------------
# Helper / key tests
# ---------------------------------------------------------------------------


class TestCacheKeys:
    def test_cache_key_deterministic(self):
        key1 = _cache_key("hello")
        key2 = _cache_key("hello")
        assert key1 == key2

    def test_cache_key_differs_for_different_text(self):
        assert _cache_key("hello") != _cache_key("world")

    def test_redis_key_has_prefix(self):
        rkey = _redis_key("hello")
        assert rkey.startswith(_REDIS_PREFIX)
        assert _cache_key("hello") in rkey


# ---------------------------------------------------------------------------
# L1 in-process cache
# ---------------------------------------------------------------------------


class TestL1Cache:
    def test_l1_miss_returns_none(self):
        assert _l1_get("nonexistent") is None

    def test_l1_put_and_get(self):
        _l1_put(SAMPLE_TEXT, SAMPLE_EMBEDDING)
        result = _l1_get(SAMPLE_TEXT)
        assert result == SAMPLE_EMBEDDING

    def test_l1_delete(self):
        _l1_put(SAMPLE_TEXT, SAMPLE_EMBEDDING)
        _l1_delete(SAMPLE_TEXT)
        assert _l1_get(SAMPLE_TEXT) is None

    def test_l1_delete_nonexistent_no_error(self):
        _l1_delete("nonexistent")

    def test_l1_eviction_when_full(self):
        """When L1 is full, oldest entries are evicted."""
        original_max = emb_module._L1_MAX_SIZE
        emb_module._L1_MAX_SIZE = 5
        try:
            for i in range(6):
                _l1_put(f"text_{i}", [float(i)])
            # Oldest entry should be evicted
            assert len(_l1_cache) <= 5
        finally:
            emb_module._L1_MAX_SIZE = original_max


# ---------------------------------------------------------------------------
# L2 Redis cache
# ---------------------------------------------------------------------------


class TestL2Cache:
    @pytest.mark.asyncio
    async def test_l2_get_miss(self):
        """L2 returns None when Redis has no key."""
        with patch.object(emb_module.redis_client, "get", new_callable=AsyncMock, return_value=None):
            result = await _l2_get("missing")
            assert result is None

    @pytest.mark.asyncio
    async def test_l2_get_hit(self):
        """L2 returns parsed embedding from Redis."""
        stored = json.dumps(SAMPLE_EMBEDDING)
        with patch.object(emb_module.redis_client, "get", new_callable=AsyncMock, return_value=stored):
            result = await _l2_get(SAMPLE_TEXT)
            assert result == SAMPLE_EMBEDDING

    @pytest.mark.asyncio
    async def test_l2_put_calls_redis_set(self):
        """L2 write calls redis set with correct key, value, and TTL."""
        mock_set = AsyncMock(return_value=True)
        with patch.object(emb_module.redis_client, "set", mock_set):
            await _l2_put(SAMPLE_TEXT, SAMPLE_EMBEDDING)
            mock_set.assert_called_once_with(
                _redis_key(SAMPLE_TEXT),
                json.dumps(SAMPLE_EMBEDDING),
                ttl=_CACHE_TTL,
            )

    @pytest.mark.asyncio
    async def test_l2_delete_calls_redis_delete(self):
        mock_delete = AsyncMock(return_value=1)
        with patch.object(emb_module.redis_client, "delete", mock_delete):
            await _l2_delete(SAMPLE_TEXT)
            mock_delete.assert_called_once_with(_redis_key(SAMPLE_TEXT))

    @pytest.mark.asyncio
    async def test_l2_get_redis_down_returns_none(self):
        """If Redis is down, L2 get gracefully returns None."""
        with patch.object(emb_module.redis_client, "get", new_callable=AsyncMock, side_effect=ConnectionError("Redis down")):
            result = await _l2_get(SAMPLE_TEXT)
            assert result is None

    @pytest.mark.asyncio
    async def test_l2_put_redis_down_no_error(self):
        """If Redis is down, L2 put silently fails."""
        with patch.object(emb_module.redis_client, "set", new_callable=AsyncMock, side_effect=ConnectionError("Redis down")):
            await _l2_put(SAMPLE_TEXT, SAMPLE_EMBEDDING)


# ---------------------------------------------------------------------------
# EmbeddingService.get_embedding — two-tier caching
# ---------------------------------------------------------------------------


class TestGetEmbedding:
    @pytest.fixture
    def service(self):
        svc = EmbeddingService.__new__(EmbeddingService)
        svc.llm = MagicMock()
        svc.model = "text-embedding-ada-002"
        svc.dimension = 1536
        return svc

    @pytest.mark.asyncio
    async def test_cache_miss_calls_api_and_populates_both_tiers(self, service):
        """On full miss: API called, L1 + L2 written."""
        service.llm.get_embedding = AsyncMock(return_value=SAMPLE_EMBEDDING)
        mock_redis_get = AsyncMock(return_value=None)
        mock_redis_set = AsyncMock(return_value=True)

        with patch.object(emb_module.redis_client, "get", mock_redis_get), \
             patch.object(emb_module.redis_client, "set", mock_redis_set):
            result = await service.get_embedding(SAMPLE_TEXT)

        assert result == SAMPLE_EMBEDDING
        service.llm.get_embedding.assert_called_once_with(SAMPLE_TEXT)
        # L1 populated
        assert _l1_get(SAMPLE_TEXT) == SAMPLE_EMBEDDING
        # L2 populated
        mock_redis_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_l1_hit_no_api_no_redis(self, service):
        """L1 hit: no Redis read, no API call."""
        _l1_put(SAMPLE_TEXT, SAMPLE_EMBEDDING)
        service.llm.get_embedding = AsyncMock()
        mock_redis_get = AsyncMock()

        with patch.object(emb_module.redis_client, "get", mock_redis_get):
            result = await service.get_embedding(SAMPLE_TEXT)

        assert result == SAMPLE_EMBEDDING
        service.llm.get_embedding.assert_not_called()
        mock_redis_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_l2_hit_promotes_to_l1(self, service):
        """L2 hit: promotes to L1, no API call."""
        service.llm.get_embedding = AsyncMock()
        stored = json.dumps(SAMPLE_EMBEDDING)
        mock_redis_get = AsyncMock(return_value=stored)

        with patch.object(emb_module.redis_client, "get", mock_redis_get):
            result = await service.get_embedding(SAMPLE_TEXT)

        assert result == SAMPLE_EMBEDDING
        service.llm.get_embedding.assert_not_called()
        # Promoted to L1
        assert _l1_get(SAMPLE_TEXT) == SAMPLE_EMBEDDING

    @pytest.mark.asyncio
    async def test_use_cache_false_bypasses_both_tiers(self, service):
        """use_cache=False skips L1 and L2, calls API directly."""
        _l1_put(SAMPLE_TEXT, [9.9])  # stale L1 data
        service.llm.get_embedding = AsyncMock(return_value=SAMPLE_EMBEDDING)

        result = await service.get_embedding(SAMPLE_TEXT, use_cache=False)

        assert result == SAMPLE_EMBEDDING
        service.llm.get_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_text_returns_none(self, service):
        result = await service.get_embedding("")
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_text_returns_none(self, service):
        result = await service.get_embedding("   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_api_failure_returns_none(self, service):
        service.llm.get_embedding = AsyncMock(side_effect=RuntimeError("API down"))
        mock_redis_get = AsyncMock(return_value=None)

        with patch.object(emb_module.redis_client, "get", mock_redis_get):
            result = await service.get_embedding(SAMPLE_TEXT)

        assert result is None


# ---------------------------------------------------------------------------
# EmbeddingService.invalidate_embedding
# ---------------------------------------------------------------------------


class TestInvalidateEmbedding:
    @pytest.mark.asyncio
    async def test_invalidate_clears_both_tiers(self):
        svc = EmbeddingService.__new__(EmbeddingService)
        _l1_put(SAMPLE_TEXT, SAMPLE_EMBEDDING)
        mock_redis_delete = AsyncMock(return_value=1)

        with patch.object(emb_module.redis_client, "delete", mock_redis_delete):
            await svc.invalidate_embedding(SAMPLE_TEXT)

        assert _l1_get(SAMPLE_TEXT) is None
        mock_redis_delete.assert_called_once_with(_redis_key(SAMPLE_TEXT))


# ---------------------------------------------------------------------------
# EmbeddingService.get_embeddings_batch
# ---------------------------------------------------------------------------


class TestGetEmbeddingsBatch:
    @pytest.fixture
    def service(self):
        svc = EmbeddingService.__new__(EmbeddingService)
        svc.llm = MagicMock()
        svc.model = "text-embedding-ada-002"
        svc.dimension = 1536
        return svc

    @pytest.mark.asyncio
    async def test_batch_cache_miss(self, service):
        """Batch: all misses -> API batch call, results cached."""
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        service.llm.get_embeddings_batch = AsyncMock(return_value=embeddings)
        mock_redis_get = AsyncMock(return_value=None)
        mock_redis_set = AsyncMock(return_value=True)

        with patch.object(emb_module.redis_client, "get", mock_redis_get), \
             patch.object(emb_module.redis_client, "set", mock_redis_set):
            results = await service.get_embeddings_batch(["text1", "text2"])

        assert results == embeddings
        service.llm.get_embeddings_batch.assert_called_once_with(["text1", "text2"])
        assert mock_redis_set.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_partial_l1_hit(self, service):
        """Batch: L1 hit on first text, API called only for second."""
        _l1_put("text1", [0.1, 0.2])
        service.llm.get_embeddings_batch = AsyncMock(return_value=[[0.3, 0.4]])
        mock_redis_get = AsyncMock(return_value=None)
        mock_redis_set = AsyncMock(return_value=True)

        with patch.object(emb_module.redis_client, "get", mock_redis_get), \
             patch.object(emb_module.redis_client, "set", mock_redis_set):
            results = await service.get_embeddings_batch(["text1", "text2"])

        assert results[0] == [0.1, 0.2]
        assert results[1] == [0.3, 0.4]
        # API only called with uncached text
        service.llm.get_embeddings_batch.assert_called_once_with(["text2"])

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, service):
        results = await service.get_embeddings_batch([])
        assert results == []
