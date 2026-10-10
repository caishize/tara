"""Concrete ProfileEnrichment service.

Enriches person profiles from conversation-extracted data
and supports find-or-create for auto-extraction.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import IProfileEnrichment, PersonProfile
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class ProfileEnrichment(IProfileEnrichment):
    """Auto-enrich person profiles from conversations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enrich_from_conversation(
        self, family_id: str, person_id: str,
        extracted_data: Dict[str, Any],
    ) -> None:
        from .models import PersonProfile as PPModel

        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.id == UUID(person_id),
                    PPModel.family_id == UUID(family_id),
                )
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            logger.warning(
                "Person profile %s not found for enrichment", person_id,
            )
            return

        if "aliases" in extracted_data:
            for alias in extracted_data["aliases"]:
                profile.add_alias(alias)

        if "relationship" in extracted_data and not profile.relationship:
            profile.relationship = extracted_data["relationship"]

        if "relationship_context" in extracted_data:
            profile.relationship_context = extracted_data["relationship_context"]

        if "organization" in extracted_data and not profile.organization:
            profile.organization = extracted_data["organization"]

        if "location" in extracted_data and not profile.location:
            profile.location = extracted_data["location"]

        if "preferences" in extracted_data:
            profile.update_preferences(extracted_data["preferences"])

        if "importance" in extracted_data:
            new_imp = extracted_data["importance"]
            if isinstance(new_imp, (int, float)) and new_imp > (profile.importance or 0):
                profile.importance = int(new_imp)

        profile.record_mention()
        await self.session.flush()

        logger.debug(
            "Enriched profile %s with %d fields",
            person_id,
            len(extracted_data),
        )

    async def find_or_create_profile(
        self, family_id: str, name: str,
        user_id: str,
        hints: Optional[Dict[str, Any]] = None,
    ) -> PersonProfile:
        """Find existing profile by name/alias or create a new one.

        Search order:
        1. Exact name match within the family
        2. Alias match within the family
        3. Create new profile
        """
        from .models import PersonProfile as PPModel, ProfileStatus
        from .person_service import PersonService

        fid = UUID(family_id)
        hints = hints or {}

        # 1. Exact name match
        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == fid,
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    PPModel.name == name,
                )
            ).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.record_mention()
            await self.session.flush()
            return PersonService._to_dto(existing)

        # 2. Alias match — uses ANY on the aliases array
        result = await self.session.execute(
            select(PPModel).where(
                and_(
                    PPModel.family_id == fid,
                    PPModel.status == ProfileStatus.ACTIVE.value,
                    PPModel.aliases.any(name),
                )
            ).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.record_mention()
            await self.session.flush()
            return PersonService._to_dto(existing)

        # 3. Create new profile
        profile = PPModel(
            family_id=fid,
            user_id=UUID(user_id),
            name=name,
            importance=hints.get("importance", 3),
            relationship=hints.get("relationship"),
            organization=hints.get("organization"),
            location=hints.get("location"),
        )
        profile.record_mention()
        self.session.add(profile)
        await self.session.flush()

        logger.info(
            "Auto-created person profile '%s' in family %s",
            name,
            family_id,
        )
        return PersonService._to_dto(profile)
