"""Core interfaces for the Secretary application."""

from .llm_provider import ILLMProvider, LLMProviderError
from .notification_provider import INotificationProvider, NotificationError
from .encryption import IEncryptionProvider, EncryptionError
from .lunar_calendar_provider import ILunarCalendarProvider, LunarCalendarError
from .mcp_provider import (
    IMCPProvider,
    MCPConnectionState,
    MCPTool,
    MCPToolResult,
    MCPServerInfo,
    MCPProviderError,
    MCPConnectionError,
    MCPToolExecutionError,
)


__all__ = [
    # LLM
    "ILLMProvider",
    "LLMProviderError",
    # Notification
    "INotificationProvider",
    "NotificationError",
    # Encryption
    "IEncryptionProvider",
    "EncryptionError",
    # Lunar Calendar
    "ILunarCalendarProvider",
    "LunarCalendarError",
    # MCP (Model Context Protocol)
    "IMCPProvider",
    "MCPConnectionState",
    "MCPTool",
    "MCPToolResult",
    "MCPServerInfo",
    "MCPProviderError",
    "MCPConnectionError",
    "MCPToolExecutionError",
]
