"""Gift preference learning service.

Learns and maintains per-member gift category preferences from feedback
and purchase history. Publishes PreferenceUpdated domain events.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .models import FeedbackRating, GiftPreference
from .recommendation_repositories import HistoryRepository, PreferenceRepository
from ...core.events import get_event_bus, PreferenceUpdated
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

FEEDBACK_SCORE_DELTA = {
    FeedbackRating.LOVE_IT.value: 0.3,
    FeedbackRating.LIKE_IT.value: 0.15,
    FeedbackRating.NEUTRAL.value: 0.0,
    FeedbackRating.DISLIKE.value: -0.2,
    FeedbackRating.HATE_IT.value: -0.4,
    "love_it": 0.3, "like_it": 0.15, "neutral": 0.0, "dislike": -0.2, "hate_it": -0.4,
}

CONFIDENCE_INCREMENT = 0.1
MIN_PREFERENCE_SCORE = -1.0
MAX_PREFERENCE_SCORE = 1.0
ANNUAL_DECAY_RATE = 0.1


@dataclass
class PreferenceSummary:
    member_id: UUID
    total_preferences: int
    positive_categories: List[str]
    negative_categories: List[str]
    neutral_categories: List[str]
    high_confidence_count: int
    last_updated: Optional[datetime] = None


class PreferenceLearningService:
    """Learn user gift preferences from feedback."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.preference_repo = PreferenceRepository(session)
        self.history_repo = HistoryRepository(session)
        self.event_bus = get_event_bus()

    async def update_from_feedback(
        self,
        member_id: UUID,
        family_id: UUID,
        gift_category: str,
        feedback_rating: str,
        history_id: Optional[UUID] = None,
    ) -> GiftPreference:
        delta = FEEDBACK_SCORE_DELTA.get(feedback_rating, 0.0)
        pref = await self.preference_repo.get_by_member_category(member_id, gift_category)
        old_score = 0.0

        if pref is None:
            pref = await self.preference_repo.create({
                "member_id": member_id, "family_id": family_id,
                "gift_category": gift_category,
                "preference_score": max(MIN_PREFERENCE_SCORE, min(MAX_PREFERENCE_SCORE, delta)),
                "confidence": CONFIDENCE_INCREMENT, "source": "feedback", "feedback_count": 1,
            })
        else:
            old_score = pref.preference_score
            new_score = max(MIN_PREFERENCE_SCORE, min(MAX_PREFERENCE_SCORE, pref.preference_score + delta))
            new_confidence = min(1.0, pref.confidence + CONFIDENCE_INCREMENT)
            pref = await self.preference_repo.update(pref.id, {
                "preference_score": new_score,
                "confidence": new_confidence,
                "source": "feedback",
                "feedback_count": (pref.feedback_count or 0) + 1,
                "updated_at": utc_now(),
            })

        await self.event_bus.publish(PreferenceUpdated(
            preference_id=pref.id, family_id=family_id, member_id=member_id,
            gift_category=gift_category, old_score=old_score,
            new_score=pref.preference_score, confidence=pref.confidence, source="feedback",
        ))
        return pref

    async def decay_old_preferences(self, days_threshold: int = 730) -> int:
        threshold_date = utc_now() - timedelta(days=days_threshold)
        old_prefs = await self.preference_repo.get_stale_preferences(threshold_date)
        count = 0
        for pref in old_prefs:
            days_old = (utc_now() - pref.updated_at).days
            years_old = days_old / 365
            decay_factor = max(0.1, 1.0 - (years_old * ANNUAL_DECAY_RATE))
            await self.preference_repo.update(pref.id, {"confidence": pref.confidence * decay_factor})
            count += 1
        if count > 0:
            logger.info("Decayed confidence for %d old preferences", count)
        return count

    async def get_preference_summary(self, member_id: UUID) -> PreferenceSummary:
        preferences = await self.preference_repo.get_all_by_member(member_id)
        positive, negative, neutral = [], [], []
        high_conf = 0
        last_updated = None
        for pref in preferences:
            if pref.preference_score > 0.3:
                positive.append(pref.gift_category)
            elif pref.preference_score < -0.3:
                negative.append(pref.gift_category)
            else:
                neutral.append(pref.gift_category)
            if pref.confidence > 0.7:
                high_conf += 1
            if last_updated is None or pref.updated_at > last_updated:
                last_updated = pref.updated_at
        return PreferenceSummary(
            member_id=member_id, total_preferences=len(preferences),
            positive_categories=positive, negative_categories=negative,
            neutral_categories=neutral, high_confidence_count=high_conf,
            last_updated=last_updated,
        )

    async def infer_from_history(self, member_id: UUID, family_id: UUID) -> int:
        history = await self.history_repo.get_by_recipient(member_id, years_back=3)
        category_counts: Dict[str, int] = {}
        for h in history:
            category_counts[h.gift_category] = category_counts.get(h.gift_category, 0) + 1
        inferred = 0
        for category, count in category_counts.items():
            existing = await self.preference_repo.get_by_member_category(member_id, category)
            if existing is None and count >= 2:
                score = min(0.3, count * 0.1)
                await self.preference_repo.create({
                    "member_id": member_id, "family_id": family_id,
                    "gift_category": category, "preference_score": score,
                    "confidence": 0.3, "source": "inferred", "feedback_count": 0,
                })
                inferred += 1
        return inferred
