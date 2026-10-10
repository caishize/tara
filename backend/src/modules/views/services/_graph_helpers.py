"""Graph construction helper functions.

Pure functions extracted from EventGraphService to keep the main
service file under the 800-line limit and improve testability.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ...curation.models import CuratedEvent


# -- Priority type sets (frozen for O(1) lookup) ---

_MUST_DO_TYPES = frozenset({"task", "reminder"})
_CONVENIENT_TYPES = frozenset({"person", "place", "gift"})
_BACKGROUND_TYPES = frozenset({"date", "memory"})

_TYPE_ACTIONS: Dict[str, List[str]] = {
    "person": ["send_greeting", "view_profile"],
    "favor": ["send_gift", "mark_done"],
    "task": ["mark_done", "set_reminder"],
    "reminder": ["snooze", "mark_done"],
    "meeting": ["navigate", "set_reminder", "add_to_trip"],
    "travel": ["navigate", "check_weather", "view_details"],
    "appointment": ["navigate", "set_reminder", "add_to_trip"],
    "place": ["navigate", "check_weather", "add_to_trip", "view_details"],
    "gift": ["send_gift", "view_details"],
    "date": ["set_reminder", "view_details"],
    "memory": ["view_details"],
}

_EVENT_ICON_MAP: Dict[str, str] = {
    "business_trip": "\U0001f4bc",
    "travel": "\u2708\ufe0f",
    "meeting": "\U0001f91d",
    "appointment": "\U0001f4cb",
    "reminder": "\u23f0",
    "birthday": "\U0001f382",
    "anniversary": "\U0001f48d",
    "holiday": "\U0001f389",
}


def determine_layer(
    priority: str,
    target_type: str,
    association_type: str = "",
) -> str:
    """Determine which graph layer a node belongs to.

    Layers: must_do, convenient, background.
    """
    if priority == "strongly_recommend":
        return "must_do"
    if priority == "convenient":
        return "convenient"
    if priority == "optional":
        return "background"

    if target_type in _MUST_DO_TYPES:
        return "must_do"
    if target_type in _CONVENIENT_TYPES:
        return "convenient"
    if target_type in _BACKGROUND_TYPES:
        return "background"
    return "convenient"


def actions_for_node(
    node_type: str,
    layer: str,
    is_confirmed: bool,
) -> List[str]:
    """Determine available actions based on node type and layer."""
    actions: List[str] = []

    if not is_confirmed and layer in ("must_do", "convenient"):
        actions.append("confirm")
        actions.append("dismiss")

    actions.extend(_TYPE_ACTIONS.get(node_type, ["view_details"]))
    return actions


def calc_preparation_progress(event: CuratedEvent) -> Optional[dict]:
    """Calculate preparation item progress for an event."""
    rows = event.preparation_item_rows
    if not rows:
        return None
    total = len(rows)
    done = sum(1 for row in rows if row.done)
    return {"done": done, "total": total}


def get_event_icon(event_type: Optional[str]) -> str:
    """Return an icon character for the given event type."""
    return _EVENT_ICON_MAP.get(event_type or "", "\U0001f4cc")
