"""Shared models for the suggestion service and strategy classes."""
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from ....core.utils.timezone import utc_now


class SuggestionType(str, Enum):
    """Types of smart suggestions."""
    LOCATION_CORRELATION = "location_correlation"
    TIME_CORRELATION = "time_correlation"
    PERSON_CORRELATION = "person_correlation"
    HISTORY_CORRELATION = "history_correlation"
    PREPARATION_REMINDER = "preparation_reminder"
    ANNIVERSARY_REMINDER = "anniversary_reminder"
    GIFT_REMINDER = "gift_reminder"
    MEETUP_SUGGESTION = "meetup_suggestion"
    MEMORY_CORRELATION = "memory_correlation"
    PLAN_REMINDER = "plan_reminder"
    CURATION = "curation"
    # Life care types (caring mom features)
    WEATHER_CARE = "weather_care"
    MEAL_CARE = "meal_care"
    REST_CARE = "rest_care"
    FAMILY_GATHERING = "family_gathering"
    SEASONAL_CARE = "seasonal_care"


class SuggestionAction(str, Enum):
    """Possible actions for suggestions."""
    SCHEDULE_MEETING = "schedule_meeting"
    SEND_MESSAGE = "send_message"
    PREPARE_GIFT = "prepare_gift"
    BOOK_RESTAURANT = "book_restaurant"
    SET_REMINDER = "set_reminder"
    IGNORE = "ignore"
    VIEW_DETAILS = "view_details"
    CALL_FAMILY = "call_family"
    TAKE_BREAK = "take_break"
    NOTED = "noted"


class Suggestion(BaseModel):
    """Smart suggestion model."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: SuggestionType
    title: str
    content: str
    icon: str = "lightbulb"
    related_event_ids: List[str] = Field(default_factory=list)
    related_member_ids: List[str] = Field(default_factory=list)
    related_trip_ids: List[str] = Field(default_factory=list)
    action_options: List[str] = Field(default_factory=list)
    action_data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    urgency: str = "normal"
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Config:
        from_attributes = True
