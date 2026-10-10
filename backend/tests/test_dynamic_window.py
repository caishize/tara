"""Tests for compute_window_size() dynamic active-window sizing.

Covers:
- Base window size
- Complex intent expansion
- Active tool count expansion (thresholds 3 and 5)
- Cap at 25
- Combined intent + tool expansion
- Default / None / edge cases
"""

import pytest

from src.modules.conversation.context_service import (
    compute_window_size,
    _DEFAULT_WINDOW_SIZE,
    _MAX_WINDOW_SIZE,
    _COMPLEX_INTENTS,
)


# ---------------------------------------------------------------------------
# Base case
# ---------------------------------------------------------------------------


class TestBaseWindow:
    def test_default_returns_base(self):
        assert compute_window_size() == _DEFAULT_WINDOW_SIZE

    def test_none_intent_returns_base(self):
        assert compute_window_size(intent_classification=None) == _DEFAULT_WINDOW_SIZE

    def test_empty_string_intent_returns_base(self):
        assert compute_window_size(intent_classification="") == _DEFAULT_WINDOW_SIZE

    def test_simple_intent_returns_base(self):
        assert compute_window_size(intent_classification="greeting") == _DEFAULT_WINDOW_SIZE

    def test_unknown_intent_returns_base(self):
        assert compute_window_size(intent_classification="unknown") == _DEFAULT_WINDOW_SIZE


# ---------------------------------------------------------------------------
# Complex intent expansion
# ---------------------------------------------------------------------------


class TestComplexIntentExpansion:
    @pytest.mark.parametrize("intent", list(_COMPLEX_INTENTS))
    def test_complex_intents_add_five(self, intent):
        result = compute_window_size(intent_classification=intent)
        assert result == _DEFAULT_WINDOW_SIZE + 5

    def test_complex_analysis_adds_five(self):
        result = compute_window_size(intent_classification="complex_analysis")
        assert result == 15

    def test_trip_planning_adds_five(self):
        result = compute_window_size(intent_classification="trip_planning")
        assert result == 15


# ---------------------------------------------------------------------------
# Tool count expansion
# ---------------------------------------------------------------------------


class TestToolCountExpansion:
    def test_zero_tools_no_change(self):
        assert compute_window_size(active_tool_count=0) == _DEFAULT_WINDOW_SIZE

    def test_one_tool_no_change(self):
        assert compute_window_size(active_tool_count=1) == _DEFAULT_WINDOW_SIZE

    def test_two_tools_no_change(self):
        assert compute_window_size(active_tool_count=2) == _DEFAULT_WINDOW_SIZE

    def test_three_tools_adds_five(self):
        assert compute_window_size(active_tool_count=3) == _DEFAULT_WINDOW_SIZE + 5

    def test_four_tools_adds_five(self):
        assert compute_window_size(active_tool_count=4) == _DEFAULT_WINDOW_SIZE + 5

    def test_five_tools_adds_ten(self):
        assert compute_window_size(active_tool_count=5) == _DEFAULT_WINDOW_SIZE + 10

    def test_ten_tools_adds_ten(self):
        assert compute_window_size(active_tool_count=10) == _DEFAULT_WINDOW_SIZE + 10


# ---------------------------------------------------------------------------
# Cap at MAX_WINDOW_SIZE
# ---------------------------------------------------------------------------


class TestWindowCap:
    def test_max_window_size_is_25(self):
        assert _MAX_WINDOW_SIZE == 25

    def test_complex_intent_plus_five_tools_capped(self):
        """complex (+5) + tools>=3 (+5) + tools>=5 (+5) = 25, at cap."""
        result = compute_window_size(
            intent_classification="complex_analysis",
            active_tool_count=5,
        )
        assert result == 25

    def test_complex_intent_plus_many_tools_capped(self):
        result = compute_window_size(
            intent_classification="trip_planning",
            active_tool_count=100,
        )
        assert result == 25

    def test_never_exceeds_cap(self):
        result = compute_window_size(
            intent_classification="schedule_planning",
            active_tool_count=999,
        )
        assert result <= _MAX_WINDOW_SIZE


# ---------------------------------------------------------------------------
# Combined expansion
# ---------------------------------------------------------------------------


class TestCombinedExpansion:
    def test_complex_intent_plus_three_tools(self):
        """complex (+5) + tools>=3 (+5) = 20."""
        result = compute_window_size(
            intent_classification="conflict_resolution",
            active_tool_count=3,
        )
        assert result == 20

    def test_simple_intent_plus_five_tools(self):
        """no intent bonus + tools>=3 (+5) + tools>=5 (+5) = 20."""
        result = compute_window_size(
            intent_classification="greeting",
            active_tool_count=5,
        )
        assert result == 20

    def test_simple_intent_plus_three_tools(self):
        """no intent bonus + tools>=3 (+5) = 15."""
        result = compute_window_size(
            intent_classification="casual_chat",
            active_tool_count=3,
        )
        assert result == 15


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_negative_tool_count_treated_as_zero(self):
        """Negative tool count should not add to the window."""
        result = compute_window_size(active_tool_count=-1)
        assert result == _DEFAULT_WINDOW_SIZE

    def test_base_constant_is_ten(self):
        assert _DEFAULT_WINDOW_SIZE == 10

    def test_complex_intents_set_contains_expected(self):
        expected = {
            "complex_analysis",
            "trip_planning",
            "schedule_planning",
            "conflict_resolution",
            "gift_recommendation",
        }
        assert _COMPLEX_INTENTS == expected
