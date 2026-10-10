"""Gift recommendation repositories — data access layer.

Provides repository classes for GiftRecommendation, GiftHistory,
and GiftPreference entities.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    GiftHistory,
    GiftPreference,
    GiftRecommendation,
    RecommendStatus,
)
from ...core.utils.timezone import utc_now


class RecommendationRepository:
    """Data access for GiftRecommendation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> GiftRecommendation:
        rec = GiftRecommendation(**data)
        self.db.add(rec)
        await self.db.commit()
        await self.db.refresh(rec)
        return rec

    async def get_by_id(self, recommendation_id: UUID) -> Optional[GiftRecommendation]:
        result = await self.db.execute(
            select(GiftRecommendation).where(GiftRecommendation.id == recommendation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_family(
        self,
        family_id: UUID,
        status: Optional[str] = None,
        member_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[GiftRecommendation]:
        query = select(GiftRecommendation).where(GiftRecommendation.family_id == family_id)
        if status:
            query = query.where(GiftRecommendation.status == status)
        if member_id:
            query = query.where(GiftRecommendation.recipient_member_id == member_id)
        query = query.order_by(GiftRecommendation.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_recipient(
        self, recipient_member_id: UUID, status: Optional[str] = None, limit: int = 20
    ) -> List[GiftRecommendation]:
        query = select(GiftRecommendation).where(
            GiftRecommendation.recipient_member_id == recipient_member_id
        )
        if status:
            query = query.where(GiftRecommendation.status == status)
        query = query.order_by(GiftRecommendation.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, recommendation_id: UUID, status: str, **kwargs
    ) -> Optional[GiftRecommendation]:
        rec = await self.get_by_id(recommendation_id)
        if not rec:
            return None
        rec.status = status
        if status == RecommendStatus.VIEWED.value and "viewed_at" not in kwargs:
            rec.viewed_at = utc_now()
        if status == RecommendStatus.SELECTED.value and "selected_at" not in kwargs:
            rec.selected_at = utc_now()
        for key, value in kwargs.items():
            if hasattr(rec, key):
                setattr(rec, key, value)
        await self.db.commit()
        await self.db.refresh(rec)
        return rec

    async def mark_expired(self, days: int = 7) -> int:
        expiry_date = utc_now() - timedelta(days=days)
        query = select(GiftRecommendation).where(and_(
            GiftRecommendation.status.in_([
                RecommendStatus.PENDING.value, RecommendStatus.VIEWED.value
            ]),
            GiftRecommendation.created_at < expiry_date,
        ))
        result = await self.db.execute(query)
        recs = result.scalars().all()
        count = 0
        for rec in recs:
            rec.status = RecommendStatus.EXPIRED.value
            rec.expires_at = utc_now()
            count += 1
        await self.db.commit()
        return count


class HistoryRepository:
    """Data access for GiftHistory."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_recipient(
        self, recipient_member_id: UUID, years_back: int = 3
    ) -> List[GiftHistory]:
        cutoff = date.today() - timedelta(days=years_back * 365)
        result = await self.db.execute(
            select(GiftHistory)
            .where(and_(
                GiftHistory.recipient_member_id == recipient_member_id,
                GiftHistory.occasion_date >= cutoff,
            ))
            .order_by(GiftHistory.occasion_date.desc())
        )
        return list(result.scalars().all())

    async def get_category_counts(
        self, recipient_member_id: UUID, years_back: int = 3
    ) -> Dict[str, int]:
        from sqlalchemy import func as sqla_func
        cutoff = date.today() - timedelta(days=years_back * 365)
        result = await self.db.execute(
            select(GiftHistory.gift_category, sqla_func.count(GiftHistory.id).label("cnt"))
            .where(and_(
                GiftHistory.recipient_member_id == recipient_member_id,
                GiftHistory.occasion_date >= cutoff,
            ))
            .group_by(GiftHistory.gift_category)
        )
        return {row.gift_category: row.cnt for row in result}


class PreferenceRepository:
    """Data access for GiftPreference."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_by_member(self, member_id: UUID) -> List[GiftPreference]:
        result = await self.db.execute(
            select(GiftPreference).where(GiftPreference.member_id == member_id)
        )
        return list(result.scalars().all())

    async def get_by_member_category(
        self, member_id: UUID, category: str
    ) -> Optional[GiftPreference]:
        result = await self.db.execute(
            select(GiftPreference).where(and_(
                GiftPreference.member_id == member_id,
                GiftPreference.gift_category == category,
            ))
        )
        return result.scalar_one_or_none()

    async def get_excluded_categories(
        self,
        member_id: UUID,
        threshold: float = -0.3,
    ) -> List[str]:
        prefs = await self.get_all_by_member(member_id)
        return [p.gift_category for p in prefs if p.preference_score < threshold and p.confidence > 0.5]

    async def create(self, data: dict) -> GiftPreference:
        pref = GiftPreference(**data)
        self.db.add(pref)
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def update(self, pref_id: UUID, data: dict) -> Optional[GiftPreference]:
        result = await self.db.execute(
            select(GiftPreference).where(GiftPreference.id == pref_id)
        )
        pref = result.scalar_one_or_none()
        if not pref:
            return None
        for key, value in data.items():
            if hasattr(pref, key):
                setattr(pref, key, value)
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def get_top_preferences(
        self,
        member_id: UUID,
        min_confidence: float = 0.0,
        limit: int = 5,
    ) -> List[GiftPreference]:
        """Return top preferences by score descending, filtering score > 0."""
        query = (
            select(GiftPreference)
            .where(
                and_(
                    GiftPreference.member_id == member_id,
                    GiftPreference.preference_score > 0,
                )
            )
        )
        if min_confidence > 0:
            query = query.where(GiftPreference.confidence >= min_confidence)
        query = query.order_by(GiftPreference.preference_score.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_stale_preferences(self, threshold_date: datetime) -> List[GiftPreference]:
        result = await self.db.execute(
            select(GiftPreference).where(GiftPreference.updated_at < threshold_date)
        )
        return list(result.scalars().all())
