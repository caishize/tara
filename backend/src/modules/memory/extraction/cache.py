"""
Extraction Cache - Three-layer caching for LLM extraction results.

Cache Layers:
1. Memory (LRU) - Fastest, 5-minute TTL, 1000 entries
2. Redis - Persistent, 1-hour TTL
3. Embedding Similarity - Semantic matching, threshold 0.95

This significantly reduces LLM API costs and latency.
"""

import asyncio
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable, List, Tuple
from collections import OrderedDict

from ....config.logging import get_logger

logger = get_logger(__name__)

# Constants for cache configuration
DEFAULT_MEMORY_CACHE_SIZE = 1000
DEFAULT_MEMORY_TTL_SECONDS = 300
DEFAULT_REDIS_TTL_SECONDS = 3600
MAX_EMBEDDING_CACHE_SIZE = 500
DEFAULT_EMBEDDING_THRESHOLD = 0.95


@dataclass
class CacheEntry:
    """A cache entry with value and metadata."""
    value: Dict[str, Any]
    created_at: float
    hit_count: int = 0


class LRUCache:
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, maxsize: int = DEFAULT_MEMORY_CACHE_SIZE, ttl: int = DEFAULT_MEMORY_TTL_SECONDS):
        """
        Initialize LRU cache.

        Args:
            maxsize: Maximum number of entries
            ttl: Time-to-live in seconds
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check TTL
            if time.time() - entry.created_at > self.ttl:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hit_count += 1

            return entry.value

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        """Set value in cache."""
        async with self._lock:
            # Remove oldest if at capacity
            while len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
            )

    async def delete(self, key: str) -> bool:
        """
        Delete a specific key from cache.

        Args:
            key: The key to delete

        Returns:
            True if key was found and deleted, False otherwise
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self._cache.clear()

    async def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics (thread-safe).

        Returns:
            Dict with size, maxsize, ttl, and total_hits
        """
        async with self._lock:
            total_hits = sum(e.hit_count for e in self._cache.values())
            return {
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "ttl": self.ttl,
                "total_hits": total_hits,
            }


class ExtractionCache:
    """
    Three-layer caching for extraction results.

    Layers:
    1. Memory (LRU) - Fast, volatile
    2. Redis - Persistent, shared
    3. Embedding - Semantic similarity matching
    """

    def __init__(
        self,
        memory_maxsize: int = DEFAULT_MEMORY_CACHE_SIZE,
        memory_ttl: int = DEFAULT_MEMORY_TTL_SECONDS,
        redis_ttl: int = DEFAULT_REDIS_TTL_SECONDS,
        embedding_threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
        redis_prefix: str = "agentic:extract:",
        max_embedding_cache_size: int = MAX_EMBEDDING_CACHE_SIZE,
    ):
        """
        Initialize extraction cache.

        Args:
            memory_maxsize: Max entries in memory cache
            memory_ttl: Memory cache TTL in seconds
            redis_ttl: Redis cache TTL in seconds
            embedding_threshold: Similarity threshold for embedding cache
            redis_prefix: Prefix for Redis keys
            max_embedding_cache_size: Max entries in embedding cache
        """
        self.memory_cache = LRUCache(maxsize=memory_maxsize, ttl=memory_ttl)
        self.redis_ttl = redis_ttl
        self.embedding_threshold = embedding_threshold
        self.redis_prefix = redis_prefix
        self.max_embedding_cache_size = max_embedding_cache_size

        self._redis = None
        self._embedding_service = None
        # Use OrderedDict for proper LRU eviction of embeddings
        self._embedding_cache: OrderedDict[str, Tuple[List[float], Dict[str, Any]]] = OrderedDict()
        self._embedding_lock = asyncio.Lock()

    @property
    def redis(self):
        """Lazy-load Redis client."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                self._redis = redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self._redis = False  # Mark as unavailable
        return self._redis if self._redis else None

    @property
    def embedding_service(self):
        """Lazy-load embedding service."""
        if self._embedding_service is None:
            try:
                from ..embedding_service import EmbeddingService
                self._embedding_service = EmbeddingService()
            except Exception as e:
                logger.warning(f"Embedding service not available: {e}")
                self._embedding_service = False
        return self._embedding_service if self._embedding_service else None

    def _hash_key(self, text: str) -> str:
        """Generate a hash key for the text."""
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    async def get(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Get cached extraction result.

        Checks layers in order: Memory -> Redis -> Embedding

        Args:
            text: The input text

        Returns:
            Cached result if found, None otherwise
        """
        key = self._hash_key(text)

        # Layer 1: Memory cache
        result = await self.memory_cache.get(key)
        if result:
            logger.debug(f"Cache hit (memory): {key[:8]}...")
            return result

        # Layer 2: Redis cache
        if self.redis:
            try:
                redis_key = f"{self.redis_prefix}{key}"
                cached = await self.redis.get(redis_key)
                if cached:
                    result = json.loads(cached)
                    # Promote to memory cache
                    await self.memory_cache.set(key, result)
                    logger.debug(f"Cache hit (redis): {key[:8]}...")
                    return result
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        # Layer 3: Embedding similarity (if enabled and we have cached embeddings)
        if self.embedding_service and self._embedding_cache:
            try:
                result = await self._semantic_lookup(text)
                if result:
                    # Promote to memory cache
                    await self.memory_cache.set(key, result)
                    logger.debug(f"Cache hit (embedding): {key[:8]}...")
                    return result
            except Exception as e:
                logger.warning(f"Embedding lookup error: {e}")

        return None

    async def set(
        self,
        text: str,
        result: Dict[str, Any],
        store_embedding: bool = True,
    ) -> None:
        """
        Cache extraction result in all layers.

        Args:
            text: The input text
            result: The extraction result
            store_embedding: Whether to store embedding for similarity matching
        """
        key = self._hash_key(text)

        # Layer 1: Memory cache
        await self.memory_cache.set(key, result)

        # Layer 2: Redis cache
        if self.redis:
            try:
                redis_key = f"{self.redis_prefix}{key}"
                await self.redis.setex(
                    redis_key,
                    self.redis_ttl,
                    json.dumps(result),
                )
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Layer 3: Store embedding for similarity matching
        if store_embedding and self.embedding_service:
            try:
                embedding = await self.embedding_service.get_embedding(text)
                if embedding:
                    async with self._embedding_lock:
                        # If key exists, move to end (most recently used)
                        if key in self._embedding_cache:
                            self._embedding_cache.move_to_end(key)
                        else:
                            self._embedding_cache[key] = (embedding, result)

                        # Proper LRU eviction: remove oldest entries
                        while len(self._embedding_cache) > self.max_embedding_cache_size:
                            self._embedding_cache.popitem(last=False)
            except Exception as e:
                logger.warning(f"Embedding store error: {e}")

    async def _semantic_lookup(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Look up similar text using embedding similarity.

        Args:
            text: The input text

        Returns:
            Cached result if similar text found, None otherwise
        """
        if not self._embedding_cache or not self.embedding_service:
            return None

        # Get embedding for input text
        query_embedding = await self.embedding_service.get_embedding(text)
        if not query_embedding:
            return None

        # Find most similar cached embedding
        best_similarity = 0.0
        best_result = None

        for _, (cached_embedding, cached_result) in self._embedding_cache.items():
            similarity = self._cosine_similarity(query_embedding, cached_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_result = cached_result

        if best_similarity >= self.embedding_threshold:
            logger.debug(f"Semantic match found: similarity={best_similarity:.3f}")
            return best_result

        return None

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def get_or_compute(
        self,
        text: str,
        compute_fn: Callable[[str], Awaitable[Dict[str, Any]]],
        store_embedding: bool = True,
    ) -> Dict[str, Any]:
        """
        Get from cache or compute and cache.

        Args:
            text: The input text
            compute_fn: Async function to compute result if not cached
            store_embedding: Whether to store embedding for similarity

        Returns:
            The extraction result (cached or freshly computed)
        """
        # Try cache first
        cached = await self.get(text)
        if cached:
            return cached

        # Compute fresh result
        result = await compute_fn(text)

        # Cache the result
        await self.set(text, result, store_embedding=store_embedding)

        return result

    async def invalidate(self, text: str) -> None:
        """
        Invalidate cache entry for text.

        Args:
            text: The input text to invalidate
        """
        key = self._hash_key(text)

        # Remove from memory cache (using public method)
        await self.memory_cache.delete(key)

        # Remove from Redis
        if self.redis:
            try:
                redis_key = f"{self.redis_prefix}{key}"
                await self.redis.delete(redis_key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")

        # Remove from embedding cache (thread-safe)
        async with self._embedding_lock:
            if key in self._embedding_cache:
                del self._embedding_cache[key]

    async def clear_all(self) -> None:
        """Clear all cache layers."""
        await self.memory_cache.clear()

        if self.redis:
            try:
                # Clear all keys with our prefix
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor, match=f"{self.redis_prefix}*", count=100
                    )
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")

        # Clear embedding cache (thread-safe)
        async with self._embedding_lock:
            self._embedding_cache.clear()

    async def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics (thread-safe).

        Returns:
            Dict with memory stats, embedding cache size, and redis availability
        """
        memory_stats = await self.memory_cache.stats()

        async with self._embedding_lock:
            embedding_size = len(self._embedding_cache)

        return {
            "memory": memory_stats,
            "embedding_cache_size": embedding_size,
            "redis_available": self.redis is not None,
        }

    def stats_sync(self) -> Dict[str, Any]:
        """
        Get approximate cache statistics (sync version for non-async contexts).

        Note: This provides best-effort stats without locking. For accurate
        stats in concurrent scenarios, use the async stats() method instead.
        """
        return {
            "memory": {
                "size": len(self.memory_cache._cache),
                "maxsize": self.memory_cache.maxsize,
                "ttl": self.memory_cache.ttl,
            },
            "embedding_cache_size": len(self._embedding_cache),
            "redis_available": self._redis is not None and self._redis is not False,
        }


# Global cache instance with thread-safe initialization
_extraction_cache: Optional[ExtractionCache] = None
_cache_lock = threading.Lock()


def get_extraction_cache() -> ExtractionCache:
    """
    Get or create the global extraction cache instance (thread-safe).

    Uses double-checked locking pattern for thread safety.
    """
    global _extraction_cache
    if _extraction_cache is None:
        with _cache_lock:
            # Double-check after acquiring lock
            if _extraction_cache is None:
                _extraction_cache = ExtractionCache()
    return _extraction_cache
