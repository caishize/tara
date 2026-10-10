"""
Tool Registry for Claude Agent.

Provides a centralized registry for all tools available to the agent.
Tools can be registered with categories and filtered based on context.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

from ...config.logging import get_logger

logger = get_logger(__name__)


class ToolCategory(str, Enum):
    """Categories for grouping tools."""

    CORE = "core"  # Always available
    FAMILY = "family"  # Family member management
    DATES = "dates"  # Important dates
    SHOPPING = "shopping"  # Shopping list
    TRAVEL = "travel"  # Trip planning
    TASKS = "tasks"  # Task management
    MEMORY = "memory"  # Memory recall/extraction
    RESEARCH = "research"  # NotebookLM, web search
    SEARCH = "search"  # Web search (Tavily/Serper)
    CALENDAR = "calendar"  # External calendar integration
    EMAIL = "email"  # Email integration


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""

    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]

    # Availability
    always_available: bool = True
    required_connectors: List[str] = field(default_factory=list)

    # Execution hints
    supports_progress: bool = False
    is_stateful: bool = False  # If True, results shouldn't be cached
    sequential_only: bool = False  # If True, can't run in parallel


@dataclass
class ToolExecutionContext:
    """Context passed to tool executors."""

    family_id: UUID
    user_id: UUID
    session_id: str
    progress_callback: Optional[Callable[[str, str], None]] = None


# Type for tool executor functions
ToolExecutor = Callable[[str, Dict[str, Any], ToolExecutionContext], Any]


class ToolRegistry:
    """
    Central registry for all agent tools.

    Manages tool registration, filtering, and lookup.

    Note: This class no longer uses a singleton pattern. Each instance is independent,
    which allows for better testing and multi-tenant scenarios. Use the factory function
    `create_tool_registry()` to create new instances, or use dependency injection.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolMetadata] = {}
        self._executors: Dict[str, ToolExecutor] = {}
        self._categories: Dict[ToolCategory, Set[str]] = {
            cat: set() for cat in ToolCategory
        }

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        executor: ToolExecutor,
        category: ToolCategory = ToolCategory.CORE,
        always_available: bool = True,
        required_connectors: Optional[List[str]] = None,
        supports_progress: bool = False,
        is_stateful: bool = False,
        sequential_only: bool = False,
    ) -> None:
        """
        Register a tool with the registry.

        Args:
            name: Unique tool name
            description: Description for the LLM
            parameters: JSON schema for parameters
            executor: Async function to execute the tool
            category: Tool category for filtering
            always_available: If False, requires connectors
            required_connectors: List of required data connections
            supports_progress: If True, tool can emit progress updates
            is_stateful: If True, tool modifies state (no caching)
            sequential_only: If True, can't run in parallel
        """
        if name in self._tools:
            logger.warning(f"Overwriting existing tool: {name}")

        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            parameters=parameters,
            always_available=always_available,
            required_connectors=required_connectors or [],
            supports_progress=supports_progress,
            is_stateful=is_stateful,
            sequential_only=sequential_only,
        )

        self._tools[name] = metadata
        self._executors[name] = executor
        self._categories[category].add(name)

        logger.debug(f"Registered tool: {name} (category: {category})")

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Get tool metadata by name."""
        return self._tools.get(name)

    def get_executor(self, name: str) -> Optional[ToolExecutor]:
        """Get tool executor by name."""
        return self._executors.get(name)

    def get_tools_by_category(self, category: ToolCategory) -> List[ToolMetadata]:
        """Get all tools in a category."""
        return [
            self._tools[name]
            for name in self._categories.get(category, set())
        ]

    def get_available_tools(
        self,
        connected_services: Optional[List[str]] = None,
        categories: Optional[List[ToolCategory]] = None,
    ) -> List[ToolMetadata]:
        """
        Get tools available based on connected services and categories.

        Args:
            connected_services: List of connected service names
            categories: Optional list of categories to filter by

        Returns:
            List of available tool metadata
        """
        connected = set(connected_services or [])
        result = []

        for name, metadata in self._tools.items():
            # Check category filter
            if categories and metadata.category not in categories:
                continue

            # Check availability
            if metadata.always_available:
                result.append(metadata)
            elif metadata.required_connectors:
                # Check if any required connector is connected
                if any(c in connected for c in metadata.required_connectors):
                    result.append(metadata)

        return result

    def get_tool_definitions(
        self,
        tool_names: Optional[List[str]] = None,
        connected_services: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get tool definitions in Anthropic Claude format.

        Anthropic uses a flat structure with 'input_schema' instead of
        OpenAI's nested structure with 'parameters'.

        Args:
            tool_names: Optional list of specific tools to include
            connected_services: Optional list of connected services

        Returns:
            List of tool definitions for the Anthropic API
        """
        if tool_names:
            tools = [self._tools[n] for n in tool_names if n in self._tools]
        else:
            tools = self.get_available_tools(connected_services)

        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def get_all_tool_names(self) -> List[str]:
        """Get all registered tool names."""
        return list(self._tools.keys())

    def get_stateful_tools(self) -> Set[str]:
        """Get names of stateful tools (shouldn't be cached)."""
        return {
            name for name, meta in self._tools.items()
            if meta.is_stateful
        }

    def get_sequential_tools(self) -> Set[str]:
        """Get names of tools that must run sequentially."""
        return {
            name for name, meta in self._tools.items()
            if meta.sequential_only
        }


def create_tool_registry() -> ToolRegistry:
    """
    Create a new tool registry instance.

    Use this factory function to create independent registry instances.
    This is preferred over a global singleton for better testability
    and multi-tenant support.

    Returns:
        New ToolRegistry instance
    """
    return ToolRegistry()


