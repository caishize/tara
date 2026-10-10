"""
Message types for Claude Agent SDK integration.

Defines the structured message types that flow through the agent system.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ..core.utils.timezone import utc_now
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentMessageType(str, Enum):
    """Types of messages produced by the agent."""

    # Content streaming
    CONTENT = "content"  # Streaming text content
    CONTENT_COMPLETE = "content_complete"  # Content fully generated

    # Tool operations
    TOOL_CALL = "tool_call"  # Agent is calling a tool
    TOOL_RESULT = "tool_result"  # Tool execution result
    TOOL_PROGRESS = "tool_progress"  # Progress update during tool execution

    # Agent state
    THINKING = "thinking"  # Agent is reasoning
    THINKING_START = "thinking_start"  # Agent started reasoning
    PROGRESS = "progress"  # General progress update
    SESSION_INIT = "session_init"  # Session initialized

    # Completion
    RESULT = "result"  # Final result
    ERROR = "error"  # Error occurred


@dataclass
class AgentMessage:
    """Base class for all agent messages."""

    type: AgentMessageType = field(default=AgentMessageType.PROGRESS)
    timestamp: datetime = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentMessage(AgentMessage):
    """Streaming content from the agent."""

    content: str = ""
    is_partial: bool = True  # False when content is complete

    def __post_init__(self):
        self.type = (
            AgentMessageType.CONTENT
            if self.is_partial
            else AgentMessageType.CONTENT_COMPLETE
        )


@dataclass
class ToolCallMessage(AgentMessage):
    """Agent is calling a tool."""

    tool_name: str = ""
    tool_id: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = AgentMessageType.TOOL_CALL


@dataclass
class ToolResultMessage(AgentMessage):
    """Result from tool execution."""

    tool_name: str = ""
    tool_id: str = ""
    success: bool = True
    result: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""  # Human-readable summary
    error: Optional[str] = None

    def __post_init__(self):
        self.type = AgentMessageType.TOOL_RESULT


@dataclass
class ToolProgressMessage(AgentMessage):
    """Progress update during tool execution."""

    tool_name: str = ""
    tool_id: str = ""
    stage: str = ""
    message: str = ""
    progress: Optional[float] = None  # 0.0 to 1.0

    def __post_init__(self):
        self.type = AgentMessageType.TOOL_PROGRESS


@dataclass
class ProgressMessage(AgentMessage):
    """General progress update from the agent."""

    stage: str = ""
    message: str = ""
    data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        self.type = AgentMessageType.PROGRESS


@dataclass
class ThinkingMessage(AgentMessage):
    """Agent reasoning/thinking."""

    thinking: str = ""

    def __post_init__(self):
        self.type = AgentMessageType.THINKING


@dataclass
class ThinkingStartMessage(AgentMessage):
    """Agent started reasoning."""

    def __post_init__(self):
        self.type = AgentMessageType.THINKING_START


@dataclass
class SessionInitMessage(AgentMessage):
    """Session initialization."""

    session_id: str = ""

    def __post_init__(self):
        self.type = AgentMessageType.SESSION_INIT


@dataclass
class ResultMessage(AgentMessage):
    """Final result from the agent."""

    content: str = ""
    tool_calls_made: List[Dict[str, Any]] = field(default_factory=list)
    session_id: str = ""
    usage: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.type = AgentMessageType.RESULT


@dataclass
class ErrorMessage(AgentMessage):
    """Error from the agent."""

    error_type: str = "unknown"
    message: str = ""
    details: Optional[Dict[str, Any]] = None
    recoverable: bool = False

    def __post_init__(self):
        self.type = AgentMessageType.ERROR


def serialize_message(message: AgentMessage) -> Dict[str, Any]:
    """Serialize an agent message to a dictionary for JSON stream output."""
    base = {
        "type": message.type.value,
        "timestamp": message.timestamp.isoformat(),
    }

    if isinstance(message, ContentMessage):
        base["content"] = message.content
        base["is_partial"] = message.is_partial

    elif isinstance(message, ToolCallMessage):
        base["tool_name"] = message.tool_name
        base["tool_id"] = message.tool_id
        base["arguments"] = message.arguments

    elif isinstance(message, ToolResultMessage):
        base["tool_name"] = message.tool_name
        base["tool_id"] = message.tool_id
        base["success"] = message.success
        base["summary"] = message.summary
        if message.error:
            base["error"] = message.error

    elif isinstance(message, ToolProgressMessage):
        base["tool_name"] = message.tool_name
        base["stage"] = message.stage
        base["message"] = message.message
        if message.progress is not None:
            base["progress"] = message.progress

    elif isinstance(message, ProgressMessage):
        base["stage"] = message.stage
        base["message"] = message.message
        if message.data:
            base["data"] = message.data

    elif isinstance(message, ResultMessage):
        base["content"] = message.content
        base["session_id"] = message.session_id
        base["tool_calls_made"] = message.tool_calls_made
        base["usage"] = message.usage

    elif isinstance(message, ErrorMessage):
        base["error_type"] = message.error_type
        base["message"] = message.message
        base["recoverable"] = message.recoverable
        if message.details:
            base["details"] = message.details

    elif isinstance(message, ThinkingMessage):
        base["thinking"] = message.thinking

    elif isinstance(message, ThinkingStartMessage):
        pass  # Just type is enough

    return base
