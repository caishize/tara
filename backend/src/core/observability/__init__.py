"""Observability -- health checks, metrics, structured logging."""

from .health import health_check_router

__all__ = [
    "health_check_router",
]
