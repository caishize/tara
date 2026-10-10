"""Three-Layer Favor Depth Model (L1/L2/L3).

Extends the existing L1 quantifiable favor tracking with:
- L2: Unquantifiable emotional debt (helping care for kids, sick visits, etc.)
- L3: Relationship capital (derived composite score from L1 + L2 + interaction)

Zero LLM cost — L2 is derived from keyword matching in conversation history,
L3 is a weighted combination formula. No new DB tables required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class FavorLayer(str, Enum):
    """Three layers of favor/relationship tracking."""
    L1_QUANTIFIABLE = "l1_quantifiable"   # 礼金 (existing FavorRecord)
    L2_EMOTIONAL = "l2_emotional"         # 帮忙照顾/生病送饭/关键帮助
    L3_CAPITAL = "l3_capital"             # 面子/关系资本 (derived)


# L2 emotional debt keywords and their weights.
# These Chinese keywords map to emotional help categories.
_L2_KEYWORD_WEIGHTS: Dict[str, tuple] = {
    # keyword -> (debt_type, weight)
    "帮忙照顾": ("help_childcare", 3.0),
    "照顾孩子": ("help_childcare", 3.0),
    "帮忙带娃": ("help_childcare", 3.0),
    "帮忙接送": ("help_childcare", 2.0),
    "帮带孩子": ("help_childcare", 3.0),
    "送饭": ("sick_visit", 2.5),
    "生病": ("sick_visit", 2.0),
    "看望": ("sick_visit", 1.5),
    "探望": ("sick_visit", 1.5),
    "陪护": ("sick_visit", 2.5),
    "帮了大忙": ("critical_help", 4.0),
    "帮了个忙": ("critical_help", 2.0),
    "关键时刻": ("critical_help", 3.0),
    "雪中送炭": ("critical_help", 4.0),
    "帮忙搬家": ("critical_help", 2.5),
    "帮忙": ("emotional_support", 1.5),
    "照顾": ("emotional_support", 1.5),
    "陪": ("emotional_support", 1.0),
    "安慰": ("emotional_support", 1.5),
    "鼓励": ("emotional_support", 1.0),
    "支持": ("emotional_support", 1.0),
}

# L3 composite weights
L3_L1_WEIGHT = 0.3    # Quantifiable gift balance contribution
L3_L2_WEIGHT = 0.5    # Emotional debt contribution
L3_FREQ_WEIGHT = 0.2  # Interaction frequency contribution

# L1 normalization: amounts above this are capped at 100 score
L1_NORMALIZATION_CAP = 10000.0

# L2 score normalization: raw weighted count above this caps at 100
L2_NORMALIZATION_CAP = 20.0

# Interaction frequency normalization: messages above this cap at 100
FREQ_NORMALIZATION_CAP = 50

# Time window for conversation history scan
CONVERSATION_SCAN_DAYS = 90

# Minimum L2 score to consider as "high emotional debt"
HIGH_L2_DEBT_THRESHOLD = 40.0

# Window for finding upcoming events for reciprocation opportunities
RECIPROCATION_LOOKAHEAD_DAYS = 60


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmotionalDebt:
    """A single detected emotional debt instance from conversation history."""

    contact_id: str
    contact_name: str
    debt_type: str  # help_childcare, sick_visit, critical_help, emotional_support
    description: str
    occurred_at: datetime
    reciprocated: bool


@dataclass(frozen=True)
class RelationshipCapital:
    """Composite relationship capital score for a contact."""

    contact_id: str
    l1_balance: float       # net gift money balance (given - received)
    l2_score: float         # emotional debt score (0-100)
    l3_overall: float       # combined relationship capital (0-100)
    trend: str              # growing, stable, declining


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_score(raw: float, cap: float) -> float:
    """Normalize a raw value to 0-100 scale, capping at the given threshold."""
    if cap <= 0:
        return 0.0
    normalized = (abs(raw) / cap) * 100.0
    return min(normalized, 100.0)


def _scan_content_for_l2(
    content: str,
    contact_name: str,
) -> List[Dict[str, Any]]:
    """Scan a message content string for L2 emotional debt keywords.

    Returns a list of detected debt signals with type and weight.
    Only matches keywords that co-occur with the contact name in the
    same message.
    """
    if not content or contact_name not in content:
        return []

    matches: List[Dict[str, Any]] = []
    seen_types: set = set()

    for keyword, (debt_type, weight) in _L2_KEYWORD_WEIGHTS.items():
        if keyword in content and debt_type not in seen_types:
            seen_types.add(debt_type)
            matches.append({
                "debt_type": debt_type,
                "weight": weight,
                "keyword": keyword,
            })

    return matches


def _compute_l3(
    l1_normalized: float,
    l2_score: float,
    freq_normalized: float,
) -> float:
    """Compute the L3 composite relationship capital score."""
    return round(
        l1_normalized * L3_L1_WEIGHT
        + l2_score * L3_L2_WEIGHT
        + freq_normalized * L3_FREQ_WEIGHT,
        1,
    )


def _determine_capital_trend(
    recent_l2_count: int,
    total_l2_count: int,
    l1_balance: float,
) -> str:
    """Determine relationship capital trend.

    - growing: recent emotional interactions or positive L1 balance
    - declining: no recent interactions and negative L1 balance
    - stable: default
    """
    has_recent_l2 = recent_l2_count > 0
    positive_l1 = l1_balance > 0

    if has_recent_l2 and positive_l1:
        return "growing"
    if not has_recent_l2 and l1_balance < 0 and total_l2_count == 0:
        return "declining"
    if has_recent_l2 or positive_l1:
        return "growing"
    return "stable"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compute_relationship_capital(
    db: AsyncSession,
    user_id: UUID,
    contact_id: UUID,
) -> RelationshipCapital:
    """Compute the three-layer relationship capital for a contact.

    L1: Sum of favor_records (given - received).
    L2: Emotional debt score from conversation history keyword matching.
    L3: Weighted combination of L1 normalized + L2 + interaction frequency.

    Gracefully returns neutral defaults if data is insufficient.
    """
    # ── L1: Quantifiable favor balance ────────────────────────────────
    l1_balance = await _compute_l1_balance(db, user_id, contact_id)

    # ── L2: Emotional debt from conversation keywords ─────────────────
    l2_score, recent_l2, total_l2, contact_name = await _compute_l2_score(
        db, user_id, contact_id,
    )

    # ── Interaction frequency ─────────────────────────────────────────
    freq_count = await _count_interactions(db, user_id, contact_id)

    # ── L3: Composite score ───────────────────────────────────────────
    l1_normalized = _normalize_score(l1_balance, L1_NORMALIZATION_CAP)
    freq_normalized = _normalize_score(float(freq_count), float(FREQ_NORMALIZATION_CAP))

    l3_overall = _compute_l3(l1_normalized, l2_score, freq_normalized)
    trend = _determine_capital_trend(recent_l2, total_l2, l1_balance)

    return RelationshipCapital(
        contact_id=str(contact_id),
        l1_balance=round(l1_balance, 2),
        l2_score=round(l2_score, 1),
        l3_overall=l3_overall,
        trend=trend,
    )


async def find_reciprocation_opportunities(
    db: AsyncSession,
    user_id: UUID,
    family_id: Optional[UUID] = None,
) -> List[Dict[str, Any]]:
    """Find contacts with high L2 debt who have upcoming important dates.

    Cross-references emotional debt with ImportantDate/SocialEvent to
    surface reciprocation opportunities like:
    "张阿姨帮你照顾了3次孩子，她女儿下月结婚"
    """
    from ..relationship.models import FavorRecord
    from ..member.models import PersonProfile
    from ..member.models.enums import ProfileStatus

    now = utc_now()

    # Step 1: Find contacts with pending favors (they gave to us)
    favor_stmt = (
        select(
            FavorRecord.contact_id,
            FavorRecord.contact_name,
            func.count(FavorRecord.id).label("favor_count"),
        )
        .where(
            and_(
                FavorRecord.user_id == user_id,
                FavorRecord.direction == "receive",
                FavorRecord.status == "pending",
                FavorRecord.contact_id.isnot(None),
            )
        )
        .group_by(FavorRecord.contact_id, FavorRecord.contact_name)
        .having(func.count(FavorRecord.id) >= 1)
        .limit(20)
    )

    try:
        favor_result = await db.execute(favor_stmt)
        favor_contacts = list(favor_result.all())
    except Exception as exc:
        logger.warning("Failed to query favor contacts: %s", exc)
        return []

    if not favor_contacts:
        return []

    contact_ids = [row.contact_id for row in favor_contacts if row.contact_id]
    contact_names = {
        str(row.contact_id): row.contact_name
        for row in favor_contacts
        if row.contact_id
    }
    contact_favor_counts = {
        str(row.contact_id): int(row.favor_count)
        for row in favor_contacts
        if row.contact_id
    }

    # Step 2: Check for upcoming important dates linked to these contacts
    opportunities: List[Dict[str, Any]] = []

    try:
        from ..date_manager.date_models import ImportantDate

        lookahead = now + timedelta(days=RECIPROCATION_LOOKAHEAD_DAYS)

        date_stmt = (
            select(ImportantDate)
            .where(
                and_(
                    ImportantDate.member_id.in_(contact_ids),
                    ImportantDate.solar_date >= now.date(),
                    ImportantDate.solar_date <= lookahead.date(),
                )
            )
            .order_by(ImportantDate.solar_date.asc())
            .limit(20)
        )
        date_result = await db.execute(date_stmt)
        upcoming_dates = list(date_result.scalars().all())

        for imp_date in upcoming_dates:
            member_id_str = str(imp_date.member_id)
            c_name = contact_names.get(member_id_str, "unknown")
            favors = contact_favor_counts.get(member_id_str, 0)

            opportunities.append({
                "contact_id": member_id_str,
                "contact_name": c_name,
                "pending_favor_count": favors,
                "upcoming_event_title": imp_date.title,
                "upcoming_event_date": imp_date.solar_date.isoformat(),
                "upcoming_event_type": imp_date.date_type,
                "suggestion": (
                    f"{c_name}有{favors}笔待回人情，"
                    f"{imp_date.title}({imp_date.solar_date.isoformat()})是回礼好时机"
                ),
            })
    except Exception as exc:
        logger.warning("Failed to query upcoming dates for reciprocation: %s", exc)

    # Step 3: Also check upcoming social events linked via FavorRecord
    try:
        from ..relationship.models import SocialEvent, FavorRecord as FR

        se_stmt = (
            select(SocialEvent, FR.contact_id, FR.contact_name)
            .join(FR, FR.event_id == SocialEvent.id)
            .where(
                and_(
                    FR.contact_id.in_(contact_ids),
                    SocialEvent.event_date >= now.date(),
                    SocialEvent.event_date <= (
                        now + timedelta(days=RECIPROCATION_LOOKAHEAD_DAYS)
                    ).date(),
                    SocialEvent.status.in_(["upcoming", "confirmed", "pending"]),
                )
            )
            .order_by(SocialEvent.event_date.asc())
            .limit(20)
        )
        se_result = await db.execute(se_stmt)
        upcoming_rows = list(se_result.all())

        for event, c_id, c_name_from_favor in upcoming_rows:
            c_id_str = str(c_id) if c_id else None
            if c_id_str is None:
                continue
            c_name = contact_names.get(c_id_str, c_name_from_favor or "unknown")
            favors = contact_favor_counts.get(c_id_str, 0)

            opportunities.append({
                "contact_id": c_id_str,
                "contact_name": c_name,
                "pending_favor_count": favors,
                "upcoming_event_title": event.title,
                "upcoming_event_date": event.event_date.isoformat(),
                "upcoming_event_type": event.event_type,
                "suggestion": (
                    f"{c_name}有{favors}笔待回人情，"
                    f"{event.title}({event.event_date.isoformat()})是回礼好时机"
                ),
            })
    except Exception as exc:
        logger.warning("Failed to query social events for reciprocation: %s", exc)

    logger.info(
        "Found %d reciprocation opportunities for user %s",
        len(opportunities), user_id,
    )

    return opportunities


# ---------------------------------------------------------------------------
# Internal query helpers
# ---------------------------------------------------------------------------


async def _compute_l1_balance(
    db: AsyncSession,
    user_id: UUID,
    contact_id: UUID,
) -> float:
    """Compute net L1 gift balance: given - received."""
    from ..relationship.models import FavorRecord

    given_case = case(
        (FavorRecord.direction == "give", FavorRecord.amount),
        else_=0,
    )
    received_case = case(
        (FavorRecord.direction == "receive", FavorRecord.amount),
        else_=0,
    )

    stmt = (
        select(
            func.coalesce(func.sum(given_case), 0).label("total_given"),
            func.coalesce(func.sum(received_case), 0).label("total_received"),
        )
        .where(
            and_(
                FavorRecord.contact_id == contact_id,
                FavorRecord.user_id == user_id,
            )
        )
    )

    try:
        result = await db.execute(stmt)
        row = result.one()
        return float(row.total_given) - float(row.total_received)
    except Exception as exc:
        logger.warning("L1 balance query failed for contact %s: %s", contact_id, exc)
        return 0.0


async def _compute_l2_score(
    db: AsyncSession,
    user_id: UUID,
    contact_id: UUID,
) -> tuple:
    """Compute L2 emotional debt score from conversation keyword matching.

    Returns:
        (l2_score, recent_count, total_count, contact_name)
    """
    from ..member.models import PersonProfile
    from ..conversation.models import ConversationMessage

    # Resolve contact name
    contact_name = ""
    try:
        name_stmt = (
            select(PersonProfile.name)
            .where(PersonProfile.id == contact_id)
        )
        name_result = await db.execute(name_stmt)
        contact_name = name_result.scalar_one_or_none() or ""
    except Exception as exc:
        logger.debug("Failed to resolve contact name for %s: %s", contact_id, exc)

    if not contact_name:
        return (0.0, 0, 0, "")

    # Scan conversation messages for L2 keywords mentioning this contact
    from ..conversation.models import AssistantChatSession

    scan_cutoff = utc_now() - timedelta(days=CONVERSATION_SCAN_DAYS)
    recent_cutoff = utc_now() - timedelta(days=30)

    # Escape LIKE-special characters in contact name
    safe_name = (
        contact_name
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    # Scope by user_id via session join for data isolation
    session_subq = (
        select(AssistantChatSession.id)
        .where(
            and_(
                AssistantChatSession.user_id == user_id,
                AssistantChatSession.started_at >= scan_cutoff,
            )
        )
        .subquery()
    )

    msg_stmt = (
        select(
            ConversationMessage.content,
            ConversationMessage.created_at,
        )
        .where(
            and_(
                ConversationMessage.session_id.in_(select(session_subq)),
                ConversationMessage.role == "user",
                ConversationMessage.created_at >= scan_cutoff,
                ConversationMessage.content.ilike(f"%{safe_name}%"),
            )
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(200)
    )

    try:
        result = await db.execute(msg_stmt)
        messages = list(result.all())
    except Exception as exc:
        logger.warning("L2 conversation scan failed for contact %s: %s", contact_id, exc)
        return (0.0, 0, 0, contact_name)

    total_weighted = 0.0
    total_count = 0
    recent_count = 0

    for content, created_at in messages:
        if content is None:
            continue
        matches = _scan_content_for_l2(content, contact_name)
        for match in matches:
            total_weighted += match["weight"]
            total_count += 1
            if created_at and created_at >= recent_cutoff:
                recent_count += 1

    l2_score = _normalize_score(total_weighted, L2_NORMALIZATION_CAP)
    return (l2_score, recent_count, total_count, contact_name)


async def _count_interactions(
    db: AsyncSession,
    user_id: UUID,
    contact_id: UUID,
) -> int:
    """Count recent conversation messages mentioning the contact."""
    from ..member.models import PersonProfile
    from ..conversation.models import ConversationMessage, AssistantChatSession

    # Resolve contact name
    try:
        name_stmt = select(PersonProfile.name).where(PersonProfile.id == contact_id)
        name_result = await db.execute(name_stmt)
        contact_name = name_result.scalar_one_or_none() or ""
    except Exception as exc:
        logger.debug("Failed to resolve contact name for %s: %s", contact_id, exc)
        return 0

    if not contact_name:
        return 0

    # Escape LIKE-special characters
    safe_name = (
        contact_name
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    scan_cutoff = utc_now() - timedelta(days=CONVERSATION_SCAN_DAYS)

    # Scope by user_id via session join for data isolation
    session_subq = (
        select(AssistantChatSession.id)
        .where(
            and_(
                AssistantChatSession.user_id == user_id,
                AssistantChatSession.started_at >= scan_cutoff,
            )
        )
        .subquery()
    )

    count_stmt = (
        select(func.count(ConversationMessage.id))
        .where(
            and_(
                ConversationMessage.session_id.in_(select(session_subq)),
                ConversationMessage.role == "user",
                ConversationMessage.created_at >= scan_cutoff,
                ConversationMessage.content.ilike(f"%{safe_name}%"),
            )
        )
    )

    try:
        result = await db.execute(count_stmt)
        return result.scalar_one() or 0
    except Exception as exc:
        logger.warning(
            "Interaction count failed for contact %s: %s", contact_id, exc,
        )
        return 0


# Short window constant re-exported for use in L2 trend detection
SHORT_WINDOW_DAYS_L2 = 7
