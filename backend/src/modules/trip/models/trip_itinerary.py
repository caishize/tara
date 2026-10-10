"""
TripItinerary entity model.
Stores daily itinerary schedule with activities, locations, times, and notes.
"""
from sqlalchemy import Column, Integer, TIMESTAMP, CheckConstraint, Index, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ....db.session import Base


class TripItinerary(Base):
    """TripItinerary (旅行行程) entity."""

    __tablename__ = "trip_itineraries"

    # Primary Key
    itinerary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Day number (1-indexed: Day 1, Day 2, ...)
    day_number = Column(Integer, nullable=False)

    # Daily Schedule (JSONB array)
    # Format: [
    #   {
    #     "time": "09:00",
    #     "activity_type": "transportation|accommodation|attraction|meal|other",
    #     "title": "高铁出发",
    #     "location": "上海虹桥站",
    #     "description": "G1234次，09:00-11:30",
    #     "estimated_cost": 150.00,
    #     "booking_info": {"order_number": "xxx", "confirmation_code": "yyy"},
    #     "notes": "提前30分钟到达车站"
    #   },
    #   ...
    # ]
    schedule = Column(JSONB, nullable=False, default=list)

    # Packing list for this day (if applicable)
    packing_notes = Column(JSONB, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    trip_plan = relationship("TripPlan", back_populates="itineraries")

    # Constraints
    __table_args__ = (
        CheckConstraint("day_number > 0", name="check_day_number_positive"),
        Index("idx_itinerary_trip", "trip_id", "day_number", unique=True),
    )

    def __repr__(self):
        return f"<TripItinerary(itinerary_id={self.itinerary_id}, trip_id={self.trip_id}, day={self.day_number})>"

    @property
    def total_estimated_cost(self) -> float:
        """Calculate total estimated cost for this day."""
        total = 0.0
        if self.schedule:
            for item in self.schedule:
                cost = item.get("estimated_cost")
                if cost:
                    total += float(cost)
        return total

    @property
    def activity_count(self) -> int:
        """Count number of activities in this day's schedule."""
        return len(self.schedule) if self.schedule else 0
