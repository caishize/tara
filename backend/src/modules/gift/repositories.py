"""Gift module repositories — trending gifts and recommendation data access.

Merged from:
  - trending_gifts/repositories/trending_gift_repository.py
  - trending_gifts/repositories/occasion_repository.py
  - trending_gifts/repositories/update_log_repository.py
  - gift_recommendation/repositories/conversation_context_repository.py
  - gift_recommendation/repositories/memory_repository.py
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    GiftCategory,
    GiftConversationContext,
    MemberGiftMemory,
    Occasion,
    OccasionGift,
    TrendingGift,
    UpdateLog,
    UpdateStatus,
)
from ...core.utils.timezone import utc_now


# ═══════════════════════════════════════════════════════════════════════════════
# TrendingGiftRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TrendingGiftRepository:
    """Repository for TrendingGift CRUD operations."""

    def __init__(self, session):
        self.session = session

    async def create(self, gift_data: Dict[str, Any]) -> TrendingGift:
        gift = TrendingGift(**gift_data)
        self.session.add(gift)
        await self.session.flush()
        await self.session.refresh(gift)
        return gift

    async def bulk_create(self, gifts_data: List[Dict[str, Any]]) -> List[TrendingGift]:
        gifts = [TrendingGift(**data) for data in gifts_data]
        self.session.add_all(gifts)
        await self.session.flush()
        return gifts

    async def get_by_id(self, gift_id: UUID) -> Optional[TrendingGift]:
        stmt = select(TrendingGift).where(TrendingGift.id == gift_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str, data_source: str) -> Optional[TrendingGift]:
        stmt = select(TrendingGift).where(
            and_(TrendingGift.external_id == external_id, TrendingGift.data_source == data_source)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_category(
        self, category: str, page: int = 1, page_size: int = 20,
        sort_by: str = "popularity", active_only: bool = True
    ) -> tuple:
        conditions = [TrendingGift.category == category]
        if active_only:
            conditions.append(TrendingGift.is_active == True)  # noqa: E712

        count_stmt = select(func.count()).select_from(TrendingGift).where(and_(*conditions))
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(TrendingGift).where(and_(*conditions))
        if sort_by == "popularity":
            stmt = stmt.order_by(desc(TrendingGift.popularity_score), TrendingGift.rank)
        elif sort_by == "price_asc":
            stmt = stmt.order_by(TrendingGift.price)
        elif sort_by == "price_desc":
            stmt = stmt.order_by(desc(TrendingGift.price))
        elif sort_by == "rating":
            stmt = stmt.order_by(desc(TrendingGift.rating))
        elif sort_by == "discount":
            stmt = stmt.order_by(desc(TrendingGift.discount_percent))
        else:
            stmt = stmt.order_by(TrendingGift.rank)

        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def list_all_active(self, page: int = 1, page_size: int = 20, sort_by: str = "popularity") -> tuple:
        conditions = [TrendingGift.is_active == True]  # noqa: E712

        count_stmt = select(func.count()).select_from(TrendingGift).where(and_(*conditions))
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(TrendingGift).where(and_(*conditions))
        if sort_by == "popularity":
            stmt = stmt.order_by(desc(TrendingGift.popularity_score))
        elif sort_by == "price_asc":
            stmt = stmt.order_by(TrendingGift.price)
        elif sort_by == "price_desc":
            stmt = stmt.order_by(desc(TrendingGift.price))
        elif sort_by == "rating":
            stmt = stmt.order_by(desc(TrendingGift.rating))

        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def search(self, query: str, category: Optional[str] = None, page: int = 1, page_size: int = 20) -> tuple:
        conditions = [
            TrendingGift.is_active == True,  # noqa: E712
            or_(TrendingGift.name.ilike(f'%{query}%'), TrendingGift.brand.ilike(f'%{query}%'))
        ]
        if category:
            conditions.append(TrendingGift.category == category)

        count_stmt = select(func.count()).select_from(TrendingGift).where(and_(*conditions))
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(TrendingGift).where(and_(*conditions)).order_by(desc(TrendingGift.popularity_score))
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def upsert(self, gift_data: Dict[str, Any]) -> TrendingGift:
        existing = await self.get_by_external_id(gift_data.get("external_id"), gift_data.get("data_source"))
        if existing:
            for key, value in gift_data.items():
                if key not in ("id", "created_at"):
                    setattr(existing, key, value)
            existing.updated_at = utc_now()
            existing.last_verified_at = utc_now()
            await self.session.flush()
            return existing
        return await self.create(gift_data)

    async def update(self, gift_id: UUID, gift_data: Dict[str, Any]) -> Optional[TrendingGift]:
        gift_data["updated_at"] = utc_now()
        stmt = (
            update(TrendingGift).where(TrendingGift.id == gift_id)
            .values(**gift_data).returning(TrendingGift)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def deactivate_expired(self, days: int = 30) -> int:
        cutoff = utc_now() - timedelta(days=days)
        stmt = (
            update(TrendingGift)
            .where(and_(TrendingGift.is_active == True, TrendingGift.updated_at < cutoff))  # noqa: E712
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def delete_old(self, days: int = 90) -> int:
        cutoff = utc_now() - timedelta(days=days)
        stmt = delete(TrendingGift).where(TrendingGift.created_at < cutoff)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_category_counts(self) -> Dict[str, int]:
        stmt = (
            select(TrendingGift.category, func.count(TrendingGift.id))
            .where(TrendingGift.is_active == True)  # noqa: E712
            .group_by(TrendingGift.category)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_active(self) -> int:
        stmt = select(func.count()).select_from(TrendingGift).where(TrendingGift.is_active == True)  # noqa: E712
        return (await self.session.execute(stmt)).scalar() or 0

    async def count_total(self) -> int:
        stmt = select(func.count()).select_from(TrendingGift)
        return (await self.session.execute(stmt)).scalar() or 0


# ═══════════════════════════════════════════════════════════════════════════════
# OccasionRepository
# ═══════════════════════════════════════════════════════════════════════════════

class OccasionRepository:
    """Repository for Occasion CRUD operations."""

    def __init__(self, session):
        self.session = session

    async def create(self, occasion_data: Dict[str, Any]) -> Occasion:
        occasion = Occasion(**occasion_data)
        self.session.add(occasion)
        await self.session.flush()
        await self.session.refresh(occasion)
        return occasion

    async def get_by_id(self, occasion_id) -> Optional[Occasion]:
        stmt = select(Occasion).where(Occasion.id == occasion_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Occasion]:
        stmt = select(Occasion).where(Occasion.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_active(self) -> List[Occasion]:
        stmt = select(Occasion).where(Occasion.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_gifts_for_occasion(self, occasion_id: UUID, page: int = 1, page_size: int = 10, active_only: bool = True) -> tuple:
        if active_only:
            count_stmt = (
                select(func.count()).select_from(OccasionGift)
                .join(TrendingGift, OccasionGift.gift_id == TrendingGift.id)
                .where(and_(OccasionGift.occasion_id == occasion_id, TrendingGift.is_active == True))  # noqa: E712
            )
        else:
            count_stmt = select(func.count()).select_from(OccasionGift).where(OccasionGift.occasion_id == occasion_id)

        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(TrendingGift).join(OccasionGift, OccasionGift.gift_id == TrendingGift.id)
            .where(OccasionGift.occasion_id == occasion_id)
        )
        if active_only:
            stmt = stmt.where(TrendingGift.is_active == True)  # noqa: E712
        stmt = stmt.order_by(OccasionGift.sort_order, TrendingGift.popularity_score.desc())

        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def add_gift_to_occasion(self, occasion_id: UUID, gift_id: UUID, sort_order: int = 0, match_reason: Optional[str] = None) -> OccasionGift:
        stmt = select(OccasionGift).where(and_(OccasionGift.occasion_id == occasion_id, OccasionGift.gift_id == gift_id))
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.sort_order = sort_order
            if match_reason:
                existing.match_reason = match_reason
            await self.session.flush()
            return existing

        occasion_gift = OccasionGift(occasion_id=occasion_id, gift_id=gift_id, sort_order=sort_order, match_reason=match_reason)
        self.session.add(occasion_gift)
        await self.session.flush()
        return occasion_gift

    async def count_total(self) -> int:
        stmt = select(func.count()).select_from(Occasion)
        return (await self.session.execute(stmt)).scalar() or 0


# ═══════════════════════════════════════════════════════════════════════════════
# UpdateLogRepository
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateLogRepository:
    """Repository for UpdateLog CRUD operations."""

    def __init__(self, session):
        self.session = session

    async def create(self, log_data: Dict[str, Any]) -> UpdateLog:
        log = UpdateLog(**log_data)
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def create_running(self, task_id: Optional[str] = None) -> UpdateLog:
        log = UpdateLog(task_id=task_id, started_at=utc_now(), status=UpdateStatus.RUNNING.value)
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_by_id(self, log_id: UUID) -> Optional[UpdateLog]:
        stmt = select(UpdateLog).where(UpdateLog.id == log_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest(self) -> Optional[UpdateLog]:
        stmt = select(UpdateLog).order_by(desc(UpdateLog.started_at)).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest_successful(self) -> Optional[UpdateLog]:
        stmt = (
            select(UpdateLog).where(UpdateLog.status == UpdateStatus.SUCCESS.value)
            .order_by(desc(UpdateLog.started_at)).limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_recent(self, page: int = 1, page_size: int = 20) -> tuple:
        count_stmt = select(func.count()).select_from(UpdateLog)
        total_count = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = select(UpdateLog).order_by(desc(UpdateLog.started_at))
        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def mark_success(self, log_id: UUID, gifts_added: int = 0, gifts_updated: int = 0, gifts_deleted: int = 0, source_stats: Optional[Dict] = None) -> Optional[UpdateLog]:
        log = await self.get_by_id(log_id)
        if not log:
            return None
        log.mark_success(gifts_added, gifts_updated, gifts_deleted)
        if source_stats:
            log.source_stats = source_stats
        await self.session.flush()
        return log

    async def mark_failed(self, log_id: UUID, error_message: str, source_stats: Optional[Dict] = None) -> Optional[UpdateLog]:
        log = await self.get_by_id(log_id)
        if not log:
            return None
        log.mark_failed(error_message)
        if source_stats:
            log.source_stats = source_stats
        await self.session.flush()
        return log

    async def is_update_running(self) -> bool:
        stmt = select(UpdateLog).where(UpdateLog.status == UpdateStatus.RUNNING.value).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def get_stats(self) -> Dict[str, Any]:
        total_count = (await self.session.execute(select(func.count()).select_from(UpdateLog))).scalar() or 0
        success_count = (await self.session.execute(
            select(func.count()).select_from(UpdateLog).where(UpdateLog.status == UpdateStatus.SUCCESS.value)
        )).scalar() or 0
        failed_count = (await self.session.execute(
            select(func.count()).select_from(UpdateLog).where(UpdateLog.status == UpdateStatus.FAILED.value)
        )).scalar() or 0
        latest = await self.get_latest_successful()
        return {
            "total_updates": total_count,
            "successful_updates": success_count,
            "failed_updates": failed_count,
            "partial_updates": total_count - success_count - failed_count,
            "last_success_at": latest.completed_at.isoformat() if latest and latest.completed_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ConversationContextRepository
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationContextRepository:
    """Repository for GiftConversationContext operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, context: GiftConversationContext) -> GiftConversationContext:
        self.session.add(context)
        await self.session.flush()
        await self.session.refresh(context)
        return context

    async def get_by_id(self, context_id: UUID) -> Optional[GiftConversationContext]:
        result = await self.session.execute(
            select(GiftConversationContext).where(GiftConversationContext.id == context_id)
        )
        return result.scalar_one_or_none()

    async def get_by_member(
        self, member_id: UUID, active_only: bool = True,
        context_types: Optional[List[str]] = None, limit: int = 50,
    ) -> List[GiftConversationContext]:
        query = select(GiftConversationContext).where(GiftConversationContext.member_id == member_id)
        if active_only:
            query = query.where(GiftConversationContext.is_active == True)  # noqa: E712
            query = query.where(
                or_(GiftConversationContext.expires_at.is_(None), GiftConversationContext.expires_at > utc_now())
            )
        if context_types:
            query = query.where(GiftConversationContext.context_type.in_(context_types))
        query = query.order_by(desc(GiftConversationContext.mentioned_at)).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_preferences_for_member(self, member_id: UUID, include_dislikes: bool = True) -> List[GiftConversationContext]:
        types = ["preference", "brand_preference", "category_interest"]
        if include_dislikes:
            types.append("dislike")
        return await self.get_by_member(member_id=member_id, active_only=True, context_types=types)

    async def get_constraints_for_member(self, member_id: UUID) -> List[GiftConversationContext]:
        return await self.get_by_member(member_id=member_id, active_only=True, context_types=["constraint"])

    async def get_history_mentions(self, member_id: UUID) -> List[GiftConversationContext]:
        return await self.get_by_member(member_id=member_id, active_only=True, context_types=["history_mention", "feedback"])

    async def get_recent_mentions(self, family_id: UUID, days: int = 30, limit: int = 20) -> List[GiftConversationContext]:
        cutoff = utc_now() - timedelta(days=days)
        query = (
            select(GiftConversationContext)
            .where(and_(
                GiftConversationContext.family_id == family_id,
                GiftConversationContext.is_active == True,  # noqa: E712
                GiftConversationContext.mentioned_at > cutoff
            ))
            .order_by(desc(GiftConversationContext.mentioned_at)).limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def deactivate(self, context_id: UUID) -> bool:
        context = await self.get_by_id(context_id)
        if context:
            context.is_active = False
            await self.session.flush()
            return True
        return False

    async def deactivate_old_contexts(self, member_id: UUID, older_than_days: int = 365) -> int:
        cutoff = utc_now() - timedelta(days=older_than_days)
        query = select(GiftConversationContext).where(and_(
            GiftConversationContext.member_id == member_id,
            GiftConversationContext.is_active == True,  # noqa: E712
            GiftConversationContext.mentioned_at < cutoff
        ))
        result = await self.session.execute(query)
        count = 0
        for ctx in result.scalars().all():
            ctx.is_active = False
            count += 1
        await self.session.flush()
        return count

    async def search_by_text(self, family_id: UUID, search_text: str, limit: int = 10) -> List[GiftConversationContext]:
        query = (
            select(GiftConversationContext)
            .where(and_(
                GiftConversationContext.family_id == family_id,
                GiftConversationContext.is_active == True,  # noqa: E712
                or_(
                    GiftConversationContext.raw_text.ilike(f"%{search_text}%"),
                    GiftConversationContext.extracted_value.ilike(f"%{search_text}%")
                )
            ))
            .order_by(desc(GiftConversationContext.confidence)).limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_confidence(self, context_id: UUID, new_confidence: float) -> bool:
        context = await self.get_by_id(context_id)
        if context:
            context.confidence = max(0.0, min(1.0, new_confidence))
            await self.session.flush()
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryRepository
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryRepository:
    """Repository for MemberGiftMemory operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, memory: MemberGiftMemory) -> MemberGiftMemory:
        self.session.add(memory)
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def get_by_id(self, memory_id: UUID) -> Optional[MemberGiftMemory]:
        result = await self.session.execute(
            select(MemberGiftMemory).where(MemberGiftMemory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def get_by_member(self, member_id: UUID) -> Optional[MemberGiftMemory]:
        result = await self.session.execute(
            select(MemberGiftMemory).where(MemberGiftMemory.member_id == member_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, member_id: UUID, family_id: UUID) -> MemberGiftMemory:
        memory = await self.get_by_member(member_id)
        if memory:
            return memory
        memory = MemberGiftMemory(
            member_id=member_id, family_id=family_id,
            total_gifts_received=0, gifts_last_year=0, gifts_last_3_years=0,
            total_recommendations=0, accepted_recommendations=0, memory_richness_score=0.0,
        )
        self.session.add(memory)
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def get_by_family(self, family_id: UUID, min_richness: Optional[float] = None) -> List[MemberGiftMemory]:
        query = select(MemberGiftMemory).where(MemberGiftMemory.family_id == family_id)
        if min_richness is not None:
            query = query.where(MemberGiftMemory.memory_richness_score >= min_richness)
        query = query.order_by(desc(MemberGiftMemory.memory_richness_score))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, memory: MemberGiftMemory) -> MemberGiftMemory:
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def update_gift_stats(
        self, member_id: UUID, total_gifts: int, gifts_last_year: int,
        gifts_last_3_years: int, recent_gifts: list, category_counts: dict,
        last_gift_date: Optional[datetime] = None
    ) -> Optional[MemberGiftMemory]:
        memory = await self.get_by_member(member_id)
        if not memory:
            return None
        memory.total_gifts_received = total_gifts
        memory.gifts_last_year = gifts_last_year
        memory.gifts_last_3_years = gifts_last_3_years
        memory.recent_gifts = recent_gifts
        memory.category_counts = category_counts
        if last_gift_date:
            memory.last_gift_date = last_gift_date
        memory.memory_richness_score = memory.calculate_richness_score()
        await self.session.flush()
        return memory

    async def update_preferences(
        self, member_id: UUID, liked_categories: List[str],
        disliked_categories: List[str], preference_scores: dict,
        brand_preferences: Optional[dict] = None
    ) -> Optional[MemberGiftMemory]:
        memory = await self.get_by_member(member_id)
        if not memory:
            return None
        memory.liked_categories = liked_categories
        memory.disliked_categories = disliked_categories
        memory.preference_scores = preference_scores
        if brand_preferences:
            memory.brand_preferences = brand_preferences
        memory.memory_richness_score = memory.calculate_richness_score()
        await self.session.flush()
        return memory

    async def add_gift_to_avoid(
        self, member_id: UUID, gift_name: str, category: str,
        reason: str, until: Optional[datetime] = None
    ) -> Optional[MemberGiftMemory]:
        memory = await self.get_by_member(member_id)
        if not memory:
            return None
        avoid_entry = {
            "name": gift_name, "category": category, "reason": reason,
            "until": until.isoformat() if until else None, "added_at": utc_now().isoformat()
        }
        if not memory.gifts_to_avoid:
            memory.gifts_to_avoid = []
        memory.gifts_to_avoid.append(avoid_entry)
        await self.session.flush()
        return memory

    async def get_members_needing_update(self, family_id: UUID, days_since_update: int = 30) -> List[MemberGiftMemory]:
        cutoff = utc_now() - timedelta(days=days_since_update)
        query = (
            select(MemberGiftMemory)
            .where(and_(MemberGiftMemory.family_id == family_id, MemberGiftMemory.updated_at < cutoff))
            .order_by(MemberGiftMemory.updated_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
