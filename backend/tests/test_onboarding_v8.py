"""Tests for V8 cold-start onboarding service (stage-based) and feature tiers."""

import pytest
from uuid import uuid4

from src.modules.conversation.onboarding_service import (
    OnboardingService,
    OnboardingStage,
    _DAILY_QUESTIONS,
    _WELCOME_CARD,
)


# ===========================================================================
# OnboardingStage enum
# ===========================================================================


class TestOnboardingStageEnum:
    """Verify the OnboardingStage enum values."""

    def test_all_stages_present(self):
        stages = {s.value for s in OnboardingStage}
        assert stages == {"first_chat", "first_day", "first_week", "graduated"}

    def test_stage_string_values(self):
        assert OnboardingStage.FIRST_CHAT.value == "first_chat"
        assert OnboardingStage.FIRST_DAY.value == "first_day"
        assert OnboardingStage.FIRST_WEEK.value == "first_week"
        assert OnboardingStage.GRADUATED.value == "graduated"


# ===========================================================================
# OnboardingService.get_onboarding_stage
# ===========================================================================


class TestGetOnboardingStage:
    """Verify stage determination based on registration age and conversation count."""

    def test_new_user_no_conversations(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=0, conversation_count=0,
        )
        assert stage == OnboardingStage.FIRST_CHAT

    def test_day_0_with_conversations(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=0, conversation_count=3,
        )
        assert stage == OnboardingStage.FIRST_DAY

    def test_day_1_is_first_week(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=1, conversation_count=0,
        )
        assert stage == OnboardingStage.FIRST_WEEK

    def test_day_3_is_first_week(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=3, conversation_count=10,
        )
        assert stage == OnboardingStage.FIRST_WEEK

    def test_day_6_is_first_week(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=6, conversation_count=50,
        )
        assert stage == OnboardingStage.FIRST_WEEK

    def test_day_7_is_graduated(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=7, conversation_count=0,
        )
        assert stage == OnboardingStage.GRADUATED

    def test_day_30_is_graduated(self):
        stage = OnboardingService.get_onboarding_stage(
            days_since_registration=30, conversation_count=100,
        )
        assert stage == OnboardingStage.GRADUATED


# ===========================================================================
# OnboardingService.get_welcome_card
# ===========================================================================


class TestGetWelcomeCard:
    """Verify the V8 welcome card structure."""

    def test_welcome_card_has_title(self):
        card = OnboardingService.get_welcome_card()
        assert "title" in card
        assert len(card["title"]) > 0

    def test_welcome_card_has_subtitle(self):
        card = OnboardingService.get_welcome_card()
        assert "subtitle" in card
        assert len(card["subtitle"]) > 0

    def test_welcome_card_has_quick_actions(self):
        card = OnboardingService.get_welcome_card()
        assert "quick_actions" in card
        assert len(card["quick_actions"]) == 4

    def test_quick_action_structure(self):
        card = OnboardingService.get_welcome_card()
        for action in card["quick_actions"]:
            assert "id" in action
            assert "label" in action
            assert "icon" in action

    def test_quick_action_ids(self):
        card = OnboardingService.get_welcome_card()
        ids = {a["id"] for a in card["quick_actions"]}
        assert ids == {"family_birthday", "plan_trip", "remember_something", "just_chat"}

    def test_welcome_card_is_new_dict(self):
        """Verify the card is a copy, not the original (immutability)."""
        card1 = OnboardingService.get_welcome_card()
        card2 = OnboardingService.get_welcome_card()
        assert card1 is not card2


# ===========================================================================
# OnboardingService.get_daily_question
# ===========================================================================


class TestGetDailyQuestion:
    """Verify daily questions for FIRST_WEEK stage."""

    def test_day_1_question(self):
        q = OnboardingService.get_daily_question(1)
        assert q is not None
        assert q["day"] == 1
        assert "category" in q
        assert "question" in q

    def test_all_7_days_have_questions(self):
        for day in range(1, 8):
            q = OnboardingService.get_daily_question(day)
            assert q is not None, f"No question for day {day}"
            assert q["day"] == day

    def test_day_0_no_question(self):
        q = OnboardingService.get_daily_question(0)
        assert q is None

    def test_day_8_no_question(self):
        q = OnboardingService.get_daily_question(8)
        assert q is None

    def test_negative_day_no_question(self):
        q = OnboardingService.get_daily_question(-1)
        assert q is None

    def test_question_is_copy(self):
        """Verify returned dict is a copy (immutability)."""
        q1 = OnboardingService.get_daily_question(1)
        q2 = OnboardingService.get_daily_question(1)
        assert q1 is not q2

    def test_question_categories(self):
        categories = set()
        for day in range(1, 8):
            q = OnboardingService.get_daily_question(day)
            categories.add(q["category"])
        # Should cover multiple categories
        assert len(categories) >= 3


# ===========================================================================
# OnboardingService.should_suppress_proactive
# ===========================================================================


class TestShouldSuppressProactive:
    """Verify proactive suppression logic."""

    def test_first_chat_suppresses(self):
        assert OnboardingService.should_suppress_proactive(OnboardingStage.FIRST_CHAT) is True

    def test_first_day_suppresses(self):
        assert OnboardingService.should_suppress_proactive(OnboardingStage.FIRST_DAY) is True

    def test_first_week_does_not_suppress(self):
        assert OnboardingService.should_suppress_proactive(OnboardingStage.FIRST_WEEK) is False

    def test_graduated_does_not_suppress(self):
        assert OnboardingService.should_suppress_proactive(OnboardingStage.GRADUATED) is False


# ===========================================================================
# Daily questions data integrity
# ===========================================================================


class TestDailyQuestionsData:
    """Verify the _DAILY_QUESTIONS list integrity."""

    def test_has_7_questions(self):
        assert len(_DAILY_QUESTIONS) == 7

    def test_days_are_1_through_7(self):
        days = sorted(q["day"] for q in _DAILY_QUESTIONS)
        assert days == list(range(1, 8))

    def test_all_have_required_keys(self):
        for q in _DAILY_QUESTIONS:
            assert "day" in q
            assert "question" in q
            assert "category" in q

    def test_categories_are_valid(self):
        valid_categories = {"family", "dates", "preferences", "routines"}
        for q in _DAILY_QUESTIONS:
            assert q["category"] in valid_categories, (
                f"Invalid category: {q['category']}"
            )
