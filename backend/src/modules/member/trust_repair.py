"""Trust repair — correction tracking and proactive mention cycle.

When a user says "not right", "wrong" (or Chinese equivalents like
"不对", "错了", "搞错了"), the system stores a CorrectionRecord.
On the next relevant interaction, the assistant proactively mentions
"last time you corrected..." to build trust.

Components:
- CorrectionRecord: frozen dataclass for a single correction
- record_correction(): persist a correction to DB
- get_pending_repairs(): retrieve unacknowledged corrections
- acknowledge_repair(): mark a correction as surfaced
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text, Boolean, and_, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.utils.timezone import utc_now
from ...db.session import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Correction detection patterns
# ---------------------------------------------------------------------------

CORRECTION_PATTERNS = re.compile(
    r"(?i)"
    r"(?:不对|错了|搞错了|说错了|弄错了|不是这样|记错了|"
    r"no[,\s]+that'?s?\s+(?:not|wrong)|"
    r"that'?s?\s+incorrect|you'?(?:re|ve)\s+(?:got\s+it\s+)?wrong|"
    r"actually[,\s]+it'?s|correction[:\s]|"
    r"wrong[,\s]|not\s+right|不准确|有误)",
)


def contains_correction(text: str) -> bool:
    """Check whether user text contains a correction signal."""
    return bool(CORRECTION_PATTERNS.search(text))


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------


class CorrectionLog(Base):
    """Persistent store for user corrections to build trust via repair cycle."""

    __tablename__ = "correction_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)

    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    context = Column(Text, nullable=True)

    # Whether the correction has been proactively mentioned back to user
    is_surfaced = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    surfaced_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "original_text": self.original_text,
            "corrected_text": self.corrected_text,
            "context": self.context,
            "is_surfaced": self.is_surfaced,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "surfaced_at": self.surfaced_at.isoformat() if self.surfaced_at else None,
        }


# ---------------------------------------------------------------------------
# Value object (frozen dataclass)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrectionRecord:
    """Immutable snapshot of a user correction."""
    id: str
    user_id: str
    family_id: str
    original_text: str
    corrected_text: str
    context: Optional[str] = None
    is_surfaced: bool = False
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def record_correction(
    user_id: UUID,
    family_id: UUID,
    original: str,
    corrected: str,
    context: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> CorrectionRecord:
    """Record a user correction for future trust repair.

    Args:
        user_id: The user who made the correction.
        family_id: Family scope.
        original: What the system said incorrectly.
        corrected: What the user corrected it to.
        context: Optional surrounding context.
        db: Async SQLAlchemy session. If None, returns an in-memory record only.

    Returns:
        A CorrectionRecord representing the stored correction.
    """
    record_id = uuid4()
    now = utc_now()

    if db is not None:
        log_entry = CorrectionLog(
            id=record_id,
            user_id=user_id,
            family_id=family_id,
            original_text=original,
            corrected_text=corrected,
            context=context,
            is_surfaced=False,
            created_at=now,
        )
        db.add(log_entry)
        await db.flush()

    return CorrectionRecord(
        id=str(record_id),
        user_id=str(user_id),
        family_id=str(family_id),
        original_text=original,
        corrected_text=corrected,
        context=context,
        is_surfaced=False,
        created_at=now,
    )


async def get_pending_repairs(
    user_id: UUID,
    db: AsyncSession,
    limit: int = 5,
) -> List[CorrectionRecord]:
    """Retrieve corrections that have not yet been proactively surfaced.

    Args:
        user_id: The user whose corrections to fetch.
        db: Async SQLAlchemy session.
        limit: Max number of records to return.

    Returns:
        List of CorrectionRecord (oldest first).
    """
    try:
        result = await db.execute(
            select(CorrectionLog)
            .where(
                and_(
                    CorrectionLog.user_id == user_id,
                    CorrectionLog.is_surfaced == False,  # noqa: E712
                )
            )
            .order_by(CorrectionLog.created_at.asc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            CorrectionRecord(
                id=str(row.id),
                user_id=str(row.user_id),
                family_id=str(row.family_id),
                original_text=row.original_text,
                corrected_text=row.corrected_text,
                context=row.context,
                is_surfaced=row.is_surfaced,
                created_at=row.created_at,
            )
            for row in rows
        ]
    except Exception:
        logger.warning("Failed to query pending corrections", exc_info=True)
        return []


async def acknowledge_repair(
    correction_id: UUID,
    db: AsyncSession,
) -> bool:
    """Mark a correction as surfaced (proactively mentioned to user).

    Args:
        correction_id: The correction to acknowledge.
        db: Async SQLAlchemy session.

    Returns:
        True if the record was found and updated, False otherwise.
    """
    try:
        result = await db.execute(
            select(CorrectionLog).where(CorrectionLog.id == correction_id)
        )
        log_entry = result.scalar_one_or_none()
        if log_entry is None:
            return False

        log_entry.is_surfaced = True
        log_entry.surfaced_at = utc_now()
        await db.flush()
        return True
    except Exception:
        logger.warning("Failed to acknowledge correction repair", exc_info=True)
        return False


def format_repair_mention(record: CorrectionRecord) -> str:
    """Format a correction for proactive mention in conversation.

    Returns a human-readable string the assistant can use.
    """
    return (
        f"I remember you corrected me before: "
        f"I said \"{record.original_text}\" but you pointed out "
        f"it should be \"{record.corrected_text}\". "
        f"I've noted that."
    )
