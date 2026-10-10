"""Helpers for normalizing curation event types."""

from typing import Optional

from ..schemas import EventType


_SUPPORTED_EVENT_TYPES = {event_type.value for event_type in EventType}

# Aliases from upstream sources/LLM output to canonical curation event types.
_EVENT_TYPE_ALIASES = {
    "holiday_lunar": "holiday",
}

_IMPORTANT_DATE_TYPE_MAPPING = {
    "birthday": "birthday",
    "anniversary": "anniversary",
    "memorial": "anniversary",
    "holiday": "holiday",
    "holiday_solar_term": "holiday_solar_term",
    "solar_term": "solar_term",
    "holiday_lunar": "holiday_lunar",
    "custom": "reminder",
}


def normalize_event_type(event_type: Optional[str], default: str = "other") -> str:
    """Normalize arbitrary event type input into supported curation types."""
    normalized = str(event_type or "").strip().lower()
    if not normalized:
        return default
    if normalized in _SUPPORTED_EVENT_TYPES:
        return normalized
    alias = _EVENT_TYPE_ALIASES.get(normalized)
    if alias and alias in _SUPPORTED_EVENT_TYPES:
        return alias
    return default


def map_important_date_type(date_type: Optional[str]) -> str:
    """Map date-manager date types into curated event types."""
    normalized_date_type = str(date_type or "").strip().lower()
    mapped_type = _IMPORTANT_DATE_TYPE_MAPPING.get(normalized_date_type, "other")
    return normalize_event_type(mapped_type, default="other")
