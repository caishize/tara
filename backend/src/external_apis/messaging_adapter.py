"""
Messaging Adapter – handles send_message actions.

Configure via environment variables:
  MESSAGING_PROVIDER_API_KEY
  MESSAGING_PROVIDER_BASE_URL
"""
import logging
import os
from typing import Any, Dict

from .base import AdapterResult, BaseAdapter

logger = logging.getLogger(__name__)


class MessagingAdapter(BaseAdapter):
    """Adapter for external messaging services (SMS, WeChat, etc.)."""

    def __init__(self) -> None:
        self._api_key = os.getenv("MESSAGING_PROVIDER_API_KEY", "")
        self._base_url = os.getenv("MESSAGING_PROVIDER_BASE_URL", "")

    @property
    def provider_name(self) -> str:
        return "messaging_provider"

    def is_configured(self) -> bool:
        return bool(self._api_key and self._base_url)

    async def execute(
        self,
        action: str,
        payload: Dict[str, Any],
        user_id: str,
    ) -> AdapterResult:
        if not self.is_configured():
            return AdapterResult(
                success=False,
                provider=self.provider_name,
                error="Messaging provider is not configured",
            )

        # TODO: integrate with real messaging API
        logger.info(
            "MessagingAdapter.execute: action=%s, user=%s (not yet implemented)",
            action, user_id,
        )
        return AdapterResult(
            success=False,
            provider=self.provider_name,
            error=f"Messaging action '{action}' is not yet implemented. "
                  "Please configure the messaging provider integration.",
        )
