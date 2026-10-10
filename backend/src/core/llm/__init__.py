"""LLM Provider -- unified LLM access layer.

Houses the OpenAI-compatible adapter (``OpenAIAdapter``), the singleton
``openai_adapter`` instance, and the shared Haiku client factory used by
IntentRouter and InterventionClassifier.
"""

from .haiku_client import get_haiku_client
from .llm_provider import OpenAIAdapter, openai_adapter

__all__ = [
    "OpenAIAdapter",
    "openai_adapter",
    "get_haiku_client",
]
