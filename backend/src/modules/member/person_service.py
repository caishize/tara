"""Concrete PersonService wrapping PersonProfile ORM model."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import IPersonService, PersonProfile
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class PersonService(IPersonService):
    """Person profile CRUD (family members + external contacts)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_profile(
        self, person_id: str, family_id: str,
    ) -> Optional[PersonProfile]:
        from .models import PersonProfile as PPModel, ProfileStatus

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.id == UUID(person_id),
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                )
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_dto(row)

    async def list_people(
        self, family_id: str,
        min_importance: Optional[float] = None,
        relationship: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PersonProfile]:
        from .models import PersonProfile as PPModel, ProfileStatus

        query = select(PPModel).where(
            and_(
                PPModel.family_id == UUID(family_id),
                PPModel.status == ProfileStatus.ACTIVE.value,
            )
        )
        if min_importance is not None:
            query = query.where(PPModel.importance >= min_importance)
        if relationship is not None:
            query = query.where(PPModel.relationship == relationship)
        query = (
            query
            .order_by(PPModel.importance.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return [self._to_dto(row) for row in result.scalars().all()]

    async def create_profile(
        self, family_id: str, name: str,
        relationship: Optional[str] = None, **kwargs: Any,
    ) -> PersonProfile:
        from .models import PersonProfile as PPModel

        # user_id is required by the model; caller should provide it in kwargs
        user_id = kwargs.pop("user_id", None)
        if user_id is None:
            raise ValueError("user_id is required to create a person profile")

        profile = PPModel(
            family_id=UUID(family_id),
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            name=name,
            relationship=relationship,
        )
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        self.session.add(profile)
        await self.session.flush()
        return self._to_dto(profile)

    async def update_profile(
        self, person_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> PersonProfile:
        from .models import PersonProfile as PPModel

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.id == UUID(person_id),
                    PPModel.family_id == UUID(family_id),
                )
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError(f"Person profile {person_id} not found")

        for key, value in updates.items():
            if hasattr(profile, key) and key not in ("id", "family_id", "user_id"):
                setattr(profile, key, value)

        profile.updated_at = utc_now()
        await self.session.flush()
        return self._to_dto(profile)

    async def get_neglected(
        self, family_id: str,
        threshold_days: int = 90,
        min_importance: float = 5.0,
    ) -> List[PersonProfile]:
        from .models import PersonProfile as PPModel, ProfileStatus
        from datetime import timedelta

        cutoff = utc_now() - timedelta(days=threshold_days)
        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    PPModel.importance >= min_importance,
                    PPModel.last_mentioned_at < cutoff,
                )
            ).order_by(PPModel.last_mentioned_at.asc())
        )
        return [self._to_dto(row) for row in result.scalars().all()]

    async def get_people_with_favors(
        self, family_id: str,
    ) -> List[PersonProfile]:
        from .models import PersonProfile as PPModel, ProfileStatus

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    or_(
                        PPModel.favor_balance > 0.5,
                        PPModel.favor_balance < -0.5,
                    ),
                )
            ).order_by(PPModel.favor_balance.asc())
        )
        return [self._to_dto(row) for row in result.scalars().all()]

    async def search_contacts(
        self, family_id: str, query: str,
        limit: int = 20,
    ) -> List[PersonProfile]:
        from .models import PersonProfile as PPModel, ProfileStatus

        pattern = f"%{query}%"
        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    or_(
                        PPModel.name.ilike(pattern),
                        PPModel.organization.ilike(pattern),
                        sa_func.array_to_string(
                            PPModel.aliases, ","
                        ).ilike(pattern),
                    ),
                )
            )
            .order_by(PPModel.importance.desc())
            .limit(limit)
        )
        return [self._to_dto(row) for row in result.scalars().all()]

    async def update_favor_balance(
        self, person_id: str, family_id: str,
        new_balance: float,
    ) -> None:
        from .models import PersonProfile as PPModel

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.id == UUID(person_id),
                    PPModel.family_id == UUID(family_id),
                )
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError(f"Person profile {person_id} not found")
        profile.favor_balance = new_balance
        profile.updated_at = utc_now()
        await self.session.flush()

    @staticmethod
    def _to_dto(row: Any) -> PersonProfile:
        return PersonProfile(
            id=str(row.id),
            family_id=str(row.family_id),
            name=row.name,
            member_id=str(row.member_id) if row.member_id else None,
            aliases=row.aliases,
            relationship=row.relationship,
            relationship_context=row.relationship_context,
            organization=row.organization,
            location=row.location,
            preferences=row.preferences,
            favor_balance=row.favor_balance or 0.0,
            mention_count=row.mention_count or 0,
            last_mentioned_at=row.last_mentioned_at,
            importance=float(row.importance or 0),
            status=row.status,
        )
