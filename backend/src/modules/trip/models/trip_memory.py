"""
TripMemory entity model.
Stores photos, videos, and notes from trips with AI-generated captions and ratings.
"""
from sqlalchemy import Column, String, Text, Integer, TIMESTAMP, CheckConstraint, Index, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ....db.session import Base


class TripMemory(Base):
    """TripMemory (旅行回忆) entity."""

    __tablename__ = "trip_memories"

    # Primary Key
    memory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Memory Type: photo, video, note
    content_type = Column(String(50), nullable=False)

    # Media URLs (for photos/videos, can be multiple)
    content_urls = Column(ARRAY(String(500)), nullable=True, default=list)

    # Caption/Description
    caption = Column(Text, nullable=True)

    # AI-generated caption (separate from user caption)
    ai_caption = Column(Text, nullable=True)

    # Location where memory was created
    location = Column(String(200), nullable=True)

    # GPS coordinates (for photo EXIF data)
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)

    # When the memory happened (from photo EXIF or user input)
    memory_date = Column(DateTime(timezone=True), nullable=True)

    # Rating (1-5 stars for this moment/activity)
    rating = Column(Integer, nullable=True)

    # Associated itinerary item (if photo/video taken during scheduled activity)
    itinerary_item_id = Column(UUID(as_uuid=True), nullable=True)

    # Tags (e.g., "family", "景点", "美食")
    tags = Column(ARRAY(String(50)), nullable=True, default=list)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    trip_plan = relationship("TripPlan", back_populates="memories")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "content_type IN ('photo', 'video', 'note')",
            name="check_content_type_valid"
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="check_rating_range"
        ),
        Index("idx_memory_trip", "trip_id", "memory_date"),
        Index("idx_memory_type", "trip_id", "content_type"),
    )

    def __repr__(self):
        return f"<TripMemory(memory_id={self.memory_id}, type={self.content_type}, trip_id={self.trip_id})>"
