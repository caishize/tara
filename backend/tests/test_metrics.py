"""Tests for Prometheus metrics module.

Verifies that:
- No-op fallback works when prometheus_client is not imported
- Metric increment/observe calls do not crash
- Labels work correctly on all metric types
"""
import importlib
import sys
from unittest.mock import patch

import pytest


def test_metrics_module_imports_cleanly():
    """The metrics module should import without errors regardless of prometheus_client."""
    from src.core.observability import metrics
    assert hasattr(metrics, "route_requests_total")
    assert hasattr(metrics, "route_upgrades_total")
    assert hasattr(metrics, "context_tokens_used")
    assert hasattr(metrics, "context_assembly_seconds")
    assert hasattr(metrics, "context_cache_ops")
    assert hasattr(metrics, "llm_call_seconds")
    assert hasattr(metrics, "llm_call_errors")
    assert hasattr(metrics, "llm_token_usage")
    assert hasattr(metrics, "l1_notes_total")
    assert hasattr(metrics, "l1_notes_created_total")
    assert hasattr(metrics, "l1_notes_confirmed_total")
    assert hasattr(metrics, "dirty_bit_queue_depth")


def test_counter_labels_and_inc():
    """Counter.labels().inc() should not raise."""
    from src.core.observability.metrics import route_requests_total, route_upgrades_total

    route_requests_total.labels(path_type="fast").inc()
    route_requests_total.labels(path_type="slow").inc()
    route_requests_total.labels(path_type="hybrid").inc()
    route_upgrades_total.labels(reason="tool_limit_exceeded").inc()
    route_upgrades_total.labels(reason="complexity_detected").inc()


def test_histogram_observe():
    """Histogram.observe() should not raise."""
    from src.core.observability.metrics import (
        context_tokens_used,
        context_assembly_seconds,
        llm_call_seconds,
    )

    context_tokens_used.labels(layer="l1").observe(250)
    context_tokens_used.labels(layer="l4").observe(1500)
    context_assembly_seconds.observe(0.15)
    llm_call_seconds.labels(model="haiku", purpose="classify").observe(0.2)


def test_gauge_set():
    """Gauge.set() should not raise."""
    from src.core.observability.metrics import dirty_bit_queue_depth

    dirty_bit_queue_depth.labels(family_id="fam-1").set(5)
    dirty_bit_queue_depth.labels(family_id="fam-2").set(0)


def test_generate_latest():
    """generate_latest() should return bytes."""
    from src.core.observability.metrics import generate_latest

    result = generate_latest()
    assert isinstance(result, bytes)


def test_cache_ops_counter():
    """Cache ops counter should accept hit/miss labels."""
    from src.core.observability.metrics import context_cache_ops

    context_cache_ops.labels(result="hit").inc()
    context_cache_ops.labels(result="miss").inc()


def test_llm_error_counter():
    """LLM error counter should accept model label."""
    from src.core.observability.metrics import llm_call_errors

    llm_call_errors.labels(model="haiku").inc()
    llm_call_errors.labels(model="sonnet").inc()


def test_l1_notes_counter():
    """L1 notes counter should accept result label."""
    from src.core.observability.metrics import l1_notes_total

    l1_notes_total.labels(result="created").inc()
    l1_notes_total.labels(result="duplicate").inc()


def test_llm_token_usage_histogram():
    """LLM token usage histogram should accept model and direction labels."""
    from src.core.observability.metrics import llm_token_usage

    llm_token_usage.labels(model="haiku", direction="input").observe(150)
    llm_token_usage.labels(model="haiku", direction="output").observe(75)
    llm_token_usage.labels(model="sonnet", direction="input").observe(2000)
    llm_token_usage.labels(model="sonnet", direction="output").observe(500)


def test_l1_notes_created_counter():
    """L1 notes created counter should increment without error."""
    from src.core.observability.metrics import l1_notes_created_total

    l1_notes_created_total.inc()


def test_l1_notes_confirmed_counter():
    """L1 notes confirmed counter should increment without error."""
    from src.core.observability.metrics import l1_notes_confirmed_total

    l1_notes_confirmed_total.inc()


def test_observe_token_usage_helper():
    """_observe_token_usage should not raise even with None usage."""
    from src.core.llm.llm_provider import _observe_token_usage

    # None usage should be a no-op
    _observe_token_usage("test-model", None)

    # Usage object with tokens
    from unittest.mock import MagicMock
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    _observe_token_usage("test-model", usage)

    # Usage object with zero tokens
    usage.prompt_tokens = 0
    usage.completion_tokens = 0
    _observe_token_usage("test-model", usage)


def test_noop_fallback_when_prometheus_missing():
    """When prometheus_client is not importable, all metrics should be no-op stubs."""
    # Save original module state
    metrics_mod_name = "src.core.observability.metrics"
    original_mod = sys.modules.get(metrics_mod_name)

    # Remove the cached module so we can re-import
    for mod_name in list(sys.modules.keys()):
        if "prometheus_client" in mod_name or mod_name == metrics_mod_name:
            sys.modules.pop(mod_name, None)

    # Block prometheus_client import
    import builtins
    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if "prometheus_client" in name:
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    try:
        builtins.__import__ = blocking_import
        # Re-import with prometheus_client blocked
        mod = importlib.import_module(metrics_mod_name)
        importlib.reload(mod)

        assert mod._HAS_PROMETHEUS is False

        # All operations should be no-ops
        mod.route_requests_total.labels(path_type="test").inc()
        mod.context_assembly_seconds.observe(1.0)
        mod.dirty_bit_queue_depth.labels(family_id="x").set(10)
        result = mod.generate_latest()
        assert result == b""
    finally:
        builtins.__import__ = real_import
        # Restore original module
        for mod_name in list(sys.modules.keys()):
            if mod_name == metrics_mod_name:
                sys.modules.pop(mod_name, None)
        if original_mod is not None:
            sys.modules[metrics_mod_name] = original_mod
