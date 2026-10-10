"""
Tool Providers for Tool Gateway.

Defines the interface and implementations for executing external tools.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict


logger = logging.getLogger(__name__)

class ToolProvider(ABC):
    """Abstract base class for tool providers."""

    @abstractmethod
    async def execute(
        self,
        action_type: str,
        payload: Dict[str, Any],
        user_id: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Execute the action."""
        pass


class RealToolProvider(ToolProvider):
    """
    Production provider that routes to external API adapters.

    Returns an explicit error when the adapter for an action is not
    configured. Never returns fake/simulated data.
    """

    def __init__(self):
        self._adapters = None  # lazy-loaded

    def _get_adapters(self):
        """Lazy-load adapters so missing config doesn't crash on import."""
        if self._adapters is None:
            from ...external_apis.payment_adapter import PaymentAdapter
            from ...external_apis.booking_adapter import BookingAdapter
            from ...external_apis.messaging_adapter import MessagingAdapter

            self._adapters = {
                "purchase": PaymentAdapter(),
                "transfer_money": PaymentAdapter(),
                "book_ticket": BookingAdapter(),
                "cancel_booking": BookingAdapter(),
                "send_message": MessagingAdapter(),
            }
        return self._adapters

    async def execute(
        self,
        action_type: str,
        payload: Dict[str, Any],
        user_id: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Execute action via real external API or internal handler."""
        if action_type == "reschedule_event":
            return await self._execute_reschedule(payload)

        adapter = self._get_adapters().get(action_type)

        if not adapter:
            logger.error(
                "RealToolProvider: no adapter registered for action '%s'",
                action_type,
            )
            return {
                "success": False,
                "error": f"操作 '{action_type}' 暂不支持，请联系管理员配置相应服务",
            }

        if not adapter.is_configured():
            provider_name = adapter.provider_name
            logger.error(
                "RealToolProvider: adapter '%s' for action '%s' is not configured",
                provider_name, action_type,
            )
            return {
                "success": False,
                "error": (
                    f"服务 '{provider_name}' 尚未配置，无法执行 '{action_type}' 操作。"
                    "请联系管理员完成服务配置。"
                ),
            }

        logger.info(
            "RealToolProvider: using %s for %s", adapter.provider_name, action_type
        )
        result = await adapter.execute(
            action=action_type,
            payload=payload,
            user_id=user_id,
        )

        return {
            "success": result.success,
            "transaction_id": result.transaction_id,
            "provider": result.provider,
            **(result.data if result.success else {}),
            **({"error": result.error} if result.error else {}),
        }

    async def _execute_reschedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute event reschedule by delegating to curation EventService.

        Enforces the unique writer principle: only curation module writes to
        curated_events.
        """
        from datetime import datetime

        event_id_str = payload.get("event_id", "")
        family_id_str = payload.get("family_id", "")
        new_start_str = payload.get("new_start", "")
        new_end_str = payload.get("new_end", "")

        if not event_id_str or not new_start_str:
            return {
                "success": False,
                "error": "Missing event_id or new_start in payload",
            }

        try:
            from uuid import UUID as PyUUID
            from ...db.session import async_session_maker
            from ...modules.curation.event_service import EventService

            event_uuid = PyUUID(event_id_str)
            family_uuid = PyUUID(family_id_str) if family_id_str else event_uuid
            new_start = datetime.fromisoformat(new_start_str.replace("Z", "+00:00"))
            new_end = (
                datetime.fromisoformat(new_end_str.replace("Z", "+00:00"))
                if new_end_str else None
            )

            trip_id_str = payload.get("trip_id")
            trip_day_label = payload.get("trip_day_label")
            trip_uuid = PyUUID(trip_id_str) if trip_id_str else None

            async with async_session_maker() as session:
                service = EventService(session)
                return await service.reschedule_event(
                    event_id=event_uuid,
                    family_id=family_uuid,
                    new_start=new_start,
                    new_end=new_end,
                    trip_id=trip_uuid,
                    trip_day_label=trip_day_label,
                )

        except Exception as e:
            logger.error("Reschedule event failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }
