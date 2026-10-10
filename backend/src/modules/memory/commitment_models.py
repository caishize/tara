"""Commitment item persistence model.

Stores tracked commitments extracted from conversations, including
social intent classification and follow-up scheduling.
"""

from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from ...core.utils.timezone import utc_now
from ...db.session import Base


class CommitmentItemRecord(Base):
    """Persisted commitment extracted from a conversation.

    Maps to the in-memory CommitmentItem dataclass but adds DB persistence,
    tracking scores, and follow-up scheduling.
    """

    __tablename__ = "commitment_items"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    # What was committed
    commitment_type = Column(String(30), nullable=False)  # firm, vague, conditional, delegated
    who = Column(String(200), nullable=False)  # who promised
    what = Column(Text, nullable=False)  # what was promised
    to_whom = Column(String(200), nullable=False)  # to whom

    # Deadline and scheduling
    deadline = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="pending", index=True)

    # Social intent classification
    social_intent = Column(String(30), nullable=True)  # genuine, social_courtesy, obligation

    # Tracking
    tracking_score = Column(Float, default=0.5)  # 0.0-1.0 intent score
    follow_up_count = Column(Integer, default=0)
    next_follow_up_at = Column(DateTime(timezone=True), nullable=True)

    # Source
    source_conversation_id = Column(PGUUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "commitment_type": self.commitment_type,
            "who": self.who,
            "what": self.what,
            "to_whom": self.to_whom,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "social_intent": self.social_intent,
            "tracking_score": self.tracking_score,
            "follow_up_count": self.follow_up_count,
            "next_follow_up_at": self.next_follow_up_at.isoformat() if self.next_follow_up_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def record_follow_up(self) -> None:
        """Increment follow-up count and update timestamp."""
        self.follow_up_count = (self.follow_up_count or 0) + 1
        self.updated_at = utc_now()
