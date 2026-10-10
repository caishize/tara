"""
TripExpense entity model.
Tracks individual expenses during a trip with category, amount, and description.
"""
from sqlalchemy import Column, String, Numeric, Date, Text, TIMESTAMP, CheckConstraint, Index, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ....db.session import Base


class TripExpense(Base):
    """TripExpense (旅行支出) entity."""

    __tablename__ = "trip_expenses"

    # Primary Key
    expense_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Expense Details
    expense_date = Column(Date, nullable=False)

    # Category: transportation, accommodation, tickets, food, shopping, other
    category = Column(String(50), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(Text, nullable=True)

    # Location where expense occurred
    location = Column(String(200), nullable=True)

    # Payment method
    payment_method = Column(String(100), nullable=True)

    # Receipt/proof URL (if uploaded)
    receipt_url = Column(String(500), nullable=True)

    # Associated itinerary item (optional)
    itinerary_item_id = Column(UUID(as_uuid=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    trip_plan = relationship("TripPlan", back_populates="expenses")

    # Constraints
    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_amount_positive"),
        CheckConstraint(
            "category IN ('transportation', 'accommodation', 'tickets', 'food', 'shopping', 'other')",
            name="check_category_valid"
        ),
        Index("idx_expense_trip", "trip_id", "expense_date"),
        Index("idx_expense_category", "trip_id", "category"),
    )

    def __repr__(self):
        return f"<TripExpense(expense_id={self.expense_id}, category={self.category}, amount={self.amount})>"
