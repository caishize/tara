"""
ProfessionalRelationService - Business logic for professional relationship management.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .repositories.professional_relation_repository import ProfessionalRelationRepository
from .repositories.member_repository import MemberRepository
from .models import ProfessionalRelationType
from ...core.auth.permission_service import permission_service
from ...core.interfaces.permission import Operation
from ...config.logging import get_logger


logger = get_logger(__name__)


class ProfessionalRelationService:
    """Professional relationship management business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.prof_rel_repo = ProfessionalRelationRepository(session)
        self.member_repo = MemberRepository(session)

    async def create_professional_relation(
        self,
        from_member_id: UUID,
        to_member_id: UUID,
        relation_type: str,
        requester_id: UUID,
        company_name: Optional[str] = None,
        is_current: bool = True,
        notes: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new professional relation.

        Args:
            from_member_id: "Me" member UUID
            to_member_id: Other member UUID
            relation_type: Type of professional relation
            requester_id: User creating the relation
            company_name: Optional company where relation exists
            is_current: Whether the relation is current
            notes: Optional notes
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Created professional relation data
        """
        # Get both members to verify access
        from_member = await self.member_repo.get_by_id(from_member_id)
        to_member = await self.member_repo.get_by_id(to_member_id)

        if not from_member or not to_member:
            raise ValueError("One or both members not found")

        if from_member.family_id != to_member.family_id:
            raise ValueError("Members must be from the same family")

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            from_member.family_id,
            "member_management",
            Operation.EDIT_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to create professional relations")

        # Parse relation type
        try:
            rel_type = ProfessionalRelationType(relation_type)
        except ValueError:
            rel_type = ProfessionalRelationType.OTHER

        # Prepare data
        relation_data = {
            'family_id': from_member.family_id,
            'from_member_id': from_member_id,
            'to_member_id': to_member_id,
            'relation_type': rel_type,
            'company_name': company_name,
            'is_current': is_current,
            'notes': notes,
        }

        # Parse dates
        if start_date:
            from datetime import datetime
            relation_data['start_date'] = datetime.fromisoformat(start_date).date()
        if end_date:
            from datetime import datetime
            relation_data['end_date'] = datetime.fromisoformat(end_date).date()

        # Create relation
        relation = await self.prof_rel_repo.create(relation_data)

        logger.info(f"Professional relation created: {relation.id}")

        return self._to_dict(relation)

    async def get_professional_relation(
        self,
        relation_id: UUID,
        requester_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get professional relation by ID."""
        relation = await self.prof_rel_repo.get_by_id(relation_id)
        if not relation:
            return None

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            relation.family_id,
            "member_management",
            Operation.VIEW_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to view professional relations")

        return self._to_dict(relation)

    async def list_professional_relations(
        self,
        member_id: UUID,
        requester_id: UUID,
        direction: str = 'both',
        include_past: bool = True
    ) -> List[Dict[str, Any]]:
        """List all professional relations for a member."""
        # Get member to verify access
        member = await self.member_repo.get_by_id(member_id)
        if not member:
            raise ValueError("Member not found")

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            member.family_id,
            "member_management",
            Operation.VIEW_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to view professional relations")

        relations = await self.prof_rel_repo.list_by_member(member_id, direction, include_past)

        return [self._to_dict(rel) for rel in relations]

    async def update_professional_relation(
        self,
        relation_id: UUID,
        updates: Dict[str, Any],
        requester_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Update professional relation."""
        relation = await self.prof_rel_repo.get_by_id(relation_id)
        if not relation:
            return None

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            relation.family_id,
            "member_management",
            Operation.EDIT_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to edit professional relations")

        # Parse relation type if provided
        if 'relation_type' in updates and isinstance(updates['relation_type'], str):
            try:
                updates['relation_type'] = ProfessionalRelationType(updates['relation_type'])
            except ValueError:
                updates['relation_type'] = ProfessionalRelationType.OTHER

        # Parse dates if provided
        if 'start_date' in updates and updates['start_date']:
            from datetime import datetime
            updates['start_date'] = datetime.fromisoformat(updates['start_date']).date()
        if 'end_date' in updates and updates['end_date']:
            from datetime import datetime
            updates['end_date'] = datetime.fromisoformat(updates['end_date']).date()

        # Update relation
        updated = await self.prof_rel_repo.update(relation_id, updates)

        logger.info(f"Professional relation updated: {relation_id}")

        return self._to_dict(updated) if updated else None

    async def delete_professional_relation(
        self,
        relation_id: UUID,
        requester_id: UUID
    ) -> bool:
        """Delete professional relation."""
        relation = await self.prof_rel_repo.get_by_id(relation_id)
        if not relation:
            return False

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            relation.family_id,
            "member_management",
            Operation.EDIT_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to delete professional relations")

        result = await self.prof_rel_repo.delete(relation_id)

        logger.info(f"Professional relation deleted: {relation_id}")

        return result

    async def get_relation_types(self) -> List[Dict[str, str]]:
        """Get all professional relation types with display names."""
        return [
            {'value': ProfessionalRelationType.BOSS.value, 'label': '上级'},
            {'value': ProfessionalRelationType.SUBORDINATE.value, 'label': '下属'},
            {'value': ProfessionalRelationType.PEER.value, 'label': '同事'},
            {'value': ProfessionalRelationType.MENTOR.value, 'label': '导师'},
            {'value': ProfessionalRelationType.MENTEE.value, 'label': '学员'},
            {'value': ProfessionalRelationType.CLIENT.value, 'label': '客户'},
            {'value': ProfessionalRelationType.VENDOR.value, 'label': '供应商'},
            {'value': ProfessionalRelationType.PARTNER.value, 'label': '合作伙伴'},
            {'value': ProfessionalRelationType.OTHER.value, 'label': '其他'},
        ]

    def _to_dict(self, relation) -> Dict[str, Any]:
        """Convert ProfessionalRelation model to dict."""
        # Get display label for relation type
        label_map = {
            ProfessionalRelationType.BOSS: '上级',
            ProfessionalRelationType.SUBORDINATE: '下属',
            ProfessionalRelationType.PEER: '同事',
            ProfessionalRelationType.MENTOR: '导师',
            ProfessionalRelationType.MENTEE: '学员',
            ProfessionalRelationType.CLIENT: '客户',
            ProfessionalRelationType.VENDOR: '供应商',
            ProfessionalRelationType.PARTNER: '合作伙伴',
            ProfessionalRelationType.OTHER: '其他',
        }

        data = {
            'id': str(relation.id),
            'family_id': str(relation.family_id),
            'from_member_id': str(relation.from_member_id),
            'to_member_id': str(relation.to_member_id),
            'relation_type': relation.relation_type.value,
            'relation_type_label': label_map.get(relation.relation_type, '其他'),
            'company_name': relation.company_name,
            'start_date': relation.start_date.isoformat() if relation.start_date else None,
            'end_date': relation.end_date.isoformat() if relation.end_date else None,
            'is_current': relation.is_current,
            'notes': relation.notes,
            'created_at': relation.created_at.isoformat(),
            'updated_at': relation.updated_at.isoformat(),
        }

        # Include member info if loaded
        if relation.from_member:
            data['from_member_name'] = relation.from_member.name
        if relation.to_member:
            data['to_member_name'] = relation.to_member.name

        return data
