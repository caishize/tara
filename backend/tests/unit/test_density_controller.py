"""Tests for DensityController -- pure rule engine, no DB/LLM dependencies."""

from datetime import date
from types import SimpleNamespace

import pytest

from src.modules.briefing.services.density_controller import (
    DAILY_NOISE_BUDGET,
    CleanDeskResult,
    DensityController,
    DensityLevel,
    DensityProfile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_orchestrated_day(density_score: float, target_date=None):
    """Create a minimal OrchestratedDay-like object with just the needed attrs."""
    return SimpleNamespace(
        density_score=density_score,
        target_date=target_date or date(2026, 2, 23),  # Monday
    )


def _mock_family_prefs(density_preferences=None):
    """Create a minimal FamilyPreference-like object."""
    return SimpleNamespace(density_preferences=density_preferences)


# ---------------------------------------------------------------------------
# compute_profile -- base level mapping
# ---------------------------------------------------------------------------

class TestComputeProfileBaseLevel:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_focused_when_density_above_0_8(self):
        day = _mock_orchestrated_day(0.85)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.density_level == DensityLevel.FOCUSED

    def test_standard_when_density_between_0_4_and_0_8(self):
        day = _mock_orchestrated_day(0.6)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.density_level == DensityLevel.STANDARD

    def test_relaxed_when_density_below_0_4_morning(self):
        day = _mock_orchestrated_day(0.2)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.density_level == DensityLevel.RELAXED

    def test_reflective_when_evening_and_low_density(self):
        day = _mock_orchestrated_day(0.2)
        profile = self.ctrl.compute_profile(day, "evening")
        assert profile.density_level == DensityLevel.REFLECTIVE

    def test_none_orchestrated_day_gives_zero_density(self):
        profile = self.ctrl.compute_profile(None, "morning")
        assert profile.day_density == 0.0
        assert profile.density_level == DensityLevel.RELAXED


# ---------------------------------------------------------------------------
# compute_profile -- modifiers
# ---------------------------------------------------------------------------

class TestComputeProfileModifiers:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_weekend_relaxes_one_level(self):
        saturday = date(2026, 2, 28)  # Saturday
        day = _mock_orchestrated_day(0.85, target_date=saturday)
        profile = self.ctrl.compute_profile(day, "morning", target_date=saturday)
        # FOCUSED -> STANDARD on weekend
        assert profile.density_level == DensityLevel.STANDARD

    def test_declining_emotional_trend_relaxes_one_level(self):
        day = _mock_orchestrated_day(0.85)  # Normally FOCUSED
        profile = self.ctrl.compute_profile(
            day, "morning", emotional_trend="declining",
        )
        # FOCUSED -> STANDARD due to declining
        assert profile.density_level == DensityLevel.STANDARD

    def test_double_downgrade_weekend_and_declining(self):
        saturday = date(2026, 2, 28)
        day = _mock_orchestrated_day(0.85, target_date=saturday)
        profile = self.ctrl.compute_profile(
            day, "morning", emotional_trend="declining", target_date=saturday,
        )
        # FOCUSED -> STANDARD (weekend) -> RELAXED (declining)
        assert profile.density_level == DensityLevel.RELAXED

    def test_double_downgrade_does_not_go_below_reflective(self):
        saturday = date(2026, 2, 28)
        day = _mock_orchestrated_day(0.6, target_date=saturday)
        profile = self.ctrl.compute_profile(
            day, "morning", emotional_trend="declining", target_date=saturday,
        )
        # STANDARD -> RELAXED (weekend) -> REFLECTIVE (declining)
        assert profile.density_level == DensityLevel.REFLECTIVE

    def test_improving_trend_does_not_change_level(self):
        day = _mock_orchestrated_day(0.85)
        profile = self.ctrl.compute_profile(
            day, "morning", emotional_trend="improving",
        )
        assert profile.density_level == DensityLevel.FOCUSED


# ---------------------------------------------------------------------------
# compute_profile -- emotional state mapping
# ---------------------------------------------------------------------------

class TestComputeProfileEmotionalState:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_declining_maps_to_stressed(self):
        day = _mock_orchestrated_day(0.5)
        profile = self.ctrl.compute_profile(day, "morning", emotional_trend="declining")
        assert profile.emotional_state == "stressed"

    def test_improving_maps_to_relaxed(self):
        day = _mock_orchestrated_day(0.5)
        profile = self.ctrl.compute_profile(day, "morning", emotional_trend="improving")
        assert profile.emotional_state == "relaxed"

    def test_stable_maps_to_normal(self):
        day = _mock_orchestrated_day(0.5)
        profile = self.ctrl.compute_profile(day, "morning", emotional_trend="stable")
        assert profile.emotional_state == "normal"


# ---------------------------------------------------------------------------
# compute_profile -- period multiplier
# ---------------------------------------------------------------------------

class TestComputeProfilePeriodMultiplier:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_morning_multiplier_is_1(self):
        day = _mock_orchestrated_day(0.5)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.period_multiplier == 1.0

    def test_afternoon_multiplier_is_0_7(self):
        day = _mock_orchestrated_day(0.5)
        profile = self.ctrl.compute_profile(day, "afternoon")
        assert profile.period_multiplier == 0.7

    def test_evening_multiplier_is_0_5(self):
        day = _mock_orchestrated_day(0.85)
        profile = self.ctrl.compute_profile(day, "evening")
        assert profile.period_multiplier == 0.5

    def test_afternoon_scales_recommendations_down(self):
        day = _mock_orchestrated_day(0.5)
        morning = self.ctrl.compute_profile(day, "morning")
        afternoon = self.ctrl.compute_profile(day, "afternoon")
        assert afternoon.max_recommendations <= morning.max_recommendations

    def test_recommendations_never_below_1(self):
        day = _mock_orchestrated_day(0.85)  # FOCUSED -> max 3
        profile = self.ctrl.compute_profile(day, "evening")
        assert profile.max_recommendations >= 1
        assert profile.max_annotations >= 1


# ---------------------------------------------------------------------------
# compute_profile -- FamilyPreference overrides
# ---------------------------------------------------------------------------

class TestComputeProfileFamilyPrefs:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_forced_level_overrides_computed(self):
        day = _mock_orchestrated_day(0.85)  # Normally FOCUSED
        prefs = _mock_family_prefs({"forced_level": "RELAXED"})
        profile = self.ctrl.compute_profile(day, "morning", family_prefs=prefs)
        assert profile.density_level == DensityLevel.RELAXED

    def test_relax_by_shifts_levels(self):
        day = _mock_orchestrated_day(0.85)  # FOCUSED
        prefs = _mock_family_prefs({"relax_by": 2})
        profile = self.ctrl.compute_profile(day, "morning", family_prefs=prefs)
        # FOCUSED -> STANDARD -> RELAXED (relax_by=2)
        assert profile.density_level == DensityLevel.RELAXED

    def test_no_density_preferences_is_passthrough(self):
        day = _mock_orchestrated_day(0.85)
        prefs = _mock_family_prefs(None)
        profile = self.ctrl.compute_profile(day, "morning", family_prefs=prefs)
        assert profile.density_level == DensityLevel.FOCUSED

    def test_invalid_forced_level_ignored(self):
        day = _mock_orchestrated_day(0.85)
        prefs = _mock_family_prefs({"forced_level": "NONEXISTENT"})
        profile = self.ctrl.compute_profile(day, "morning", family_prefs=prefs)
        assert profile.density_level == DensityLevel.FOCUSED


# ---------------------------------------------------------------------------
# compute_profile -- level config values
# ---------------------------------------------------------------------------

class TestLevelConfigValues:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_focused_config(self):
        day = _mock_orchestrated_day(0.9)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.max_recommendations == 3
        assert profile.max_annotations == 2
        assert profile.show_household is False
        assert profile.show_upcoming_trips is False

    def test_standard_config(self):
        day = _mock_orchestrated_day(0.6)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.max_recommendations == 5
        assert profile.max_annotations == 4
        assert profile.show_household is True
        assert profile.show_upcoming_trips is True

    def test_relaxed_config(self):
        day = _mock_orchestrated_day(0.2)
        profile = self.ctrl.compute_profile(day, "morning")
        assert profile.max_recommendations == 7
        assert profile.max_annotations == 6
        assert profile.show_household is True
        assert profile.show_upcoming_trips is True


# ---------------------------------------------------------------------------
# apply_clean_desk
# ---------------------------------------------------------------------------

class TestApplyCleanDesk:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_urgency_items_always_visible(self):
        profile = DensityProfile(
            day_density=0.8,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=5,
            max_annotations=4,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.STANDARD,
            noise_budget=3,
        )
        urgency = ["alert1", "alert2", "alert3", "alert4"]
        scored = ["item1", "item2"]
        result = self.ctrl.apply_clean_desk(profile, urgency, scored)

        # All urgency items must be visible even exceeding budget
        assert all(item in result.visible_items for item in urgency)

    def test_remaining_budget_correct(self):
        profile = DensityProfile(
            day_density=0.5,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=5,
            max_annotations=4,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.STANDARD,
            noise_budget=DAILY_NOISE_BUDGET,
        )
        urgency = ["alert1", "alert2"]
        scored = [f"item{i}" for i in range(15)]
        result = self.ctrl.apply_clean_desk(profile, urgency, scored)

        expected_extra = DAILY_NOISE_BUDGET - 2  # budget - urgency count
        assert len(result.visible_items) == 2 + expected_extra
        assert result.budget_used == 2 + expected_extra
        assert result.budget_total == DAILY_NOISE_BUDGET

    def test_deferred_items_correct(self):
        profile = DensityProfile(
            day_density=0.5,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=5,
            max_annotations=4,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.STANDARD,
            noise_budget=5,
        )
        urgency = ["alert1"]
        scored = ["a", "b", "c", "d", "e", "f"]
        result = self.ctrl.apply_clean_desk(profile, urgency, scored)

        # Budget=5, urgency=1, remaining=4, so 4 scored items visible, 2 deferred
        assert result.deferred_items == ("e", "f")

    def test_empty_inputs(self):
        profile = DensityProfile(
            day_density=0.0,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=5,
            max_annotations=4,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.RELAXED,
        )
        result = self.ctrl.apply_clean_desk(profile, [], [])
        assert result.visible_items == ()
        assert result.deferred_items == ()
        assert result.budget_used == 0


# ---------------------------------------------------------------------------
# filter_by_priority
# ---------------------------------------------------------------------------

class TestFilterByPriority:

    def setup_method(self):
        self.ctrl = DensityController()

    def test_focused_mode_filters_to_p0_p1(self):
        profile = DensityProfile(
            day_density=0.9,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=3,
            max_annotations=2,
            show_household=False,
            show_upcoming_trips=False,
            density_level=DensityLevel.FOCUSED,
        )
        events = [
            {"title": "A", "priority_level": "P0"},
            {"title": "B", "priority_level": "P1"},
            {"title": "C", "priority_level": "P2"},
            {"title": "D", "priority_level": "P3"},
        ]
        result = self.ctrl.filter_by_priority(profile, events)
        assert len(result) == 2
        assert all(e["priority_level"] in ("P0", "P1") for e in result)

    def test_standard_mode_keeps_all(self):
        profile = DensityProfile(
            day_density=0.5,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=5,
            max_annotations=4,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.STANDARD,
        )
        events = [
            {"title": "A", "priority_level": "P0"},
            {"title": "B", "priority_level": "P3"},
        ]
        result = self.ctrl.filter_by_priority(profile, events)
        assert len(result) == 2

    def test_relaxed_mode_keeps_all(self):
        profile = DensityProfile(
            day_density=0.2,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=7,
            max_annotations=6,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.RELAXED,
        )
        events = [{"title": "X", "priority_level": "P3"}]
        result = self.ctrl.filter_by_priority(profile, events)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:

    def test_density_profile_is_frozen(self):
        profile = DensityProfile(
            day_density=0.5,
            period_multiplier=1.0,
            emotional_state="normal",
            max_recommendations=5,
            max_annotations=4,
            show_household=True,
            show_upcoming_trips=True,
            density_level=DensityLevel.STANDARD,
        )
        with pytest.raises(AttributeError):
            profile.density_level = DensityLevel.FOCUSED

    def test_clean_desk_result_is_frozen(self):
        result = CleanDeskResult(
            visible_items=("a",),
            deferred_items=("b",),
            budget_used=1,
            budget_total=10,
        )
        with pytest.raises(AttributeError):
            result.budget_used = 99
