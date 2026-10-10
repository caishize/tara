"""Prometheus metrics for Secretary V8.

Uses try/except import so the app does not crash if prometheus_client
is not installed.  Provides no-op fallbacks for all metric types.

Metrics defined:
- Route distribution: route_requests_total, route_upgrades_total
- Context assembly: context_tokens_used, context_assembly_seconds, context_cache_ops
- LLM: llm_call_seconds, llm_call_errors, llm_token_usage
- Memory: l1_notes_total, l1_notes_created_total, l1_notes_confirmed_total, dirty_bit_queue_depth
"""

try:
    from prometheus_client import (  # type: ignore[import-untyped]
        Counter,
        Histogram,
        Gauge,
        generate_latest,
    )

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


if not _HAS_PROMETHEUS:

    class _NoOpMetric:
        """No-op metric stub when prometheus_client is not installed."""

        def labels(self, **kw):  # type: ignore[no-untyped-def]
            return self

        def inc(self, amount=1):  # type: ignore[no-untyped-def]
            pass

        def dec(self, amount=1):  # type: ignore[no-untyped-def]
            pass

        def set(self, value):  # type: ignore[no-untyped-def]
            pass

        def observe(self, value):  # type: ignore[no-untyped-def]
            pass

    def _noop_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _NoOpMetric()

    Counter = _noop_factory  # type: ignore[assignment,misc]
    Histogram = _noop_factory  # type: ignore[assignment,misc]
    Gauge = _noop_factory  # type: ignore[assignment,misc]

    def generate_latest():  # type: ignore[no-redef]
        return b""


# ---------------------------------------------------------------------------
# Route distribution
# ---------------------------------------------------------------------------
route_requests_total = Counter(
    "secretary_route_requests_total",
    "Total requests by route path",
    ["path_type"],
)
route_upgrades_total = Counter(
    "secretary_route_upgrades_total",
    "Fast to Slow upgrades",
    ["reason"],
)
classification_mismatches_total = Counter(
    "secretary_classification_mismatches_total",
    "Post-hoc classification mismatches detected",
    ["reason", "path"],
)

# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------
context_tokens_used = Histogram(
    "secretary_context_tokens",
    "Tokens used per context assembly",
    ["layer"],
    buckets=[100, 500, 1000, 2000, 4000, 6000],
)
context_assembly_seconds = Histogram(
    "secretary_context_assembly_seconds",
    "Context assembly latency",
)
context_cache_ops = Counter(
    "secretary_context_cache_ops",
    "Context cache operations",
    ["result"],
)

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
llm_call_seconds = Histogram(
    "secretary_llm_call_seconds",
    "LLM call latency",
    ["model", "purpose"],
)
llm_call_errors = Counter(
    "secretary_llm_call_errors",
    "LLM call errors",
    ["model"],
)
llm_token_usage = Histogram(
    "secretary_llm_token_usage",
    "Token usage per LLM call",
    ["model", "direction"],
    buckets=[50, 100, 250, 500, 1000, 2000, 4000, 8000],
)

# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
l1_notes_total = Counter(
    "secretary_l1_notes_total",
    "L1 notes created",
    ["result"],
)
l1_notes_created_total = Counter(
    "secretary_l1_note_creations",
    "Total L1 secretary notes created",
)
l1_notes_confirmed_total = Counter(
    "secretary_l1_note_confirmations",
    "Total L1 secretary notes confirmed by user",
)
dirty_bit_queue_depth = Gauge(
    "secretary_dirty_bit_queue_depth",
    "DirtyBit pending items",
    ["family_id"],
)
vector_search_fallback_total = Counter(
    "secretary_vector_search_fallback_total",
    "Times semantic search fell back from pgvector to in-memory ARRAY cosine",
    ["reason"],
)
