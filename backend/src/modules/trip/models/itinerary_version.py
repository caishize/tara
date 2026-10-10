"""
ItineraryVersion entity model.
Stores different versions of itinerary plans for a trip, allowing users to compare and switch between them.
"""
from sqlalchemy import Column, String, Integer, Numeric, Boolean, TIMESTAMP, CheckConstraint, Index, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from typing import Optional, List, Dict, Any

from ....db.session import Base


class ItineraryVersion(Base):
    """ItineraryVersion (行程版本) entity."""

    __tablename__ = "itinerary_versions"

    # Primary Key
    version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Version info
    version_number = Column(Integer, nullable=False)
    version_name = Column(String(200), nullable=True)  # e.g., "方案A - 紧凑型"

    # Style tags for quick filtering
    style_tags = Column(JSONB, nullable=True, default=list)  # e.g., ["intensive", "cultural"]

    # Whether this is the currently active version
    is_active = Column(Boolean, nullable=False, default=False)

    # Total estimated cost for this version
    total_estimated_cost = Column(Numeric(12, 2), nullable=True)

    # Complete daily schedules data
    # Format: [
    #   {
    #     "day_number": 1,
    #     "schedule": [
    #       {
    #         "time": "09:00",
    #         "activity_type": "attraction",
    #         "title": "香港故宫",
    #         "location": "...",
    #         "estimated_cost": 200,
    #         "alternatives": [
    #           {"id": "...", "title": "...", "reason": "...", "estimated_cost": ...}
    #         ]
    #       }
    #     ],
    #     "packing_notes": "..."
    #   }
    # ]
    schedules = Column(JSONB, nullable=False, default=list)

    # Store the generation config (styles, family composition, preferences)
    generation_config = Column(JSONB, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    trip_plan = relationship("TripPlan", back_populates="versions")

    # Constraints
    __table_args__ = (
        CheckConstraint("version_number > 0", name="check_version_number_positive"),
        Index("idx_itinerary_version_trip", "trip_id", "version_number"),
        Index("idx_itinerary_version_active", "trip_id", "is_active"),
    )

    def __repr__(self):
        return f"<ItineraryVersion(version_id={self.version_id}, trip_id={self.trip_id}, v{self.version_number})>"

    @property
    def total_days(self) -> int:
        """Get the number of days in this version."""
        return len(self.schedules) if self.schedules else 0

    @property
    def total_activities(self) -> int:
        """Get the total number of activities across all days."""
        if not self.schedules:
            return 0
        return sum(len(day.get("schedule", [])) for day in self.schedules)

    def calculate_total_cost(self) -> float:
        """Calculate total estimated cost from all activities."""
        total = 0.0
        if self.schedules:
            for day in self.schedules:
                for activity in day.get("schedule", []):
                    cost = activity.get("estimated_cost")
                    if cost:
                        total += float(cost)
        return total

    def get_style_display_names(self) -> List[str]:
        """Get display names for style tags."""
        style_map = {
            "intensive": "紧凑型",
            "relaxed": "轻松型",
            "budget": "经济型",
            "luxury": "豪华型",
            "adventure": "探险型",
            "cultural": "文化型",
        }
        if not self.style_tags:
            return []
        return [style_map.get(tag, tag) for tag in self.style_tags]
