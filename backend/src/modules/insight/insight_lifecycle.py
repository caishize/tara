"""Shared insight lifecycle helpers.

Extracted to avoid duplication of status transition validation and
insight lookup across InsightFeedbackService and InsightAdoptService.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Insight,
    InsightStatus,
    VALID_TRANSITIONS,
    InvalidTransitionError,
)


def transition_status(insight: Insight, new_status: InsightStatus) -> None:
    """Validate and apply a status transition.

    Raises:
        InvalidTransitionError: If the transition is not in ``VALID_TRANSITIONS``.
    """
    current = InsightStatus(insight.status)
    allowed = VALID_TRANSITIONS.get(current, frozenset())
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {new_status.value}. "
            f"Allowed: {sorted(s.value for s in allowed)}"
        )
    insight.status = new_status.value


async def get_insight(db: AsyncSession, insight_id: UUID) -> Optional[Insight]:
    """Fetch an insight by ID."""
    result = await db.execute(
        select(Insight).where(Insight.id == insight_id)
    )
    return result.scalar_one_or_none()


def ensure_active_before(
    insight: Insight, target_status: InsightStatus,
) -> None:
    """If insight is PENDING and target requires ACTIVE, step through ACTIVE first.

    Common pattern for ACKNOWLEDGED and ACTED transitions which require
    PENDING -> ACTIVE -> target.
    """
    if InsightStatus(insight.status) == InsightStatus.PENDING:
        transition_status(insight, InsightStatus.ACTIVE)
