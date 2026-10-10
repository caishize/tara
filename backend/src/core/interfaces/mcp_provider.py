"""
MCP (Model Context Protocol) Provider Interface.

Defines the interface for MCP client adapters that connect to external MCP servers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum


class MCPConnectionState(str, Enum):
    """MCP connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for parameters


class MCPToolResult(BaseModel):
    """Result from MCP tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None


class MCPServerInfo(BaseModel):
    """Information about an MCP server."""
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    tools: List[MCPTool] = []


class IMCPProvider(ABC):
    """Interface for MCP client providers."""

    @property
    @abstractmethod
    def server_name(self) -> str:
        """Get the name of this MCP server."""
        pass

    @property
    @abstractmethod
    def connection_state(self) -> MCPConnectionState:
        """Get current connection state."""
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        pass

    @abstractmethod
    async def list_tools(self) -> List[MCPTool]:
        """
        List available tools from the MCP server.

        Returns:
            List of available tools with their schemas.
        """
        pass

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            Result of the tool execution.
        """
        pass

    @abstractmethod
    async def get_server_info(self) -> MCPServerInfo:
        """
        Get information about the MCP server.

        Returns:
            Server information including name, version, and available tools.
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if the MCP server is healthy.

        Returns:
            True if server is healthy, False otherwise.
        """
        return self.connection_state == MCPConnectionState.CONNECTED


class MCPProviderError(Exception):
    """Exception raised by MCP provider."""
    pass


class MCPConnectionError(MCPProviderError):
    """Exception raised when connection to MCP server fails."""
    pass


class MCPToolExecutionError(MCPProviderError):
    """Exception raised when tool execution fails."""
    pass
