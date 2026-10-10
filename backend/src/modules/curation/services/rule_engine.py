"""
Rule-Based Association Engine for curation.

Provides rule-based association discovery as a complement to LLM-based discovery.
"""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.settings import settings
from ....core.utils.timezone import utc_now
from ..models import CuratedEvent, EventAssociation, SocialIntent
from .family_context import FamilyRelationContext
from .query_utils import escape_like
from ...member.models import Member, PersonProfile, ProfileStatus
from ...date_manager.models import ImportantDate

logger = logging.getLogger(__name__)


def _extract_target_date(target: Any) -> Optional[Any]:
    """Extract the date from a target, preferring solar_date over date."""
    d = getattr(target, "solar_date", None)
    if d is not None:
        return d
    return getattr(target, "date", None)


class RuleBasedAssociationEngine:
    """
    Rule-based association discovery engine.

    Discovers associations using deterministic rules:
    1. Location-based person matching
    2. Date-based important date matching
    3. Social intent matching
    4. Stale contact detection
    """

    def __init__(
        self,
        session: AsyncSession,
        family_ctx: Optional[FamilyRelationContext] = None,
    ):
        self.session = session
        self._family_ctx = family_ctx

    async def discover_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
        context: Dict[str, Any] = None,
    ) -> List[EventAssociation]:
        """Discover associations using rule-based matching."""
        associations = []

        if event.location or event.city:
            location_associations = await self._find_location_based_associations(
                family_id, event
            )
            associations.extend(location_associations)

        if event.normalized_start:
            date_associations = await self._find_date_based_associations(
                family_id, event
            )
            associations.extend(date_associations)

        intent_associations = await self._find_social_intent_associations(
            family_id, event
        )
        associations.extend(intent_associations)

        # Stale contact detection — not just for trips, also for any event
        # that creates an opportunity to reach out (holiday, anniversary, etc.)
        stale_event_types = [
            "business_trip", "travel", "holiday", "birthday", "anniversary",
        ]
        if event.event_type in stale_event_types:
            stale_associations = await self._find_stale_contact_associations(
                family_id, event
            )
            associations.extend(stale_associations)

        return associations

    async def _batch_get_temperature_statuses(
        self, user_id: Optional[UUID], member_ids: List[UUID],
    ) -> Dict[UUID, Optional[str]]:
        """Batch compute temperature statuses for multiple members in parallel."""
        if not member_ids:
            return {}
        if user_id is None:
            return {mid: None for mid in member_ids}
        sem = asyncio.Semaphore(10)

        async def _limited(mid: UUID):
            async with sem:
                return await self._get_member_temperature_status(user_id, mid)

        tasks = [_limited(mid) for mid in member_ids]
        statuses = await asyncio.gather(*tasks, return_exceptions=True)
        result: Dict[UUID, Optional[str]] = {}
        for mid, status in zip(member_ids, statuses):
            if isinstance(status, Exception):
                logger.debug(
                    "temperature fetch failed for member %s: %s", mid, status,
                )
                result[mid] = None
            else:
                result[mid] = status
        return result

    async def _find_location_based_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
    ) -> List[EventAssociation]:
        """Find members whose location matches the event location."""
        associations = []
        location = event.location or event.city

        if not location:
            return associations

        query = select(Member).where(
            and_(
                Member.family_id == family_id,
                Member.locations.isnot(None),
            )
        )

        result = await self.session.execute(query)
        members = result.scalars().all()

        # Filter candidate members first (exclude the user themselves)
        user_id = event.user_id
        candidate_members = []
        for member in members:
            if user_id is not None and member.id == user_id:
                continue
            member_loc = member.primary_location
            if not member_loc or location.lower() not in member_loc.lower():
                continue
            candidate_members.append(member)

        if not candidate_members:
            return associations

        # Batch fetch temperature statuses for all candidates
        candidate_ids = [m.id for m in candidate_members]
        temp_statuses = await self._batch_get_temperature_statuses(
            event.user_id, candidate_ids
        )

        for member in candidate_members:
            member_loc = member.primary_location
            confidence = self._calculate_location_confidence(
                location, member_loc
            )

            association = EventAssociation(
                id=uuid4(),
                family_id=family_id,
                source_event_id=event.id,
                target_id=str(member.id),
                target_type="person",
                association_type="location",
                title=None,
                reason=None,
                priority="convenient",
                confidence=confidence,
            )

            association.priority = self.classify_association_priority(
                association, event, member
            )

            # Thermometer bonus: cold/frozen relationships get priority boost
            temp_status = temp_statuses.get(member.id)
            if temp_status in ("cold", "frozen"):
                association.priority = "strongly_recommend"
                association.confidence = min(1.0, (association.confidence or 0.5) + 0.2)

            associations.append(association)

        return associations

    @staticmethod
    def _skip_association_date_types() -> set[str]:
        """Date types that are too minor to create trip associations for."""
        return {
            str(event_type).strip().lower()
            for event_type in (settings.curation_low_importance_event_types or [])
            if str(event_type).strip()
        }

    @staticmethod
    def _is_same_important_date_source(event: CuratedEvent, imp_date: ImportantDate) -> bool:
        """Avoid creating a preparation association for the event's own source date."""
        source_ids = {
            str(source_id)
            for source_id in (event.original_event_ids or [])
            if source_id is not None
        }
        return bool(source_ids) and str(imp_date.id) in source_ids

    async def _find_date_based_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
    ) -> List[EventAssociation]:
        """Find important dates near the event date.

        E7 enhancement: uses per-date ``preparation_lead_days`` instead of
        a fixed 7-day window.  The broad query uses the maximum possible
        lead (60 days), then each date is filtered by its specific lead.
        """
        associations = []
        event_date = event.normalized_start.date()

        # E7: Use maximum possible lead days for the broad query,
        # then filter per-date below.  Must cover wedding=90d (the largest
        # value in date_service._DEFAULT_LEAD_DAYS).
        max_lead_days = 90
        start_range = event_date - timedelta(days=7)  # Keep backward window at 7
        end_range = event_date + timedelta(days=max_lead_days)

        query = select(ImportantDate).where(
            and_(
                ImportantDate.family_id == family_id,
                ImportantDate.solar_date >= start_range,
                ImportantDate.solar_date <= end_range,
            )
        )

        result = await self.session.execute(query)
        important_dates = result.scalars().all()

        for imp_date in important_dates:
            if self._is_same_important_date_source(event, imp_date):
                continue

            # Skip low-importance dates (e.g. solar terms) from trip associations
            imp_date_type = str(getattr(imp_date, "date_type", "") or "").strip().lower()
            if imp_date_type in self._skip_association_date_types():
                continue

            # E7: Use per-date preparation lead days
            lead_days = getattr(imp_date, "preparation_lead_days", None) or 7
            # days_diff > 0 means the important date is after the event
            days_diff = (imp_date.solar_date - event_date).days

            # Skip if important date is too far in the past (>7 days ago)
            # or beyond this date's specific preparation window
            if days_diff < -7 or days_diff > lead_days:
                continue

            # E7: Adjust confidence based on proximity relative to lead days
            abs_diff = abs(days_diff)
            if days_diff <= 0:
                # Event is on or after the important date (preparation time passed)
                confidence = 0.9 if abs_diff <= 3 else 0.75
            else:
                # Event is before the important date (within preparation window)
                proximity_ratio = days_diff / max(lead_days, 1)
                if proximity_ratio <= 0.2:  # Very close
                    confidence = 0.95
                elif proximity_ratio <= 0.5:  # Within half the lead time
                    confidence = 0.85
                else:  # Early warning
                    confidence = 0.70

            association = EventAssociation(
                id=uuid4(),
                family_id=family_id,
                source_event_id=event.id,
                target_id=str(imp_date.id),
                target_type="date",
                association_type="temporal",
                title=None,
                reason=None,
                priority="convenient",
                confidence=confidence,
            )

            association.priority = self.classify_association_priority(
                association, event, imp_date
            )

            # PLAN-005: Intimate member's date -> priority boost + confidence boost
            if self._family_ctx is not None and imp_date.member_id is not None:
                if self._family_ctx.is_intimate(imp_date.member_id):
                    association.priority = "strongly_recommend"
                    association.confidence = min(
                        1.0, (association.confidence or 0.5) + 0.15,
                    )

            associations.append(association)

        return associations

    async def _find_social_intent_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
    ) -> List[EventAssociation]:
        """Find social intents triggered by this event."""
        associations = []

        query = select(SocialIntent).where(
            and_(
                SocialIntent.family_id == family_id,
                SocialIntent.status == "active",
            )
        )

        if event.location or event.city:
            location = event.location or event.city
            query = query.where(
                SocialIntent.trigger_location.ilike(f"%{escape_like(location)}%", escape="\\")
            )

        if event.event_type:
            query = query.where(
                or_(
                    SocialIntent.trigger_event_type == event.event_type,
                    SocialIntent.trigger_event_type.is_(None),
                )
            )

        result = await self.session.execute(query)
        intents = result.scalars().all()

        for intent in intents:
            confidence = 0.95

            # PLAN-005: Intimate member intent -> confidence boost (+0.10)
            intent_member_id = getattr(intent, "target_member_id", None)
            if (
                self._family_ctx is not None
                and intent_member_id is not None
                and self._family_ctx.is_intimate(intent_member_id)
            ):
                confidence = min(1.0, confidence + 0.10)

            association = EventAssociation(
                id=uuid4(),
                family_id=family_id,
                source_event_id=event.id,
                target_id=str(intent.id),
                target_type="memory",
                association_type="memory",
                title=None,
                reason=None,
                priority="strongly_recommend",
                confidence=confidence,
            )
            associations.append(association)

        return associations

    async def _find_stale_contact_associations(
        self,
        family_id: UUID,
        event: CuratedEvent,
        days_threshold: Optional[int] = None,
    ) -> List[EventAssociation]:
        """Find stale contacts in destination city using profile freshness signals."""
        associations = []
        location = event.location or event.city

        if not location:
            return associations

        if days_threshold is None:
            days_threshold = max(1, int(settings.curation_stale_contact_days))
        min_importance = max(1, int(settings.curation_stale_contact_min_importance))
        now = utc_now()
        cutoff = now - timedelta(days=days_threshold)
        location_lower = location.lower()

        query = (
            select(PersonProfile, Member)
            .outerjoin(Member, Member.id == PersonProfile.member_id)
            .where(
                and_(
                    PersonProfile.family_id == family_id,
                    PersonProfile.status == ProfileStatus.ACTIVE.value,
                    PersonProfile.importance >= min_importance,
                    or_(
                        PersonProfile.last_mentioned_at.is_(None),
                        PersonProfile.last_mentioned_at < cutoff,
                    ),
                )
            )
        )

        result = await self.session.execute(query)
        profile_rows = result.all()

        # Filter candidates by location match first (exclude the user themselves)
        user_id = event.user_id
        candidate_rows = []
        for profile, member in profile_rows:
            if member is None:
                continue
            if user_id is not None and member.id == user_id:
                continue

            candidate_locations = [profile.location, member.primary_location]
            if not any(
                candidate and location_lower in candidate.lower()
                for candidate in candidate_locations
            ):
                continue

            candidate_rows.append((profile, member))

        if not candidate_rows:
            return associations

        # Batch fetch temperature statuses for all candidates
        candidate_member_ids = [member.id for _, member in candidate_rows]
        temp_statuses = await self._batch_get_temperature_statuses(
            event.user_id, candidate_member_ids
        )

        for profile, member in candidate_rows:
            days_since = None
            if profile.last_mentioned_at is not None:
                days_since = max(0, (now - profile.last_mentioned_at).days)

            if days_since is None:
                confidence = 0.65
            else:
                confidence = 0.85 if days_since >= days_threshold * 2 else 0.75

            association = EventAssociation(
                id=uuid4(),
                family_id=family_id,
                source_event_id=event.id,
                target_id=str(member.id),
                target_type="person",
                association_type="stale_contact",
                title=None,
                reason=None,
                priority="optional",
                confidence=confidence,
            )

            # Thermometer bonus: cold/frozen relationships get priority boost
            temp_status = temp_statuses.get(member.id)
            if temp_status in ("cold", "frozen"):
                association.priority = "strongly_recommend"
                association.confidence = min(1.0, (association.confidence or 0.5) + 0.2)

            associations.append(association)

        return associations

    async def _get_member_temperature_status(
        self,
        user_id: Optional[UUID],
        member_id: UUID,
    ) -> Optional[str]:
        """Get relationship temperature status for a member.

        Returns one of: "warm", "cool", "cold", "frozen", or None on failure.
        """
        if user_id is None:
            return None
        try:
            from ...relationship.thermometer import compute_temperature
            temp = await compute_temperature(user_id, member_id, self.session)
            return temp.status
        except Exception:
            logger.debug(
                "Failed to compute temperature for member %s", member_id,
                exc_info=True,
            )
            return None

    def _calculate_location_confidence(
        self,
        event_location: str,
        member_location: str,
    ) -> float:
        """Calculate confidence score for location match."""
        if not event_location or not member_location:
            return 0.5

        event_loc = event_location.lower().strip()
        member_loc = member_location.lower().strip()

        if event_loc == member_loc:
            return 0.85

        if event_loc in member_loc or member_loc in event_loc:
            return 0.75

        return 0.5

    def calculate_association_confidence(
        self,
        event: CuratedEvent,
        target: Any,
        association_type: str,
    ) -> float:
        """Calculate association confidence score."""
        base_scores = {
            "memory": 0.9,
            "temporal": 0.85,
            "location": 0.8,
            "person": 0.75,
            "task": 0.7,
        }
        base_score = base_scores.get(association_type, 0.5)

        geo_factor = 1.0
        if hasattr(target, "location") and (event.location or event.city):
            event_loc = event.location or event.city
            target_loc = getattr(target, "location", None)
            if target_loc:
                if event_loc.lower() in target_loc.lower():
                    geo_factor = 1.0
                else:
                    geo_factor = 0.7

        time_factor = 1.0
        target_date = _extract_target_date(target)
        if target_date is not None and event.normalized_start:
            days_diff = abs((target_date - event.normalized_start.date()).days)
            if days_diff > 7:
                time_factor = 0.5
            elif days_diff > 3:
                time_factor = 0.7
            else:
                time_factor = 1.0

        importance_factor = 1.0
        if hasattr(target, "importance"):
            importance = getattr(target, "importance", 5)
            importance_factor = 0.8 + (importance / 10) * 0.2

        final_confidence = base_score * geo_factor * time_factor * importance_factor
        return min(final_confidence, 1.0)

    def classify_association_priority(
        self,
        association: EventAssociation,
        event: CuratedEvent,
        target: Any = None,
    ) -> str:
        """Classify association priority.

        PLAN-005: Intimate member associations get minimum "convenient" (never "low"/"optional").
        """
        if association.association_type == "memory":
            return "strongly_recommend"

        if association.association_type == "temporal":
            target_date = _extract_target_date(target) if target else None
            if target_date is not None and event.normalized_start:
                days_diff = abs((target_date - event.normalized_start.date()).days)
                if days_diff <= 3:
                    return "strongly_recommend"
                elif days_diff <= 7:
                    return "convenient"

        if event.event_type in ["business_trip", "travel"]:
            if association.association_type == "location":
                if association.confidence >= 0.8:
                    return "strongly_recommend"

        if association.association_type == "location":
            if association.confidence >= 0.7:
                return "convenient"

        if association.association_type == "task":
            return "convenient"

        base_priority = "optional"

        # PLAN-005: Intimate member associations get minimum "convenient"
        if self._family_ctx is not None:
            target_member_id = self._get_target_member_id(association, target)
            if target_member_id is not None and self._family_ctx.is_intimate(target_member_id):
                if base_priority in ("optional", "low"):
                    base_priority = "convenient"

        return base_priority

    @staticmethod
    def _get_target_member_id(
        association: EventAssociation,
        target: Any = None,
    ) -> Optional[UUID]:
        """Extract the target member UUID from an association or its target object."""
        # Try target object first (ImportantDate.member_id, Member.id)
        if target is not None:
            mid = getattr(target, "member_id", None) or getattr(target, "id", None)
            if mid is not None:
                return mid if isinstance(mid, UUID) else None

        # Try association target_id if target_type is "person"
        if association.target_type == "person" and association.target_id:
            try:
                return UUID(str(association.target_id))
            except (ValueError, AttributeError):
                pass

        return None
