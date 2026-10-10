"""
Queue-related types and enums.

RouteType is canonically defined in ``router.types`` and re-exported
here for convenience.
"""
from enum import Enum

from ..router.types import RouteType  # noqa: F401 — canonical location


class TaskStatus(str, Enum):
    """Task processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
