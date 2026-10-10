"""Repository for FamilyPreference CRUD and JSONB merge operations."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FamilyPreference
from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

# JSONB fields that support merge-style updates
_MERGEABLE_FIELDS = frozenset({
    "priority_weights",
    "event_type_severity",
    "buffer_minutes",
    "recommendation_weights",
    "association_weights",
    "density_preferences",
    "annotation_preferences",
})


class FamilyPreferenceRepository:
    """Data-access layer for the family_preferences table."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_family_id(self, family_id: UUID) -> Optional[FamilyPreference]:
        """Return the preference row for *family_id*, or ``None``."""
        query = select(FamilyPreference).where(
            FamilyPreference.family_id == family_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_default(self, family_id: UUID) -> FamilyPreference:
        """Return existing preferences or create a blank row with server defaults."""
        pref = await self.get_by_family_id(family_id)
        if pref is not None:
            return pref

        pref = FamilyPreference(family_id=family_id)
        self.db.add(pref)
        await self.db.flush()
        await self.db.refresh(pref)
        logger.info("Created default FamilyPreference for family %s", family_id)
        return pref

    async def update_weights(
        self, family_id: UUID, field: str, updates: dict,
    ) -> FamilyPreference:
        """Merge *updates* into one of the JSONB weight columns.

        The merge is shallow: top-level keys in *updates* overwrite existing
        keys while leaving untouched keys intact.

        Raises ``ValueError`` if *field* is not a recognised mergeable column.
        """
        if field not in _MERGEABLE_FIELDS:
            raise ValueError(
                f"Field '{field}' is not a mergeable JSONB column. "
                f"Allowed: {sorted(_MERGEABLE_FIELDS)}"
            )

        pref = await self.get_or_create_default(family_id)
        current: dict = getattr(pref, field) or {}
        merged = {**current, **updates}
        setattr(pref, field, merged)
        pref.updated_at = utc_now()
        await self.db.flush()
        await self.db.refresh(pref)
        logger.info(
            "Updated FamilyPreference.%s for family %s (keys: %s)",
            field, family_id, sorted(updates.keys()),
        )
        return pref

    async def add_suppressed_type(self, family_id: UUID, type_name: str) -> None:
        """Append *type_name* to the suppressed_types list (idempotent)."""
        pref = await self.get_or_create_default(family_id)
        current: list = list(pref.suppressed_types or [])
        if type_name not in current:
            updated = [*current, type_name]
            pref.suppressed_types = updated
            pref.updated_at = utc_now()
            await self.db.flush()
            logger.info(
                "Suppressed type '%s' for family %s", type_name, family_id,
            )

    async def remove_suppressed_type(self, family_id: UUID, type_name: str) -> None:
        """Remove *type_name* from the suppressed_types list (idempotent)."""
        pref = await self.get_by_family_id(family_id)
        if pref is None:
            return
        current: list = list(pref.suppressed_types or [])
        if type_name in current:
            updated = [t for t in current if t != type_name]
            pref.suppressed_types = updated
            pref.updated_at = utc_now()
            await self.db.flush()
            logger.info(
                "Unsuppressed type '%s' for family %s", type_name, family_id,
            )
