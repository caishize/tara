"""AI Engine - the system's "brain".

Encapsulates all LLM interactions, intent routing, tool calls,
SDK client pool, Skills, Sub-Agents, and Tool Gateway.
"""

from .agent_context import AgentContext, ContextBuilder
from .message_types import (
    AgentMessage,
    AgentMessageType,
    ToolCallMessage,
    ToolProgressMessage,
    ToolResultMessage,
    ContentMessage,
    ProgressMessage,
    ResultMessage,
    ErrorMessage,
    ThinkingMessage,
    ThinkingStartMessage,
)
from .tools.registry import ToolExecutionContext, ToolExecutor

__all__ = [
    # Context
    "AgentContext",
    "ContextBuilder",
    # Messages
    "AgentMessage",
    "AgentMessageType",
    "ToolCallMessage",
    "ToolProgressMessage",
    "ToolResultMessage",
    "ContentMessage",
    "ProgressMessage",
    "ResultMessage",
    "ErrorMessage",
    "ThinkingMessage",
    "ThinkingStartMessage",
    # Tools
    "ToolExecutionContext",
    "ToolExecutor",
]
