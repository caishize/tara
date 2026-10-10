"""
DashboardService - Gift dashboard service.

Provides aggregated data for the gift recommendation dashboard.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from ...core.utils.timezone import local_today, utc_now
from .models import (
    GiftTask,
    TaskStatus,
    GiftRecommendation,
    GiftHistory,
    RecommendStatus,
)
from .task_service import GiftTaskRepository
from .recommendation_service import RecommendationRepository, HistoryRepository
from ..member.repositories.member_repository import MemberRepository

logger = logging.getLogger(__name__)


class DashboardService:
    """Gift dashboard service."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = GiftTaskRepository(session)
        self.recommendation_repo = RecommendationRepository(session)
        self.history_repo = HistoryRepository(session)
        self.member_repo = MemberRepository(session)

    async def get_dashboard(self, family_id: UUID) -> Dict[str, Any]:
        """
        Get complete gift dashboard data.

        Args:
            family_id: Family ID

        Returns:
            Dashboard data
        """
        upcoming_tasks = await self._get_upcoming_tasks(family_id)
        pending_recommendations = await self._get_pending_recommendations(family_id)
        recent_history = await self._get_recent_history(family_id)
        stats = await self._get_stats(family_id)

        return {
            "upcoming_tasks": upcoming_tasks,
            "pending_recommendations": pending_recommendations,
            "recent_history": recent_history,
            "stats": stats,
            "generated_at": utc_now().isoformat()
        }

    async def _get_upcoming_tasks(
        self,
        family_id: UUID,
        days: int = 60
    ) -> List[Dict[str, Any]]:
        """Get upcoming tasks."""
        tasks = await self.task_repo.get_upcoming_tasks(family_id, days)

        result = []
        for task in tasks:
            member = await self.member_repo.get_by_id(task.member_id)
            member_name = member.name if member else "Unknown"

            days_until = (task.occasion_date - local_today()).days

            result.append({
                "id": str(task.id),
                "member_id": str(task.member_id),
                "member_name": member_name,
                "occasion": task.occasion,
                "occasion_title": task.occasion_title,
                "occasion_date": task.occasion_date.isoformat(),
                "days_until": days_until,
                "status": task.status,
                "has_recommendation": task.recommendation_id is not None,
                "recommendation_id": str(task.recommendation_id) if task.recommendation_id else None,
                "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else None,
                "urgency": self._calculate_urgency(days_until)
            })

        result.sort(key=lambda x: x["days_until"])
        return result

    def _calculate_urgency(self, days_until: int) -> str:
        """Calculate urgency level."""
        if days_until < 0:
            return "overdue"
        elif days_until <= 3:
            return "critical"
        elif days_until <= 7:
            return "high"
        elif days_until <= 14:
            return "medium"
        else:
            return "low"

    async def _get_pending_recommendations(
        self,
        family_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get pending recommendations."""
        result = await self.session.execute(
            select(GiftRecommendation)
            .where(
                and_(
                    GiftRecommendation.family_id == family_id,
                    GiftRecommendation.status.in_([
                        RecommendStatus.PENDING.value,
                        RecommendStatus.VIEWED.value
                    ])
                )
            )
            .order_by(GiftRecommendation.created_at.desc())
            .limit(limit)
        )
        recommendations = list(result.scalars().all())

        pending = []
        for rec in recommendations:
            member = await self.member_repo.get_by_id(rec.recipient_member_id)
            member_name = member.name if member else "Unknown"

            expires_in_days = None
            if rec.expires_at:
                expires_in_days = (rec.expires_at.date() - local_today()).days

            pending.append({
                "id": str(rec.id),
                "member_id": str(rec.recipient_member_id),
                "member_name": member_name,
                "occasion": rec.occasion,
                "occasion_date": rec.occasion_date.isoformat() if rec.occasion_date else None,
                "status": rec.status,
                "options_count": len(rec.recommendations or []),
                "recommendations": rec.recommendations,
                "dedup_warnings": rec.dedup_warnings,
                "created_at": rec.created_at.isoformat(),
                "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
                "expires_in_days": expires_in_days,
                "budget_min": float(rec.budget_min) if rec.budget_min else None,
                "budget_max": float(rec.budget_max) if rec.budget_max else None
            })

        return pending

    async def _get_recent_history(
        self,
        family_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent gift history."""
        result = await self.session.execute(
            select(GiftHistory)
            .where(GiftHistory.family_id == family_id)
            .order_by(GiftHistory.occasion_date.desc())
            .limit(limit)
        )
        history_list = list(result.scalars().all())

        recent = []
        for h in history_list:
            member = await self.member_repo.get_by_id(h.recipient_member_id)
            member_name = member.name if member else "Unknown"

            recent.append({
                "id": str(h.id),
                "member_id": str(h.recipient_member_id),
                "member_name": member_name,
                "gift_name": h.gift_name,
                "gift_category": h.gift_category,
                "occasion": h.occasion,
                "occasion_date": h.occasion_date.isoformat(),
                "feedback_rating": h.feedback_rating,
                "feedback_text": h.feedback_text,
                "has_feedback": h.feedback_rating is not None,
                "image_url": h.image_url,
                "created_at": h.created_at.isoformat()
            })

        return recent

    async def _get_stats(self, family_id: UUID) -> Dict[str, Any]:
        """Get statistics."""
        today = local_today()
        year_start = date(today.year, 1, 1)

        # Gifts this year
        result = await self.session.execute(
            select(func.count(GiftHistory.id))
            .where(
                and_(
                    GiftHistory.family_id == family_id,
                    GiftHistory.occasion_date >= year_start
                )
            )
        )
        total_gifts_this_year = result.scalar() or 0

        total_spent = 0  # TODO: decrypt and calculate

        # Most gifted member
        result = await self.session.execute(
            select(
                GiftHistory.recipient_member_id,
                func.count(GiftHistory.id).label('count')
            )
            .where(
                and_(
                    GiftHistory.family_id == family_id,
                    GiftHistory.occasion_date >= year_start
                )
            )
            .group_by(GiftHistory.recipient_member_id)
            .order_by(func.count(GiftHistory.id).desc())
            .limit(1)
        )
        top_recipient = result.first()

        most_gifted_member = None
        if top_recipient:
            member = await self.member_repo.get_by_id(top_recipient[0])
            if member:
                most_gifted_member = {
                    "id": str(member.id),
                    "name": member.name,
                    "gift_count": top_recipient[1]
                }

        # Most used category
        result = await self.session.execute(
            select(
                GiftHistory.gift_category,
                func.count(GiftHistory.id).label('count')
            )
            .where(
                and_(
                    GiftHistory.family_id == family_id,
                    GiftHistory.occasion_date >= year_start
                )
            )
            .group_by(GiftHistory.gift_category)
            .order_by(func.count(GiftHistory.id).desc())
            .limit(1)
        )
        top_category = result.first()
        favorite_category = top_category[0] if top_category else None

        # Pending task count
        task_stats = await self.task_repo.get_stats(family_id)

        # Recommendation adoption rate
        year_start_dt = datetime(year_start.year, 1, 1)
        result = await self.session.execute(
            select(
                func.count(GiftRecommendation.id).filter(
                    GiftRecommendation.status.in_([
                        RecommendStatus.SELECTED.value,
                        RecommendStatus.PURCHASED.value
                    ])
                ).label('adopted'),
                func.count(GiftRecommendation.id).label('total')
            )
            .where(
                and_(
                    GiftRecommendation.family_id == family_id,
                    GiftRecommendation.created_at >= year_start_dt
                )
            )
        )
        adoption_result = result.first()
        adoption_rate = 0.0
        if adoption_result and adoption_result[1] > 0:
            adoption_rate = adoption_result[0] / adoption_result[1]

        return {
            "total_gifts_this_year": total_gifts_this_year,
            "total_spent": total_spent,
            "most_gifted_member": most_gifted_member,
            "favorite_category": favorite_category,
            "pending_tasks": task_stats.get("pending", 0),
            "completed_tasks": task_stats.get("completed", 0),
            "adoption_rate": round(adoption_rate, 2),
            "year": today.year
        }

    async def get_member_gift_summary(
        self,
        family_id: UUID,
        member_id: UUID
    ) -> Dict[str, Any]:
        """
        Get gift summary for a member.

        Args:
            family_id: Family ID
            member_id: Member ID

        Returns:
            Member gift summary
        """
        member = await self.member_repo.get_by_id(member_id)
        if not member:
            return {"error": "Member not found"}

        history = await self.history_repo.get_by_recipient(member_id, years_back=5)

        yearly_stats: Dict[int, int] = {}
        category_stats: Dict[str, int] = {}
        occasion_stats: Dict[str, int] = {}

        for h in history:
            year = h.occasion_date.year
            yearly_stats[year] = yearly_stats.get(year, 0) + 1
            category_stats[h.gift_category] = category_stats.get(h.gift_category, 0) + 1
            occasion_stats[h.occasion] = occasion_stats.get(h.occasion, 0) + 1

        tasks = await self.task_repo.get_by_member(
            member_id=member_id,
            family_id=family_id,
            status=TaskStatus.PENDING
        )

        return {
            "member": {
                "id": str(member.id),
                "name": member.name,
                "gender": member.gender,
                "age": member.age
            },
            "total_gifts": len(history),
            "yearly_stats": yearly_stats,
            "category_stats": category_stats,
            "occasion_stats": occasion_stats,
            "recent_gifts": [
                {
                    "gift_name": h.gift_name,
                    "category": h.gift_category,
                    "occasion": h.occasion,
                    "date": h.occasion_date.isoformat(),
                    "feedback": h.feedback_rating
                }
                for h in history[:5]
            ],
            "pending_tasks": len(tasks),
            "upcoming_occasions": [
                {
                    "occasion": t.occasion,
                    "date": t.occasion_date.isoformat(),
                    "days_until": (t.occasion_date - local_today()).days
                }
                for t in tasks
            ]
        }
