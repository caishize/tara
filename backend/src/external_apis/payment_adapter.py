"""
Payment Adapter – handles purchase / transfer_money actions.

Configure via environment variables:
  PAYMENT_PROVIDER_API_KEY
  PAYMENT_PROVIDER_BASE_URL
"""
import logging
import os
from typing import Any, Dict

from .base import AdapterResult, BaseAdapter

logger = logging.getLogger(__name__)


class PaymentAdapter(BaseAdapter):
    """Adapter for external payment services (Alipay, WeChat Pay, etc.)."""

    def __init__(self) -> None:
        self._api_key = os.getenv("PAYMENT_PROVIDER_API_KEY", "")
        self._base_url = os.getenv("PAYMENT_PROVIDER_BASE_URL", "")

    @property
    def provider_name(self) -> str:
        return "payment_provider"

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
                error="Payment provider is not configured",
            )

        # TODO: integrate with real payment API
        logger.info(
            "PaymentAdapter.execute: action=%s, user=%s (not yet implemented)",
            action, user_id,
        )
        return AdapterResult(
            success=False,
            provider=self.provider_name,
            error=f"Payment action '{action}' is not yet implemented. "
                  "Please configure the payment provider integration.",
        )
