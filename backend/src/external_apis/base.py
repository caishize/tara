"""
Base External API Adapter.

All external service adapters inherit from this base class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AdapterResult:
    """Standardised result returned by every adapter."""

    success: bool
    transaction_id: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """Abstract base class for external API adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the underlying service provider."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when all required credentials / env vars are present."""
        ...

    @abstractmethod
    async def execute(
        self,
        action: str,
        payload: Dict[str, Any],
        user_id: str,
    ) -> AdapterResult:
        """Execute the action and return a standardised result."""
        ...
