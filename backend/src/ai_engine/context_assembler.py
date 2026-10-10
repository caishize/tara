"""Unified context assembly engine with token budget management.

Replaces scattered context assembly across:
- conversation/context_service.py (rehydration)
- memory/recall_service.py (ContextAwareRecallService)
- ai_engine/agent_context.py (system prompt)

Implements a 6-step pipeline:
  Step 0: Entity Linking (resolve pronouns/aliases to person_id UUIDs)
  Step 1: Collect (parallel fetch from L1-L4)
  Step 1.5: Timestamp Guard (prevent L2/L3 overlap)
  Step 2: Budget allocation (TokenBudget-based)
  Step 3: Filter (PrivacyFilter + ExclusionFilter)
  Step 4: Rank (importance x feedback_weight x recency_decay)
  Step 5: Serialize (format prompt text + metadata)
"""

import asyncio
import dataclasses
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

# Default TTL for context cache entries (seconds)
CONTEXT_CACHE_TTL = 300
CONTEXT_CACHE_PREFIX = "ctx_cache"


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def _estimate_tokens_heuristic(text: str) -> int:
    """Character-based fallback when tiktoken is unavailable."""
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - cn_chars
    return int(cn_chars * 0.7 + other_chars / 4)


try:
    import tiktoken as _tiktoken
    _enc = _tiktoken.get_encoding("cl100k_base")
    _USE_TIKTOKEN = True
except ImportError:
    _enc = None
    _USE_TIKTOKEN = False


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in *text*.

    Uses tiktoken (cl100k_base) when available for accurate counting.
    Falls back to a character-based heuristic when tiktoken is not installed.
    Returns at least 0.
    """
    if not text:
        return 0
    if _USE_TIKTOKEN and _enc is not None:
        return len(_enc.encode(text))
    return _estimate_tokens_heuristic(text)


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------

# Task-type override presets. Each key maps to a dict of TokenBudget field
# overrides applied via dataclasses.replace().
TASK_OVERRIDES: Dict[str, Dict[str, int]] = {
    "analyze": {"l2_fixed": 800, "l4_min": 1000, "l4_max": 2500},
    "plan": {"l2_fixed": 1500, "l3_max": 800, "l4_max": 2200, "l5_fixed": 1000},
    "lookup": {"l2_fixed": 800, "l3_max": 500, "l4_max": 800, "l5_fixed": 400},
}

# L5 injection scope per task type.
# "skip"       — do not inject orchestration context at all
# "today_only" — inject today's schedule only (default, backward-compatible)
# "full_window" — inject today's schedule + 7-day event overview
L5_SCOPE_POLICY: Dict[str, str] = {
    "weather": "skip",
    "chat": "skip",
    "lookup": "today_only",
    "reminder": "today_only",
    "plan": "full_window",
    "trip": "full_window",
    "analyze": "full_window",
}


@dataclass(frozen=True)
class TokenBudget:
    """Token budget configuration for context assembly.

    Supports per-task-type dynamic adjustment to prevent budget deadlocks.
    For example, ANALYZE tasks need more L4 space for historical retrieval,
    so L2 (conversation history -- less valuable for analysis) is compressed.

    Layer definitions:
      L1 -- Fact base (secretary notes, always injected)
      L2 -- Active window (recent conversation turns)
      L3 -- Person profiles (relationship data)
      L4 -- Long-term memory (semantic + keyword recall)
      L5 -- Orchestration context (today's schedule + annotations)
    """

    total: int = 6900
    l1_fixed: int = 600
    l2_fixed: int = 2000
    l3_min: int = 500
    l3_max: int = 1500
    l4_min: int = 500
    l4_max: int = 2000
    l5_fixed: int = 800

    def __post_init__(self) -> None:
        """Validate budget invariants at construction time.

        Raises ValueError if fixed allocations exceed total or if
        minimum flexible allocations exceed the flexible pool.
        """
        fixed_sum = self.l1_fixed + self.l2_fixed + self.l5_fixed
        if fixed_sum > self.total:
            raise ValueError(
                f"Fixed allocations ({fixed_sum} = l1:{self.l1_fixed} + "
                f"l2:{self.l2_fixed} + l5:{self.l5_fixed}) exceed "
                f"total budget ({self.total})"
            )
        flex_pool = self.total - fixed_sum
        min_flex_sum = self.l3_min + self.l4_min
        if min_flex_sum > flex_pool:
            raise ValueError(
                f"Minimum flexible allocations ({min_flex_sum} = "
                f"l3_min:{self.l3_min} + l4_min:{self.l4_min}) exceed "
                f"flexible pool ({flex_pool})"
            )

    def for_action(self, action_type: str) -> "TokenBudget":
        """Return an adjusted budget for the given action type.

        Unknown action types return the budget unchanged.
        Validates the result to catch inconsistent overrides.
        """
        overrides = TASK_OVERRIDES.get(action_type, {})
        if not overrides:
            return self
        return dataclasses.replace(self, **overrides)

    @property
    def flexible_pool(self) -> int:
        """Tokens available for flexible allocation across L3/L4.

        This is the total budget minus the fixed L1, L2, and L5 allocations.
        """
        return max(0, self.total - self.l1_fixed - self.l2_fixed - self.l5_fixed)


# ---------------------------------------------------------------------------
# Context metadata (observability)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContextMetadata:
    """Metadata about the assembled context for observability and debugging."""

    total_tokens_used: int = 0
    l1_tokens: int = 0
    l2_tokens: int = 0
    l3_tokens: int = 0
    l4_tokens: int = 0
    l5_tokens: int = 0
    memories_included: int = 0
    memories_filtered: int = 0
    assembly_time_ms: float = 0.0
    budget_total: int = 6900

    @property
    def budget_utilization(self) -> float:
        """Fraction of the configured budget used (0.0 - 1.0+)."""
        if self.total_tokens_used <= 0 or self.budget_total <= 0:
            return 0.0
        return self.total_tokens_used / float(self.budget_total)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for logging / API responses."""
        return {
            "total_tokens_used": self.total_tokens_used,
            "budget_total": self.budget_total,
            "l1_tokens": self.l1_tokens,
            "l2_tokens": self.l2_tokens,
            "l3_tokens": self.l3_tokens,
            "l4_tokens": self.l4_tokens,
            "l5_tokens": self.l5_tokens,
            "memories_included": self.memories_included,
            "memories_filtered": self.memories_filtered,
            "assembly_time_ms": round(self.assembly_time_ms, 2),
            "budget_utilization": round(self.budget_utilization, 4),
        }


# ---------------------------------------------------------------------------
# Context item (internal representation for pipeline stages)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContextItem:
    """A single item flowing through the assembly pipeline.

    Carries enough metadata for ranking, filtering, and serialization.
    """

    layer: str  # "l1", "l2", "l3", "l4"
    source: str  # e.g. "secretary_note", "conversation", "person_profile", "memory"
    content: str
    tokens: int = 0
    importance: float = 1.0
    feedback_weight: float = 1.0
    recency_days: float = 0.0
    entity_ids: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Privacy fields (populated by fetchers from DB models)
    sensitivity_level: str = "public"
    source_member_id: Optional[str] = None

    @property
    def rank_score(self) -> float:
        """Composite score used by Step 4 ranking.

        Formula: importance * feedback_weight * recency_decay
        where recency_decay = max(0.1, 1 - days_old / 90)
        """
        recency_decay = max(0.1, 1.0 - self.recency_days / 90.0)
        return self.importance * self.feedback_weight * recency_decay

    def remove_fields(self, field_names: List[str]) -> "ContextItem":
        """Return a new ContextItem with specified metadata keys removed.

        ContextItem is frozen, so this creates a copy with filtered metadata.
        """
        if not field_names:
            return self
        new_metadata = {k: v for k, v in self.metadata.items() if k not in field_names}
        return dataclasses.replace(self, metadata=new_metadata)


# ---------------------------------------------------------------------------
# Timestamp Guard (Step 1.5)
# ---------------------------------------------------------------------------

TIMESTAMP_GUARD_NOTICE = (
    "[注意: 以下摘要包含 L2 已覆盖的时间段，若有出入以 L2 原文为准]"
)


def _ensure_aware(dt: datetime) -> datetime:
    """Normalize a datetime to timezone-aware (UTC) for safe comparison.

    Naive datetimes are assumed to be UTC and get ``timezone.utc`` attached.
    Already-aware datetimes are returned unchanged.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def apply_timestamp_guard(
    l3_items: List[ContextItem],
    l2_items: List[ContextItem],
) -> List[ContextItem]:
    """Step 1.5: Prevent L2/L3 semantic overlap.

    When an L3 digest covers a time range that overlaps with the L2 active
    window, prepend a guard notice to the item content so the LLM knows
    to prefer L2 verbatim data over L3 summaries.

    Overlap is detected via ``period_start``/``period_end`` metadata on L3
    items vs ``created_at`` metadata on L2 items.
    """
    if not l3_items or not l2_items:
        return l3_items

    l2_timestamps: List[datetime] = []
    for item in l2_items:
        ts = item.metadata.get("created_at")
        if isinstance(ts, datetime):
            l2_timestamps.append(_ensure_aware(ts))

    if not l2_timestamps:
        return l3_items

    l2_earliest = min(l2_timestamps)
    l2_latest = max(l2_timestamps)

    result: List[ContextItem] = []
    for item in l3_items:
        period_start = item.metadata.get("period_start")
        period_end = item.metadata.get("period_end")

        if (
            isinstance(period_start, datetime)
            and isinstance(period_end, datetime)
            and _ensure_aware(period_start) <= l2_latest
            and _ensure_aware(period_end) >= l2_earliest
        ):
            guarded_content = f"{TIMESTAMP_GUARD_NOTICE}\n{item.content}"
            guarded = dataclasses.replace(
                item,
                content=guarded_content,
                tokens=estimate_tokens(guarded_content),
            )
            result.append(guarded)
        else:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Step 3 Filters (delegated to context_filters.py)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Dynamic L2 window sizing
# ---------------------------------------------------------------------------


def compute_window_size(
    intent_classification: Optional[Any] = None,
    active_tool_count: int = 0,
) -> int:
    """Compute the dynamic L2 active window size based on intent and tool usage.

    Returns the number of recent conversation turns to include in L2.
    Deeper tasks (PLAN, ANALYZE) need more context; heavy tool use also
    warrants a larger window so the LLM can see prior tool outputs.

    Args:
        intent_classification: An IntentClassification (or any object with
            an ``action`` attribute whose ``.value`` is a string).  ``None``
            falls back to the default window.
        active_tool_count: Number of tools currently active/available in
            the session.

    Returns:
        Integer window size, clamped to [5, 25].
    """
    base = 10

    if intent_classification is not None:
        action_value = getattr(
            getattr(intent_classification, "action", None), "value", None
        )
        if action_value in ("plan", "analyze"):
            base = 20

    if active_tool_count > 3:
        base = min(base + 5, 25)

    return base


from .context_filters import (  # noqa: E402
    DEFAULT_COOLDOWN_DAYS,
    ExclusionFilter,
    FEEDBACK_WEIGHT_EXCLUSION_THRESHOLD,
    LOCATION_INFERABLE_FIELDS,
    PrivacyFilter,
    PrivacyInferenceGuard,
    SCHEDULE_INFERABLE_FIELDS,
    apply_filters,
)


# ---------------------------------------------------------------------------
# Budget allocator helpers
# ---------------------------------------------------------------------------

def _truncate_items_to_budget(
    items: List[ContextItem],
    max_tokens: int,
) -> List[ContextItem]:
    """Keep items in order until the token budget is exhausted.

    Items are assumed to be pre-sorted by priority (highest first).

    At-least-one policy: The first item is always included even if it
    exceeds the budget, so every non-empty layer contributes at least one
    item to the assembled context. However, if the first item exceeds the
    budget by more than 1.2x, its content is truncated to fit within 1.2x
    the budget to prevent a single oversized item from dominating the context.
    """
    if max_tokens <= 0:
        return []
    used = 0
    kept: List[ContextItem] = []
    for item in items:
        if used + item.tokens > max_tokens and kept:
            break
        # Size guard: if this is the first item and it exceeds 1.2x budget,
        # truncate content to fit within 1.2x budget.
        if not kept and item.tokens > int(max_tokens * 1.2):
            ratio = (max_tokens * 1.2) / item.tokens if item.tokens > 0 else 1.0
            truncated_len = max(1, int(len(item.content) * ratio))
            truncated_content = item.content[:truncated_len] + "..."
            item = dataclasses.replace(
                item,
                content=truncated_content,
                tokens=estimate_tokens(truncated_content),
            )
        kept.append(item)
        used += item.tokens
    return kept


def allocate_budget(
    l1: List[ContextItem],
    l2: List[ContextItem],
    l3: List[ContextItem],
    l4: List[ContextItem],
    budget: TokenBudget,
    l5: Optional[List[ContextItem]] = None,
) -> List[ContextItem]:
    """Step 2: Distribute tokens across layers respecting the budget.

    Fixed layers (L1, L2, L5) are truncated to their fixed budgets.
    Flexible layers (L3, L4) share the remaining pool, bounded by min/max.
    """
    l5_items = l5 or []

    l1_truncated = _truncate_items_to_budget(l1, budget.l1_fixed)
    l2_truncated = _truncate_items_to_budget(l2, budget.l2_fixed)
    l5_truncated = _truncate_items_to_budget(l5_items, budget.l5_fixed)

    l1_used = sum(i.tokens for i in l1_truncated)
    l2_used = sum(i.tokens for i in l2_truncated)
    l5_used = sum(i.tokens for i in l5_truncated)

    remaining = max(0, budget.total - l1_used - l2_used - l5_used)

    l3_total_available = sum(i.tokens for i in l3)
    l4_total_available = sum(i.tokens for i in l4)

    if l3_total_available + l4_total_available <= remaining:
        l3_budget = l3_total_available
        l4_budget = l4_total_available
    else:
        l3_budget = min(budget.l3_max, max(budget.l3_min, remaining // 2))
        l4_budget = min(budget.l4_max, max(budget.l4_min, remaining - l3_budget))
        # Re-check: if l4 took less than its share, give remainder back to l3
        l3_budget = min(budget.l3_max, remaining - l4_budget)

    # Hard clamp: l3 + l4 must not exceed remaining tokens.
    # If min guarantees push the sum over remaining, scale proportionally.
    if l3_budget + l4_budget > remaining and remaining > 0:
        total_flex = l3_budget + l4_budget
        l3_budget = int(l3_budget * remaining / total_flex)
        l4_budget = remaining - l3_budget
    elif remaining <= 0:
        l3_budget = 0
        l4_budget = 0

    l3_truncated = _truncate_items_to_budget(l3, l3_budget)
    l4_truncated = _truncate_items_to_budget(l4, l4_budget)

    result = l1_truncated + l2_truncated + l3_truncated + l4_truncated + l5_truncated

    # Post-allocation enforcement: trim lowest-ranked items if total exceeds budget.
    # This is the primary safety net that catches overruns from the at-least-one
    # policy and min-guarantee interactions.
    result = _enforce_total_budget(result, budget.total)

    return result


def _enforce_total_budget(
    items: List[ContextItem],
    total_budget: int,
) -> List[ContextItem]:
    """Trim lowest-ranked items until total tokens fit within the budget.

    L1 items are exempt from removal (fact base is always required).
    Items are removed in ascending rank_score order (lowest first).
    """
    total_used = sum(i.tokens for i in items)
    if total_used <= total_budget:
        return items

    # Separate L1 (exempt) from removable items
    l1_items = [i for i in items if i.layer == "l1"]
    removable = [i for i in items if i.layer != "l1"]

    # Sort removable by rank_score ascending (lowest first = first to drop)
    removable.sort(key=lambda x: x.rank_score)

    tokens_to_shed = total_used - total_budget
    shed = 0
    removed_indices: Set[int] = set()

    for idx, item in enumerate(removable):
        if shed >= tokens_to_shed:
            break
        removed_indices.add(idx)
        shed += item.tokens

    kept_removable = [
        item for idx, item in enumerate(removable)
        if idx not in removed_indices
    ]

    logger.warning(
        "Budget enforcement trimmed %d items (%d tokens) to fit within %d total budget",
        len(removed_indices),
        shed,
        total_budget,
    )

    # Reconstruct in original layer order: L1 first, then remaining by layer
    remaining = l1_items + kept_removable
    layer_order = {"l1": 0, "l2": 1, "l3": 2, "l4": 3, "l5": 4}
    remaining.sort(key=lambda x: layer_order.get(x.layer, 5))
    return remaining


# ---------------------------------------------------------------------------
# ContextAssembler
# ---------------------------------------------------------------------------

class ContextAssembler:
    """Unified context assembly engine with token budget management.

    Replaces the scattered context assembly in:
    - conversation/context_service.py (rehydration)
    - memory/recall_service.py (ContextAwareRecallService)
    - ai_engine/agent_context.py (system prompt)

    Constructor accepts optional data-fetcher callables so the assembler
    is testable without real DB sessions. In production, these are bound
    to actual service methods.
    """

    def __init__(
        self,
        budget: Optional[TokenBudget] = None,
        l1_fetcher: Optional[Any] = None,
        l2_fetcher: Optional[Any] = None,
        l3_fetcher: Optional[Any] = None,
        l4_fetcher: Optional[Any] = None,
        l5_fetcher: Optional[Any] = None,
        entity_resolver: Optional[Any] = None,
        feedback_aggregator: Optional[Any] = None,
        cache_ttl: int = CONTEXT_CACHE_TTL,
    ):
        self.budget = budget or TokenBudget()
        self._l1_fetcher = l1_fetcher
        self._l2_fetcher = l2_fetcher
        self._l3_fetcher = l3_fetcher
        self._l4_fetcher = l4_fetcher
        self._l5_fetcher = l5_fetcher
        self._entity_resolver = entity_resolver
        self._feedback_aggregator = feedback_aggregator
        self._cache_ttl = cache_ttl

    # -- Cache helpers --------------------------------------------------------

    @staticmethod
    def _compute_context_hash(
        user_id: UUID,
        family_id: UUID,
        session_id: str,
        user_message: str,
        facts_version: str = "",
        exclusion_version: str = "",
        last_message_id: str = "",
    ) -> str:
        """Compute a deterministic hash of the assembly inputs.

        Uses MD5 for speed -- this is a cache key, not a security hash.

        ``facts_version`` and ``exclusion_version`` allow the cache to
        expire naturally when underlying facts or exclusion rules change.
        A lightweight approximation (5-minute time bucket) is used so the
        cache turns over without requiring explicit invalidation signals.

        ``last_message_id`` (E9) ensures the cache auto-invalidates when
        new messages are added to the session.
        """
        payload = json.dumps(
            [
                str(user_id),
                str(family_id),
                session_id,
                user_message,
                facts_version,
                exclusion_version,
                last_message_id,
            ],
            sort_keys=True,
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    async def _get_redis_client() -> Optional[Any]:
        """Return the global redis_client, or None if unavailable."""
        try:
            from ..core.cache import redis_client
            return redis_client
        except Exception:
            return None

    async def _cache_get(
        self,
        user_id: UUID,
        context_hash: str,
    ) -> Optional[Tuple[str, ContextMetadata]]:
        """Attempt to retrieve a cached context assembly result."""
        try:
            rc = await self._get_redis_client()
            if rc is None:
                return None
            key = f"{CONTEXT_CACHE_PREFIX}:{user_id}:{context_hash}"
            raw = await rc.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            prompt_text = data["prompt_text"]
            # Filter out computed properties that aren't constructor fields
            meta_dict = {
                k: v for k, v in data["metadata"].items()
                if k in ContextMetadata.__dataclass_fields__
            }
            metadata = ContextMetadata(**meta_dict)
            return prompt_text, metadata
        except Exception:
            logger.debug("Context cache get failed, proceeding without cache", exc_info=True)
            return None

    async def _cache_set(
        self,
        user_id: UUID,
        context_hash: str,
        prompt_text: str,
        metadata: ContextMetadata,
    ) -> None:
        """Store an assembled context result in the cache."""
        try:
            rc = await self._get_redis_client()
            if rc is None:
                return
            key = f"{CONTEXT_CACHE_PREFIX}:{user_id}:{context_hash}"
            payload = json.dumps({
                "prompt_text": prompt_text,
                "metadata": metadata.to_dict(),
            }, ensure_ascii=False)
            await rc.set(key, payload, ttl=self._cache_ttl)
        except Exception:
            logger.debug("Context cache set failed", exc_info=True)

    @staticmethod
    async def invalidate_context_cache(user_id: UUID) -> int:
        """Delete all cached context entries for a given user.

        Also sets a short-lived invalidation marker so that any in-flight
        cache lookups skip stale entries (C5).

        Returns the number of keys deleted.
        """
        deleted = 0
        try:
            rc = await ContextAssembler._get_redis_client()
            if rc is None:
                return 0
            client = rc.client
            if client is None:
                return 0

            # C5: Set invalidation marker (30s TTL) so concurrent lookups miss
            marker_key = f"ctx_invalidated:{user_id}"
            await client.set(marker_key, "1", ex=30)

            pattern = f"{CONTEXT_CACHE_PREFIX}:{user_id}:*"
            keys_to_delete: List[str] = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys_to_delete.append(key)
            if keys_to_delete:
                deleted = await client.delete(*keys_to_delete)
        except Exception:
            logger.debug("Context cache invalidation failed", exc_info=True)
        return deleted

    @staticmethod
    async def _is_cache_invalidated(user_id: UUID) -> bool:
        """Check if a recent invalidation marker exists for this user (C5)."""
        try:
            rc = await ContextAssembler._get_redis_client()
            if rc is None:
                return False
            client = rc.client
            if client is None:
                return False
            marker_key = f"ctx_invalidated:{user_id}"
            return bool(await client.exists(marker_key))
        except Exception:
            return False

    @staticmethod
    async def _get_last_message_id(session_id: str) -> str:
        """Query the latest message ID for the session (E9).

        Returns empty string if unavailable (session_id missing, DB error, etc.).
        """
        if not session_id:
            return ""
        try:
            from sqlalchemy import select, func
            from ..db.session import get_db_session
            from ..modules.conversation.models import ConversationMessage

            session_uuid = UUID(session_id)
            async with get_db_session() as db:
                result = await db.execute(
                    select(ConversationMessage.id)
                    .where(ConversationMessage.session_id == session_uuid)
                    .order_by(ConversationMessage.created_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                return str(row) if row else ""
        except Exception:
            logger.debug("E9: Failed to query last_message_id", exc_info=True)
            return ""

    # -- Main pipeline --------------------------------------------------------

    async def assemble(
        self,
        user_id: UUID,
        family_id: UUID,
        session_id: str,
        user_message: str,
        action_type: Optional[str] = None,
        dismissed_entity_ids: Optional[Set[str]] = None,
        intent_classification: Optional[Any] = None,
        active_tool_count: int = 0,
    ) -> Tuple[str, ContextMetadata]:
        """Execute the 6-step context assembly pipeline.

        Returns (formatted_prompt_context, metadata).

        Before running the pipeline, checks a content-hash-based cache.
        On cache hit the full pipeline is skipped.
        """
        # Compute lightweight version strings for cache key.
        # Truncating the current timestamp to a 5-minute bucket ensures that
        # the cache expires naturally when facts or exclusion rules may have
        # changed, without requiring explicit invalidation signals.
        _bucket_seconds = 300  # 5 minutes
        _now_epoch = int(time.time())
        _bucket = _now_epoch // _bucket_seconds
        facts_version = str(_bucket)
        exclusion_version = str(_bucket)

        # E9: Include last_message_id in cache key for auto-invalidation
        last_message_id = await self._get_last_message_id(session_id)

        # Cache check (C5: skip if invalidation marker exists)
        context_hash = self._compute_context_hash(
            user_id, family_id, session_id, user_message,
            facts_version=facts_version,
            exclusion_version=exclusion_version,
            last_message_id=last_message_id,
        )
        cache_invalidated = await self._is_cache_invalidated(user_id)
        cached = None if cache_invalidated else await self._cache_get(user_id, context_hash)
        if cached is not None:
            logger.debug("Context cache hit for user=%s hash=%s", user_id, context_hash)
            from ..core.observability.metrics import context_cache_ops
            context_cache_ops.labels(result="hit").inc()
            return cached

        from ..core.observability.metrics import context_cache_ops
        context_cache_ops.labels(result="miss").inc()

        start_ns = time.monotonic_ns()
        effective_budget = self.budget
        if action_type:
            effective_budget = self.budget.for_action(action_type)

        # Step 0: Entity Linking
        resolved_ids = await self._resolve_entities(
            user_message, user_id, family_id,
        )

        # Compute dynamic L2 window size
        window_size = compute_window_size(intent_classification, active_tool_count)

        # Determine L5 injection scope based on action type
        l5_scope = L5_SCOPE_POLICY.get(action_type or "", "today_only")

        # Step 1: Collect (parallel)
        l1, l2, l3, l4, l5 = await self._collect(
            user_id, family_id, session_id, user_message, resolved_ids,
            l5_scope=l5_scope,
        )

        # Apply dynamic window: keep only the most recent `window_size` L2 items
        # Phase 1: count-based window (preserves intent of compute_window_size)
        if len(l2) > window_size:
            l2 = l2[-window_size:]

        # Phase 2: token-aware trimming within the count window (newest-first)
        l2_budget = effective_budget.l2_fixed
        trimmed: list = []
        used = 0
        for item in reversed(l2):
            if used + item.tokens <= l2_budget or not trimmed:
                # at-least-one: always include newest item even if oversized,
                # but apply 1.2x size guard consistent with _truncate_items_to_budget
                if not trimmed and item.tokens > int(l2_budget * 1.2):
                    ratio = (l2_budget * 1.2) / item.tokens if item.tokens > 0 else 1.0
                    truncated_len = max(1, int(len(item.content) * ratio))
                    truncated_content = item.content[:truncated_len] + "..."
                    item = dataclasses.replace(
                        item,
                        content=truncated_content,
                        tokens=estimate_tokens(truncated_content),
                    )
                trimmed.append(item)
                used += item.tokens
            else:
                break  # budget exhausted
        trimmed.reverse()  # restore chronological order
        l2 = trimmed

        # Step 1.5: Timestamp Guard
        l3 = apply_timestamp_guard(l3, l2)

        # Step 2: Budget allocation
        allocated = allocate_budget(l1, l2, l3, l4, effective_budget, l5=l5)

        # Step 3: Privacy + exclusion filter
        filtered, filter_count = self._apply_filters(
            allocated, str(user_id), str(family_id), resolved_ids,
            dismissed_entity_ids=dismissed_entity_ids,
        )

        # Step 3.5: Enrich feedback weights from cross-module aggregator
        filtered = await self._enrich_feedback_weights(filtered, family_id)

        # Step 4: Rank
        ranked = self._rank(filtered)

        # Step 5: Serialize
        elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000
        prompt_text, metadata = self._serialize(
            ranked, filter_count, elapsed_ms, effective_budget.total,
        )

        # Instrument assembly latency
        from ..core.observability.metrics import context_assembly_seconds
        context_assembly_seconds.observe(elapsed_ms / 1000.0)

        # Cache the result
        await self._cache_set(user_id, context_hash, prompt_text, metadata)

        return prompt_text, metadata

    # -- Step 0 ---------------------------------------------------------------

    async def _resolve_entities(
        self,
        user_message: str,
        user_id: UUID,
        family_id: UUID,
    ) -> Set[UUID]:
        """Step 0: Entity Linking -- resolve names/pronouns to person_id UUIDs."""
        if self._entity_resolver is not None:
            return await self._entity_resolver(user_message, user_id, family_id)
        return set()

    # -- Step 1 ---------------------------------------------------------------

    async def _collect(
        self,
        user_id: UUID,
        family_id: UUID,
        session_id: str,
        user_message: str,
        resolved_ids: Set[UUID],
        l5_scope: str = "today_only",
    ) -> Tuple[List[ContextItem], List[ContextItem], List[ContextItem], List[ContextItem], List[ContextItem]]:
        """Step 1: Parallel collection from L1-L5 data sources.

        Phase 1 fetchers (L1, L2, L4, L5) run in parallel with independent
        sessions. Phase 2 (L3) runs sequentially after L4 and reuses a
        shared DB session when the fetcher supports the ``db`` parameter.

        Args:
            l5_scope: Injection scope for L5 orchestration context.
                "skip" skips L5 entirely, "today_only" loads today's schedule,
                "full_window" loads a 7-day window.
        """

        async def _fetch(fetcher: Optional[Any], *args: Any, **kwargs: Any) -> List[ContextItem]:
            if fetcher is None:
                return []
            try:
                return await fetcher(*args, **kwargs)
            except Exception:
                logger.warning(
                    "Context fetcher %s failed, returning empty layer",
                    getattr(fetcher, "__name__", repr(fetcher)),
                    exc_info=True,
                )
                return []

        # Phase 1: Run L1, L2, L4, L5 in parallel.
        # L3 is deferred to Phase 2 so L4 results can boost L3 profiles.
        l1_task = _fetch(self._l1_fetcher, user_id, family_id)
        l2_task = _fetch(self._l2_fetcher, user_id, session_id)
        l4_task = _fetch(self._l4_fetcher, user_id, user_message)
        l5_task = _fetch(self._l5_fetcher, user_id, family_id, scope=l5_scope)

        phase1 = await asyncio.gather(l1_task, l2_task, l4_task, l5_task)

        l1_items: List[ContextItem] = phase1[0]
        l2_items: List[ContextItem] = phase1[1]
        l4_items: List[ContextItem] = phase1[2]
        l5_items: List[ContextItem] = phase1[3]

        # Phase 2: Extract person IDs from L4 for cross-layer boost, then fetch L3.
        # L3 runs sequentially after L4 and reuses a shared DB session
        # (PLAN-005) to avoid opening an extra connection.
        from .context_fetchers import extract_person_ids_from_l4

        boost_ids = extract_person_ids_from_l4(l4_items)

        from ..db.session import get_db_session

        async with get_db_session() as db:
            l3_items: List[ContextItem] = await _fetch(
                self._l3_fetcher, user_id, family_id, resolved_ids,
                boost_person_ids=boost_ids if boost_ids else None,
                db=db,
            )

        # Debug assertion: all fetchers must set token counts on every item.
        # This replaces the previous _ensure_tokens pass that redundantly
        # re-estimated ~116 items via tiktoken per assembly call.
        assert all(
            i.tokens > 0
            for layer in (l1_items, l2_items, l3_items, l4_items, l5_items)
            for i in layer
        ), "Fetcher returned ContextItem with tokens=0; all fetchers must set token counts"

        return l1_items, l2_items, l3_items, l4_items, l5_items

    # -- Step 3 ---------------------------------------------------------------

    @staticmethod
    def _apply_filters(
        items: List[ContextItem],
        viewer_user_id: str,
        viewer_family_id: str,
        resolved_ids: Set[UUID],
        dismissed_entity_ids: Optional[Set[str]] = None,
        privacy_settings: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[List[ContextItem], int]:
        """Step 3: Privacy + exclusion + inference guard filter.

        Chains PrivacyFilter -> ExclusionFilter -> PrivacyInferenceGuard.
        Returns (kept, filtered_count).
        """
        return apply_filters(
            items,
            viewer_user_id,
            viewer_family_id,
            resolved_ids,
            dismissed_entity_ids,
            privacy_settings=privacy_settings,
        )

    # -- Step 3.5 (feedback enrichment) ----------------------------------------

    async def _enrich_feedback_weights(
        self,
        items: List[ContextItem],
        family_id: UUID,
    ) -> List[ContextItem]:
        """Enrich ContextItems with cross-module feedback scores.

        For L3/L4 items that carry entity_ids in their metadata, queries the
        FeedbackAggregator for unified scores and replaces the default
        feedback_weight. L1/L2 items are left unchanged (their order is fixed).
        """
        if self._feedback_aggregator is None:
            return items

        # Collect entity IDs from items that could benefit from enrichment
        entity_ids_to_query: List[UUID] = []
        item_entity_map: Dict[int, UUID] = {}  # item index -> entity_id

        for idx, item in enumerate(items):
            if item.layer in ("l1", "l2"):
                continue
            # Try metadata.memory_id first, then first entity_id
            memory_id = item.metadata.get("memory_id")
            if memory_id:
                try:
                    eid = UUID(str(memory_id))
                    entity_ids_to_query.append(eid)
                    item_entity_map[idx] = eid
                    continue
                except (ValueError, AttributeError):
                    pass
            if item.entity_ids:
                try:
                    eid = UUID(str(item.entity_ids[0]))
                    entity_ids_to_query.append(eid)
                    item_entity_map[idx] = eid
                except (ValueError, AttributeError):
                    pass

        if not entity_ids_to_query:
            return items

        try:
            scores = await self._feedback_aggregator.get_bulk_feedback_scores(
                entity_ids=entity_ids_to_query,
                family_id=family_id,
            )
        except Exception:
            logger.debug(
                "Feedback aggregator failed, using default weights",
                exc_info=True,
            )
            return items

        if not scores:
            return items

        enriched: List[ContextItem] = []
        for idx, item in enumerate(items):
            if idx in item_entity_map:
                eid_str = str(item_entity_map[idx])
                score = scores.get(eid_str)
                if score is not None and score != item.feedback_weight:
                    item = dataclasses.replace(item, feedback_weight=score)
            enriched.append(item)
        return enriched

    # -- Step 4 ---------------------------------------------------------------

    @staticmethod
    def _rank(items: List[ContextItem]) -> List[ContextItem]:
        """Step 4: Rank items by composite score within each layer.

        L1, L2, and L5 items preserve their original order (insertion order
        matters for facts, conversation, and schedule).
        L3 and L4 are sorted by rank_score desc.
        """
        ordered: List[ContextItem] = []
        flexible: List[ContextItem] = []

        for item in items:
            if item.layer in ("l1", "l2", "l5"):
                ordered.append(item)
            else:
                flexible.append(item)

        flexible.sort(key=lambda x: x.rank_score, reverse=True)
        return ordered + flexible

    # -- Step 5 ---------------------------------------------------------------

    @staticmethod
    def _serialize(
        items: List[ContextItem],
        filtered_count: int,
        elapsed_ms: float,
        budget_total: int = 6900,
    ) -> Tuple[str, ContextMetadata]:
        """Step 5: Serialize ranked items into prompt text + metadata."""
        layer_tokens: Dict[str, int] = {"l1": 0, "l2": 0, "l3": 0, "l4": 0, "l5": 0}
        memory_count = 0
        sections: Dict[str, List[str]] = {
            "l1": [],
            "l2": [],
            "l3": [],
            "l4": [],
            "l5": [],
        }

        for item in items:
            layer = item.layer
            layer_tokens[layer] = layer_tokens.get(layer, 0) + item.tokens
            sections.setdefault(layer, []).append(item.content)
            if layer == "l4":
                memory_count += 1

        parts: List[str] = []
        if sections["l1"]:
            parts.append("【事实基座 (L1)】\n" + "\n".join(sections["l1"]))
        if sections["l2"]:
            parts.append("【活跃窗口 (L2)】\n" + "\n".join(sections["l2"]))
        if sections["l3"]:
            parts.append("【人物档案 (L3)】\n" + "\n".join(sections["l3"]))
        if sections["l4"]:
            parts.append("【相关记忆 (L4)】\n" + "\n".join(sections["l4"]))
        if sections["l5"]:
            parts.append("【编排上下文 (L5)】\n" + "\n".join(sections["l5"]))

        prompt_text = "\n\n".join(parts)
        total_used = sum(layer_tokens.values())

        metadata = ContextMetadata(
            total_tokens_used=total_used,
            l1_tokens=layer_tokens["l1"],
            l2_tokens=layer_tokens["l2"],
            l3_tokens=layer_tokens["l3"],
            l4_tokens=layer_tokens["l4"],
            l5_tokens=layer_tokens["l5"],
            memories_included=memory_count,
            memories_filtered=filtered_count,
            assembly_time_ms=elapsed_ms,
            budget_total=budget_total,
        )
        return prompt_text, metadata
