"""
Tool Bridge - Connects domain executors with the tool registry.

No longer delegates to the monolithic LegacyToolExecutor.
Each domain has its own executor class under executors/.
"""

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger

from .registry import (
    ToolExecutionContext,
    ToolRegistry,
    create_tool_registry,
)
from .shared.errors import ToolExecutionError
from .executors import create_domain_executors
from .member_tools import register_member_tools
from .date_tools import register_date_tools
from .trip_tools import register_trip_tools
from .task_tools import register_task_tools
from .memory_tools import register_memory_tools
from .event_tools import register_event_tools
from .mcp_tools import register_mcp_tools
from .recall_tools import register_recall_tools
from .search_tools import register_search_tools
from .executors.recall_executor import RecallToolExecutor

logger = get_logger(__name__)


class ToolBridge:
    """
    Bridge between domain executors and the tool registry.

    Each domain (date, event, member, ...) has its own executor class.
    Tools are registered with wrapper functions that delegate to executor methods.
    """

    def __init__(
        self,
        db: AsyncSession,
        registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.db = db
        self.registry = registry or create_tool_registry()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the bridge and register all tools."""
        if self._initialized:
            return

        executors = create_domain_executors(self.db)

        # Register all domain tools with their executor methods
        register_date_tools(self.registry, executors["date"])
        register_event_tools(self.registry, executors["event"])
        register_member_tools(self.registry, executors["member"])
        register_task_tools(self.registry, executors["task"], executors["reminder"])
        register_memory_tools(self.registry, executors["memory"], executors["favor_gift"])
        register_trip_tools(self.registry, executors["trip"])
        register_mcp_tools(self.registry, executors["mcp"])
        register_search_tools(self.registry, executors["search"])

        # Recall tools (view_tool_details, recall_tool_result)
        recall_executor = RecallToolExecutor(self.db)
        register_recall_tools(self.registry, recall_executor)

        # Sub-agent delegation tool (delegate_to_sub_agent)
        from ..sub_agents import get_delegate_tool_definition
        delegate_def = get_delegate_tool_definition()
        # Register with a no-op executor; actual execution is intercepted
        # by the PreToolUse SDK hook (create_sub_agent_intercept_hook).
        async def _delegate_noop(
            tool_name: str, args: dict, ctx: ToolExecutionContext
        ) -> dict:
            return {"success": False, "error": "delegate_to_sub_agent must be intercepted by SDK hook"}

        self.registry.register(
            name=delegate_def["name"],
            description=delegate_def["description"],
            parameters=delegate_def["input_schema"],
            executor=_delegate_noop,
        )

        # Validate sub-agent tool references against the registry
        from ..sub_agents import validate_sub_agent_tools
        missing = validate_sub_agent_tools(self.registry)
        if missing:
            logger.error("Sub-agent tool mismatches: %s", missing)

        self._initialized = True
        logger.info(
            "Tool bridge initialized with %d tools", len(self.registry.get_all_tool_names())
        )

    def get_registry(self) -> ToolRegistry:
        """Get the tool registry."""
        return self.registry

    def get_tool_definitions(
        self,
        tool_names: Optional[list] = None,
        connected_services: Optional[list] = None,
    ) -> list:
        """Get tool definitions for the Claude API."""
        return self.registry.get_tool_definitions(
            tool_names=tool_names,
            connected_services=connected_services,
        )

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolExecutionContext,
    ) -> Dict[str, Any]:
        """
        Execute a tool by name.

        Returns the raw result dict from the domain executor — no more
        ``{"success": True, "result": {...}}`` wrapping.
        """
        executor = self.registry.get_executor(tool_name)
        if not executor:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "error_type": "not_found",
            }

        try:
            result = await executor(tool_name, arguments, context)
            # ToolExecutionError is converted to dict by the executor itself
            # via tool_error(), but we catch it here as well for safety.
            return result
        except ToolExecutionError as te:
            return te.to_dict()
        except Exception as e:
            logger.exception(f"Tool execution error: {tool_name}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal",
            }


async def create_tool_bridge(db: AsyncSession) -> ToolBridge:
    """Create and initialize a tool bridge."""
    bridge = ToolBridge(db)
    await bridge.initialize()
    return bridge
