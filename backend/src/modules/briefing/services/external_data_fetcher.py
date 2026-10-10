"""
External data fetchers for daily briefings.

Retrieves calendar events, shipping updates, and flight bookings from
external integrations (Google Calendar, Outlook, couriers, airlines).
"""
from typing import List
from datetime import date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import to_local_date

from ..schemas import BriefingEvent

logger = get_logger(__name__)


class ExternalDataFetcher:
    """Fetches briefing-relevant data from external data connections."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_external_calendar_events(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[BriefingEvent]:
        """Retrieve external calendar events (Google / Outlook)."""
        events: List[BriefingEvent] = []
        try:
            from ...data_connection.services.external_data_service import ExternalDataService

            external_service = ExternalDataService(self.session)
            external_events = await external_service.get_calendar_events(
                family_id=family_id,
                start_date=target_date,
                end_date=target_date,
                usage_type="daily_briefing",
            )

            for ext_event in external_events:
                if ext_event.is_all_day:
                    time_str = "\u5168\u5929"
                else:
                    time_str = ext_event.start_time.strftime("%H:%M")

                if "google" in ext_event.source:
                    icon = "\U0001f4c5"
                elif "outlook" in ext_event.source:
                    icon = "\U0001f4c6"
                else:
                    icon = "\U0001f5d3\ufe0f"

                description = None
                if ext_event.location:
                    description = f"\U0001f4cd {ext_event.location}"
                elif ext_event.calendar_name:
                    description = f"\u6765\u81ea {ext_event.calendar_name}"

                events.append(BriefingEvent(
                    id=f"ext_{ext_event.id}",
                    title=ext_event.title,
                    time=time_str,
                    icon=icon,
                    description=description,
                    action_label="\u67e5\u770b\u8be6\u60c5" if ext_event.html_link else None,
                    event_type="external_calendar",
                ))
        except ImportError:
            logger.debug("External data service not available")
        except Exception as e:
            logger.error("Error getting external calendar events: %s", e)
        return events

    async def get_shipping_events(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[BriefingEvent]:
        """Retrieve shipping / package delivery events."""
        events: List[BriefingEvent] = []
        try:
            from ...data_connection.services.external_data_service import ExternalDataService

            external_service = ExternalDataService(self.session)
            shipments = await external_service.get_shipping_updates(
                family_id=family_id,
                since_days=14,
                active_only=True,
                usage_type="daily_briefing",
            )

            for shipment in shipments:
                is_today_delivery = False
                description = f"\u5feb\u9012\u5355\u53f7: {shipment.tracking_number}"

                if shipment.estimated_delivery:
                    delivery_date = to_local_date(shipment.estimated_delivery)
                    if delivery_date == target_date:
                        is_today_delivery = True
                        description = f"\u9884\u8ba1\u4eca\u65e5\u9001\u8fbe - {shipment.courier}"
                    elif delivery_date < target_date:
                        description = f"\u5df2\u5ef6\u8fdf - {shipment.courier}"

                if is_today_delivery or shipment.status == "out_for_delivery":
                    icon = "\U0001f4e6"
                    if shipment.status == "out_for_delivery":
                        icon = "\U0001f69a"
                        description = f"\u6b63\u5728\u6d3e\u9001\u4e2d - {shipment.courier}"

                    events.append(BriefingEvent(
                        id=f"ship_{shipment.id}",
                        title="\u5feb\u9012\u6d3e\u9001",
                        time="\u5168\u5929",
                        icon=icon,
                        description=description,
                        action_label="\u67e5\u770b\u7269\u6d41",
                        event_type="shipping",
                    ))
        except ImportError:
            logger.debug("External data service not available")
        except Exception as e:
            logger.error("Error getting shipping events: %s", e)
        return events

    async def get_flight_events(
        self,
        family_id: UUID,
        target_date: date,
    ) -> List[BriefingEvent]:
        """Retrieve flight booking events for the target date."""
        events: List[BriefingEvent] = []
        try:
            from ...data_connection.services.external_data_service import ExternalDataService

            external_service = ExternalDataService(self.session)
            flights = await external_service.get_travel_bookings(
                family_id=family_id,
                start_date=target_date,
                end_date=target_date,
                booking_type="flight",
                usage_type="daily_briefing",
            )

            for flight in flights:
                if not flight.departure_time:
                    continue

                time_str = flight.departure_time.strftime("%H:%M")
                dep_city = flight.departure_city or "\u51fa\u53d1"
                arr_city = flight.arrival_city or "\u76ee\u7684\u5730"
                route = f"{dep_city} \u2192 {arr_city}"
                flight_num = flight.flight_number or "\u822a\u73ed"

                events.append(BriefingEvent(
                    id=f"flight_{flight.id}",
                    title=f"{flight_num} {route}",
                    time=time_str,
                    icon="\u2708\ufe0f",
                    description=f"{flight.airline or ''} {flight.passenger_name or ''}".strip() or None,
                    action_label="\u67e5\u770b\u822a\u73ed",
                    event_type="flight",
                ))
        except ImportError:
            logger.debug("External data service not available")
        except Exception as e:
            logger.error("Error getting flight events: %s", e)
        return events
