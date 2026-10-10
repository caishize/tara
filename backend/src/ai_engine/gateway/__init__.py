"""Tool Gateway - permission verification, routing, and audit for tool execution.

Implements the "Action Decoupling" pattern:
- Agent workers don't hold real API credentials
- All sensitive operations go through this gateway
- Provides audit logging and permission checking
"""

from .tool_gateway import ToolGateway

__all__ = ["ToolGateway"]
