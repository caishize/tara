"""Relationships API routes - /api/v1/relationships/*

Thin routing layer for relationship health and favor management.
Delegates to relationship module services.

Endpoints:
    GET      /relationships/health              - Relationship health overview
    GET/POST /relationships/favors              - Favor records list/create
    GET      /relationships/favors/statistics   - Favor statistics summary
    GET      /relationships/favors/pending      - Pending favor returns
    POST     /relationships/favors/quick        - Quick-create favor record
    GET      /relationships/favors/balance      - Favor balance overview
    GET      /relationships/suggestions         - Smart care suggestions
"""

import logging
from datetime import date as date_type
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user, get_current_family
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/relationships", tags=["relationships"])


# --- Request / Response schemas ---

class RecordFavorRequest(BaseModel):
    """Record a favor exchange."""
    person_id: str
    direction: str  # gave, received
    type: str  # help, gift, money, meal, other
    amount: Optional[float] = None
    description: Optional[str] = None
    date: Optional[str] = None  # ISO format YYYY-MM-DD


class QuickFavorRequest(BaseModel):
    """Quick-create a favor record (used by mobile ledger form)."""
    contact_name: str
    contact_id: Optional[str] = None
    amount: float
    direction: str  # give, receive
    event_type: str  # wedding, funeral, birthday, baby, housewarming, other


class FavorRecordResponse(BaseModel):
    """Favor record response."""
    id: str
    person_id: str
    family_id: str
    direction: str
    favor_type: str
    amount: Optional[float] = None
    description: Optional[str] = None
    weight: float = 1.0
    date: Optional[str] = None


class CareSuggestionResponse(BaseModel):
    """Care suggestion response."""
    person_id: str
    person_name: str
    suggestion_type: str
    content: str
    urgency: float = 0.5


# --- Endpoints ---

@router.get("/health")
async def get_health_overview(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get relationship health overview for the family."""
    from ...modules.relationship.care_service import CareService

    service = CareService(db)
    return await service.get_health_overview(str(family_id))


@router.get("/health/members")
async def get_health_members(
    category: Optional[str] = None,
    sort_by: str = "score",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get all family members with relationship health scores.

    Returns members grouped into 'family' and 'network' categories,
    plus a summary object.  Used by the relationships management page.
    """
    from ...modules.member.models.member import Member, MemberRelation

    from sqlalchemy import select, and_, or_

    # -- 1. Fetch all relations for this family --------------------------
    rel_result = await db.execute(
        select(MemberRelation).where(MemberRelation.family_id == family_id)
    )
    relations = rel_result.scalars().all()

    # Collect member IDs involved in relations + self
    member_ids = {user_id}
    for r in relations:
        member_ids.add(r.from_member_id)
        member_ids.add(r.to_member_id)

    # -- 2. Fetch members ------------------------------------------------
    member_result = await db.execute(
        select(Member).where(
            and_(
                Member.id.in_(member_ids),
                Member.family_id == family_id,
                or_(Member.is_deleted.is_(None), Member.is_deleted.is_(False)),
            )
        )
    )
    members_by_id = {m.id: m for m in member_result.scalars().all()}

    # relation_type lookup: to_member_id -> type
    relation_map: Dict[UUID, str] = {}
    for r in relations:
        rel_type = r.relation_type.value if hasattr(r.relation_type, 'value') else str(r.relation_type)
        relation_map[r.to_member_id] = rel_type

    # -- 3. Categorisation helpers ---------------------------------------
    _FAMILY_TYPES = {
        "self", "spouse", "father", "mother", "parent",
        "son", "daughter", "child", "brother", "sister", "sibling",
        "grandfather_paternal", "grandmother_paternal",
        "grandfather_maternal", "grandmother_maternal", "grandparent",
        "grandson", "granddaughter", "grandchild",
        "uncle_paternal", "aunt_paternal", "uncle_maternal",
        "aunt_maternal", "uncle_aunt", "nephew", "niece", "nephew_niece",
        "cousin",
        "father_in_law", "mother_in_law", "parent_in_law",
        "son_in_law", "daughter_in_law", "child_in_law",
        "brother_in_law", "sister_in_law", "sibling_in_law",
    }

    _RELATION_DISPLAY = {
        "self": "本人", "spouse": "配偶", "father": "父亲", "mother": "母亲",
        "son": "儿子", "daughter": "女儿", "child": "孩子",
        "brother": "兄弟", "sister": "姐妹",
        "grandfather_paternal": "爷爷", "grandmother_paternal": "奶奶",
        "grandfather_maternal": "外公", "grandmother_maternal": "外婆",
        "father_in_law": "公公/岳父", "mother_in_law": "婆婆/岳母",
        "colleague": "同事", "classmate": "同学", "friend": "朋友",
        "neighbor": "邻居",
    }

    # Batch-fetch current work from work_histories
    from ...modules.member.current_work_helper import get_current_work_batch
    all_member_ids = list(members_by_id.keys())
    work_map = await get_current_work_batch(db, all_member_ids) if all_member_ids else {}

    def _make_member(mid: UUID, member) -> Dict[str, Any]:
        rel_type = "self" if mid == user_id else relation_map.get(mid, "other")
        cat = "family" if rel_type in _FAMILY_TYPES else "network"
        display = member.nickname or member.name
        cw = work_map.get(mid) or {}
        return {
            "id": str(mid),
            "name": member.name,
            "nickname": member.nickname,
            "display_name": display,
            "avatar_url": member.avatar_url,
            "relation_type": rel_type,
            "relation_display": _RELATION_DISPLAY.get(rel_type, rel_type),
            "category": cat,
            "phone": member.phone,
            "email": member.email,
            "age": member.age,
            "gender": member.gender.value if hasattr(member.gender, 'value') and member.gender else (str(member.gender) if member.gender else None),
            "occupation": cw.get("position"),
            "workplace": cw.get("company_name"),
            "profile_completion": member.profile_completion or 0,
            "score": {
                "total": 100 if rel_type == "self" else 50,
                "contact_score": 100 if rel_type == "self" else 50,
                "threshold_days": 30,
            },
            "status": {
                "level": "excellent" if rel_type == "self" else "warning",
                "color": "#10B981" if rel_type == "self" else "#EAB308",
                "label": "本人" if rel_type == "self" else "需要维护",
                "emoji": "👤" if rel_type == "self" else "💡",
            },
        }

    # -- 4. Build grouped response ---------------------------------------
    family_list = []
    network_list = []
    for mid, member in members_by_id.items():
        item = _make_member(mid, member)
        if item["category"] == "family":
            family_list.append(item)
        else:
            network_list.append(item)

    return {
        "family": family_list,
        "network": network_list,
        "summary": {
            "total_count": len(members_by_id),
            "family_count": len(family_list),
            "network_count": len(network_list),
            "average_score": 60,
            "needs_attention": 0,
            "excellent": 1,
        },
    }


@router.get("/health/members/{member_id}")
async def get_health_member_detail(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get single member health details."""
    from ...modules.member.models.member import Member, MemberRelation
    from sqlalchemy import select

    result = await db.execute(
        select(Member).where(Member.id == member_id, Member.family_id == family_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # Determine relation
    rel_type = "self"
    if member_id != user_id:
        rel_result = await db.execute(
            select(MemberRelation.relation_type).where(
                MemberRelation.from_member_id == user_id,
                MemberRelation.to_member_id == member_id,
            )
        )
        row = rel_result.scalar_one_or_none()
        rel_type = row.value if hasattr(row, 'value') and row else (str(row) if row else "other")

    _RELATION_DISPLAY = {
        "self": "本人", "spouse": "配偶", "father": "父亲", "mother": "母亲",
        "son": "儿子", "daughter": "女儿", "colleague": "同事",
        "friend": "朋友", "classmate": "同学",
    }

    from ...modules.member.current_work_helper import get_current_work
    current_work = await get_current_work(db, member_id)

    display = member.nickname or member.name
    return {
        "id": str(member.id),
        "name": member.name,
        "nickname": member.nickname,
        "display_name": display,
        "avatar_url": member.avatar_url,
        "relation_type": rel_type,
        "relation_display": _RELATION_DISPLAY.get(rel_type, rel_type),
        "category": "family",
        "phone": member.phone,
        "email": member.email,
        "age": member.age,
        "gender": member.gender.value if hasattr(member.gender, 'value') and member.gender else (str(member.gender) if member.gender else None),
        "occupation": (current_work or {}).get("position"),
        "workplace": (current_work or {}).get("company_name"),
        "profile_completion": member.profile_completion or 0,
        "score": {
            "total": 100 if rel_type == "self" else 50,
            "contact_score": 100 if rel_type == "self" else 50,
            "threshold_days": 30,
        },
        "status": {
            "level": "excellent" if rel_type == "self" else "warning",
            "color": "#10B981" if rel_type == "self" else "#EAB308",
            "label": "本人" if rel_type == "self" else "需要维护",
            "emoji": "👤" if rel_type == "self" else "💡",
        },
    }


@router.get("/health/attention")
async def get_attention_needed(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> List[Dict[str, Any]]:
    """Get members needing attention (placeholder — returns empty list)."""
    return []


@router.post("/health/interactions")
async def record_interaction(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Record an interaction with a member (placeholder)."""
    return {"status": "ok"}


@router.get("/suggestions", response_model=List[CareSuggestionResponse])
async def get_care_suggestions(
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> List[Dict[str, Any]]:
    """Get smart care suggestions."""
    from ...modules.relationship.care_service import CareService

    service = CareService(db)
    suggestions = await service.get_suggestions(str(family_id), limit=limit)
    return [
        {
            "person_id": s.person_id,
            "person_name": s.person_name,
            "suggestion_type": s.suggestion_type,
            "content": s.content,
            "urgency": s.urgency,
        }
        for s in suggestions
    ]


@router.get("/favors/statistics")
async def get_favor_statistics(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get favor statistics summary for the family."""
    from ...modules.relationship.favor_service import FavorService

    service = FavorService(db)
    stats = await service.get_statistics(str(family_id))
    return stats


@router.get("/favors/pending")
async def get_pending_favors(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> List[Dict[str, Any]]:
    """Get pending favor records (awaiting return)."""
    from ...modules.relationship.favor_service import FavorService

    service = FavorService(db)
    records = await service.list_favor_records(
        family_id=str(family_id),
        status="pending",
    )
    return records


@router.post("/favors/quick", status_code=status.HTTP_201_CREATED)
async def quick_create_favor(
    request: QuickFavorRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Quick-create a favor record from the mobile ledger form."""
    from ...modules.relationship.favor_service import FavorService

    service = FavorService(db)
    record = await service.quick_create(
        family_id=str(family_id),
        contact_name=request.contact_name,
        contact_id=request.contact_id,
        amount=request.amount,
        direction=request.direction,
        event_type=request.event_type,
    )
    await db.commit()
    return record


@router.post("/favors", response_model=FavorRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_favor(
    request: RecordFavorRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Record a favor exchange."""
    from ...modules.relationship.favor_service import FavorService

    favor_date = None
    if request.date:
        favor_date = date_type.fromisoformat(request.date)

    service = FavorService(db)
    record = await service.record_favor(
        family_id=str(family_id),
        person_id=request.person_id,
        direction=request.direction,
        favor_type=request.type,
        amount=request.amount,
        description=request.description,
        favor_date=favor_date,
    )
    await db.commit()
    return {
        "id": record.id,
        "person_id": record.person_id,
        "family_id": record.family_id,
        "direction": record.direction,
        "favor_type": record.favor_type,
        "amount": record.amount,
        "description": record.description,
        "weight": record.weight,
        "date": record.date.isoformat() if record.date else None,
    }


@router.get("/favors")
async def list_favors(
    direction: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """List favor records.

    Returns { items: [...] } format expected by the mobile client.
    """
    from ...modules.relationship.favor_service import FavorService

    service = FavorService(db)
    records = await service.list_favor_records(
        family_id=str(family_id),
        direction=direction,
        status=status,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return {"items": records}


@router.get("/favors/balance")
async def get_favor_balance(
    person_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> List[Dict[str, Any]]:
    """Get favor balance overview."""
    from ...modules.relationship.favor_service import FavorService

    service = FavorService(db)
    balances = await service.get_balance(
        family_id=str(family_id),
        person_id=person_id,
    )
    return [
        {
            "person_id": b.person_id,
            "name": b.person_name,
            "favor_balance": b.favor_balance,
            "owes_favor": b.owes_favor,
            "is_owed_favor": b.is_owed_favor,
            "last_interaction_days": b.last_interaction_days,
        }
        for b in balances
    ]


@router.get("/health/graph")
async def get_relationship_graph(
    center_member_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get relationship graph data (nodes + edges) for visualization.

    Builds graph from Members + MemberRelations tables, which contain
    the actual relationship structure (self, spouse, parent, child, etc.).
    """
    from ...modules.member.models.member import Member, MemberRelation

    from sqlalchemy import select, and_, or_

    # Fetch all relations for this family
    rel_stmt = select(MemberRelation).where(
        MemberRelation.family_id == family_id,
    )
    rel_result = await db.execute(rel_stmt)
    relations = rel_result.scalars().all()

    # Collect all member IDs involved in relations
    member_ids = set()
    for r in relations:
        member_ids.add(r.from_member_id)
        member_ids.add(r.to_member_id)

    if not member_ids:
        return {"nodes": [], "edges": []}

    # Fetch members
    member_stmt = select(Member).where(
        and_(
            Member.id.in_(member_ids),
            or_(Member.is_deleted.is_(None), Member.is_deleted.is_(False)),
        )
    )
    member_result = await db.execute(member_stmt)
    members_by_id = {m.id: m for m in member_result.scalars().all()}

    # The self-member is identified by member.id == user_id (new architecture).
    # Ensure the self-member is always included in the graph.
    self_member_id = user_id
    member_ids.add(self_member_id)

    # Build relation_type lookup: to_member_id -> relation_type
    # (relations go from the user's primary member to each other member)
    relation_map: Dict[UUID, str] = {}
    for r in relations:
        rel_type = r.relation_type.value if hasattr(r.relation_type, 'value') else str(r.relation_type)
        relation_map[r.to_member_id] = rel_type
        # Legacy: also detect self via MemberRelation(SELF) if present
        if rel_type == "self":
            self_member_id = r.to_member_id

    # Categorize relation types
    _FAMILY_TYPES = {
        "self", "spouse", "father", "mother", "parent",
        "son", "daughter", "child", "brother", "sister", "sibling",
        "grandfather_paternal", "grandmother_paternal",
        "grandfather_maternal", "grandmother_maternal", "grandparent",
        "grandson", "granddaughter", "grandchild",
        "uncle_paternal", "aunt_paternal", "uncle_maternal",
        "aunt_maternal", "uncle_aunt", "nephew", "niece", "nephew_niece",
        "cousin",
    }
    _IN_LAW_TYPES = {
        "father_in_law", "mother_in_law", "parent_in_law",
        "son_in_law", "daughter_in_law", "child_in_law",
        "brother_in_law", "sister_in_law", "sibling_in_law",
        "spouse_grandfather_paternal", "spouse_grandmother_paternal",
        "spouse_grandfather_maternal", "spouse_grandmother_maternal",
        "spouse_uncle_paternal", "spouse_aunt_paternal",
        "spouse_uncle_maternal", "spouse_aunt_maternal",
    }
    _WORK_TYPES = {"colleague", "classmate"}
    _FRIEND_TYPES = {"friend", "neighbor"}

    def _categorize(rel_type: str) -> str:
        if rel_type in _FAMILY_TYPES:
            return "family"
        if rel_type in _IN_LAW_TYPES:
            return "family"
        if rel_type in _WORK_TYPES:
            return "work"
        if rel_type in _FRIEND_TYPES:
            return "friend"
        return "network"

    # Build nodes
    nodes = []
    for mid, member in members_by_id.items():
        # Self-member is identified by member.id == user_id
        rel_type = "self" if mid == self_member_id else relation_map.get(mid, "other")
        category = _categorize(rel_type)
        importance = 10 if rel_type == "self" else 7 if rel_type == "spouse" else 5

        nodes.append({
            "id": str(mid),
            "name": member.nickname or member.name,
            "relation_type": rel_type,
            "category": category,
            "importance": importance,
            "health_score": 100 if rel_type == "self" else 70,
            "last_interaction_days": None,
            "phone": member.phone,
        })

    # Build edges: connect each non-self member to the self member
    edges = []
    if self_member_id and str(self_member_id) in {n["id"] for n in nodes}:
        self_id_str = str(self_member_id)
        for mid, rel_type in relation_map.items():
            if rel_type == "self":
                continue
            if str(mid) not in {n["id"] for n in nodes}:
                continue
            edges.append({
                "source": self_id_str,
                "target": str(mid),
                "relation_type": rel_type,
                "strength": 0.9 if rel_type in ("spouse", "child", "father", "mother") else 0.6,
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/health/contacts")
async def get_contact_health(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get per-contact relationship health scores."""
    from ...modules.relationship.care_service import CareService

    service = CareService(db)
    contacts = await service.get_contact_health(str(family_id))
    return {
        "contacts": [
            {
                "person_id": c.person_id,
                "name": c.person_name,
                "favor_balance": c.favor_balance,
                "last_interaction_days": c.last_interaction_days,
                "health_score": c.health_score,
                "suggestion": c.suggestion,
            }
            for c in contacts
        ]
    }
