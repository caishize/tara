"""
ILLMProvider interface.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from pydantic import BaseModel


class LLMProviderError(Exception):
    """Exception raised by LLM provider."""
    pass


class LLMMessage(BaseModel):
    """LLM message format with tool support for agentic loops."""
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    # For assistant messages with tool calls
    tool_calls: Optional[List[Dict[str, Any]]] = None
    # For tool result messages
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # Tool name for tool result messages


class LLMResponse(BaseModel):
    """LLM response format."""
    text: str
    usage: Dict[str, int]  # {"prompt_tokens": 10, "completion_tokens": 20}
    finish_reason: str  # "stop", "length", "content_filter"


class ILLMProvider(ABC):
    """Interface for LLM provider."""

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Chat completion."""
        pass

    @abstractmethod
    async def function_call(
        self,
        messages: List[LLMMessage],
        functions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Function calling for structured output.

        Returns:
            {"name": "function_name", "arguments": {...}}
        """
        pass

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate text embedding."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 800
    ) -> str:
        """Generate plain text given a prompt."""
        pass
