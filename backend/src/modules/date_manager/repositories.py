"""Date Manager repositories.

Re-exports from date_manager's own reminder_repository module.
"""

from .reminder_repository import ReminderRepository  # noqa: F401

__all__ = [
    "ReminderRepository",
]
