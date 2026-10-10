"""Embedding Service - Generate and manage vector embeddings for semantic search.

Provides:
- Text embedding generation using OpenAI or other providers
- Batch embedding for efficiency
- Two-tier caching: L1 in-process dict + L2 Redis (shared across workers)
- Fallback handling for API failures
"""

import hashlib
import json
from typing import Dict, List, Optional, Tuple

from ...core.cache import redis_client
from ...core.llm import openai_adapter
from ...config.logging import get_logger
from ...config.settings import settings
from .config import memory_config

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------

_REDIS_PREFIX = "emb:"
_CACHE_TTL = 86400  # 24 hours


def _cache_key(text: str) -> str:
    """Build the canonical cache key for a text string."""
    return hashlib.md5(text.encode()).hexdigest()


def _redis_key(text: str) -> str:
    """Build the Redis key for a text string."""
    return f"{_REDIS_PREFIX}{_cache_key(text)}"


# ---------------------------------------------------------------------------
# L1: In-process dict cache (fast, per-worker)
# ---------------------------------------------------------------------------

_l1_cache: Dict[str, List[float]] = {}
_L1_MAX_SIZE: int = 1000


def _l1_get(text: str) -> Optional[List[float]]:
    """Read from L1 in-process cache."""
    return _l1_cache.get(_cache_key(text))


def _l1_put(text: str, embedding: List[float]) -> None:
    """Write to L1 in-process cache with simple eviction."""
    if len(_l1_cache) >= _L1_MAX_SIZE:
        keys_to_remove = list(_l1_cache.keys())[: max(1, int(_L1_MAX_SIZE * 0.1))]
        for key in keys_to_remove:
            del _l1_cache[key]
    _l1_cache[_cache_key(text)] = embedding


def _l1_delete(text: str) -> None:
    """Remove from L1 in-process cache."""
    _l1_cache.pop(_cache_key(text), None)


# ---------------------------------------------------------------------------
# L2: Redis shared cache (cross-worker)
# ---------------------------------------------------------------------------

async def _l2_get(text: str) -> Optional[List[float]]:
    """Read from Redis L2 cache. Returns None on miss or Redis down."""
    try:
        raw = await redis_client.get(_redis_key(text))
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:
        logger.debug("Redis L2 cache read failed: %s", exc)
    return None


async def _l2_put(text: str, embedding: List[float]) -> None:
    """Write to Redis L2 cache with TTL."""
    try:
        await redis_client.set(
            _redis_key(text),
            json.dumps(embedding),
            ttl=_CACHE_TTL,
        )
    except Exception as exc:
        logger.debug("Redis L2 cache write failed: %s", exc)


async def _l2_delete(text: str) -> None:
    """Remove from Redis L2 cache."""
    try:
        await redis_client.delete(_redis_key(text))
    except Exception as exc:
        logger.debug("Redis L2 cache delete failed: %s", exc)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmbeddingService:
    """Service for generating text embeddings with two-tier caching."""

    def __init__(self):
        self.llm = openai_adapter
        self.model = settings.embedding_model
        self.dimension = memory_config.embedding_dimension

    async def get_embedding(
        self,
        text: str,
        use_cache: bool = True,
    ) -> Optional[List[float]]:
        """Get embedding for a single text.

        Cache lookup order: L1 (process dict) -> L2 (Redis) -> API call.
        On API success the result is written to both L1 and L2.
        """
        if not text or not text.strip():
            return None

        if use_cache:
            # L1 check
            cached = _l1_get(text)
            if cached is not None:
                return cached

            # L2 check
            cached = await _l2_get(text)
            if cached is not None:
                _l1_put(text, cached)
                return cached

        try:
            embedding = await self._call_embedding_api(text)
            if embedding and use_cache:
                _l1_put(text, embedding)
                await _l2_put(text, embedding)
            return embedding
        except Exception as e:
            logger.error("Failed to get embedding: %s", e)
            return None

    async def get_embeddings_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[Optional[List[float]]]:
        """Get embeddings for multiple texts efficiently."""
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_embed: List[Tuple[int, str]] = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                continue
            if use_cache:
                # L1
                cached = _l1_get(text)
                if cached is not None:
                    results[i] = cached
                    continue
                # L2
                cached = await _l2_get(text)
                if cached is not None:
                    _l1_put(text, cached)
                    results[i] = cached
                    continue
            texts_to_embed.append((i, text))

        if texts_to_embed:
            try:
                batch_texts = [t[1] for t in texts_to_embed]
                embeddings = await self._call_embedding_api_batch(batch_texts)
                for (idx, text), embedding in zip(texts_to_embed, embeddings):
                    if embedding:
                        results[idx] = embedding
                        if use_cache:
                            _l1_put(text, embedding)
                            await _l2_put(text, embedding)
            except Exception as e:
                logger.error("Batch embedding failed: %s", e)
                for idx, text in texts_to_embed:
                    try:
                        embedding = await self._call_embedding_api(text)
                        if embedding:
                            results[idx] = embedding
                            if use_cache:
                                _l1_put(text, embedding)
                                await _l2_put(text, embedding)
                    except Exception as inner_e:
                        logger.warning(
                            "Individual embedding failed for index %d: %s", idx, inner_e
                        )

        return results

    async def invalidate_embedding(self, text: str) -> None:
        """Remove a cached embedding from both L1 and L2."""
        _l1_delete(text)
        await _l2_delete(text)

    async def _call_embedding_api(self, text: str) -> Optional[List[float]]:
        """Call the embedding API for a single text."""
        try:
            return await self.llm.get_embedding(text)
        except Exception as e:
            logger.error("Embedding API call failed: %s", e)
            return None

    async def _call_embedding_api_batch(
        self, texts: List[str]
    ) -> List[Optional[List[float]]]:
        """Call the embedding API for multiple texts."""
        try:
            return await self.llm.get_embeddings_batch(texts)
        except Exception as e:
            logger.error("Batch embedding API call failed: %s", e)
            return [None] * len(texts)

    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        if not embedding1 or not embedding2:
            return 0.0
        if len(embedding1) != len(embedding2):
            logger.warning("Embedding dimensions don't match")
            return 0.0

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    async def find_similar_texts(
        self,
        query_text: str,
        candidate_texts: List[str],
        threshold: float = 0.7,
        top_k: int = 5,
    ) -> List[Tuple[int, str, float]]:
        """Find texts similar to query from candidates."""
        if not query_text or not candidate_texts:
            return []

        query_embedding = await self.get_embedding(query_text)
        if not query_embedding:
            return []

        candidate_embeddings = await self.get_embeddings_batch(candidate_texts)

        similarities: List[Tuple[int, str, float]] = []
        for i, (text, embedding) in enumerate(
            zip(candidate_texts, candidate_embeddings)
        ):
            if embedding:
                sim = self.compute_similarity(query_embedding, embedding)
                if sim >= threshold:
                    similarities.append((i, text, sim))

        similarities.sort(key=lambda x: x[2], reverse=True)
        return similarities[:top_k]


# Global instance
embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    return embedding_service
