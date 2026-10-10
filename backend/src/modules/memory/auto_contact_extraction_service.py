"""
Auto Contact Extraction Service - Automatically extract and save contacts from conversations.

When users mention people in conversations (e.g., "思远说下次去北京一起约个饭"),
this service automatically:
1. Extracts person entities from memories
2. Checks if the contact already exists
3. Creates new Member records for new contacts
4. Associates the memory with the contact for future recall

This enables features like:
- "下次去北京" → automatically suggest contacts associated with Beijing
- Tracking relationships and favors over time
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ...config.logging import get_logger
from .models import ConversationMemory, MemoryType
from ..member.models.member import Member
from ..member.repositories.member_repository import MemberRepository

logger = get_logger(__name__)


# Configuration for auto-contact extraction
class AutoContactConfig:
    """Configuration for auto-contact extraction."""
    # Minimum confidence to create a contact
    min_confidence: float = 0.7
    # Memory types that may contain contact info
    contact_memory_types: List[str] = [
        MemoryType.RELATIONSHIP.value,
        MemoryType.FAVOR.value,
        MemoryType.PLAN.value,
        MemoryType.SCHEDULE.value,
        MemoryType.WORK.value,
        MemoryType.GENERAL.value,
    ]
    # Maximum contacts to create per extraction
    max_contacts_per_extraction: int = 3
    # Source tag for auto-created contacts
    auto_created_tag: str = "auto_from_conversation"


auto_contact_config = AutoContactConfig()


class AutoContactExtractionService:
    """
    Service for automatically extracting and saving contacts from conversation memories.

    This service hooks into the memory extraction pipeline and creates Member records
    when users mention people in their conversations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_repo = MemberRepository(db)
        self.config = auto_contact_config

    async def extract_contacts_from_memories(
        self,
        user_id: UUID,
        family_id: UUID,
        memories: List[ConversationMemory],
    ) -> List[Tuple[Member, ConversationMemory]]:
        """
        Extract and create contacts from a list of memories.

        Args:
            user_id: The user who mentioned these contacts
            family_id: The family to add contacts to
            memories: List of extracted memories to process

        Returns:
            List of (created_member, source_memory) tuples
        """
        created_contacts = []
        processed_names = set()  # Avoid creating duplicates in same batch

        for memory in memories:
            # Skip if memory type is not relevant
            if memory.memory_type not in self.config.contact_memory_types:
                continue

            # Skip if confidence is too low
            if memory.confidence < self.config.min_confidence:
                continue

            # Extract person names from memory
            person_names = self._extract_person_names(memory)
            if not person_names:
                continue

            for name in person_names:
                # Skip if already processed in this batch
                if name in processed_names:
                    continue
                processed_names.add(name)

                # Check if contact already exists
                existing = await self._find_existing_contact(family_id, name)
                if existing:
                    # Update existing contact with new context
                    await self._update_contact_context(existing, memory)
                    logger.info(f"Updated existing contact '{name}' with new memory context")
                    continue

                # Create new contact
                if len(created_contacts) >= self.config.max_contacts_per_extraction:
                    logger.warning(
                        f"Reached max contacts per extraction ({self.config.max_contacts_per_extraction}), "
                        f"skipping '{name}'"
                    )
                    continue

                new_contact = await self._create_contact_from_memory(
                    user_id=user_id,
                    family_id=family_id,
                    name=name,
                    memory=memory,
                )
                if new_contact:
                    created_contacts.append((new_contact, memory))
                    logger.info(
                        f"Auto-created contact '{name}' from memory: {memory.summary[:50]}..."
                    )

        return created_contacts

    def _extract_person_names(self, memory: ConversationMemory) -> List[str]:
        """Extract person names from memory entities."""
        names = []
        entities = memory.entities or {}

        # From 'persons' array (preferred)
        if persons := entities.get("persons"):
            if isinstance(persons, list):
                names.extend([p.strip() for p in persons if p and p.strip()])

        # From 'person' string (may contain multiple names)
        if person := entities.get("person"):
            # Split by common Chinese separators
            for name in str(person).replace('、', ',').replace('，', ',').split(','):
                name = name.strip()
                if name and name not in names:
                    names.append(name)

        # Filter out generic references
        generic_refs = {'我', '你', '他', '她', '它', '他们', '她们', '大家', '所有人', '某人', '有人'}
        names = [n for n in names if n not in generic_refs and len(n) >= 2]

        return names

    async def _find_existing_contact(
        self,
        family_id: UUID,
        name: str,
    ) -> Optional[Member]:
        """Find existing contact by name or nickname."""
        # Search by exact name or nickname
        members = await self.member_repo.search_by_name(family_id, name, limit=5)

        for member in members:
            # Exact match on name or nickname
            if member.name == name or member.nickname == name:
                return member
            # Partial match - name contains search term
            if name in (member.name or '') or name in (member.nickname or ''):
                return member

        return None

    async def _create_contact_from_memory(
        self,
        user_id: UUID,
        family_id: UUID,
        name: str,
        memory: ConversationMemory,
    ) -> Optional[Member]:
        """Create a new contact from memory context."""
        try:
            entities = memory.entities or {}

            # Build tags from memory context
            tags = [self.config.auto_created_tag]

            # Add location tag if available
            if location := entities.get("location"):
                tags.append(f"location:{location}")

            # Add relationship tag if available
            if relationship := entities.get("relationship"):
                tags.append(f"relationship:{relationship}")

            # Add memory type as context
            tags.append(f"source:{memory.memory_type}")

            # Add the memory summary as a reference
            if memory.summary:
                tags.append(f"context:{memory.summary[:50]}")

            # Build locations dict if we have location info
            locations = {}
            if location := entities.get("location"):
                locations["mentioned"] = {
                    "address": location,
                    "note": f"Mentioned in conversation: {memory.summary[:100]}",
                }

            # Create member data
            member_data = {
                "family_id": family_id,
                "created_by": user_id,
                "name": name,
                "tags": tags,
                "locations": locations if locations else None,
            }

            # Remove None values
            member_data = {k: v for k, v in member_data.items() if v is not None}

            # Create member
            member = await self.member_repo.create(member_data)

            # Create work_history if occupation/workplace info available
            occupation = entities.get("occupation")
            workplace = entities.get("workplace") or entities.get("location")
            if occupation or workplace:
                from ..member.models.professional import WorkHistory
                # Check for existing work history to avoid duplicates
                existing_wh_stmt = select(WorkHistory).where(
                    and_(
                        WorkHistory.member_id == member.id,
                        WorkHistory.is_current == True,
                    )
                )
                existing_wh_result = await self.db.execute(existing_wh_stmt)
                existing_wh = existing_wh_result.scalar_one_or_none()

                if existing_wh:
                    # Update existing entry if new info is richer
                    if workplace and not existing_wh.company_name:
                        existing_wh.company_name = workplace
                    if occupation and not existing_wh.position:
                        existing_wh.position = occupation
                else:
                    wh = WorkHistory(
                        family_id=family_id,
                        member_id=member.id,
                        company_name=workplace,
                        position=occupation,
                        is_current=True,
                    )
                    self.db.add(wh)
                await self.db.flush()

            # Reverse-link: find matching PersonProfile and set member_id
            from ..member.models import PersonProfile, ProfileStatus
            pp_stmt = select(PersonProfile).where(
                and_(
                    PersonProfile.family_id == family_id,
                    PersonProfile.name == name,
                    PersonProfile.status == ProfileStatus.ACTIVE.value,
                    PersonProfile.member_id.is_(None),
                )
            ).limit(1)
            pp_result = await self.db.execute(pp_stmt)
            matched_profile = pp_result.scalar_one_or_none()
            if matched_profile:
                matched_profile.member_id = member.id

            await self.db.commit()

            return member

        except Exception as e:
            logger.error(f"Failed to create contact '{name}' from memory: {e}")
            await self.db.rollback()
            return None

    async def _update_contact_context(
        self,
        member: Member,
        memory: ConversationMemory,
    ) -> None:
        """Update existing contact with new context from memory."""
        try:
            entities = memory.entities or {}
            updates = {}

            # Update tags with new context (append, don't replace)
            current_tags = member.tags or []
            new_tags = list(current_tags)

            # Add new location tag if not present
            if location := entities.get("location"):
                loc_tag = f"location:{location}"
                if loc_tag not in new_tags:
                    new_tags.append(loc_tag)

            # Add new context tag
            if memory.summary:
                context_tag = f"context:{memory.summary[:50]}"
                # Limit context tags to avoid bloat
                context_tags = [t for t in new_tags if t.startswith("context:")]
                if len(context_tags) < 5 and context_tag not in new_tags:
                    new_tags.append(context_tag)

            if new_tags != current_tags:
                updates["tags"] = new_tags

            # Update locations if we have new location info
            if location := entities.get("location"):
                current_locations = member.locations or {}
                loc_key = f"mentioned_{len(current_locations)}"
                if location not in str(current_locations):
                    current_locations[loc_key] = {
                        "address": location,
                        "note": f"Mentioned: {memory.summary[:100]}",
                    }
                    updates["locations"] = current_locations

            # Apply updates if any
            if updates:
                await self.member_repo.update(member.id, updates)
                await self.db.commit()

        except Exception as e:
            logger.warning(f"Failed to update contact context: {e}")
            await self.db.rollback()

    async def get_contacts_by_location(
        self,
        family_id: UUID,
        location: str,
    ) -> List[Member]:
        """
        Get contacts associated with a specific location.

        This is useful for trip planning - when user says "去北京",
        we can suggest contacts who are associated with Beijing.
        """
        from ..member.models.professional import WorkHistory

        # Subquery: members with matching company_name in work_histories
        wh_subquery = (
            select(WorkHistory.member_id)
            .where(WorkHistory.company_name.ilike(f"%{location}%"))
            .correlate(Member)
        )

        # Search for members with location in tags, work_histories, or locations field
        stmt = select(Member).where(
            and_(
                Member.family_id == family_id,
                Member.is_deleted == False,
                or_(
                    # Location in tags (e.g., "location:北京")
                    Member.tags.contains([f"location:{location}"]),
                    # Location in work_histories company_name
                    Member.id.in_(wh_subquery),
                    # Location in locations JSONB
                    Member.locations.cast(str).ilike(f"%{location}%"),
                )
            )
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def suggest_contacts_for_trip(
        self,
        family_id: UUID,
        destination: str,
    ) -> List[Dict[str, Any]]:
        """
        Suggest contacts for a trip destination.

        Returns contact info with context about why they're suggested.
        """
        contacts = await self.get_contacts_by_location(family_id, destination)

        suggestions = []
        for contact in contacts:
            # Extract context from tags
            context_tags = [t for t in (contact.tags or []) if t.startswith("context:")]
            relationship_tags = [t for t in (contact.tags or []) if t.startswith("relationship:")]

            suggestion = {
                "id": str(contact.id),
                "name": contact.name,
                "nickname": contact.nickname,
                "relationship": (
                    relationship_tags[0].replace("relationship:", "")
                    if relationship_tags
                    else None
                ),
                "context": (
                    context_tags[0].replace("context:", "")
                    if context_tags
                    else None
                ),
                "reason": f"You mentioned {contact.name} in relation to {destination}",
            }
            suggestions.append(suggestion)

        return suggestions
