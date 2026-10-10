"""External data suggestion strategy — shipping, flights, hotels, orders."""
from typing import List, Optional
from datetime import timedelta
from uuid import UUID

from .....config.logging import get_logger
from .....core.utils.timezone import utc_now, local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class ExternalDataStrategy(SuggestionStrategy):
    """Find suggestions based on external data sources (shipping, flights, hotels, orders)."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()

        if not family_id:
            return suggestions

        try:
            from ....data_connection.services.external_data_service import ExternalDataService

            external_service = ExternalDataService(self.db)

            await self._check_shipments(external_service, family_id, today, suggestions)
            await self._check_flights(external_service, family_id, today, suggestions)
            await self._check_hotels(external_service, family_id, today, suggestions)
            await self._check_orders(external_service, family_id, suggestions)

        except ImportError as e:
            logger.debug(f"External data service not available: {e}")
        except Exception as e:
            logger.error(f"Error finding external data suggestions: {e}")

        return suggestions

    async def _check_shipments(
        self, service: object, family_id: UUID, today: object, suggestions: List[Suggestion]
    ) -> None:
        try:
            shipments = await service.get_shipping_updates(
                family_id=family_id,
                since_days=14,
                active_only=True,
                usage_type="smart_suggestion",
            )

            out_for_delivery = [s for s in shipments if s.status == "out_for_delivery"]
            arriving_today = [
                s for s in shipments
                if s.estimated_delivery and s.estimated_delivery.date() == today
            ]

            if out_for_delivery:
                count = len(out_for_delivery)
                suggestions.append(Suggestion(
                    type=SuggestionType.PREPARATION_REMINDER,
                    title="快递派送中",
                    content=f"您有{count}个包裹正在派送，注意查收",
                    icon="local_shipping",
                    action_options=["view_details", "ignore"],
                    action_data={
                        "shipment_count": count,
                        "tracking_numbers": [s.tracking_number for s in out_for_delivery[:3]],
                    },
                    priority=80,
                    urgency="high",
                ))
            elif arriving_today and not out_for_delivery:
                count = len(arriving_today)
                suggestions.append(Suggestion(
                    type=SuggestionType.PREPARATION_REMINDER,
                    title="预计今日送达",
                    content=f"您有{count}个包裹预计今日送达",
                    icon="inventory_2",
                    action_options=["view_details", "ignore"],
                    action_data={"shipment_count": count},
                    priority=60,
                    urgency="normal",
                ))

        except Exception as e:
            logger.warning(f"Error checking shipping updates: {e}")

    async def _check_flights(
        self, service: object, family_id: UUID, today: object, suggestions: List[Suggestion]
    ) -> None:
        try:
            flights = await service.get_travel_bookings(
                family_id=family_id,
                start_date=today,
                end_date=today + timedelta(days=2),
                booking_type="flight",
                usage_type="smart_suggestion",
            )

            tomorrow = today + timedelta(days=1)
            for flight in flights:
                if not flight.departure_time:
                    continue

                flight_date = flight.departure_time.date()
                route = f"{flight.departure_city or ''} -> {flight.arrival_city or ''}"

                if flight_date == today:
                    hours_until = (flight.departure_time - utc_now()).total_seconds() / 3600
                    if 2 <= hours_until <= 24:
                        suggestions.append(Suggestion(
                            type=SuggestionType.PREPARATION_REMINDER,
                            title="航班提醒",
                            content=f"今天的航班 {flight.flight_number} {route}，请确认已值机",
                            icon="flight_takeoff",
                            action_options=["view_details", "set_reminder", "ignore"],
                            action_data={
                                "flight_number": flight.flight_number,
                                "departure_time": flight.departure_time.isoformat(),
                                "route": route,
                            },
                            priority=95,
                            urgency="high",
                        ))
                elif flight_date == tomorrow:
                    suggestions.append(Suggestion(
                        type=SuggestionType.PREPARATION_REMINDER,
                        title="明日航班",
                        content=f"明天有航班 {flight.flight_number} {route}，记得提前值机",
                        icon="flight",
                        action_options=["view_details", "set_reminder", "ignore"],
                        action_data={
                            "flight_number": flight.flight_number,
                            "departure_time": flight.departure_time.isoformat(),
                            "route": route,
                        },
                        priority=85,
                        urgency="high",
                    ))

        except Exception as e:
            logger.warning(f"Error checking flight bookings: {e}")

    async def _check_hotels(
        self, service: object, family_id: UUID, today: object, suggestions: List[Suggestion]
    ) -> None:
        try:
            hotels = await service.get_travel_bookings(
                family_id=family_id,
                start_date=today,
                end_date=today + timedelta(days=1),
                booking_type="hotel",
                usage_type="smart_suggestion",
            )

            for hotel in hotels:
                if not hotel.check_in_date:
                    continue

                check_in_date = hotel.check_in_date.date()

                if check_in_date == today:
                    suggestions.append(Suggestion(
                        type=SuggestionType.PREPARATION_REMINDER,
                        title="酒店入住",
                        content=f"今天入住 {hotel.hotel_name or '酒店'} ({hotel.city or ''})",
                        icon="hotel",
                        action_options=["view_details", "ignore"],
                        action_data={
                            "hotel_name": hotel.hotel_name,
                            "city": hotel.city,
                            "booking_id": hotel.booking_id,
                        },
                        priority=75,
                        urgency="normal",
                    ))

        except Exception as e:
            logger.warning(f"Error checking hotel bookings: {e}")

    async def _check_orders(
        self, service: object, family_id: UUID, suggestions: List[Suggestion]
    ) -> None:
        try:
            orders = await service.get_orders(
                family_id=family_id,
                since_days=30,
                status_filter=["paid", "shipped"],
                usage_type="smart_suggestion",
            )

            pending_count = len(orders)
            if pending_count >= 3:
                suggestions.append(Suggestion(
                    type=SuggestionType.TIME_CORRELATION,
                    title="待收货订单",
                    content=f"您有{pending_count}个订单待收货",
                    icon="shopping_bag",
                    action_options=["view_details", "ignore"],
                    action_data={"order_count": pending_count},
                    priority=40,
                    urgency="low",
                ))

        except Exception as e:
            logger.warning(f"Error checking orders: {e}")
