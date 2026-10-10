"""Repository for commitment item persistence.

Provides CRUD operations for CommitmentItemRecord, bridging the in-memory
CommitmentItem dataclass with the database.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit.service import AuditService
from ...core.utils.timezone import utc_now
from .commitment_models import CommitmentItemRecord


class CommitmentRepository:
    """Database operations for commitment items."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._audit = AuditService(db)

    async def create(
        self,
        user_id: UUID,
        family_id: UUID,
        commitment_type: str,
        who: str,
        what: str,
        to_whom: str,
        deadline: Optional[datetime] = None,
        social_intent: Optional[str] = None,
        tracking_score: float = 0.5,
        source_conversation_id: Optional[UUID] = None,
    ) -> CommitmentItemRecord:
        """Create and persist a new commitment item."""
        record = CommitmentItemRecord(
            user_id=user_id,
            family_id=family_id,
            commitment_type=commitment_type,
            who=who,
            what=what,
            to_whom=to_whom,
            deadline=deadline,
            social_intent=social_intent,
            tracking_score=tracking_score,
            source_conversation_id=source_conversation_id,
        )
        self._db.add(record)
        await self._db.flush()
        return record

    async def get_by_id(self, commitment_id: UUID) -> Optional[CommitmentItemRecord]:
        """Fetch a single commitment by ID."""
        result = await self._db.execute(
            select(CommitmentItemRecord).where(
                CommitmentItemRecord.id == commitment_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_for_user(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> List[CommitmentItemRecord]:
        """List all pending commitments for a user in a family."""
        result = await self._db.execute(
            select(CommitmentItemRecord).where(
                CommitmentItemRecord.user_id == user_id,
                CommitmentItemRecord.family_id == family_id,
                CommitmentItemRecord.status == "pending",
            ).order_by(CommitmentItemRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_due_for_follow_up(self) -> List[CommitmentItemRecord]:
        """List commitments whose next_follow_up_at is past due."""
        now = utc_now()
        result = await self._db.execute(
            select(CommitmentItemRecord).where(
                CommitmentItemRecord.status == "pending",
                CommitmentItemRecord.next_follow_up_at.isnot(None),
                CommitmentItemRecord.next_follow_up_at <= now,
            ).order_by(CommitmentItemRecord.next_follow_up_at.asc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        commitment_id: UUID,
        new_status: str,
    ) -> Optional[CommitmentItemRecord]:
        """Update the status of a commitment."""
        record = await self.get_by_id(commitment_id)
        if record is None:
            return None
        old_status = record.status
        record.status = new_status
        record.updated_at = utc_now()
        await self._audit.log_event(
            user_id=record.user_id,
            family_id=record.family_id,
            event_type="commitment_status_changed",
            event_data={
                "commitment_id": str(commitment_id),
                "old_status": old_status,
                "new_status": new_status,
                "what": (record.what or "")[:200],
            },
        )
        await self._db.flush()
        return record

    async def record_follow_up(
        self,
        commitment_id: UUID,
        next_follow_up_at: Optional[datetime] = None,
    ) -> Optional[CommitmentItemRecord]:
        """Record a follow-up for a commitment and schedule the next one."""
        record = await self.get_by_id(commitment_id)
        if record is None:
            return None
        record.record_follow_up()
        record.next_follow_up_at = next_follow_up_at
        await self._db.flush()
        return record
