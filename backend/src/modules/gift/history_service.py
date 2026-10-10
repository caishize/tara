"""
Gift history service.
"""
from typing import List, Dict, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from .recommendation_service import HistoryRepository, PreferenceRepository
from .models import OccasionType, FeedbackRating
from ...core.auth.encryption_service import EncryptionService


class HistoryService:
    """Service for managing gift history and feedback."""

    def __init__(
        self,
        db: AsyncSession,
        encryption_service: EncryptionService
    ):
        self.db = db
        self.history_repo = HistoryRepository(db)
        self.preference_repo = PreferenceRepository(db)
        self.encryption = encryption_service

    async def record_gift(
        self,
        family_id: UUID,
        giver_user_id: UUID,
        recipient_member_id: UUID,
        gift_name: str,
        gift_category: str,
        occasion: str,
        occasion_date: date,
        gift_price: Optional[float] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """Record a gift in history."""
        # Encrypt price if provided
        encrypted_price = None
        if gift_price is not None:
            encrypted_price = await self.encryption.encrypt(str(gift_price), family_id)

        history_data = {
            "family_id": family_id,
            "giver_user_id": giver_user_id,
            "recipient_member_id": recipient_member_id,
            "gift_name": gift_name,
            "gift_category": gift_category,
            "occasion": occasion,
            "occasion_date": occasion_date,
            "gift_price": encrypted_price,
            "notes": notes,
            "source": kwargs.get("source", "manual"),
            **{k: v for k, v in kwargs.items() if k not in ["source"]}
        }

        history = await self.history_repo.create(history_data)
        return await self._to_dict(history, family_id)

    async def add_feedback(
        self,
        history_id: UUID,
        family_id: UUID,
        feedback_rating: str,
        feedback_text: Optional[str] = None
    ) -> Optional[Dict]:
        """Add feedback to a gift history record and update preferences."""
        history = await self.history_repo.update_feedback(history_id, feedback_rating, feedback_text)
        if not history:
            return None

        # Update preference learning
        await self.preference_repo.update_from_feedback(
            history.recipient_member_id,
            family_id,
            history.gift_category,
            feedback_rating
        )

        return await self._to_dict(history, family_id)

    async def get_history(self, history_id: UUID, family_id: UUID) -> Optional[Dict]:
        """Get gift history by ID."""
        history = await self.history_repo.get_by_id(history_id)
        if not history:
            return None
        return await self._to_dict(history, family_id)

    async def list_history(
        self,
        family_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """List gift history for a family."""
        histories = await self.history_repo.get_by_family(family_id, limit, offset)
        return [await self._to_dict(h, family_id) for h in histories]

    async def get_recipient_history(
        self,
        recipient_member_id: UUID,
        family_id: UUID,
        years_back: int = 3
    ) -> List[Dict]:
        """Get gift history for a specific recipient."""
        histories = await self.history_repo.get_by_recipient(recipient_member_id, years_back)
        return [await self._to_dict(h, family_id) for h in histories]

    async def _to_dict(self, history, family_id: UUID) -> Dict:
        """Convert history entity to dict with frontend-compatible field names."""
        # Decrypt price if present
        decrypted_price = None
        if history.gift_price:
            try:
                decrypted_price = float(await self.encryption.decrypt(history.gift_price, family_id))
            except Exception:
                decrypted_price = None

        return {
            "id": str(history.id),
            "family_id": str(history.family_id),
            "giver_user_id": str(history.giver_user_id),
            "member_id": str(history.recipient_member_id),  # Frontend expects member_id
            "gift_name": history.gift_name,
            "category": history.gift_category,  # Frontend expects category (not gift_category)
            "occasion": history.occasion,
            "date_given": history.occasion_date.isoformat(),  # Frontend expects date_given
            "price": decrypted_price,  # Frontend expects price (not gift_price)
            "purchase_url": history.purchase_link,  # Frontend expects purchase_url
            "image_url": history.image_url,
            "recipient_feedback": history.feedback_rating,  # Frontend expects recipient_feedback
            "satisfaction_score": None,  # Not stored in DB yet
            "notes": history.notes,
            "created_at": history.created_at.isoformat(),
            "updated_at": history.updated_at.isoformat()
        }
