"""Trending gift service — discovery, listing, search, and caching.

This is the main entry point for the trending subsystem.
Sub-modules are re-exported here so existing imports continue to work:
    occasion_service.py      — OccasionService
    user_save_service.py     — UserGiftSaveService
    data_fetcher_service.py  — DataFetcherService
"""
import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TrendingGift
from .occasion_service import OccasionService  # noqa: F401
from .user_save_service import UserGiftSaveService  # noqa: F401
from .data_fetcher_service import DataFetcherService  # noqa: F401
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 hours


class TrendingGiftService:
    """Service for trending gift queries with Redis caching."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.session = session
        self.redis = redis_client

    # -- listing / search ------------------------------------------------------

    async def get_gifts_by_category(
        self,
        category: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "popularity",
        use_cache: bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get trending gifts by category with pagination."""
        cache_key = f"trending_gifts:category:{category}:page:{page}:size:{page_size}"
        if use_cache and self.redis and sort_by == "popularity":
            cached = await self._get_from_cache(cache_key)
            if cached:
                return cached["items"], cached["total"]

        gifts, total = await self._list_by_category(category, page, page_size, sort_by)
        result = [gift.to_dict() for gift in gifts]

        if use_cache and self.redis and sort_by == "popularity":
            await self._set_cache(cache_key, {"items": result, "total": total})

        return result, total

    async def get_all_gifts(
        self, page: int = 1, page_size: int = 20, sort_by: str = "popularity"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get all active trending gifts with pagination."""
        gifts, total = await self._list_all_active(page, page_size, sort_by)
        return [gift.to_dict() for gift in gifts], total

    async def get_gift_detail(
        self, gift_id: UUID, include_similar: bool = True, similar_count: int = 5
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information about a trending gift."""
        gift = await self._get_by_id(gift_id)
        if not gift:
            return None

        result = gift.to_dict()

        if include_similar:
            similar, _ = await self._list_by_category(
                gift.category, page=1, page_size=similar_count + 1, sort_by="popularity"
            )
            result["similar_gifts"] = [
                g.to_dict() for g in similar if g.id != gift_id
            ][:similar_count]

        return result

    async def search_gifts(
        self,
        query: str,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search trending gifts by name or brand."""
        if len(query) < 1:
            return [], 0

        conditions = [
            TrendingGift.is_active.is_(True),
            or_(
                TrendingGift.name.ilike(f"%{query}%"),
                TrendingGift.brand.ilike(f"%{query}%"),
            ),
        ]
        if category:
            conditions.append(TrendingGift.category == category)

        count_stmt = (
            select(func.count()).select_from(TrendingGift).where(and_(*conditions))
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(TrendingGift)
            .where(and_(*conditions))
            .order_by(desc(TrendingGift.popularity_score))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        gifts = list((await self.session.execute(stmt)).scalars().all())

        return [g.to_dict() for g in gifts], total

    async def upsert_gift(self, gift_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a trending gift (used by scrapers)."""
        gift = await self._upsert(gift_data)
        return gift.to_dict()

    async def deactivate_expired(self, days: int = 30) -> int:
        """Deactivate gifts not updated in the specified days."""
        cutoff = utc_now() - timedelta(days=days)
        stmt = (
            update(TrendingGift)
            .where(and_(TrendingGift.is_active.is_(True), TrendingGift.updated_at < cutoff))
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        count = result.rowcount
        logger.info("Deactivated %d expired gifts (older than %d days)", count, days)
        return count

    async def cleanup_old_gifts(self, days: int = 90) -> int:
        """Delete gifts older than the specified days."""
        cutoff = utc_now() - timedelta(days=days)
        stmt = delete(TrendingGift).where(TrendingGift.created_at < cutoff)
        result = await self.session.execute(stmt)
        await self.session.flush()
        count = result.rowcount
        logger.info("Deleted %d old gifts (older than %d days)", count, days)
        return count

    async def get_category_counts(self) -> Dict[str, int]:
        """Get count of active gifts per category."""
        stmt = (
            select(TrendingGift.category, func.count(TrendingGift.id))
            .where(TrendingGift.is_active.is_(True))
            .group_by(TrendingGift.category)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_stats(self) -> Dict[str, Any]:
        """Get trending gift statistics."""
        total = (
            await self.session.execute(
                select(func.count()).select_from(TrendingGift)
            )
        ).scalar() or 0
        active = (
            await self.session.execute(
                select(func.count())
                .select_from(TrendingGift)
                .where(TrendingGift.is_active.is_(True))
            )
        ).scalar() or 0
        category_counts = await self.get_category_counts()

        last_update = None
        if self.redis:
            raw = await self.redis.get("trending_gifts:last_update")
            if raw:
                last_update = raw.decode() if isinstance(raw, bytes) else raw

        return {
            "total_gifts": total,
            "active_gifts": active,
            "category_counts": category_counts,
            "last_update_at": last_update,
        }

    async def invalidate_cache(self, category: Optional[str] = None):
        """Invalidate cache for a category or all categories."""
        if not self.redis:
            return
        pattern = (
            f"trending_gifts:category:{category}:*"
            if category
            else "trending_gifts:*"
        )
        try:
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)
        except Exception as e:
            logger.error("Failed to invalidate cache: %s", e)

    # -- private helpers -------------------------------------------------------

    async def _get_by_id(self, gift_id: UUID) -> Optional[TrendingGift]:
        stmt = select(TrendingGift).where(TrendingGift.id == gift_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_external_id(
        self, external_id: str, data_source: str
    ) -> Optional[TrendingGift]:
        stmt = select(TrendingGift).where(
            and_(
                TrendingGift.external_id == external_id,
                TrendingGift.data_source == data_source,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _list_by_category(
        self,
        category: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "popularity",
        active_only: bool = True,
    ) -> Tuple[List[TrendingGift], int]:
        conditions = [TrendingGift.category == category]
        if active_only:
            conditions.append(TrendingGift.is_active.is_(True))

        total = (
            await self.session.execute(
                select(func.count()).select_from(TrendingGift).where(and_(*conditions))
            )
        ).scalar() or 0

        stmt = select(TrendingGift).where(and_(*conditions))
        stmt = self._apply_sort(stmt, sort_by)
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        gifts = list((await self.session.execute(stmt)).scalars().all())
        return gifts, total

    async def _list_all_active(
        self, page: int = 1, page_size: int = 20, sort_by: str = "popularity"
    ) -> Tuple[List[TrendingGift], int]:
        conditions = [TrendingGift.is_active.is_(True)]
        total = (
            await self.session.execute(
                select(func.count()).select_from(TrendingGift).where(and_(*conditions))
            )
        ).scalar() or 0

        stmt = select(TrendingGift).where(and_(*conditions))
        stmt = self._apply_sort(stmt, sort_by)
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        gifts = list((await self.session.execute(stmt)).scalars().all())
        return gifts, total

    async def _upsert(self, gift_data: Dict[str, Any]) -> TrendingGift:
        existing = await self._get_by_external_id(
            gift_data.get("external_id", ""), gift_data.get("data_source", "")
        )
        if existing:
            for key, value in gift_data.items():
                if key not in ("id", "created_at"):
                    setattr(existing, key, value)
            existing.updated_at = utc_now()
            existing.last_verified_at = utc_now()
            await self.session.flush()
            return existing
        gift = TrendingGift(**gift_data)
        self.session.add(gift)
        await self.session.flush()
        await self.session.refresh(gift)
        return gift

    @staticmethod
    def _apply_sort(stmt, sort_by: str):
        if sort_by == "popularity":
            return stmt.order_by(desc(TrendingGift.popularity_score), TrendingGift.rank)
        if sort_by == "price_asc":
            return stmt.order_by(TrendingGift.price)
        if sort_by == "price_desc":
            return stmt.order_by(desc(TrendingGift.price))
        if sort_by == "rating":
            return stmt.order_by(desc(TrendingGift.rating))
        if sort_by == "discount":
            return stmt.order_by(desc(TrendingGift.discount_percent))
        return stmt.order_by(TrendingGift.rank)

    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data.decode() if isinstance(data, bytes) else data)
        except Exception as e:
            logger.warning("Cache get failed for %s: %s", key, e)
        return None

    async def _set_cache(self, key: str, data: Dict[str, Any]):
        if not self.redis:
            return
        try:
            await self.redis.setex(key, CACHE_TTL, json.dumps(data))
        except Exception as e:
            logger.warning("Cache set failed for %s: %s", key, e)
