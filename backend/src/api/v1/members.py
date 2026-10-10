"""
Member management API endpoints.

Includes:
- Family & member CRUD
- Extended profiles (sizes/health/preferences)
- Work history & professional relations

People endpoints live in people.py.
User stats, smart services, and feedback live in user_services.py.
Schemas live in member_schemas.py.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family
from ...modules.member.member_service import MemberService
from ...modules.member.work_history_service import WorkHistoryService
from ...modules.member.professional_relation_service import ProfessionalRelationService
from ...modules.member.repositories.relation_repository import RelationRepository
from ...modules.member.models.enums import RelationType, ProfessionalRelationType
from .member_schemas import (
    CreateMemberRequest,
    MemberResponse,
    MemberDetailResponse,
    CreateWorkHistoryRequest,
    WorkHistoryResponse,
    CreateProfessionalRelationRequest,
    ProfessionalRelationResponse,
    ProfessionalRelationTypeResponse,
    MemberProfileExtResponse,
    MemberProfileExtRequest,
    PersonProfileResponse,
)


router = APIRouter(prefix="/members", tags=["Members"])


# ==================== Insight Schema ====================


class MemberInsightResponse(BaseModel):
    """Unified insight response for a specific member."""
    id: str
    source: str
    insight_type: str
    title: str
    content: str
    priority: Optional[int] = None
    importance: Optional[int] = None
    urgency: Optional[str] = None
    status: str
    created_at: str
    action_data: Optional[dict] = None
    suggested_action: Optional[str] = None
    action_options: Optional[list] = None


# ==================== Member Stats ====================


class MemberStatsResponse(BaseModel):
    total: int
    by_relation: dict


# ==================== Feature Tiers ====================


class FeatureTierResponse(BaseModel):
    unlocked: bool
    features: List[str]
    unlock_conditions: dict


class FeatureTiersResponse(BaseModel):
    tiers: dict
    available_features: List[str]
    days_active: int
    family_member_count: int


@router.get("/features", response_model=FeatureTiersResponse)
async def get_features(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get progressive feature tiers and available features for the current user."""
    from sqlalchemy import func as sa_func
    from ...modules.member.models.user import User as UserModel
    from ...modules.member.models.member import Member
    from ...modules.member.trust_service import get_feature_tiers, get_available_features
    from ...core.utils.timezone import utc_now

    # Get user registration date for days_active
    user_result = await db.execute(
        select(UserModel.created_at).where(UserModel.id == user_id)
    )
    user_created_at = user_result.scalar_one_or_none()
    if user_created_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    now = utc_now()
    if user_created_at.tzinfo is None:
        from datetime import timezone as dt_tz
        user_created_at = user_created_at.replace(tzinfo=dt_tz.utc)
    days_active = max((now - user_created_at).days, 0)

    # Count family members (excluding self)
    count_result = await db.execute(
        select(sa_func.count())
        .select_from(Member)
        .where(
            Member.family_id == family_id,
            Member.is_deleted.is_(False),
        )
    )
    family_member_count = count_result.scalar() or 0

    # TODO: manual overrides could come from user settings / family settings
    manual_overrides = None

    tiers = get_feature_tiers(days_active, family_member_count, manual_overrides)
    features = get_available_features(days_active, family_member_count, manual_overrides)

    return FeatureTiersResponse(
        tiers=tiers,
        available_features=features,
        days_active=days_active,
        family_member_count=family_member_count,
    )


# ==================== Member Stats ====================


@router.get("/stats", response_model=MemberStatsResponse)
async def get_member_stats(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get member statistics broken down by relation type."""
    from sqlalchemy import func as sa_func
    from ...modules.member.models.member import Member, MemberRelation

    # Total active members in this family (excluding self)
    total_stmt = (
        select(sa_func.count())
        .select_from(Member)
        .where(
            Member.family_id == family_id,
            Member.is_deleted.is_(False),
            Member.id != user_id,
        )
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # Count by relation type (relations from current user to other members)
    rel_stmt = (
        select(
            MemberRelation.relation_type,
            sa_func.count().label("count"),
        )
        .where(
            MemberRelation.family_id == family_id,
            MemberRelation.from_member_id == user_id,
        )
        .group_by(MemberRelation.relation_type)
    )
    rel_result = await db.execute(rel_stmt)
    by_relation = {}
    for row in rel_result.all():
        key = row.relation_type.value if hasattr(row.relation_type, 'value') else str(row.relation_type)
        by_relation[key] = row.count

    return MemberStatsResponse(total=total, by_relation=by_relation)


def _member_orm_to_detail(
    member_obj,
    relation_value: str = "other",
    person_profile=None,
    current_work: dict = None,
) -> dict:
    """Convert Member ORM object to MemberDetailResponse-compatible dict."""
    current_company = current_work["company_name"] if current_work else None
    current_position = current_work["position"] if current_work else None

    result = {
        "id": str(member_obj.id),
        "name": member_obj.name,
        "nickname": member_obj.nickname,
        "gender": member_obj.gender.value if hasattr(member_obj.gender, 'value') and member_obj.gender else (str(member_obj.gender) if member_obj.gender else None),
        "birth_date": str(member_obj.date_of_birth) if member_obj.date_of_birth else None,
        "age": member_obj.age,
        "phone": member_obj.phone,
        "email": member_obj.email,
        "id_card": member_obj.id_card,
        "relation": relation_value,
        "profile_completion": member_obj.profile_completion or 0,
        "locations": member_obj.locations,
        "default_location_type": member_obj.default_location_type,
        "current_company": current_company,
        "current_position": current_position,
        "occupation": current_position,
        "workplace": current_company,
        "tags": member_obj.tags or [],
        "created_at": member_obj.created_at.isoformat() if member_obj.created_at else "",
        "updated_at": member_obj.updated_at.isoformat() if member_obj.updated_at else "",
    }
    if person_profile:
        result["favor_balance"] = float(person_profile.favor_balance or 0.0)
        result["last_mentioned_at"] = (
            person_profile.last_mentioned_at.isoformat()
            if person_profile.last_mentioned_at else None
        )
        result["importance"] = float(person_profile.importance or 0)
        result["organization"] = person_profile.organization
        # Fill organization from current_work if not set
        if not result.get("organization") and current_company:
            result["organization"] = current_company
    return result


async def get_member_relation(
    member_id: UUID,
    user_id: UUID,
    relation_repo: RelationRepository
) -> str:
    """Get relation from user to member.

    Self-member is detected by member.id == user.id (shared UUID).
    """
    if member_id == user_id:
        return 'self'
    relations = await relation_repo.list_by_member(member_id, direction='incoming')
    user_relation = next((r for r in relations if r.from_member_id == user_id), None)
    return user_relation.relation_type.value if user_relation else 'other'


def member_to_response(
    member,
    relation: str = "other",
    person_profile=None,
    current_work: dict = None,
) -> MemberResponse:
    """Convert Member model to response with frontend field names."""
    current_company = current_work["company_name"] if current_work else None
    current_position = current_work["position"] if current_work else None

    resp = MemberResponse(
        id=str(member.id),
        name=member.name,
        nickname=member.nickname,
        gender=member.gender,
        birth_date=str(member.date_of_birth) if member.date_of_birth else None,
        age=member.age,
        phone=member.phone,
        email=member.email,
        id_card=member.id_card,
        relation=relation,
        profile_completion=member.profile_completion or 0,
        # Location fields
        locations=member.locations,
        default_location_type=member.default_location_type,
        # Professional fields (from work_histories)
        current_company=current_company,
        current_position=current_position,
    )
    if person_profile:
        resp.favor_balance = float(person_profile.favor_balance or 0.0)
        resp.last_mentioned_at = (
            person_profile.last_mentioned_at.isoformat()
            if person_profile.last_mentioned_at else None
        )
        resp.importance = float(person_profile.importance or 0)
        resp.organization = person_profile.organization
        # Fill organization from current_work if not set
        if not resp.organization and current_company:
            resp.organization = current_company
    return resp


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
    request: CreateMemberRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family)
):
    """Create a new member."""
    service = MemberService(db)
    relation_repo = RelationRepository(db)

    try:
        # Convert frontend field names to backend field names
        member_data = request.dict(exclude_unset=True)

        # Store relation for creating relation record
        relation_str = member_data.get('relation', 'other')

        # Convert birth_date to date_of_birth for backend
        if 'birth_date' in member_data:
            birth_date_str = member_data.pop('birth_date')
            if birth_date_str:
                # Parse string to date object
                from datetime import date as date_type
                if isinstance(birth_date_str, str):
                    member_data['date_of_birth'] = date_type.fromisoformat(birth_date_str)
                else:
                    member_data['date_of_birth'] = birth_date_str

        # Remove relation field as it's not part of the member table
        if 'relation' in member_data:
            member_data.pop('relation')

        # Extract name (required) and pass the rest as kwargs
        name = member_data.pop('name')
        member = await service.create_member(
            family_id=str(family_id),
            name=name,
            created_by=user_id,
            **member_data,
        )

        # Create relation record from current user to this member
        # First, ensure the current user exists as a member (create if not exists)
        from sqlalchemy import select
        from ...modules.member.models.member import Member

        stmt = select(Member).where(Member.id == user_id)
        result = await db.execute(stmt)
        current_user_member = result.scalar_one_or_none()

        if not current_user_member:
            # Create self-member for users registered before this feature.
            # Normally created at registration time.
            from ...modules.member.models.user import User as UserModel
            user_result = await db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user_obj = user_result.scalar_one_or_none()
            current_user_member = Member(
                id=user_id,
                family_id=family_id,
                created_by=user_id,
                name=user_obj.username if user_obj else "Me",
                nickname=user_obj.nickname if user_obj else None,
                phone=user_obj.phone if user_obj else None,
                email=user_obj.email if user_obj else None,
                profile_completion=30,
            )
            db.add(current_user_member)
            await db.flush()

        # Validate the relation string and convert to enum
        try:
            relation_type = RelationType(relation_str)
        except ValueError:
            relation_type = RelationType.OTHER

        await relation_repo.create({
            'family_id': family_id,
            'from_member_id': user_id,
            'to_member_id': UUID(member.id),
            'relation_type': relation_type,
            'intimacy_level': 5
        })
        await db.commit()

        # Convert MemberInfo dataclass to response dict
        return {
            "id": member.id,
            "name": member.name,
            "relation": relation_str,
            "birth_date": str(member.birthday) if member.birthday else None,
            "locations": member.locations,
        }

    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=List[MemberResponse], include_in_schema=False)
@router.get("/", response_model=List[MemberResponse])
async def list_members(
    include_deleted: bool = False,
    min_profile_completion: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family)
):
    """List family members with full profile data."""
    from ...modules.member.models.member import Member
    from ...modules.member.models import PersonProfile, ProfileStatus
    from sqlalchemy import or_

    relation_repo = RelationRepository(db)

    stmt = select(Member).where(
        Member.family_id == family_id,
        or_(Member.is_deleted.is_(None), Member.is_deleted.is_(False)),
    )
    result = await db.execute(stmt)
    members = result.scalars().all()

    # Batch-fetch PersonProfiles by member_id (O(1) extra query, not N+1)
    member_ids = [m.id for m in members]
    profile_map = {}
    if member_ids:
        profile_stmt = select(PersonProfile).where(
            PersonProfile.member_id.in_(member_ids),
            PersonProfile.status == ProfileStatus.ACTIVE.value,
        )
        profile_result = await db.execute(profile_stmt)
        for pp in profile_result.scalars().all():
            profile_map[pp.member_id] = pp

    # Batch-fetch current work from work_histories
    from ...modules.member.current_work_helper import get_current_work_batch
    work_map = await get_current_work_batch(db, member_ids) if member_ids else {}

    response = []
    for m in members:
        relation = await get_member_relation(m.id, user_id, relation_repo)
        pp = profile_map.get(m.id)
        cw = work_map.get(m.id)
        response.append(member_to_response(m, relation, person_profile=pp, current_work=cw))

    return response


@router.get("/{member_id}", response_model=MemberDetailResponse)
async def get_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Get member details."""
    service = MemberService(db)
    relation_repo = RelationRepository(db)

    try:
        from ...modules.member.models.member import Member as MemberModel
        from ...modules.member.models import PersonProfile, ProfileStatus
        from sqlalchemy import select

        result = await db.execute(
            select(MemberModel).where(
                MemberModel.id == member_id,
                MemberModel.is_deleted.is_(False),
            )
        )
        member_obj = result.scalar_one_or_none()
        if member_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

        # Fetch PersonProfile for this member
        pp_result = await db.execute(
            select(PersonProfile).where(
                PersonProfile.member_id == member_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
            ).limit(1)
        )
        person_profile = pp_result.scalar_one_or_none()

        from ...modules.member.current_work_helper import get_current_work
        current_work = await get_current_work(db, member_id)

        relation_value = await get_member_relation(member_id, user_id, relation_repo)
        return _member_orm_to_detail(member_obj, relation_value, person_profile=person_profile, current_work=current_work)

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{member_id}/insights", response_model=List[MemberInsightResponse])
async def get_member_insights(
    member_id: UUID,
    limit: int = 20,
    include_dismissed: bool = False,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Get AI-generated insights related to a specific family member."""
    from ...modules.insight.insight_query_service import InsightQueryService

    svc = InsightQueryService(db)
    cards = await svc.get_for_member(
        user_id, member_id,
        limit=limit,
        include_dismissed=include_dismissed,
    )

    return [_insight_card_to_member_response(card) for card in cards]


def _insight_card_to_member_response(card) -> "MemberInsightResponse":
    """Map an InsightCard DTO to MemberInsightResponse for backward compat."""
    return MemberInsightResponse(
        id=str(card.id),
        source="insight",
        insight_type=card.insight_type,
        title=card.title,
        content=card.content,
        priority=None,
        importance=card.importance,
        urgency=str(card.urgency) if card.urgency else None,
        status=card.status,
        created_at=card.created_at.isoformat() if card.created_at else "",
        action_data=None,
        suggested_action=card.suggested_action,
        action_options=card.action_options,
    )


@router.put("/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: UUID,
    request: CreateMemberRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Update member."""
    service = MemberService(db)
    relation_repo = RelationRepository(db)

    try:
        # Convert frontend field names to backend field names
        member_data = request.dict(exclude_unset=True)

        # Store relation for updating relation record
        relation_str = member_data.get('relation')

        # Convert birth_date to date_of_birth for backend
        if 'birth_date' in member_data:
            birth_date_str = member_data.pop('birth_date')
            if birth_date_str:
                # Parse string to date object
                from datetime import date as date_type
                if isinstance(birth_date_str, str):
                    member_data['date_of_birth'] = date_type.fromisoformat(birth_date_str)
                else:
                    member_data['date_of_birth'] = birth_date_str
            else:
                # Explicitly set to None to clear the birthday
                member_data['date_of_birth'] = None

        # Remove relation field as it's not part of the member table
        if 'relation' in member_data:
            member_data.pop('relation')

        # Look up family_id from the member record
        from sqlalchemy import select
        from ...modules.member.models.member import Member

        fam_result = await db.execute(
            select(Member.family_id).where(Member.id == member_id)
        )
        fam_id = fam_result.scalar_one_or_none()
        if fam_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

        member = await service.update_member(
            member_id=str(member_id),
            family_id=str(fam_id),
            updates=member_data,
        )

        # If updating the self-member, sync auth-essential fields to User
        if member_id == user_id:
            from ...modules.member.models.user import User as UserModel
            user_result = await db.execute(
                select(UserModel).where(UserModel.id == user_id, UserModel.is_active == True)
            )
            user_obj = user_result.scalar_one_or_none()
            if user_obj:
                # Re-fetch the updated member ORM for accurate values
                member_reload = await db.execute(
                    select(Member).where(Member.id == member_id)
                )
                updated_member = member_reload.scalar_one_or_none()
                if updated_member:
                    user_obj.username = updated_member.name
                    user_obj.nickname = updated_member.nickname
                    user_obj.phone = updated_member.phone
                    user_obj.email = updated_member.email

        # Update relation if provided
        if relation_str:
            stmt = select(Member).where(Member.id == user_id)
            result = await db.execute(stmt)
            current_user_member = result.scalar_one_or_none()

            if not current_user_member:
                from ...modules.member.models.user import User as UserModel
                user_result = await db.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
                user_obj = user_result.scalar_one_or_none()
                current_user_member = Member(
                    id=user_id,
                    family_id=fam_id,
                    created_by=user_id,
                    name=user_obj.username if user_obj else "Me",
                    nickname=user_obj.nickname if user_obj else None,
                    phone=user_obj.phone if user_obj else None,
                    email=user_obj.email if user_obj else None,
                    profile_completion=30,
                )
                db.add(current_user_member)
                await db.flush()

            relations = await relation_repo.list_by_member(member_id, direction='incoming')
            user_relation = next((r for r in relations if r.from_member_id == user_id), None)

            try:
                relation_type = RelationType(relation_str)
            except ValueError:
                relation_type = RelationType.OTHER

            if user_relation:
                await relation_repo.update(user_relation.id, {'relation_type': relation_type})
            else:
                await relation_repo.create({
                    'family_id': fam_id,
                    'from_member_id': user_id,
                    'to_member_id': member_id,
                    'relation_type': relation_type,
                    'intimacy_level': 5
                })
            await db.commit()

        relation_value = await get_member_relation(member_id, user_id, relation_repo)

        # Re-fetch the ORM object for complete response
        from ...modules.member.models.member import Member as MemberReload
        reload_result = await db.execute(
            select(MemberReload).where(MemberReload.id == member_id)
        )
        member_obj = reload_result.scalar_one_or_none()
        if member_obj:
            from ...modules.member.current_work_helper import get_current_work
            current_work = await get_current_work(db, member_id)
            return _member_orm_to_detail(member_obj, relation_value, current_work=current_work)
        return {"id": member.id, "name": member.name, "relation": relation_value}

    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Delete member (soft delete)."""
    service = MemberService(db)

    try:
        # Look up family_id from member
        from sqlalchemy import select
        from ...modules.member.models.member import Member
        fam_result = await db.execute(
            select(Member.family_id).where(Member.id == member_id)
        )
        fam_id = fam_result.scalar_one_or_none()
        if fam_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

        result = await service.delete_member(str(member_id), str(fam_id))
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        await db.commit()

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# =============================================================================
# Work History Endpoints
# =============================================================================

@router.post("/{member_id}/work-history", response_model=WorkHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_work_history(
    member_id: UUID,
    request: CreateWorkHistoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Create a work history entry for a member."""
    service = WorkHistoryService(db)

    try:
        work_history = await service.create_work_history(
            member_id=member_id,
            work_history_data=request.dict(exclude_unset=True),
            requester_id=user_id
        )
        await db.commit()
        return work_history

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{member_id}/work-history", response_model=List[WorkHistoryResponse])
async def list_work_history(
    member_id: UUID,
    include_past: bool = True,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """List all work history for a member."""
    service = WorkHistoryService(db)

    try:
        work_histories = await service.list_work_history(
            member_id=member_id,
            requester_id=user_id,
            include_past=include_past
        )
        return work_histories

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/{member_id}/work-history/{work_history_id}", response_model=WorkHistoryResponse)
async def update_work_history(
    member_id: UUID,
    work_history_id: UUID,
    request: CreateWorkHistoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Update a work history entry."""
    service = WorkHistoryService(db)

    try:
        work_history = await service.update_work_history(
            work_history_id=work_history_id,
            updates=request.dict(exclude_unset=True),
            requester_id=user_id
        )
        if not work_history:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work history not found")

        await db.commit()
        return work_history

    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{member_id}/work-history/{work_history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_history(
    member_id: UUID,
    work_history_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Delete a work history entry."""
    service = WorkHistoryService(db)

    try:
        result = await service.delete_work_history(
            work_history_id=work_history_id,
            requester_id=user_id
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work history not found")

        await db.commit()

    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# =============================================================================
# Professional Relations Endpoints
# =============================================================================

@router.get("/professional-relation-types", response_model=List[ProfessionalRelationTypeResponse])
async def get_professional_relation_types(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Get all professional relation type options."""
    service = ProfessionalRelationService(db)
    return await service.get_relation_types()


@router.post("/professional-relations", response_model=ProfessionalRelationResponse, status_code=status.HTTP_201_CREATED)
async def create_professional_relation(
    request: CreateProfessionalRelationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Create a professional relation between two members."""
    service = ProfessionalRelationService(db)

    try:
        relation = await service.create_professional_relation(
            from_member_id=UUID(request.from_member_id),
            to_member_id=UUID(request.to_member_id),
            relation_type=request.relation_type,
            requester_id=user_id,
            company_name=request.company_name,
            is_current=request.is_current,
            notes=request.notes,
            start_date=request.start_date,
            end_date=request.end_date
        )
        await db.commit()
        return relation

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{member_id}/professional-relations", response_model=List[ProfessionalRelationResponse])
async def list_professional_relations(
    member_id: UUID,
    include_past: bool = True,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """List all professional relations for a member."""
    service = ProfessionalRelationService(db)

    try:
        relations = await service.list_professional_relations(
            member_id=member_id,
            requester_id=user_id,
            include_past=include_past
        )
        return relations

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/professional-relations/{relation_id}", response_model=ProfessionalRelationResponse)
async def update_professional_relation(
    relation_id: UUID,
    request: CreateProfessionalRelationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Update a professional relation."""
    service = ProfessionalRelationService(db)

    try:
        relation = await service.update_professional_relation(
            relation_id=relation_id,
            updates=request.dict(exclude_unset=True),
            requester_id=user_id
        )
        if not relation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional relation not found")

        await db.commit()
        return relation

    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/professional-relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_professional_relation(
    relation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user)
):
    """Delete a professional relation."""
    service = ProfessionalRelationService(db)

    try:
        result = await service.delete_professional_relation(
            relation_id=relation_id,
            requester_id=user_id
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional relation not found")

        await db.commit()

    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# =============================================================================
# Family endpoint
# =============================================================================

@router.get("/family")
async def get_family(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get current family information."""
    from ...modules.member.member_service import MemberService as NewMemberService

    service = NewMemberService(db)
    family = await service.get_family(str(family_id))
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )
    return {
        "id": family.id,
        "name": family.name,
        "owner_user_id": family.owner_user_id,
        "settings": family.settings,
    }


# =============================================================================
# Extended Profile Endpoints
# =============================================================================


@router.get("/{member_id}/profile", response_model=MemberProfileExtResponse)
async def get_member_profile(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get extended profile for a member (sizes, health, preferences)."""
    from ...modules.member.member_service import MemberService as NewMemberService

    service = NewMemberService(db)
    profile = await service.get_member_profile(str(member_id), str(family_id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    return {
        "member_id": profile.member_id,
        "preferences": profile.preferences,
        "habits": profile.habits,
        "health_summary": profile.health_summary,
        "personality_traits": profile.personality_traits,
        "special_notes": profile.special_notes,
    }


@router.put("/{member_id}/profile", response_model=MemberProfileExtResponse)
async def update_member_profile(
    member_id: UUID,
    request: MemberProfileExtRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Update extended profile for a member."""
    from ...modules.member.member_service import MemberService as NewMemberService

    service = NewMemberService(db)
    updates = request.dict(exclude_unset=True)
    try:
        profile = await service.update_member_profile(
            str(member_id), str(family_id), updates,
        )
        await db.commit()
        return {
            "member_id": profile.member_id,
            "preferences": profile.preferences,
            "habits": profile.habits,
            "health_summary": profile.health_summary,
            "personality_traits": profile.personality_traits,
            "special_notes": profile.special_notes,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

