"""Preparation reminder strategy — upcoming trip reminders."""
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class PreparationStrategy(SuggestionStrategy):
    """Find preparation reminders for upcoming trips."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()
        tomorrow = today + timedelta(days=1)

        try:
            from ....trip.models.trip_plan import TripPlan

            query = select(TripPlan).where(
                and_(
                    TripPlan.is_active.is_(True),
                    TripPlan.status.in_(["planning", "confirmed"]),
                    TripPlan.start_date >= today,
                    TripPlan.start_date <= today + timedelta(days=3),
                )
            )

            if family_id:
                query = query.where(TripPlan.family_id == family_id)

            result = await self.db.execute(query)
            trips = result.scalars().all()

            for trip in trips:
                days_until = (trip.start_date - today).days

                if days_until == 1:
                    suggestions.append(Suggestion(
                        type=SuggestionType.PREPARATION_REMINDER,
                        title="行前准备提醒",
                        content=f"明天出发去{trip.destination}，今晚记得收拾行李",
                        icon="luggage",
                        related_trip_ids=[str(trip.trip_id)],
                        action_options=["view_details", "set_reminder", "ignore"],
                        action_data={
                            "trip_id": str(trip.trip_id),
                            "destination": trip.destination,
                            "start_date": trip.start_date.isoformat(),
                        },
                        priority=90,
                        urgency="high",
                        expires_at=datetime.combine(tomorrow, datetime.min.time()),
                    ))
                elif days_until == 0:
                    suggestions.append(Suggestion(
                        type=SuggestionType.PREPARATION_REMINDER,
                        title="出行当天提醒",
                        content=f"今天出发去{trip.destination}，请确认证件和行李",
                        icon="flight_takeoff",
                        related_trip_ids=[str(trip.trip_id)],
                        action_options=["view_details", "ignore"],
                        action_data={
                            "trip_id": str(trip.trip_id),
                            "destination": trip.destination,
                        },
                        priority=100,
                        urgency="high",
                    ))
                elif days_until <= 3:
                    suggestions.append(Suggestion(
                        type=SuggestionType.PREPARATION_REMINDER,
                        title="旅行计划提醒",
                        content=f"{days_until}天后出发去{trip.destination}，可以开始准备了",
                        icon="event",
                        related_trip_ids=[str(trip.trip_id)],
                        action_options=["view_details", "set_reminder", "ignore"],
                        action_data={
                            "trip_id": str(trip.trip_id),
                            "destination": trip.destination,
                            "days_until": days_until,
                        },
                        priority=60,
                        urgency="normal",
                    ))

        except Exception as e:
            logger.error(f"Error finding preparation reminders: {e}")

        return suggestions
