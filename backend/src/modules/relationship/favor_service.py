"""Concrete FavorService using favor_records table + PersonProfile balance.

The design specifies:
1. Favor records go into the `favor_records` table (primary storage)
2. `person_profiles.favor_balance` is a redundant computed field,
   recalculated after each recording
3. PersonProfile.favor_history JSONB is also updated for quick access
"""

import logging
from datetime import date
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func as sa_func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import update

from .interface import IFavorService, FavorRecord, FavorBalance
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class FavorService(IFavorService):
    """Favor recording, balance tracking, and reminders."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_statistics(self, family_id: str) -> dict:
        """Get favor statistics summary for a family.

        Returns total_received, total_given, net_balance, pending_count.
        """
        from .models import FavorRecord as FRModel

        fid = UUID(family_id)

        # Aggregate received vs given amounts
        receive_sum = sa_func.coalesce(
            sa_func.sum(
                case(
                    (FRModel.direction == "receive", FRModel.amount),
                    else_=0,
                )
            ), 0,
        )
        give_sum = sa_func.coalesce(
            sa_func.sum(
                case(
                    (FRModel.direction == "give", FRModel.amount),
                    else_=0,
                )
            ), 0,
        )
        pending_count = sa_func.count(
            case(
                (FRModel.status == "pending", FRModel.id),
                else_=None,
            )
        )

        result = await self.session.execute(
            select(receive_sum, give_sum, pending_count).where(
                FRModel.family_id == fid,
            )
        )
        row = result.one()
        total_received = float(row[0])
        total_given = float(row[1])
        pending = int(row[2])

        return {
            "total_received": total_received,
            "total_given": total_given,
            "net_balance": total_received - total_given,
            "pending_count": pending,
        }

    async def quick_create(
        self,
        family_id: str,
        contact_name: str,
        contact_id: Optional[str],
        amount: float,
        direction: str,
        event_type: str,
    ) -> dict:
        """Quick-create a favor record (mobile ledger form).

        Unlike record_favor, this doesn't require a PersonProfile.
        """
        from .models import FavorRecord as FRModel

        fid = UUID(family_id)
        cid = UUID(contact_id) if contact_id else None

        # If contact_id is provided, try to look up the name from members
        resolved_name = contact_name
        if cid:
            from ..member.models.member import Member as MemberModel
            result = await self.session.execute(
                select(MemberModel.name).where(
                    and_(MemberModel.id == cid, MemberModel.family_id == fid)
                )
            )
            member_name = result.scalar_one_or_none()
            if member_name:
                resolved_name = member_name

        # Determine status based on direction
        record_status = "pending" if direction == "receive" else "settled"

        db_record = FRModel(
            family_id=fid,
            contact_id=cid,
            contact_name=resolved_name,
            event_type=event_type,
            amount=amount,
            direction=direction,
            gift_type="cash",
            recorded_at=date.today(),
            status=record_status,
        )
        self.session.add(db_record)
        await self.session.flush()

        # Try to update PersonProfile balance if a matching profile exists
        if cid:
            from ..member.models import PersonProfile as PPModel
            # PersonProfile might be linked by name rather than ID
            result = await self.session.execute(
                select(PPModel).where(
                    and_(
                        PPModel.family_id == fid,
                        PPModel.name == resolved_name,
                    )
                )
            )
            profile = result.scalar_one_or_none()
            if profile:
                new_balance = await self._recalculate_balance(fid, cid)
                profile.favor_balance = new_balance
                profile.updated_at = utc_now()

        await self.session.flush()
        return db_record.to_dict()

    async def list_favor_records(
        self,
        family_id: str,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """List favor records as dicts (format expected by mobile client).

        Returns records with contact_name, direction, amount, event_type,
        recorded_at, status fields.
        """
        from .models import FavorRecord as FRModel

        fid = UUID(family_id)
        query = select(FRModel).where(FRModel.family_id == fid)

        if direction:
            db_direction = self._normalize_direction_to_db(direction)
            if db_direction:
                query = query.where(FRModel.direction == db_direction)

        if status:
            query = query.where(FRModel.status == status)

        query = (
            query
            .order_by(desc(FRModel.recorded_at))
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.scalars().all()
        return [row.to_dict() for row in rows]

    async def record_favor(
        self, family_id: str, person_id: str,
        direction: str, favor_type: str,
        amount: Optional[float] = None,
        description: Optional[str] = None,
        weight: float = 1.0,
        favor_date: Optional[date] = None,
    ) -> FavorRecord:
        from ..member.models import PersonProfile as PPModel
        from .models import FavorRecord

        fid = UUID(family_id)
        pid = UUID(person_id)

        # 1. Validate person exists
        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.id == pid,
                    PPModel.family_id == fid,
                )
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError(f"Person profile {person_id} not found")

        # 2. Map API direction to DB direction
        db_direction = "give" if direction == "gave" else "receive"

        # 3. Insert into favor_records (primary storage)
        db_record = FavorRecord(
            family_id=fid,
            contact_id=pid,
            contact_name=profile.name,
            event_type=favor_type,
            amount=amount or 0,
            direction=db_direction,
            gift_type=favor_type,
            recorded_at=favor_date or date.today(),
            note=description,
            status="settled" if direction == "gave" else "pending",
        )
        self.session.add(db_record)
        await self.session.flush()

        record_id = str(db_record.id)

        # 4. Also update the JSONB history on the profile (for quick access)
        profile.record_favor(
            favor_type=direction,
            description=description or favor_type,
            weight=weight,
            date=utc_now(),
        )

        # 5. Recalculate balance from favor_records and update profile
        new_balance = await self._recalculate_balance(fid, pid)
        profile.favor_balance = new_balance
        profile.updated_at = utc_now()

        await self.session.flush()

        return FavorRecord(
            id=record_id,
            person_id=person_id,
            family_id=family_id,
            direction=direction,
            favor_type=favor_type,
            amount=amount,
            description=description,
            weight=weight,
            date=favor_date or date.today(),
        )

    async def get_balance(
        self, family_id: str,
        person_id: Optional[str] = None,
    ) -> List[FavorBalance]:
        from ..member.models import PersonProfile as PPModel, ProfileStatus

        fid = UUID(family_id)
        query = select(PPModel).where(
            and_(
                PPModel.family_id == fid,
                PPModel.status == ProfileStatus.ACTIVE.value,
            )
        )
        if person_id:
            query = query.where(PPModel.id == UUID(person_id))

        result = await self.session.execute(query)
        profiles = result.scalars().all()

        balances = []
        for p in profiles:
            balance = p.favor_balance or 0.0
            if abs(balance) < 0.1:
                continue
            days = p.days_since_last_contact()
            balances.append(FavorBalance(
                person_id=str(p.id),
                person_name=p.name,
                favor_balance=balance,
                owes_favor=p.owes_favor(),
                is_owed_favor=p.is_owed_favor(),
                last_interaction_days=days,
            ))

        return balances

    async def list_favors(
        self, family_id: str,
        person_id: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 20,
    ) -> List[FavorRecord]:
        """List favor records from the favor_records table."""
        from .models import FavorRecord

        fid = UUID(family_id)
        query = select(FavorRecord).where(
            FavorRecord.family_id == fid,
        )

        if person_id:
            query = query.where(
                FavorRecord.contact_id == UUID(person_id),
            )

        if direction:
            # Normalize API direction to DB direction
            db_direction = self._normalize_direction_to_db(direction)
            if db_direction:
                query = query.where(
                    FavorRecord.direction == db_direction,
                )

        query = (
            query
            .order_by(desc(FavorRecord.recorded_at))
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.scalars().all()

        return [self._row_to_dto(row, family_id) for row in rows]

    # ------------------------------------------------------------------
    # Insight integration methods
    # ------------------------------------------------------------------

    async def mark_in_progress(
        self, favor_id: UUID, action_type: str = "adopt_to_trip",
    ) -> bool:
        """Mark a favor as in-progress (user has adopted the insight to a trip).

        Only transitions from 'pending' status. The favor_records.status
        column is String(20) and accepts arbitrary values.
        """
        from .models import FavorRecord as FRModel

        result = await self.session.execute(
            update(FRModel)
            .where(
                and_(FRModel.id == favor_id, FRModel.status == "pending"),
            )
            .values(status="in_progress")
        )
        return result.rowcount > 0

    async def mark_reciprocated(
        self, favor_id: UUID, action_type: str = "task_completed",
    ) -> bool:
        """Mark a favor as returned/reciprocated (user completed the task).

        Transitions from 'pending' or 'in_progress' to 'returned'.
        Uses 'returned' status to match the existing model vocabulary
        (pending | returned | settled). Updates updated_at timestamp.
        """
        from .models import FavorRecord as FRModel

        result = await self.session.execute(
            update(FRModel)
            .where(
                and_(
                    FRModel.id == favor_id,
                    FRModel.status.in_(["pending", "in_progress"]),
                ),
            )
            .values(status="returned", updated_at=utc_now())
        )
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _recalculate_balance(
        self, family_id: UUID, person_id: UUID,
    ) -> float:
        """Recalculate favor balance from favor_records table.

        Balance = SUM(gave_amount) - SUM(received_amount).
        Positive = they owe us. Negative = we owe them.
        """
        from .models import FavorRecord

        give_sum = sa_func.coalesce(
            sa_func.sum(
                case(
                    (FavorRecord.direction == "give",
                     FavorRecord.amount),
                    else_=0,
                )
            ), 0,
        )
        receive_sum = sa_func.coalesce(
            sa_func.sum(
                case(
                    (FavorRecord.direction == "receive",
                     FavorRecord.amount),
                    else_=0,
                )
            ), 0,
        )

        result = await self.session.execute(
            select(give_sum, receive_sum).where(
                and_(
                    FavorRecord.family_id == family_id,
                    FavorRecord.contact_id == person_id,
                )
            )
        )
        row = result.one()
        gave_total = float(row[0])
        received_total = float(row[1])

        # Positive = we gave more (they owe us)
        # Negative = they gave more (we owe them)
        return gave_total - received_total

    @staticmethod
    def _normalize_direction_to_db(direction: str) -> Optional[str]:
        """Normalize API direction names to DB column values."""
        if direction in ("gave", "given", "give"):
            return "give"
        if direction in ("received", "receive"):
            return "receive"
        return None

    @staticmethod
    def _row_to_dto(row: Any, family_id: str) -> FavorRecord:
        """Convert a FavorRecord row to a FavorRecord DTO."""
        # Map DB direction back to API direction
        api_direction = "gave" if row.direction == "give" else "received"
        return FavorRecord(
            id=str(row.id),
            person_id=str(row.contact_id) if row.contact_id else "",
            family_id=family_id,
            direction=api_direction,
            favor_type=row.event_type or "",
            amount=float(row.amount) if row.amount else None,
            description=row.note,
            weight=1.0,
            date=row.recorded_at,
        )
