"""Conversation module - manages chat sessions, messages, and context.

Persistence layer for the AI Engine. Handles session lifecycle,
message storage, tool execution context (three-layer), feedback,
and card normalization.
"""

from .models import (
    AssistantChatSession,
    ConversationMessage,
    SessionSummary,
    ToolExecutionLog,
)
from .session_service import SessionService
from .message_service import MessageService, SessionLock
from .pending_action import PendingAction, ActionType, ActionStatus
from .pending_action_service import PendingActionService
from .tool_execution_store import ToolExecutionRecord, ToolExecutionStore
from .tool_summary_generator import generate_summary_for_tool
from .card_normalizer import (
    NormalizedCard,
    normalize,
    normalize_query_trips_data,
    enrich_done_event,
)
from .feedback_service import MessageFeedbackService
from .display_builder import build_display_data

# Lazy imports for modules with heavy dependencies (anthropic SDK)
# Access via: from src.modules.conversation.context_service import ContextService

__all__ = [
    # Models
    "AssistantChatSession",
    "ConversationMessage",
    "SessionSummary",
    "ToolExecutionLog",
    # PendingAction
    "PendingAction",
    "ActionType",
    "ActionStatus",
    "PendingActionService",
    # Session
    "SessionService",
    # Messages
    "MessageService",
    "SessionLock",
    # Context (lazy -- import from .context_service directly)
    "ContextService",
    "RehydratedContext",
    # Feedback
    "MessageFeedbackService",
    # Tool execution
    "ToolExecutionRecord",
    "ToolExecutionStore",
    "generate_summary_for_tool",
    # Display builder
    "build_display_data",
    # Card normalization
    "NormalizedCard",
    "normalize",
    "normalize_query_trips_data",
    "enrich_done_event",
]


def __getattr__(name):
    if name in ("ContextService", "RehydratedContext"):
        from .context_service import ContextService, RehydratedContext
        globals()["ContextService"] = ContextService
        globals()["RehydratedContext"] = RehydratedContext
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
