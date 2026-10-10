"""LLM-aware insight deduplication.

Makes the LLM aware of existing active insights so it can decide
KEEP / UPDATE / NEW instead of blindly regenerating duplicates.

Functions:
- fetch_active_insights: query DB for active insights
- format_active_insights_for_prompt: compact formatting within token budget
- build_dedup_aware_prompt_section: full prompt section string
- process_dispositions: split candidates by disposition
- apply_updates: execute UPDATE statements for UPDATE-disposition candidates
"""

from __future__ import annotations

import json
import re
import uuid as uuid_mod
from dataclasses import replace
from typing import Any, Dict, List, NamedTuple, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from .models import (
    Insight,
    InsightCandidate,
    InsightEntity,
    InsightStatus,
)
from ..member.models.member import Member

logger = get_logger(__name__)


# Statuses considered "active" for dedup purposes
ACTIVE_STATUSES = frozenset({
    InsightStatus.PENDING.value,
    InsightStatus.ACTIVE.value,
    InsightStatus.ACKNOWLEDGED.value,
})

# Token budget for the active-insights prompt section (~1500 tokens)
_TOKEN_BUDGET = 1500
_CHARS_PER_TOKEN = 3.5
_OVERHEAD_FACTOR = 1.2


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class DispositionResult(NamedTuple):
    """Result of splitting candidates by disposition."""
    new_candidates: List[InsightCandidate]
    update_specs: List[Dict[str, Any]]
    keep_ids: List[str]
    delete_ids: List[str]


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------


class ActiveInsightRow:
    """Lightweight container for an active insight with related person names."""

    __slots__ = ("id", "title", "insight_type", "importance", "related_persons")

    def __init__(
        self,
        id: UUID,
        title: str,
        insight_type: str,
        importance: int,
        related_persons: List[str],
    ):
        self.id = id
        self.title = title
        self.insight_type = insight_type
        self.importance = importance
        self.related_persons = related_persons


async def fetch_active_insights(
    db: AsyncSession,
    user_id: UUID,
) -> List[ActiveInsightRow]:
    """Query active insights for a user with related person names.

    Returns ActiveInsightRow objects that include person names from
    insight_entities JOIN members, so the LLM can make informed
    KEEP/UPDATE/NEW decisions for person-specific insights.
    """
    # Step 1: fetch base insight rows
    base_stmt = (
        select(Insight.id, Insight.title, Insight.insight_type, Insight.importance)
        .where(
            and_(
                Insight.user_id == user_id,
                Insight.status.in_(list(ACTIVE_STATUSES)),
            )
        )
        .order_by(Insight.importance.desc())
        .limit(30)
    )
    base_result = await db.execute(base_stmt)
    base_rows = base_result.all()

    if not base_rows:
        return []

    insight_ids = [row.id for row in base_rows]

    # Step 2: fetch person names for these insights via insight_entities + members
    person_stmt = (
        select(
            InsightEntity.insight_id,
            Member.name,
        )
        .join(
            Member,
            and_(
                InsightEntity.entity_type == "person",
                InsightEntity.entity_id == Member.id,
            ),
        )
        .where(InsightEntity.insight_id.in_(insight_ids))
    )
    person_result = await db.execute(person_stmt)
    person_rows = person_result.all()

    # Group person names by insight_id
    persons_by_insight: Dict[UUID, List[str]] = {}
    for row in person_rows:
        persons_by_insight.setdefault(row.insight_id, []).append(row.name)

    # Step 3: assemble ActiveInsightRow objects
    return [
        ActiveInsightRow(
            id=row.id,
            title=row.title,
            insight_type=row.insight_type,
            importance=row.importance,
            related_persons=sorted(persons_by_insight.get(row.id, [])),
        )
        for row in base_rows
    ]


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def _sanitize_title(title: str) -> str:
    """Sanitize title: strip <>, backticks, newlines; truncate to 20 chars."""
    cleaned = re.sub(r"[<>`\n\r]", "", title)
    return cleaned[:20]


def _estimate_tokens(text: str) -> float:
    """Rough token estimation: len / 3.5 * 1.2 overhead."""
    return len(text) / _CHARS_PER_TOKEN * _OVERHEAD_FACTOR


def format_active_insights_for_prompt(rows: list) -> str:
    """Format active insight rows compactly within ~1500 token budget.

    Each row is formatted as a JSON object with id, title, type, importance,
    and related person names (when available) so the LLM can identify
    person-specific duplicates.
    Lowest-importance items are dropped first if over budget.
    """
    if not rows:
        return ""

    # Sort by importance DESC (should already be, but ensure)
    sorted_rows = sorted(rows, key=lambda r: r.importance, reverse=True)

    items: List[str] = []
    total_tokens = 0.0

    for row in sorted_rows:
        entry_dict: Dict[str, Any] = {
            "id": str(row.id),
            "title": _sanitize_title(row.title),
            "type": row.insight_type,
            "imp": row.importance,
        }
        # Include related person names when available
        related_persons = getattr(row, "related_persons", None)
        if related_persons:
            entry_dict["persons"] = related_persons

        entry = json.dumps(entry_dict, ensure_ascii=False)
        entry_tokens = _estimate_tokens(entry)

        if total_tokens + entry_tokens > _TOKEN_BUDGET:
            break  # drop remaining (lowest importance)

        items.append(entry)
        total_tokens += entry_tokens

    if not items:
        return ""

    return "\n".join(items)


def build_dedup_aware_prompt_section(rows: list) -> str:
    """Build the full prompt section with instructions, or empty string if no rows."""
    formatted = format_active_insights_for_prompt(rows)
    if not formatted:
        return ""

    return (
        "\n\n## 现有活跃洞察（去重参考）\n"
        "以下是用户当前已有的活跃洞察。persons 字段标明该洞察关联的人物。"
        "请对每条输出标注 disposition 字段:\n"
        '- "KEEP": 该洞察仍然有效，无需变更（需提供 existing_id）\n'
        '- "UPDATE": 该洞察需要更新内容（需提供 existing_id 和新的 content/importance/urgency 等）\n'
        '- "DELETE": 该洞察已过时或与其他洞察重复，应删除（需提供 existing_id，title/content 可为空）\n'
        '- "NEW": 全新洞察（默认，无需 existing_id）\n'
        "**重要**:\n"
        "- 同一主题的多条洞察应合并为一条 UPDATE，其余标记为 DELETE\n"
        "- 不要为同一主题的不同人物分别生成独立洞察\n"
        "- 必须对每条现有洞察做出明确处置（KEEP/UPDATE/DELETE），不要遗漏\n\n"
        f"{formatted}\n"
    )


# ---------------------------------------------------------------------------
# Disposition processing
# ---------------------------------------------------------------------------


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid_mod.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def process_dispositions(
    candidates: List[InsightCandidate],
) -> DispositionResult:
    """Split candidates into new, update, keep, and delete groups.

    Validation rules:
    - Invalid UUID existing_id -> downgrade to NEW
    - KEEP with missing existing_id -> downgrade to NEW
    - UPDATE with empty content -> downgrade to KEEP
    - DELETE with missing existing_id -> silently ignore
    - Unknown disposition -> default to NEW
    - Duplicate existing_ids in UPDATEs -> last-write-wins
    """
    new_candidates: List[InsightCandidate] = []
    update_map: Dict[str, Dict[str, Any]] = {}  # existing_id -> spec (last-write-wins)
    keep_ids: List[str] = []
    delete_ids: List[str] = []

    for candidate in candidates:
        disposition = candidate.disposition.upper() if candidate.disposition else "NEW"
        existing_id = candidate.existing_id

        if disposition == "KEEP":
            if not existing_id or not _is_valid_uuid(existing_id):
                new_candidates.append(replace(candidate, disposition="NEW"))
                continue
            keep_ids.append(existing_id)

        elif disposition == "UPDATE":
            if not existing_id or not _is_valid_uuid(existing_id):
                new_candidates.append(replace(candidate, disposition="NEW"))
                continue

            if not candidate.content or not candidate.content.strip():
                logger.debug("UPDATE with empty content downgraded to KEEP: %s", existing_id)
                keep_ids.append(existing_id)
                continue

            update_map[existing_id] = {
                "existing_id": existing_id,
                "content": candidate.content,
                "importance": candidate.importance,
                "urgency": candidate.urgency,
                "action_options": candidate.action_options,
                "suggested_action": candidate.suggested_action,
            }

        elif disposition == "DELETE":
            if existing_id and _is_valid_uuid(existing_id):
                delete_ids.append(existing_id)

        else:
            # NEW or unknown disposition
            new_candidates.append(replace(candidate, disposition="NEW"))

    logger.info(
        "Disposition split: new=%d update=%d keep=%d delete=%d",
        len(new_candidates),
        len(update_map),
        len(keep_ids),
        len(delete_ids),
    )

    return DispositionResult(
        new_candidates=new_candidates,
        update_specs=list(update_map.values()),
        keep_ids=keep_ids,
        delete_ids=delete_ids,
    )


# ---------------------------------------------------------------------------
# DB updates
# ---------------------------------------------------------------------------


async def apply_updates(
    db: AsyncSession,
    user_id: UUID,
    update_specs: List[Dict[str, Any]],
) -> List[str]:
    """Execute individual UPDATEs with WHERE id=X AND user_id=Y AND status IN ACTIVE_STATUSES.

    Updates: content, importance, urgency, action_options, suggested_action.
    Returns list of successfully updated insight IDs.
    """
    if not update_specs:
        return []

    updated_ids: List[str] = []

    for spec in update_specs:
        try:
            stmt = (
                update(Insight)
                .where(
                    and_(
                        Insight.id == spec["existing_id"],
                        Insight.user_id == user_id,
                        Insight.status.in_(list(ACTIVE_STATUSES)),
                    )
                )
                .values(
                    content=spec["content"],
                    importance=spec["importance"],
                    urgency=spec["urgency"],
                    action_options=spec["action_options"],
                    suggested_action=spec["suggested_action"],
                )
            )
            result = await db.execute(stmt)

            if result.rowcount > 0:
                updated_ids.append(spec["existing_id"])
                logger.info(
                    "Updated insight %s for user %s",
                    spec["existing_id"],
                    user_id,
                )
            else:
                logger.warning(
                    "Update matched 0 rows for insight %s user %s",
                    spec["existing_id"],
                    user_id,
                )
        except Exception as exc:
            logger.error(
                "Failed to update insight %s: %s",
                spec["existing_id"],
                exc,
            )

    return updated_ids


async def expire_unreferenced_insights(
    db: AsyncSession,
    user_id: UUID,
    active_ids: List[UUID],
    referenced_ids: List[str],
) -> int:
    """Expire active insights that the LLM did not reference (KEEP/UPDATE/DELETE).

    After the LLM processes all active insights and outputs dispositions,
    any active insight NOT referenced is considered no longer relevant.
    This prevents stale insights (e.g., per-person duplicates from old
    rule engine) from lingering indefinitely.

    Args:
        active_ids: IDs of all insights that were shown to the LLM.
        referenced_ids: IDs the LLM explicitly referenced (KEEP + UPDATE + DELETE).

    Returns:
        Number of insights expired.
    """
    unreferenced = [
        aid for aid in active_ids
        if str(aid) not in referenced_ids
    ]
    if not unreferenced:
        return 0

    stmt = (
        update(Insight)
        .where(
            and_(
                Insight.id.in_(unreferenced),
                Insight.user_id == user_id,
                Insight.status.in_(list(ACTIVE_STATUSES)),
            )
        )
        .values(
            status=InsightStatus.EXPIRED.value,
            feedback_source="llm_disposition_gc",
        )
    )
    result = await db.execute(stmt)
    count = result.rowcount

    if count > 0:
        logger.info(
            "Expired %d unreferenced insights for user %s (of %d shown to LLM)",
            count, user_id, len(active_ids),
        )

    return count
