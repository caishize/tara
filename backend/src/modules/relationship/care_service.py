"""Concrete CareService for relationship health and suggestions."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import ICareService, CareSuggestion, RelationshipHealth
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class CareService(ICareService):
    """Care suggestions and relationship health scoring."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_health_overview(
        self, family_id: str,
    ) -> Dict[str, Any]:
        from ..member.models import PersonProfile as PPModel, ProfileStatus

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    PPModel.importance >= 3,
                )
            )
        )
        profiles = result.scalars().all()

        total = len(profiles)
        neglected = sum(1 for p in profiles if p.needs_contact_reminder())
        owes = sum(1 for p in profiles if p.owes_favor())
        owed = sum(1 for p in profiles if p.is_owed_favor())

        if total > 0:
            health_score = max(0.0, 1.0 - (neglected / total) * 0.5)
        else:
            health_score = 1.0

        return {
            "total_contacts": total,
            "neglected_count": neglected,
            "owes_favor_count": owes,
            "owed_favor_count": owed,
            "health_score": round(health_score, 2),
        }

    async def get_contact_health(
        self, family_id: str,
    ) -> List[RelationshipHealth]:
        from ..member.models import PersonProfile as PPModel, ProfileStatus

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    PPModel.importance >= 3,
                )
            ).order_by(PPModel.importance.desc())
        )
        profiles = result.scalars().all()

        contacts = []
        for p in profiles:
            days = p.days_since_last_contact()
            score = self._compute_health_score(p, days)
            suggestion = self._generate_suggestion(p, days)

            contacts.append(RelationshipHealth(
                person_id=str(p.id),
                person_name=p.name,
                favor_balance=p.favor_balance or 0.0,
                last_interaction_days=days,
                health_score=round(score, 2),
                suggestion=suggestion,
            ))

        # Sort by health score ascending (worst first)
        contacts.sort(key=lambda c: c.health_score)
        return contacts

    async def get_suggestions(
        self, family_id: str, limit: int = 5,
    ) -> List[CareSuggestion]:
        from ..member.models import PersonProfile as PPModel, ProfileStatus

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == UUID(family_id),
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    PPModel.importance >= 5,
                )
            ).order_by(PPModel.last_mentioned_at.asc().nullslast())
        )
        profiles = result.scalars().all()

        suggestions = []
        for p in profiles:
            if len(suggestions) >= limit:
                break

            days = p.days_since_last_contact()

            # Contact reminder (90+ days)
            if days is not None and days >= 90:
                urgency = min(1.0, days / 365)
                suggestions.append(CareSuggestion(
                    person_id=str(p.id),
                    person_name=p.name,
                    suggestion_type="contact_reminder",
                    content=f"已经{days}天没有联系{p.name}了，可以问候一下",
                    urgency=urgency,
                ))
            # Favor reciprocation
            elif p.owes_favor():
                suggestions.append(CareSuggestion(
                    person_id=str(p.id),
                    person_name=p.name,
                    suggestion_type="reciprocate_favor",
                    content=f"{p.name}之前帮了忙，考虑回个礼或请吃饭",
                    urgency=0.7,
                ))
            # Birthday coming up (check via member module if linked)
            elif p.is_owed_favor() and days is not None and days >= 60:
                suggestions.append(CareSuggestion(
                    person_id=str(p.id),
                    person_name=p.name,
                    suggestion_type="maintain_connection",
                    content=f"有段时间没联系{p.name}了，关系需要维护",
                    urgency=0.5,
                ))

        return suggestions

    @staticmethod
    def _compute_health_score(profile: Any, days: Optional[int] = None) -> float:
        """Compute 0-1 health score for a relationship.

        Factors:
        - Recency of contact (higher = worse)
        - Favor balance (imbalanced = worse)
        - Importance (amplifies problems)
        """
        score = 1.0

        # Recency penalty
        if days is not None:
            if days > 180:
                score -= 0.5
            elif days > 90:
                score -= 0.3
            elif days > 30:
                score -= 0.1

        # Favor imbalance penalty
        balance = abs(profile.favor_balance or 0.0)
        if balance > 3.0:
            score -= 0.3
        elif balance > 1.5:
            score -= 0.15

        return max(0.0, min(1.0, score))

    @staticmethod
    def _generate_suggestion(profile: Any, days: Optional[int] = None) -> Optional[str]:
        """Generate a single suggestion string for a contact."""
        if profile.owes_favor():
            return f"欠了人情，考虑回礼"
        if days is not None and days >= 90:
            return f"已{days}天未联系"
        if profile.is_owed_favor():
            return None
        return None
