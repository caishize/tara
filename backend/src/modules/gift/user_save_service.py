"""User gift save service — favorited / saved trending gifts.

Allows users to save, unsave, and list their favorite trending gifts
with pagination and save-status enrichment.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import TrendingGift, UserGiftSave

logger = logging.getLogger(__name__)


class UserGiftSaveService:
    """Service for user gift save (favorites) operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_gift(
        self, user_id: UUID, gift_id: UUID, note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save a gift for a user. Returns saved gift info."""
        gift = await self._get_trending_gift(gift_id)
        if not gift:
            raise ValueError(f"Gift {gift_id} not found")

        existing = await self._get_by_user_and_gift(user_id, gift_id)
        if existing:
            if note is not None:
                existing.note = note
                await self.session.flush()
            save = existing
        else:
            save = UserGiftSave(user_id=user_id, gift_id=gift_id, note=note)
            self.session.add(save)
            await self.session.flush()
            await self.session.refresh(save)

        return {
            "id": str(save.id),
            "gift": gift.to_dict(),
            "saved_at": save.saved_at.isoformat() if save.saved_at else None,
            "note": save.note,
        }

    async def unsave_gift(self, user_id: UUID, gift_id: UUID) -> bool:
        """Remove a gift from user's saves."""
        save = await self._get_by_user_and_gift(user_id, gift_id)
        if save:
            await self.session.delete(save)
            await self.session.flush()
            return True
        return False

    async def get_user_saved_gifts(
        self, user_id: UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get user's saved gifts with pagination."""
        count_stmt = (
            select(func.count())
            .select_from(UserGiftSave)
            .join(TrendingGift, UserGiftSave.gift_id == TrendingGift.id)
            .where(
                and_(UserGiftSave.user_id == user_id, TrendingGift.is_active.is_(True))
            )
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(UserGiftSave)
            .join(TrendingGift, UserGiftSave.gift_id == TrendingGift.id)
            .options(selectinload(UserGiftSave.gift))
            .where(
                and_(UserGiftSave.user_id == user_id, TrendingGift.is_active.is_(True))
            )
            .order_by(desc(UserGiftSave.saved_at))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        saves = list((await self.session.execute(stmt)).scalars().all())

        result = []
        for save in saves:
            gift = save.gift or await self._get_trending_gift(save.gift_id)
            result.append({
                "id": str(save.id),
                "gift": gift.to_dict() if gift else None,
                "saved_at": save.saved_at.isoformat() if save.saved_at else None,
                "note": save.note,
            })
        return result, total

    async def is_gift_saved(self, user_id: UUID, gift_id: UUID) -> bool:
        """Check if a gift is saved by a user."""
        return (await self._get_by_user_and_gift(user_id, gift_id)) is not None

    async def get_saved_gift_ids(self, user_id: UUID) -> List[str]:
        """Get list of saved gift IDs for a user."""
        stmt = select(UserGiftSave.gift_id).where(UserGiftSave.user_id == user_id)
        result = await self.session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    async def enrich_gifts_with_save_status(
        self, gifts: List[Dict[str, Any]], user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Add is_saved field to a list of gifts for a user."""
        if not user_id:
            return gifts
        stmt = select(UserGiftSave.gift_id).where(UserGiftSave.user_id == user_id)
        saved_ids = {row[0] for row in (await self.session.execute(stmt)).all()}

        for gift in gifts:
            gid = UUID(gift["id"]) if isinstance(gift["id"], str) else gift["id"]
            gift["is_saved"] = gid in saved_ids
        return gifts

    # -- private helpers -------------------------------------------------------

    async def _get_trending_gift(self, gift_id: UUID) -> Optional[TrendingGift]:
        stmt = select(TrendingGift).where(TrendingGift.id == gift_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _get_by_user_and_gift(
        self, user_id: UUID, gift_id: UUID
    ) -> Optional[UserGiftSave]:
        stmt = select(UserGiftSave).where(
            and_(UserGiftSave.user_id == user_id, UserGiftSave.gift_id == gift_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
