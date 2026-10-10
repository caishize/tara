"""Location correlation strategy — friends in the same city during travel."""
from typing import List, Optional
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class LocationStrategy(SuggestionStrategy):
    """Find location-based suggestions (e.g. friends in same city during travel)."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()

        try:
            from ....trip.models.trip_plan import TripPlan
            from ....member.models.member import Member

            trip_query = select(TripPlan).where(
                and_(
                    TripPlan.is_active.is_(True),
                    TripPlan.status.in_(["planning", "confirmed"]),
                    TripPlan.start_date >= today,
                    TripPlan.start_date <= today + timedelta(days=14),
                )
            )

            if family_id:
                trip_query = trip_query.where(TripPlan.family_id == family_id)

            trip_result = await self.db.execute(trip_query)
            trips = trip_result.scalars().all()

            for trip in trips:
                destination_lower = trip.destination.lower()

                member_query = select(Member).where(
                    and_(
                        Member.is_deleted == False,
                        Member.locations.isnot(None),
                    )
                )

                if family_id:
                    member_query = member_query.where(Member.family_id == family_id)

                member_result = await self.db.execute(member_query)
                members = member_result.scalars().all()

                for member in members:
                    if not member.locations:
                        continue

                    for loc_type, loc_data in member.locations.items():
                        if isinstance(loc_data, dict) and loc_data.get("address"):
                            address = loc_data.get("address", "").lower()
                            if destination_lower in address or any(
                                city in address
                                for city in [destination_lower, destination_lower.replace("市", "")]
                            ):
                                days_until = (trip.start_date - today).days
                                suggestions.append(Suggestion(
                                    type=SuggestionType.MEETUP_SUGGESTION,
                                    title="出差顺便见面",
                                    content=(
                                        f"您{days_until}天后出差{trip.destination}，"
                                        f"{member.name}也在{trip.destination}，"
                                        f"需要顺便约见面吗？"
                                    ),
                                    icon="people",
                                    related_trip_ids=[str(trip.trip_id)],
                                    related_member_ids=[str(member.id)],
                                    action_options=["schedule_meeting", "send_message", "ignore"],
                                    action_data={
                                        "trip_id": str(trip.trip_id),
                                        "member_id": str(member.id),
                                        "member_name": member.name,
                                        "destination": trip.destination,
                                        "trip_dates": (
                                            f"{trip.start_date.isoformat()} - "
                                            f"{trip.end_date.isoformat()}"
                                        ),
                                    },
                                    priority=75,
                                    urgency="normal" if days_until > 3 else "high",
                                ))
                                break

        except Exception as e:
            logger.error(f"Error finding location correlations: {e}")

        return suggestions
