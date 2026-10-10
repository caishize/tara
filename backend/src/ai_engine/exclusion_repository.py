"""Repository for exclusion rule persistence.

Provides CRUD operations for ExclusionRule, allowing the ExclusionFilter
to query persisted rules from the database.
"""

from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.audit.service import AuditService
from ..core.utils.timezone import utc_now
from ..modules.curation.models import ExclusionRule


class ExclusionRepository:
    """Database operations for exclusion rules."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._audit = AuditService(db)

    async def create(
        self,
        user_id: UUID,
        family_id: UUID,
        entity_type: str,
        entity_id: str,
        reason: Optional[str] = None,
        cooldown_until=None,
    ) -> ExclusionRule:
        """Create a new exclusion rule."""
        rule = ExclusionRule(
            user_id=user_id,
            family_id=family_id,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            cooldown_until=cooldown_until,
        )
        self._db.add(rule)
        await self._db.flush()
        await self._audit.log_event(
            user_id=user_id,
            family_id=family_id,
            event_type="exclusion_created",
            event_data={
                "rule_id": str(rule.id),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "reason": reason,
            },
        )
        return rule

    async def get_active_entity_ids(
        self,
        user_id: UUID,
        family_id: UUID,
        entity_type: Optional[str] = None,
    ) -> Set[str]:
        """Fetch all active (non-expired) excluded entity ID strings.

        This is the main query used by ExclusionFilter.apply() to build
        the dismissed_entity_ids set.
        """
        now = utc_now()
        stmt = select(ExclusionRule.entity_id).where(
            ExclusionRule.user_id == user_id,
            ExclusionRule.family_id == family_id,
            ExclusionRule.status == "active",
        )
        if entity_type is not None:
            stmt = stmt.where(ExclusionRule.entity_type == entity_type)

        # Active = no cooldown, or cooldown still in the future
        stmt = stmt.where(
            (ExclusionRule.cooldown_until.is_(None))
            | (ExclusionRule.cooldown_until > now)
        )

        result = await self._db.execute(stmt)
        return {row[0] for row in result.all()}

    async def list_for_user(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> List[ExclusionRule]:
        """List all exclusion rules for a user (active and expired)."""
        result = await self._db.execute(
            select(ExclusionRule).where(
                ExclusionRule.user_id == user_id,
                ExclusionRule.family_id == family_id,
            ).order_by(ExclusionRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def record_override(self, rule_id: UUID) -> Optional[ExclusionRule]:
        """Increment override_count for a rule. Returns the rule or None if not found."""
        result = await self._db.execute(
            select(ExclusionRule).where(ExclusionRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            return None
        rule.override_count = (rule.override_count or 0) + 1
        await self._db.flush()
        return rule

    async def deactivate(self, rule_id: UUID) -> Optional[ExclusionRule]:
        """Set a rule's status to 'inactive'. Returns the rule or None if not found."""
        result = await self._db.execute(
            select(ExclusionRule).where(ExclusionRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            return None
        rule.status = "inactive"
        await self._db.flush()
        if rule.user_id and rule.family_id:
            await self._audit.log_event(
                user_id=rule.user_id,
                family_id=rule.family_id,
                event_type="exclusion_deactivated",
                event_data={
                    "rule_id": str(rule_id),
                    "entity_type": rule.entity_type,
                    "entity_id": rule.entity_id,
                },
            )
        return rule

    async def delete_rule(self, rule_id: UUID) -> bool:
        """Delete a single exclusion rule. Returns True if found and deleted."""
        rule = await self._db.execute(
            select(ExclusionRule).where(ExclusionRule.id == rule_id)
        )
        existing = rule.scalar_one_or_none()
        if existing:
            await self._audit.log_event(
                user_id=existing.user_id,
                family_id=existing.family_id,
                event_type="exclusion_deleted",
                event_data={
                    "rule_id": str(rule_id),
                    "entity_type": existing.entity_type,
                    "entity_id": existing.entity_id,
                },
            )
        result = await self._db.execute(
            delete(ExclusionRule).where(ExclusionRule.id == rule_id)
        )
        await self._db.flush()
        return result.rowcount > 0

    async def delete_for_entity(
        self,
        user_id: UUID,
        family_id: UUID,
        entity_id: str,
    ) -> int:
        """Delete all exclusion rules for a specific entity. Returns count deleted."""
        await self._audit.log_event(
            user_id=user_id,
            family_id=family_id,
            event_type="exclusion_deleted",
            event_data={
                "entity_id": entity_id,
                "bulk": True,
            },
        )
        result = await self._db.execute(
            delete(ExclusionRule).where(
                ExclusionRule.user_id == user_id,
                ExclusionRule.family_id == family_id,
                ExclusionRule.entity_id == entity_id,
            )
        )
        await self._db.flush()
        return result.rowcount
