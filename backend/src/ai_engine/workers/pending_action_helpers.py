"""Sensitive action guard for the agent worker.

Defines which tool names require user confirmation before execution.
Display data construction is handled by
``src.modules.conversation.display_builder``.
"""


# Sensitive actions that require user confirmation.
# These names MUST match the ActionType enum values in pending_action.py
# and the tool names used by the agent.
SENSITIVE_ACTIONS = frozenset({
    "purchase",
    "book_ticket",
    "transfer_money",
    "cancel_booking",
    "delete_event",
    "send_message",
    "send_message_external",
    "create_calendar_event",
    "create_event",  # matches ActionType.CREATE_EVENT
    "reschedule_event",
})
