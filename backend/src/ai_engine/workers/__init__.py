"""Workers - Fast/Hybrid/Slow path workers for the dual-brain routing architecture.

FastWorker:
    Handles ~80% of traffic (weather, time, chat, data lookups) using Haiku.
    No SDK dependency — uses direct Anthropic API.

AgentWorker:
    Handles ~20% slow-path + hybrid-background traffic using Claude Agent SDK.
    Lazy-imported because it requires ``claude_agent_sdk`` at import time.

Hybrid Path:
    Split between ``api.v1.ws_publishers.publish_hybrid_path()`` (fast leg, uses FastWorker)
    and ``AgentWorker`` (background leg, receives ``route_type=hybrid_background``).
    See ``hybrid_worker.py`` for architectural documentation.
"""

from .fast_worker import FastWorker

# AgentWorker requires claude_agent_sdk; lazy-import to avoid breaking
# modules that only need FastWorker or other lightweight helpers.
_LAZY_IMPORTS = {
    "AgentWorker": ".agent_worker",
}


def __getattr__(name: str):
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is not None:
        import importlib
        mod = importlib.import_module(module_path, __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["FastWorker", "AgentWorker"]
