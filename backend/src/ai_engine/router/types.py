"""
Router types and data structures.

Two-axis classification system:
- Axis 1: Difficulty (immediate/thinking) -> maps to route
- Axis 2: ActionType (lookup/create/greet/chat/weather/time/plan/analyze/transact)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RouteType(str, Enum):
    """
    Route types for bi-modal routing.

    FAST: Direct response without agent reasoning (80% of traffic)
    SLOW: Queue for deep processing (20% of traffic)
    HYBRID: Fast response + background enhancement
    """
    FAST = "fast"
    SLOW = "slow"
    HYBRID = "hybrid"


# ---- Axis 1: Difficulty ----

class Difficulty(str, Enum):
    """How hard is this request to fulfill?"""
    IMMEDIATE = "immediate"
    THINKING = "thinking"
    UNSURE = "unsure"


# ---- Axis 2: Action Type ----

class ActionType(str, Enum):
    """What kind of action does the user want?"""
    LOOKUP = "lookup"
    CREATE = "create"
    GREET = "greet"
    CHAT = "chat"
    WEATHER = "weather"
    TIME = "time"
    PLAN = "plan"
    ANALYZE = "analyze"
    TRANSACT = "transact"


# ---- Lookup Target (sub-classification for lookup action) ----

class LookupTarget(str, Enum):
    """What data is the user looking up?"""
    TASK = "task"
    REMINDER = "reminder"
    SCHEDULE = "schedule"
    TRIP = "trip"
    MEMBER = "member"
    TODAY = "today"
    UNKNOWN = "unknown"


# ---- IntentCategory (used for streaming event typing) ----

class IntentCategory(str, Enum):
    """Categories of user intent used in streaming events."""
    # Fast Path intents
    GREETING = "greeting"
    SIMPLE_QA = "simple_qa"
    WEATHER_QUERY = "weather_query"
    TIME_QUERY = "time_query"
    DATA_LOOKUP = "data_lookup"
    CASUAL_CHAT = "casual_chat"

    # Slow Path intents
    TRIP_PLANNING = "trip_planning"
    SCHEDULE_PLANNING = "schedule_planning"
    GIFT_RECOMMENDATION = "gift_recommendation"
    CONFLICT_RESOLUTION = "conflict_resolution"
    COMPLEX_ANALYSIS = "complex_analysis"
    TASK_CREATION = "task_creation"
    PURCHASE_REQUEST = "purchase_request"
    BOOKING_REQUEST = "booking_request"

    # Hybrid intents (fast response + background)
    WEATHER_WITH_ADVICE = "weather_with_advice"
    SCHEDULE_WITH_SUGGESTIONS = "schedule_with_suggestions"
    REMINDER_WITH_CONTEXT = "reminder_with_context"

    # Unknown
    UNKNOWN = "unknown"


# ---- Route Maps ----

DIFFICULTY_ROUTE_MAP = {
    Difficulty.IMMEDIATE: RouteType.FAST,
    Difficulty.THINKING: RouteType.SLOW,
    Difficulty.UNSURE: RouteType.SLOW,
}

CATEGORY_ROUTE_MAP = {
    IntentCategory.GREETING: RouteType.FAST,
    IntentCategory.SIMPLE_QA: RouteType.FAST,
    IntentCategory.WEATHER_QUERY: RouteType.FAST,
    IntentCategory.TIME_QUERY: RouteType.FAST,
    IntentCategory.DATA_LOOKUP: RouteType.FAST,
    IntentCategory.CASUAL_CHAT: RouteType.FAST,
    IntentCategory.TRIP_PLANNING: RouteType.SLOW,
    IntentCategory.SCHEDULE_PLANNING: RouteType.SLOW,
    IntentCategory.GIFT_RECOMMENDATION: RouteType.SLOW,
    IntentCategory.CONFLICT_RESOLUTION: RouteType.SLOW,
    IntentCategory.COMPLEX_ANALYSIS: RouteType.SLOW,
    IntentCategory.TASK_CREATION: RouteType.SLOW,
    IntentCategory.PURCHASE_REQUEST: RouteType.SLOW,
    IntentCategory.BOOKING_REQUEST: RouteType.SLOW,
    IntentCategory.WEATHER_WITH_ADVICE: RouteType.HYBRID,
    IntentCategory.SCHEDULE_WITH_SUGGESTIONS: RouteType.HYBRID,
    IntentCategory.REMINDER_WITH_CONTEXT: RouteType.HYBRID,
    IntentCategory.UNKNOWN: RouteType.SLOW,
}

# Tools typically needed by each category
CATEGORY_TOOLS_MAP = {
    IntentCategory.WEATHER_QUERY: ["get_weather"],
    IntentCategory.TIME_QUERY: [],
    IntentCategory.DATA_LOOKUP: [
        "search_events",
        "query_tasks",
        "query_members",
        "query_trips",
        "search_memory",
    ],
    IntentCategory.TRIP_PLANNING: [
        "query_trips",
        "add_trip_itinerary",
        "update_trip",
        "web_search",
    ],
    IntentCategory.GIFT_RECOMMENDATION: [
        "query_members",
        "recommend_gift",
        "web_search",
    ],
    IntentCategory.TASK_CREATION: ["create_task", "set_reminder"],
    IntentCategory.PURCHASE_REQUEST: ["call_mcp_tool"],
    IntentCategory.BOOKING_REQUEST: ["query_trip_bookings", "call_mcp_tool"],
}

# Sensitive actions that require confirmation
SENSITIVE_ACTIONS = {
    "purchase",
    "book_ticket",
    "transfer",
    "cancel_booking",
    "delete_event",
    "send_message",
}


# ---- Two-axis to category mapping ----

_ACTION_TO_CATEGORY = {
    (Difficulty.IMMEDIATE, ActionType.GREET): IntentCategory.GREETING,
    (Difficulty.IMMEDIATE, ActionType.CHAT): IntentCategory.CASUAL_CHAT,
    (Difficulty.IMMEDIATE, ActionType.WEATHER): IntentCategory.WEATHER_QUERY,
    (Difficulty.IMMEDIATE, ActionType.TIME): IntentCategory.TIME_QUERY,
    (Difficulty.IMMEDIATE, ActionType.LOOKUP): IntentCategory.DATA_LOOKUP,
    (Difficulty.THINKING, ActionType.PLAN): IntentCategory.TRIP_PLANNING,
    (Difficulty.THINKING, ActionType.CREATE): IntentCategory.TASK_CREATION,
    (Difficulty.THINKING, ActionType.ANALYZE): IntentCategory.COMPLEX_ANALYSIS,
    (Difficulty.THINKING, ActionType.TRANSACT): IntentCategory.PURCHASE_REQUEST,
}


def map_to_intent_category(difficulty: Difficulty, action: ActionType, enhance: bool) -> IntentCategory:
    """Map (difficulty, action, enhance) to IntentCategory for stream compatibility."""
    if enhance and action == ActionType.WEATHER:
        return IntentCategory.WEATHER_WITH_ADVICE
    if enhance and action == ActionType.LOOKUP:
        return IntentCategory.SCHEDULE_WITH_SUGGESTIONS

    return _ACTION_TO_CATEGORY.get(
        (difficulty, action),
        IntentCategory.UNKNOWN,
    )


def resolve_route(difficulty: Difficulty, enhance: bool) -> RouteType:
    """Resolve route from two-axis classification."""
    if difficulty == Difficulty.IMMEDIATE and enhance:
        return RouteType.HYBRID
    return DIFFICULTY_ROUTE_MAP.get(difficulty, RouteType.SLOW)


@dataclass(frozen=True)
class IntentClassification:
    """
    Result of intent classification.

    Primary fields (two-axis):
        difficulty: How hard the request is (immediate/thinking)
        action: What kind of action (lookup/create/greet/...)
        enhance: Whether background enhancement is needed (triggers HYBRID)
        lookup_target: What data to look up (when action=lookup)
        lookup_filter: Filter condition (e.g. city name for trip)

    Derived fields:
        route_type: Determined route (FAST, SLOW, HYBRID)
        intent_category: Category for stream event types
        confidence: Classification confidence (0-1)
    """
    route_type: RouteType
    intent_category: IntentCategory
    confidence: float

    # Two-axis fields
    difficulty: Difficulty = Difficulty.UNSURE
    action: ActionType = ActionType.CHAT
    enhance: bool = False
    lookup_target: Optional[LookupTarget] = None
    lookup_filter: Optional[str] = None

    # Skill hint — populated by SkillRegistry.resolve()
    skill_hint: Optional[str] = None

    # Supplementary fields
    implicit_needs: List[str] = field(default_factory=list)
    requires_tools: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    reasoning: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "route_type": self.route_type.value,
            "intent_category": self.intent_category.value,
            "confidence": self.confidence,
            "difficulty": self.difficulty.value,
            "action": self.action.value,
            "enhance": self.enhance,
            "lookup_target": self.lookup_target.value if self.lookup_target else None,
            "lookup_filter": self.lookup_filter,
            "implicit_needs": self.implicit_needs,
            "requires_tools": self.requires_tools,
            "requires_confirmation": self.requires_confirmation,
            "reasoning": self.reasoning,
            "skill_hint": self.skill_hint,
        }
