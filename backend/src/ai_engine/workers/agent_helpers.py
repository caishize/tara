"""
Helper functions extracted from agent_worker.py to keep files under 800 lines.

Contains:
- Card enrichment: extract_card_enrichment() and CARD_INTENT_PRIORITY
- Pending action creation: create_pending_action()
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ...core.pubsub import RedisPubSubManager
from ...modules.conversation.display_builder import build_display_data
from ..queue import TaskPayload

logger = logging.getLogger(__name__)


# ── Card Enrichment ─────────────────────────────────────────────────

# Intent priority used when multiple card-producing tools are present.
# Higher = more likely to be the primary card.  Travel and event cards
# are typically the main answer; tasks/members are often supplementary.
CARD_INTENT_PRIORITY: Dict[str, int] = {
    "plan_smart_trip": 10,
    "trip_itinerary": 10,
    "travel_itinerary": 10,
    "event_card": 8,
    "recommend_gift": 7,
    "upcoming_dates": 6,
    "favor_balance": 5,
    "task_card": 3,
    "member_profile": 3,
}


def extract_card_enrichment(
    collected_tool_calls: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Pick the most relevant card-producing tool result.

    Instead of blindly picking the *last* card tool ("last tool wins"),
    we collect all successful card-producing calls and select by intent
    priority.  When there is only one candidate we use it directly.

    Returns a dict with ``intent``, ``data``, and ``quick_actions`` keys
    suitable for inclusion in the PubSub COMPLETE payload, or None.
    """
    from ...modules.conversation.card_normalizer import (
        TOOL_CARD_MAP,
        CARD_QUICK_ACTIONS,
        normalize_query_trips_data,
        normalize as _normalize_card,
    )

    candidates: List = []  # (order, tool_name, intent, result)
    for order, tc in enumerate(collected_tool_calls):
        if tc.get("status") != "success":
            continue
        tool_name = tc.get("tool_name", "")
        card_intent = TOOL_CARD_MAP.get(tool_name)
        if card_intent is None:
            continue
        full_result = tc.get("full_result")
        if full_result is None:
            continue
        candidates.append((order, tool_name, card_intent, full_result))

    if not candidates:
        return None

    # Pick the candidate with the highest intent priority
    _, best_tool, best_intent, best_result = max(
        candidates,
        key=lambda c: (CARD_INTENT_PRIORITY.get(c[2], 1), c[0]),
    )

    if best_tool == "query_trips":
        best_intent, best_result = normalize_query_trips_data(best_result)

    normalized = _normalize_card(best_tool, best_result)

    enrichment: Dict[str, Any] = {
        "card_type": best_intent,
        "intent": best_intent,
        "data": best_result,
        "quick_actions": CARD_QUICK_ACTIONS.get(best_intent, []),
    }
    if normalized is not None:
        enrichment["normalized_card"] = normalized.to_dict()

    return enrichment


# ── Pending Action Creation ─────────────────────────────────────────


async def create_pending_action(
    db,
    task: TaskPayload,
    tool_name: str,
    tool_input: Dict[str, Any],
    pubsub: RedisPubSubManager,
    action_ttl_minutes: int = 15,
) -> str:
    """Create a pending action for user confirmation.

    Parameters
    ----------
    db : AsyncSession
        Database session for persisting the action.
    task : TaskPayload
        Current task with user/family/job context.
    tool_name : str
        Name of the sensitive tool being guarded.
    tool_input : dict
        Arguments passed to the tool.
    pubsub : RedisPubSubManager
        PubSub manager for publishing the confirm card.
    action_ttl_minutes : int
        Minutes until the action expires (default 15).

    Returns
    -------
    str
        Confirmation message indicating the action was created.
    """
    from ...modules.conversation.pending_action import PendingAction
    from ...core.utils.timezone import utc_now as _utc_now

    action_id = uuid4()
    expires_at = _utc_now() + timedelta(minutes=action_ttl_minutes)
    display_data = build_display_data(tool_name, tool_input)

    try:
        action = PendingAction(
            id=action_id,
            user_id=UUID(task.user_id),
            family_id=UUID(task.family_id),
            job_id=UUID(task.job_id) if task.job_id else None,
            action_type=tool_name,
            payload=tool_input,
            display_data=display_data,
            status="pending",
            expires_at=expires_at,
        )
        db.add(action)
        await db.commit()
    except Exception as e:
        logger.error("Failed to create pending action: %s", e)
        raise

    await pubsub.publish_confirm_card(
        user_id=task.user_id,
        action_id=str(action_id),
        action_type=tool_name,
        display_data=display_data,
        trace_id=task.job_id,
    )

    return f"已创建待确认操作 (ID: {action_id})。请用户在App中确认后执行。"
