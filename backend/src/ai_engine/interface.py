"""AI Engine public interface.

Defines the abstract contracts that other modules use to interact with
the AI Engine. The AI Engine is the system's brain -- it handles intent
routing, LLM orchestration, and tool execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

from .router.types import IntentClassification, RouteType


@dataclass(frozen=True)
class ChatRequest:
    """Incoming chat request."""
    user_id: str
    family_id: str
    session_id: str
    message: str
    metadata: Optional[dict] = None


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result of a tool execution with three-layer context."""
    execution_id: str
    tool_name: str
    summary: str
    key_results: Optional[dict] = None
    full_result: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None


class IAIEngine(ABC):
    """Public interface for the AI Engine module."""

    @abstractmethod
    async def classify_intent(
        self,
        request: ChatRequest,
    ) -> IntentClassification:
        """Classify user intent and determine routing path."""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream a chat response (stream events)."""
        ...

    @abstractmethod
    async def cancel_generation(
        self,
        session_id: str,
    ) -> bool:
        """Cancel an in-progress generation."""
        ...

    @abstractmethod
    async def get_tool_execution(
        self,
        execution_id: str,
    ) -> Optional[ToolExecutionResult]:
        """Retrieve full tool execution result (Layer 3)."""
        ...
