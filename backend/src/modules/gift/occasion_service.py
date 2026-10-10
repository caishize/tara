"""Occasion service — occasion management with reminder support.

Manages preset occasions (holidays, birthdays, etc.) and their
association with trending gift suggestions.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Occasion, OccasionGift, TrendingGift

logger = logging.getLogger(__name__)


class OccasionService:
    """Service for occasion-related operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_upcoming_occasions(
        self, days: int = 30, from_date: Optional[date] = None, preview_count: int = 5
    ) -> List[Dict[str, Any]]:
        """Get upcoming occasions with gift previews."""
        if from_date is None:
            from_date = date.today()

        upcoming = await self._list_upcoming(days, from_date)
        result = []

        for occasion, days_until in upcoming:
            preview_gifts = await self._get_gift_preview(occasion.id, limit=preview_count)
            year = from_date.year if days_until <= 365 else from_date.year + 1
            occasion_date = occasion.calculate_date(year)

            result.append({
                "id": str(occasion.id),
                "name": occasion.name,
                "name_en": occasion.name_en,
                "date": occasion_date.isoformat() if occasion_date else None,
                "days_until": days_until,
                "gift_categories": occasion.gift_categories,
                "description": occasion.description,
                "preview_gifts": [g.to_dict() for g in preview_gifts],
            })

        return result

    async def get_occasion_by_id(self, occasion_id: UUID) -> Optional[Dict[str, Any]]:
        """Get occasion details by ID."""
        occasion = await self._get_by_id(occasion_id)
        if not occasion:
            return None

        gift_count = await self._get_gift_count_for_occasion(occasion_id)
        today = date.today()
        days_until = occasion.days_until(today)
        year = today.year if days_until and days_until <= 365 else today.year + 1
        occasion_date = occasion.calculate_date(year)

        return {
            **occasion.to_dict(),
            "date": occasion_date.isoformat() if occasion_date else None,
            "days_until": days_until,
            "gift_count": gift_count,
        }

    async def get_all_occasions(self) -> List[Dict[str, Any]]:
        """Get all active occasions with their next dates."""
        occasions = await self._list_all_active()
        today = date.today()
        result = []

        for occasion in occasions:
            days_until = occasion.days_until(today)
            year = today.year if days_until and days_until <= 365 else today.year + 1
            occasion_date = occasion.calculate_date(year)
            result.append({
                **occasion.to_dict(),
                "date": occasion_date.isoformat() if occasion_date else None,
                "days_until": days_until,
            })

        result.sort(key=lambda x: x.get("days_until") or float("inf"))
        return result

    async def get_gifts_for_occasion(
        self, occasion_id: UUID, page: int = 1, page_size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get trending gifts for an occasion with pagination."""
        gifts, total = await self._get_occasion_gifts(occasion_id, page, page_size)
        return [g.to_dict() for g in gifts], total

    async def get_reminder_occasions(
        self,
        thresholds: Optional[List[int]] = None,
        from_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Get occasions that should trigger reminders."""
        if thresholds is None:
            thresholds = [30, 7, 3, 1]
        if from_date is None:
            from_date = date.today()

        occasions = await self._list_all_active()
        reminders = []

        for occasion in occasions:
            days_until = occasion.days_until(from_date)
            if days_until is None:
                continue
            for threshold in thresholds:
                if days_until == threshold:
                    year = from_date.year if days_until <= 365 else from_date.year + 1
                    occasion_date = occasion.calculate_date(year)
                    preview_gifts = await self._get_gift_preview(occasion.id, limit=5)

                    reminders.append({
                        "id": str(occasion.id),
                        "name": occasion.name,
                        "name_en": occasion.name_en,
                        "date": occasion_date.isoformat() if occasion_date else None,
                        "days_until": days_until,
                        "reminder_type": f"{threshold}_day",
                        "urgency": "high" if threshold <= 3 else "medium" if threshold <= 7 else "low",
                        "preview_gifts": [g.to_dict() for g in preview_gifts],
                    })
                    break

        urgency_order = {"high": 0, "medium": 1, "low": 2}
        reminders.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), x["days_until"]))
        return reminders

    async def add_gift_to_occasion(
        self,
        occasion_id: UUID,
        gift_id: UUID,
        sort_order: int = 0,
        match_reason: Optional[str] = None,
    ) -> bool:
        """Add a gift to an occasion."""
        try:
            stmt = select(OccasionGift).where(
                and_(OccasionGift.occasion_id == occasion_id, OccasionGift.gift_id == gift_id)
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()

            if existing:
                existing.sort_order = sort_order
                if match_reason:
                    existing.match_reason = match_reason
            else:
                self.session.add(
                    OccasionGift(
                        occasion_id=occasion_id,
                        gift_id=gift_id,
                        sort_order=sort_order,
                        match_reason=match_reason,
                    )
                )
            await self.session.flush()
            return True
        except Exception as e:
            logger.error("Failed to add gift %s to occasion %s: %s", gift_id, occasion_id, e)
            return False

    async def remove_gift_from_occasion(self, occasion_id: UUID, gift_id: UUID) -> bool:
        """Remove a gift from an occasion."""
        stmt = select(OccasionGift).where(
            and_(OccasionGift.occasion_id == occasion_id, OccasionGift.gift_id == gift_id)
        )
        og = (await self.session.execute(stmt)).scalar_one_or_none()
        if og:
            await self.session.delete(og)
            await self.session.flush()
            return True
        return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get occasion statistics."""
        total = (
            await self.session.execute(select(func.count()).select_from(Occasion))
        ).scalar() or 0
        active = len(await self._list_all_active())
        upcoming = await self._list_upcoming(days=30)
        return {
            "total_occasions": total,
            "active_occasions": active,
            "upcoming_in_30_days": len(upcoming),
        }

    # -- private helpers -------------------------------------------------------

    async def _get_by_id(self, occasion_id: UUID) -> Optional[Occasion]:
        stmt = select(Occasion).where(Occasion.id == occasion_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _list_all_active(self) -> List[Occasion]:
        stmt = select(Occasion).where(Occasion.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def _list_upcoming(
        self, days: int = 30, from_date: Optional[date] = None
    ) -> List[Tuple[Occasion, int]]:
        if from_date is None:
            from_date = date.today()
        occasions = await self._list_all_active()
        upcoming = []
        for occ in occasions:
            d = occ.days_until(from_date)
            if d is not None and 0 <= d <= days:
                upcoming.append((occ, d))
        upcoming.sort(key=lambda x: x[1])
        return upcoming

    async def _get_gift_preview(self, occasion_id: UUID, limit: int = 5) -> List[TrendingGift]:
        stmt = (
            select(TrendingGift)
            .join(OccasionGift, OccasionGift.gift_id == TrendingGift.id)
            .where(
                and_(
                    OccasionGift.occasion_id == occasion_id,
                    TrendingGift.is_active.is_(True),
                )
            )
            .order_by(OccasionGift.sort_order, desc(TrendingGift.popularity_score))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _get_occasion_gifts(
        self, occasion_id: UUID, page: int = 1, page_size: int = 10, active_only: bool = True
    ) -> Tuple[List[TrendingGift], int]:
        base_cond = [OccasionGift.occasion_id == occasion_id]
        if active_only:
            count_stmt = (
                select(func.count())
                .select_from(OccasionGift)
                .join(TrendingGift, OccasionGift.gift_id == TrendingGift.id)
                .where(and_(*base_cond, TrendingGift.is_active.is_(True)))
            )
        else:
            count_stmt = (
                select(func.count()).select_from(OccasionGift).where(and_(*base_cond))
            )
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(TrendingGift)
            .join(OccasionGift, OccasionGift.gift_id == TrendingGift.id)
            .where(OccasionGift.occasion_id == occasion_id)
        )
        if active_only:
            stmt = stmt.where(TrendingGift.is_active.is_(True))
        stmt = (
            stmt.order_by(OccasionGift.sort_order, desc(TrendingGift.popularity_score))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        gifts = list((await self.session.execute(stmt)).scalars().all())
        return gifts, total

    async def _get_gift_count_for_occasion(self, occasion_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(OccasionGift)
            .join(TrendingGift, OccasionGift.gift_id == TrendingGift.id)
            .where(
                and_(
                    OccasionGift.occasion_id == occasion_id,
                    TrendingGift.is_active.is_(True),
                )
            )
        )
        return (await self.session.execute(stmt)).scalar() or 0
