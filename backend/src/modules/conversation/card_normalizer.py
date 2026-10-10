"""Card data normalizer for standardizing tool results into UI cards.

Transforms raw tool result data into a consistent NormalizedCard structure
that the Flutter client can render without tool-specific knowledge.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Tool name -> UI card intent mapping
# ---------------------------------------------------------------------------
TOOL_CARD_MAP: Dict[str, Optional[str]] = {
    "query_tasks": "task_card",
    "create_task": "task_card",
    "complete_task": "task_card",
    "update_task": "task_card",
    "search_events": "event_card",
    "create_event": "event_card",
    "update_event": "event_card",
    "query_members": "member_profile",
    "get_member_details": "member_profile",
    "query_trips": "trip_itinerary",
    "add_trip_itinerary": "trip_itinerary",
    "update_trip": "trip_itinerary",
    "create_trip": "trip_itinerary",
    "query_upcoming_dates": "upcoming_dates",
    "recommend_gift": "recommend_gift",
    "record_favor": "favor_balance",
    "check_favor_balance": "favor_balance",
    "get_weather": None,
}

CARD_PRODUCING_TOOLS: frozenset = frozenset(
    name for name, intent in TOOL_CARD_MAP.items() if intent is not None
)

# ---------------------------------------------------------------------------
# Predefined quick actions per card intent
# ---------------------------------------------------------------------------
CARD_QUICK_ACTIONS: Dict[str, List[dict]] = {
    "event_card": [
        {"label": "调整日期", "action": "帮我调整这个日程的时间", "type": "navigate", "icon": "calendar_month"},
        {"label": "取消日程", "action": "帮我取消这个日程", "type": "message", "icon": "cancel", "variant": "destructive"},
    ],
    "task_card": [
        {"label": "查看全部", "action": "帮我查看所有待办任务", "type": "message", "icon": "list_alt"},
        {"label": "新建任务", "action": "帮我新建一个任务", "type": "message", "icon": "add_task"},
    ],
    "member_profile": [
        {"label": "更新信息", "action": "帮我更新这个家人的信息", "type": "navigate", "icon": "edit"},
        {"label": "查看偏好", "action": "查看这个家人的偏好", "type": "navigate", "icon": "favorite"},
    ],
    "plan_smart_trip": [
        {"label": "加入行程", "action": "帮我把这个行程加入日程", "type": "message", "icon": "flight_takeoff", "variant": "primary"},
        {"label": "调整计划", "action": "帮我调整这个旅行计划", "type": "message", "icon": "edit_calendar"},
    ],
    "trip_itinerary": [
        {"label": "查看行程", "action": "帮我查看这个旅行的完整行程", "type": "navigate", "icon": "map", "variant": "primary"},
        {"label": "调整行程", "action": "帮我调整这个行程安排", "type": "message", "icon": "edit_calendar"},
    ],
    "recommend_gift": [
        {"label": "查看详情", "action": "帮我看看这个礼物的详情", "type": "message", "icon": "card_giftcard"},
        {"label": "换个推荐", "action": "帮我换一些礼物推荐", "type": "message", "icon": "refresh"},
    ],
    "upcoming_dates": [
        {"label": "添加日期", "action": "帮我添加一个重要日期", "type": "message", "icon": "event"},
        {"label": "查看详情", "action": "帮我查看近期日期详情", "type": "message", "icon": "info"},
    ],
    "favor_balance": [
        {"label": "记录人情", "action": "帮我记录一笔人情", "type": "message", "icon": "handshake"},
        {"label": "回报建议", "action": "/relationships/favors", "type": "navigate", "icon": "lightbulb"},
    ],
}


def normalize_query_trips_data(tool_data: dict) -> Tuple[str, dict]:
    """For query_trips, extract first trip for card display."""
    trips = tool_data.get("trips", [])
    if not trips:
        return "trip_itinerary", tool_data

    first = trips[0]
    normalized = {
        **tool_data,
        "trip_name": first.get("title") or first.get("trip_name", ""),
        "title": first.get("title") or first.get("trip_name", ""),
        "destination": first.get("location") or first.get("destination") or first.get("title", ""),
        "trip_id": first.get("id"),
        "start_date": first.get("start_date"),
        "end_date": first.get("end_date"),
        "status": first.get("status"),
    }
    return "trip_itinerary", normalized


def _extract_entity_metadata(
    card_intent: str, tool_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Extract entity IDs from tool_data based on card intent."""
    if card_intent in ("trip_itinerary", "plan_smart_trip"):
        trip_id = tool_data.get("trip_id") or tool_data.get("id")
        if trip_id is not None:
            return {"trip_id": str(trip_id)}
    elif card_intent == "event_card":
        event_id = tool_data.get("event_id") or tool_data.get("id")
        if event_id is not None:
            return {"event_id": str(event_id)}
    elif card_intent == "member_profile":
        member_id = tool_data.get("member_id") or tool_data.get("id")
        if member_id is not None:
            return {"member_id": str(member_id)}
    return None


def _build_quick_actions_with_metadata(
    card_intent: str, tool_data: Dict[str, Any]
) -> List[dict]:
    """Build quick actions list with entity metadata injected."""
    templates = CARD_QUICK_ACTIONS.get(card_intent, [])
    metadata = _extract_entity_metadata(card_intent, tool_data)
    if not metadata:
        return list(templates)
    return [{**a, "metadata": metadata} for a in templates]


def enrich_done_event(
    done_event: Dict,
    card_tool_result: Optional[Tuple[str, dict]],
) -> None:
    """Add card intent, data and quick actions to *done_event* in-place."""
    if card_tool_result is None:
        return
    tool_name, tool_data = card_tool_result
    card_intent = TOOL_CARD_MAP.get(tool_name)
    if card_intent is None:
        return

    if tool_name == "query_trips":
        card_intent, tool_data = normalize_query_trips_data(tool_data)

    done_event["card_type"] = card_intent
    done_event["intent"] = card_intent
    done_event["data"] = tool_data
    done_event["quick_actions"] = _build_quick_actions_with_metadata(
        card_intent, tool_data
    )

    normalized = normalize(tool_name, tool_data)
    if normalized is not None:
        done_event["normalized_card"] = normalized.to_dict()


# ---------------------------------------------------------------------------
# NormalizedCard
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedCard:
    """Standardized card structure for the Flutter client."""

    card_type: str
    title: str
    subtitle: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sections: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "card_type": self.card_type,
            "title": self.title,
        }
        if self.subtitle is not None:
            result["subtitle"] = self.subtitle
        if self.icon is not None:
            result["icon"] = self.icon
        if self.color is not None:
            result["color"] = self.color
        if self.sections:
            result["sections"] = self.sections
        if self.actions:
            result["actions"] = self.actions
        if self.raw_data:
            result["raw_data"] = self.raw_data
        return result


# Intent -> default card metadata
_CARD_DEFAULTS: Dict[str, Dict[str, str]] = {
    "event_card": {"icon": "event", "color": "#2196F3"},
    "task_card": {"icon": "task_alt", "color": "#4CAF50"},
    "member_profile": {"icon": "person", "color": "#9C27B0"},
    "plan_smart_trip": {"icon": "flight_takeoff", "color": "#FF9800"},
    "trip_itinerary": {"icon": "map", "color": "#FF9800"},
    "recommend_gift": {"icon": "card_giftcard", "color": "#E91E63"},
    "upcoming_dates": {"icon": "calendar_month", "color": "#00BCD4"},
    "favor_balance": {"icon": "handshake", "color": "#795548"},
}


def _extract_title(card_intent: str, data: Dict[str, Any]) -> str:
    if card_intent in ("event_card",):
        return data.get("title") or data.get("event_title") or data.get("name") or "日程"
    if card_intent in ("task_card",):
        return data.get("title") or data.get("task_title") or data.get("name") or "任务"
    if card_intent == "member_profile":
        return data.get("name") or data.get("nickname") or "家人"
    if card_intent in ("plan_smart_trip", "trip_itinerary"):
        return (
            data.get("trip_name")
            or data.get("title")
            or data.get("destination")
            or data.get("location")
            or "旅行"
        )
    if card_intent == "recommend_gift":
        return data.get("name") or data.get("gift_name") or "礼物推荐"
    if card_intent == "upcoming_dates":
        return "近期重要日期"
    if card_intent == "favor_balance":
        return data.get("person_name") or "人情往来"
    return data.get("title", "")


def _extract_subtitle(card_intent: str, data: Dict[str, Any]) -> Optional[str]:
    if card_intent in ("event_card",):
        start = data.get("start_time") or data.get("start_date") or ""
        location = data.get("location") or ""
        parts = [p for p in [start, location] if p]
        return " · ".join(parts) if parts else None
    if card_intent in ("plan_smart_trip", "trip_itinerary"):
        start = data.get("start_date") or ""
        end = data.get("end_date") or ""
        if start and end:
            return f"{start} ~ {end}"
        return start or None
    if card_intent == "member_profile":
        return data.get("relationship") or data.get("role")
    return None


def normalize(
    tool_name: str, raw_data: Dict[str, Any]
) -> Optional[NormalizedCard]:
    """Normalize a tool result into a NormalizedCard."""
    card_intent = TOOL_CARD_MAP.get(tool_name)
    if card_intent is None:
        return None

    data = dict(raw_data)

    if tool_name == "query_trips":
        card_intent, data = normalize_query_trips_data(data)

    defaults = _CARD_DEFAULTS.get(card_intent, {})
    actions = CARD_QUICK_ACTIONS.get(card_intent, [])

    return NormalizedCard(
        card_type=card_intent,
        title=_extract_title(card_intent, data),
        subtitle=_extract_subtitle(card_intent, data),
        icon=defaults.get("icon"),
        color=defaults.get("color"),
        actions=list(actions),
        raw_data=data,
    )
