"""
Insight Settings Repository - Data access layer for user insight settings
"""

from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from .insight_settings_model import UserInsightSettings
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)


class InsightSettingsRepository:
    """Repository for user insight settings"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Optional[UserInsightSettings]:
        """
        Get insight settings for a specific user.

        Args:
            user_id: The user ID

        Returns:
            UserInsightSettings if found, None otherwise
        """
        query = select(UserInsightSettings).where(
            UserInsightSettings.user_id == user_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_defaults(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get user settings or return defaults if not configured.

        Args:
            user_id: The user ID

        Returns:
            Dictionary with all settings (user's or defaults)
        """
        settings = await self.get_by_user_id(user_id)
        if settings:
            return settings.to_dict()

        # Return defaults if no settings exist
        defaults = UserInsightSettings.get_defaults()
        defaults["user_id"] = str(user_id)
        defaults["is_default"] = True
        return defaults

    async def upsert(
        self,
        user_id: UUID,
        family_id: UUID,
        data: Dict[str, int],
    ) -> UserInsightSettings:
        """
        Create or update insight settings for a user.

        Args:
            user_id: The user ID
            family_id: The family ID
            data: Dictionary of settings to update

        Returns:
            The created or updated settings
        """
        # Validate and clamp all values
        validated_data = {}
        for field, value in data.items():
            if field in UserInsightSettings.RANGES:
                validated_data[field] = UserInsightSettings.clamp_value(field, value)
            elif field in ("auto_curate_on_trip_create", "auto_curate_on_event_change"):
                # Boolean field - no clamping needed
                validated_data[field] = bool(value)

        # Try to get existing settings
        settings = await self.get_by_user_id(user_id)

        if settings:
            # Update existing settings
            for field, value in validated_data.items():
                setattr(settings, field, value)
            settings.updated_at = utc_now()
        else:
            # Create new settings with defaults for unspecified fields
            all_fields = {**UserInsightSettings.DEFAULTS, **validated_data}
            settings = UserInsightSettings(
                user_id=user_id,
                family_id=family_id,
                **all_fields,
            )
            self.db.add(settings)

        await self.db.commit()
        await self.db.refresh(settings)

        logger.info(f"Upserted insight settings for user {user_id}")
        return settings

    async def delete(self, user_id: UUID) -> bool:
        """
        Delete insight settings for a user (resets to defaults).

        Args:
            user_id: The user ID

        Returns:
            True if deleted, False if not found
        """
        settings = await self.get_by_user_id(user_id)
        if settings:
            await self.db.delete(settings)
            await self.db.commit()
            logger.info(f"Deleted insight settings for user {user_id}")
            return True
        return False

    async def get_effective_settings(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get the effective settings for insight generation.

        This method returns just the settings values, suitable for
        direct use in the proactive insight service and curation service.

        Args:
            user_id: The user ID

        Returns:
            Dictionary with setting names and their values
        """
        settings = await self.get_by_user_id(user_id)
        if settings:
            return {
                "emotion_pattern_window_days": settings.emotion_pattern_window_days,
                "relationship_reminder_threshold_days": settings.relationship_reminder_threshold_days,
                "insight_expiry_days": settings.insight_expiry_days,
                "old_plan_followup_threshold_days": settings.old_plan_followup_threshold_days,
                "upcoming_trip_check_days": settings.upcoming_trip_check_days,
                "curation_schedule_hour": settings.curation_schedule_hour,
                "curation_days_ahead": settings.curation_days_ahead,
                "auto_curate_on_trip_create": settings.auto_curate_on_trip_create,
                "curation_interval_minutes": settings.curation_interval_minutes,
                "auto_curate_on_event_change": settings.auto_curate_on_event_change,
            }
        return UserInsightSettings.get_defaults()
