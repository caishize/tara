"""Four-dimension relationship temperature model.

Computes a weighted relationship health score based on:
  - interaction_freq (0.3): how often interactions occur
  - interaction_quality (0.3): average importance of interactions
  - commitment_fulfillment (0.2): commitment follow-through rate
  - recency (0.2): how recently last interaction occurred
"""
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RelationshipTemperature:
    """Weighted relationship health composite."""

    interaction_freq: float = 0.0
    interaction_quality: float = 0.0
    commitment_fulfillment: float = 0.0
    recency: float = 0.0

    @property
    def composite(self) -> float:
        """Weighted composite: freq(0.3) + quality(0.3) + commitment(0.2) + recency(0.2)."""
        return (
            self.interaction_freq * 0.3
            + self.interaction_quality * 0.3
            + self.commitment_fulfillment * 0.2
            + self.recency * 0.2
        )

    @property
    def status(self) -> str:
        """Human-readable status label."""
        score = self.composite
        if score >= 0.7:
            return "warm"
        if score >= 0.4:
            return "cool"
        if score >= 0.2:
            return "cold"
        return "frozen"


async def compute_temperature(
    user_id: UUID,
    target_member_id: UUID,
    db,  # AsyncSession
) -> RelationshipTemperature:
    """Compute relationship temperature by querying interaction data.

    Args:
        user_id: The user who owns the memories.
        target_member_id: The member whose relationship is being measured.
        db: An async SQLAlchemy session.

    Returns:
        A frozen RelationshipTemperature dataclass.
    """
    from ...core.utils.timezone import utc_now
    from ..memory.models import ConversationMemory

    now = utc_now()
    thirty_days_ago = now - timedelta(days=30)

    # --- interaction_freq ---
    # Count active memories mentioning this user in the last 30 days
    freq_result = await db.execute(
        select(func.count(ConversationMemory.id)).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.created_at >= thirty_days_ago,
            ConversationMemory.status == "active",
        )
    )
    total_memories = freq_result.scalar() or 0
    freq_score = min(1.0, total_memories / 30.0)

    # --- interaction_quality ---
    # Average importance of recent active memories
    quality_result = await db.execute(
        select(func.avg(ConversationMemory.importance)).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.created_at >= thirty_days_ago,
            ConversationMemory.status == "active",
        )
    )
    avg_importance = quality_result.scalar()
    quality_score = min(1.0, float(avg_importance or 5.0) / 10.0)

    # --- commitment_fulfillment ---
    commitment_score = await _compute_commitment_score(user_id, db)

    # --- recency ---
    recency_result = await db.execute(
        select(func.max(ConversationMemory.created_at)).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == "active",
        )
    )
    last_interaction = recency_result.scalar()
    if last_interaction:
        days_since = (now - last_interaction).days
        recency_score = max(0.0, 1.0 - days_since / 30.0)
    else:
        recency_score = 0.0

    return RelationshipTemperature(
        interaction_freq=freq_score,
        interaction_quality=quality_score,
        commitment_fulfillment=commitment_score,
        recency=recency_score,
    )


async def record_interaction_intent(
    person_id: UUID,
    db,  # AsyncSession
    interaction_type: str = "insight_adopted",
) -> None:
    """Record that user intends to interact (adopted insight). Lightweight signal.

    Updates the PersonProfile's last_mentioned_at as a low-weight interaction
    signal, following the existing record_mention() pattern.
    """
    from ..member.models import PersonProfile as PPModel

    result = await db.execute(
        select(PPModel).where(PPModel.id == person_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.debug(
            "record_interaction_intent: person %s not found, skipping",
            person_id,
        )
        return

    # Use record_mention as a lightweight signal (increments mention_count)
    profile.record_mention()
    logger.debug(
        "Recorded interaction intent (%s) for person %s",
        interaction_type, person_id,
    )


async def record_interaction(
    person_id: UUID,
    db,  # AsyncSession
    interaction_type: str = "insight_acted",
) -> None:
    """Record actual interaction completion.

    Updates the PersonProfile's last_mentioned_at and increments
    mention_count as a full interaction signal.
    """
    from ..member.models import PersonProfile as PPModel

    result = await db.execute(
        select(PPModel).where(PPModel.id == person_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.debug(
            "record_interaction: person %s not found, skipping",
            person_id,
        )
        return

    # Record as a full interaction (same as record_mention but semantically
    # represents a completed interaction rather than a conversation mention)
    profile.record_mention()
    logger.debug(
        "Recorded interaction (%s) for person %s",
        interaction_type, person_id,
    )



async def _compute_commitment_score(user_id: UUID, db) -> float:
    """Compute commitment fulfillment rate from commitment_items table.

    Falls back to 0.5 (neutral) if no commitments exist or table is absent.
    """
    try:
        from ..memory.commitment_models import CommitmentItemRecord

        total_result = await db.execute(
            select(func.count(CommitmentItemRecord.id)).where(
                CommitmentItemRecord.user_id == user_id,
            )
        )
        total = total_result.scalar() or 0
        if total == 0:
            return 0.5

        fulfilled_result = await db.execute(
            select(func.count(CommitmentItemRecord.id)).where(
                CommitmentItemRecord.user_id == user_id,
                CommitmentItemRecord.status == "fulfilled",
            )
        )
        fulfilled = fulfilled_result.scalar() or 0
        return fulfilled / total
    except Exception:
        logger.debug("commitment_items unavailable, using neutral score")
        return 0.5
