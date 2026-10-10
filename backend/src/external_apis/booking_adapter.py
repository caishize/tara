"""
Booking Adapter – handles book_ticket / cancel_booking actions.

Configure via environment variables:
  BOOKING_PROVIDER_API_KEY
  BOOKING_PROVIDER_BASE_URL
"""
import logging
import os
from typing import Any, Dict

from .base import AdapterResult, BaseAdapter

logger = logging.getLogger(__name__)


class BookingAdapter(BaseAdapter):
    """Adapter for external booking services (flights, hotels, etc.)."""

    def __init__(self) -> None:
        self._api_key = os.getenv("BOOKING_PROVIDER_API_KEY", "")
        self._base_url = os.getenv("BOOKING_PROVIDER_BASE_URL", "")

    @property
    def provider_name(self) -> str:
        return "booking_provider"

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
                error="Booking provider is not configured",
            )

        # TODO: integrate with real booking API
        logger.info(
            "BookingAdapter.execute: action=%s, user=%s (not yet implemented)",
            action, user_id,
        )
        return AdapterResult(
            success=False,
            provider=self.provider_name,
            error=f"Booking action '{action}' is not yet implemented. "
                  "Please configure the booking provider integration.",
        )
