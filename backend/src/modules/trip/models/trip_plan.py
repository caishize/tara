"""
TripPlan entity model.
Stores overall trip information including destination, dates, budget, participants, and status.
This is the single canonical trip table after consolidation of the legacy `trips` table.
"""
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Date,
    Text,
    TIMESTAMP,
    CheckConstraint,
    Index,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from datetime import date
from typing import Optional

from ....db.session import Base


class TripPlan(Base):
    """TripPlan (旅行计划) entity."""

    __tablename__ = "trips"

    # Primary Key
    trip_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)

    # Trip Basic Info
    trip_name = Column(String(200), nullable=True)
    destination = Column(String(500), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Trip Category: personal, business (top-level classification)
    category = Column(String(50), nullable=False, default="personal")

    # Trip Type: leisure, family, visit, business_trip, conference, client_visit, other
    trip_type = Column(String(50), nullable=True, default="leisure")

    # Budget
    budget = Column(Numeric(12, 2), nullable=True)  # Total budget
    actual_expense = Column(Numeric(12, 2), nullable=False, default=0)  # Actual spending

    # Participants (list of member IDs from Module 1)
    participants = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)

    # Status: planning, confirmed, in_progress, completed, cancelled
    status = Column(String(50), nullable=False, default="planning")

    # Canonical linkage for semantic dedup (history/superseded chain)
    canonical_trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    # Priority: low, normal, high, critical
    priority = Column(String(10), nullable=False, default="normal", server_default="normal")

    # Notes
    notes = Column(Text, nullable=True)

    # Description (from legacy trips table)
    description = Column(Text, nullable=True)

    # Recommendation context (stores LLM recommendation data)
    recommendation_context = Column(JSONB, nullable=True)

    # Extra data (flexible JSONB storage, from legacy trips table)
    extra_data = Column(JSONB, nullable=True, default=dict)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    itineraries = relationship(
        "TripItinerary",
        back_populates="trip_plan",
        cascade="all, delete-orphan",
        order_by="TripItinerary.day_number"
    )
    expenses = relationship(
        "TripExpense",
        back_populates="trip_plan",
        cascade="all, delete-orphan"
    )
    memories = relationship(
        "TripMemory",
        back_populates="trip_plan",
        cascade="all, delete-orphan"
    )
    versions = relationship(
        "ItineraryVersion",
        back_populates="trip_plan",
        cascade="all, delete-orphan",
        order_by="ItineraryVersion.version_number"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="check_trip_dates"),
        CheckConstraint("budget >= 0", name="check_budget_positive"),
        CheckConstraint("actual_expense >= 0", name="check_expense_positive"),
        CheckConstraint(
            "status IN ('planning', 'confirmed', 'in_progress', 'completed', 'cancelled')",
            name="check_status_valid"
        ),
        CheckConstraint(
            "category IN ('personal', 'business')",
            name="check_category_valid"
        ),
        CheckConstraint(
            "trip_type IN ('leisure', 'family', 'visit', 'business_trip', 'conference', 'client_visit', 'other')",
            name="check_trip_type_valid"
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')",
            name="check_priority_valid"
        ),
        Index("idx_trip_family", "family_id", "status"),
        Index("idx_trip_family_active", "family_id", "is_active"),
        Index("idx_trip_category", "family_id", "category"),
        Index("idx_trip_dates", "start_date", "end_date"),
        Index("idx_trip_status", "status"),
    )

    def __repr__(self):
        return f"<TripPlan(trip_id={self.trip_id}, destination={self.destination}, status={self.status})>"

    @property
    def duration_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def budget_used_percentage(self) -> Optional[float]:
        """Calculate budget usage percentage."""
        if not self.budget or self.budget == 0:
            return None
        return float(self.actual_expense / self.budget * 100)

    @property
    def remaining_budget(self) -> Optional[float]:
        """Calculate remaining budget."""
        if not self.budget:
            return None
        return float(self.budget - self.actual_expense)

    @property
    def is_ongoing(self) -> bool:
        """Check if trip is currently ongoing."""
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self) -> bool:
        """Check if trip is in the future."""
        return self.start_date > date.today()

    @property
    def days_until(self) -> int:
        """Days until trip starts (negative if past)."""
        return (self.start_date - date.today()).days

    def get_day_number(self, event_date: date) -> int:
        """Get the day number within the trip for a given date."""
        if event_date < self.start_date or event_date > self.end_date:
            return 0
        return (event_date - self.start_date).days + 1

    def get_day_label(self, event_date: date) -> str:
        """Get a label like 'Day 1' for a given date within the trip."""
        day_num = self.get_day_number(event_date)
        if day_num > 0:
            label = self.trip_name or self.destination
            return f"{label} Day {day_num}"
        return ""
