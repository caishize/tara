"""Cold-start onboarding service — guided conversation for new users.

Implements V8 Brain section 9.1 progressive onboarding:

  Stage          Time      Strategy
  FIRST_CHAT     0-5 min   Secretary self-intro + natural chat to collect core info
  FIRST_DAY      0-24h     Passively extract from conversations, no proactive interruption
  FIRST_WEEK     1-7 days  1-2 small questions per day to enrich profile
  GRADUATED      7+ days   Full feature access, normal operation

Each step yields an OnboardingCard (frozen dataclass) that the front-end
renders as a welcome / question card.  Progress is tracked via a simple
Redis key so it survives restarts without requiring a DB table.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------


class OnboardingPhase(str, Enum):
    """Progressive onboarding phases (legacy, kept for backward compat)."""
    WELCOME = "welcome"
    FAMILY_BASICS = "family_basics"
    PREFERENCES = "preferences"
    ROUTINES = "routines"
    COMPLETED = "completed"


class OnboardingStage(str, Enum):
    """V8 design doc onboarding stages (section 9.1)."""
    FIRST_CHAT = "first_chat"    # 0-5 min: self-intro + collect core info
    FIRST_DAY = "first_day"      # 0-24h: passive extraction, no proactive interruption
    FIRST_WEEK = "first_week"    # 1-7 days: 1-2 small questions per day
    GRADUATED = "graduated"      # 7+ days: full operation


# Phase ordering for progression
_PHASE_ORDER: List[OnboardingPhase] = [
    OnboardingPhase.WELCOME,
    OnboardingPhase.FAMILY_BASICS,
    OnboardingPhase.PREFERENCES,
    OnboardingPhase.ROUTINES,
    OnboardingPhase.COMPLETED,
]

# Redis key prefix for onboarding progress
_REDIS_KEY_PREFIX = "onboarding:progress:"

# Default TTL for onboarding state (30 days)
_ONBOARDING_TTL_SECONDS = 30 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# Value objects (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingCard:
    """A single onboarding card to display to the user."""
    phase: str
    title: str
    content: str
    suggested_prompts: tuple  # Immutable list of suggested prompts
    progress_pct: int  # 0-100

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "title": self.title,
            "content": self.content,
            "suggested_prompts": list(self.suggested_prompts),
            "progress_pct": self.progress_pct,
        }


# ---------------------------------------------------------------------------
# Card templates
# ---------------------------------------------------------------------------


_CARD_TEMPLATES = {
    OnboardingPhase.WELCOME: OnboardingCard(
        phase=OnboardingPhase.WELCOME.value,
        title="Welcome to Secretary",
        content="I'm your family assistant. Let me help organize your family life. "
                "First, tell me about your family members.",
        suggested_prompts=(
            "My family has...",
            "I live with my spouse and two kids",
            "It's just me for now",
        ),
        progress_pct=0,
    ),
    OnboardingPhase.FAMILY_BASICS: OnboardingCard(
        phase=OnboardingPhase.FAMILY_BASICS.value,
        title="Tell me about your family",
        content="Who are the important people in your life? "
                "Share names, relationships, and any birthdays you'd like me to remember.",
        suggested_prompts=(
            "My mom's birthday is...",
            "My partner's name is...",
            "I have a daughter named...",
        ),
        progress_pct=25,
    ),
    OnboardingPhase.PREFERENCES: OnboardingCard(
        phase=OnboardingPhase.PREFERENCES.value,
        title="What matters to you?",
        content="Tell me about your preferences and habits so I can give better suggestions. "
                "What does your family enjoy?",
        suggested_prompts=(
            "We like to eat...",
            "On weekends we usually...",
            "My spouse is allergic to...",
        ),
        progress_pct=50,
    ),
    OnboardingPhase.ROUTINES: OnboardingCard(
        phase=OnboardingPhase.ROUTINES.value,
        title="Your daily routines",
        content="Tell me about your regular schedule. "
                "When do you wake up, commute, or have recurring commitments?",
        suggested_prompts=(
            "I usually wake up at...",
            "Kids go to school at...",
            "We have dinner around...",
        ),
        progress_pct=75,
    ),
}


# ---------------------------------------------------------------------------
# Welcome card (V8 design doc)
# ---------------------------------------------------------------------------

_WELCOME_CARD = {
    "title": "\u4f60\u597d\uff01\u6211\u662f\u4f60\u7684\u751f\u6d3b\u79d8\u4e66",
    "subtitle": "\u8d8a\u4e86\u89e3\u4f60\uff0c\u6211\u8d8a\u80fd\u5e2e\u5230\u4f60\u3002\u5148\u4ece\u4e00\u4ef6\u5c0f\u4e8b\u5f00\u59cb\uff1f",
    "quick_actions": [
        {
            "id": "family_birthday",
            "label": "\u544a\u8bc9\u6211\u5bb6\u4eba\u7684\u751f\u65e5",
            "icon": "cake",
        },
        {
            "id": "plan_trip",
            "label": "\u5e2e\u6211\u89c4\u5212\u4e00\u6b21\u51fa\u5dee",
            "icon": "flight",
        },
        {
            "id": "remember_something",
            "label": "\u8bb0\u4f4f\u4e00\u4e2a\u91cd\u8981\u7684\u4e8b",
            "icon": "bookmark",
        },
        {
            "id": "just_chat",
            "label": "\u968f\u4fbf\u804a\u804a",
            "icon": "chat",
        },
    ],
}


# ---------------------------------------------------------------------------
# Daily questions for FIRST_WEEK stage (1-2 per day)
# ---------------------------------------------------------------------------

_DAILY_QUESTIONS: List[dict] = [
    {
        "day": 1,
        "question": "\u4f60\u5bb6\u91cc\u6709\u51e0\u53e3\u4eba\uff1f\u90fd\u6709\u8c01\uff1f",
        "category": "family",
    },
    {
        "day": 2,
        "question": "\u5bb6\u91cc\u6709\u54ea\u4e9b\u91cd\u8981\u7684\u7eaa\u5ff5\u65e5\u6216\u751f\u65e5\u9700\u8981\u8bb0\u4f4f\uff1f",
        "category": "dates",
    },
    {
        "day": 3,
        "question": "\u4f60\u4eec\u5bb6\u5e73\u65f6\u559c\u6b22\u5403\u4ec0\u4e48\u7c7b\u578b\u7684\u9910\u5385\uff1f\u6709\u5fcc\u53e3\u5417\uff1f",
        "category": "preferences",
    },
    {
        "day": 4,
        "question": "\u5bb6\u91cc\u4eba\u7684\u65e5\u5e38\u4f5c\u606f\u5927\u6982\u662f\u600e\u6837\u7684\uff1f",
        "category": "routines",
    },
    {
        "day": 5,
        "question": "\u5468\u672b\u4f60\u4eec\u4e00\u822c\u559c\u6b22\u505a\u4ec0\u4e48\uff1f",
        "category": "preferences",
    },
    {
        "day": 6,
        "question": "\u5bb6\u4eba\u4eec\u5e73\u65f6\u6709\u4ec0\u4e48\u5174\u8da3\u7231\u597d\uff1f",
        "category": "preferences",
    },
    {
        "day": 7,
        "question": "\u6709\u6ca1\u6709\u4ec0\u4e48\u5b9a\u671f\u7684\u5b89\u6392\uff0c\u6bd4\u5982\u6bcf\u5468\u7684\u8bfe\u7a0b\u6216\u6d3b\u52a8\uff1f",
        "category": "routines",
    },
]


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def get_onboarding_card(phase: str) -> Optional[OnboardingCard]:
    """Return the card template for a given phase name.

    Returns None if the phase is 'completed' or unrecognized.
    """
    try:
        phase_enum = OnboardingPhase(phase)
    except ValueError:
        return None
    return _CARD_TEMPLATES.get(phase_enum)


def next_phase(current_phase: str) -> str:
    """Return the phase that follows the current one.

    If current is already completed or unrecognized, returns 'completed'.
    """
    try:
        current = OnboardingPhase(current_phase)
    except ValueError:
        return OnboardingPhase.COMPLETED.value

    idx = _PHASE_ORDER.index(current)
    if idx + 1 < len(_PHASE_ORDER):
        return _PHASE_ORDER[idx + 1].value
    return OnboardingPhase.COMPLETED.value


async def get_onboarding_step(
    user_id: UUID,
    redis_client=None,
) -> Optional[OnboardingCard]:
    """Determine the current onboarding step for a user.

    Reads progress from Redis.  If no key exists, the user is new
    and starts at WELCOME.  Returns None when onboarding is complete.

    Args:
        user_id: The user to check.
        redis_client: An async Redis client (optional; returns WELCOME
            card if not available).

    Returns:
        An OnboardingCard or None if onboarding is done.
    """
    key = f"{_REDIS_KEY_PREFIX}{user_id}"

    if redis_client is not None:
        try:
            current_phase = await redis_client.get(key)
            if current_phase is not None:
                current_phase = current_phase.decode() if isinstance(current_phase, bytes) else current_phase
            else:
                current_phase = OnboardingPhase.WELCOME.value
        except Exception:
            logger.warning("Redis unavailable for onboarding, defaulting to welcome", exc_info=True)
            current_phase = OnboardingPhase.WELCOME.value
    else:
        current_phase = OnboardingPhase.WELCOME.value

    return get_onboarding_card(current_phase)


async def advance_onboarding(
    user_id: UUID,
    redis_client=None,
) -> Optional[OnboardingCard]:
    """Advance the user to the next onboarding phase.

    Persists the new phase in Redis and returns the new card (or None
    if now completed).

    Args:
        user_id: The user to advance.
        redis_client: An async Redis client. If None, advancement is
            a no-op and returns None.

    Returns:
        The next OnboardingCard, or None if completed.
    """
    if redis_client is None:
        return None

    key = f"{_REDIS_KEY_PREFIX}{user_id}"

    try:
        current_phase = await redis_client.get(key)
        if current_phase is not None:
            current_phase = current_phase.decode() if isinstance(current_phase, bytes) else current_phase
        else:
            current_phase = OnboardingPhase.WELCOME.value

        new_phase = next_phase(current_phase)
        await redis_client.set(key, new_phase, ex=_ONBOARDING_TTL_SECONDS)
        return get_onboarding_card(new_phase)
    except Exception:
        logger.warning("Failed to advance onboarding phase", exc_info=True)
        return None


def is_onboarding_complete(phase: str) -> bool:
    """Check if the given phase indicates onboarding is done."""
    return phase == OnboardingPhase.COMPLETED.value


# ---------------------------------------------------------------------------
# V8 Stage-based onboarding (design doc section 9.1)
# ---------------------------------------------------------------------------


class OnboardingService:
    """Stage-aware onboarding service per V8 Brain section 9.1.

    Determines the user's onboarding stage based on registration date
    and conversation count, and returns appropriate welcome cards and
    daily questions.
    """

    @staticmethod
    def get_onboarding_stage(
        days_since_registration: int,
        conversation_count: int,
    ) -> OnboardingStage:
        """Determine the onboarding stage from registration age and activity.

        Args:
            days_since_registration: Days since the user registered.
            conversation_count: Total number of conversations the user has had.

        Returns:
            The current OnboardingStage.
        """
        if days_since_registration >= 7:
            return OnboardingStage.GRADUATED
        if days_since_registration >= 1:
            return OnboardingStage.FIRST_WEEK
        # Day 0: distinguish first chat from first day
        if conversation_count == 0:
            return OnboardingStage.FIRST_CHAT
        return OnboardingStage.FIRST_DAY

    @staticmethod
    def get_welcome_card() -> dict:
        """Return the V8 welcome card (replaces empty chat page).

        Returns a dict with title, subtitle, and quick_actions list
        matching the design doc specification.
        """
        return dict(_WELCOME_CARD)

    @staticmethod
    def get_daily_question(day_number: int) -> Optional[dict]:
        """Return a guided question for the given day of the first week.

        Args:
            day_number: Day number since registration (1-7).

        Returns:
            A dict with 'day', 'question', and 'category' keys,
            or None if no question for that day.
        """
        for q in _DAILY_QUESTIONS:
            if q["day"] == day_number:
                return dict(q)
        return None

    @staticmethod
    def should_suppress_proactive(stage: OnboardingStage) -> bool:
        """Whether proactive suggestions should be suppressed.

        During FIRST_DAY, the system passively extracts information
        from conversations without proactively interrupting the user.
        During FIRST_CHAT, proactive suggestions are also suppressed
        to avoid overwhelming new users.

        Args:
            stage: The user's current onboarding stage.

        Returns:
            True if proactive suggestions should be suppressed.
        """
        return stage in (OnboardingStage.FIRST_CHAT, OnboardingStage.FIRST_DAY)


# ---------------------------------------------------------------------------
# Day-threshold onboarding steps (progressive drip)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingStep:
    """A single onboarding question dripped over the first weeks."""

    step_id: str
    title: str
    question: str
    category: str  # "family", "preference", "routine"
    day_threshold: int  # minimum days since registration


ONBOARDING_STEPS: List[OnboardingStep] = [
    OnboardingStep(
        "family_size", "\u5bb6\u5ead\u57fa\u672c\u4fe1\u606f",
        "\u4f60\u5bb6\u91cc\u6709\u51e0\u53e3\u4eba\uff1f\u90fd\u6709\u8c01\uff1f", "family", 0,
    ),
    OnboardingStep(
        "family_names", "\u5bb6\u5ead\u6210\u5458",
        "\u80fd\u544a\u8bc9\u6211\u5bb6\u4eba\u7684\u540d\u5b57\u548c\u5173\u7cfb\u5417\uff1f", "family", 0,
    ),
    OnboardingStep(
        "food_pref", "\u996e\u98df\u504f\u597d",
        "\u4f60\u4eec\u5bb6\u5e73\u65f6\u559c\u6b22\u5403\u4ec0\u4e48\u7c7b\u578b\u7684\u9910\u5385\uff1f\u6709\u5fcc\u53e3\u5417\uff1f", "preference", 3,
    ),
    OnboardingStep(
        "schedule", "\u65e5\u5e38\u4f5c\u606f",
        "\u5bb6\u91cc\u4eba\u7684\u65e5\u5e38\u4f5c\u606f\u5927\u6982\u662f\u600e\u6837\u7684\uff1f", "routine", 7,
    ),
    OnboardingStep(
        "important_dates", "\u91cd\u8981\u65e5\u671f",
        "\u5bb6\u91cc\u6709\u54ea\u4e9b\u91cd\u8981\u7684\u7eaa\u5ff5\u65e5\u6216\u751f\u65e5\u9700\u8981\u8bb0\u4f4f\uff1f", "routine", 7,
    ),
    OnboardingStep(
        "hobbies", "\u5174\u8da3\u7231\u597d",
        "\u5bb6\u4eba\u4eec\u5e73\u65f6\u6709\u4ec0\u4e48\u5174\u8da3\u7231\u597d\uff1f", "preference", 14,
    ),
]


async def get_next_onboarding_step(
    user_id,  # UUID — reserved for per-user logic
    days_since_registration: int,
    completed_steps: Optional[List[str]] = None,
) -> Optional[OnboardingStep]:
    """Return the next incomplete day-threshold-based step.

    Steps are returned in order; the first step whose day_threshold is met
    and that hasn't been completed is returned.

    Returns None when all eligible steps are done.
    """
    done = set(completed_steps or [])
    for step in ONBOARDING_STEPS:
        if step.step_id not in done and days_since_registration >= step.day_threshold:
            return step
    return None
