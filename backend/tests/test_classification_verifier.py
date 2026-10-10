"""Tests for ClassificationVerifier — post-hoc misclassification detection."""
import logging
from typing import Optional

import pytest

from src.ai_engine.router.classification_verifier import (
    ClassificationVerifier,
    VerificationResult,
)
from src.ai_engine.router.types import (
    ActionType,
    Difficulty,
    IntentCategory,
    IntentClassification,
    RouteType,
)


def _make_classification(
    difficulty: Difficulty = Difficulty.IMMEDIATE,
    action: ActionType = ActionType.CHAT,
    route_type: Optional[RouteType] = None,
) -> IntentClassification:
    """Helper to build a minimal IntentClassification."""
    if route_type is None:
        if difficulty == Difficulty.IMMEDIATE:
            route_type = RouteType.FAST
        else:
            route_type = RouteType.SLOW
    return IntentClassification(
        route_type=route_type,
        intent_category=IntentCategory.UNKNOWN,
        confidence=0.9,
        difficulty=difficulty,
        action=action,
    )


class TestFastToSlowUpgrade:
    """Signal 1: immediate classification that got upgraded to slow path."""

    def test_upgrade_detected(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.IMMEDIATE)

        result = verifier.verify(
            classification=classification,
            worker_status="upgrade_to_slow",
        )

        assert not result.is_correct
        assert result.suggested_correction == "thinking"
        assert result.confidence == 0.85
        assert result.reason == "fast_path_exhausted_upgraded_to_slow"

    def test_thinking_with_upgrade_not_flagged(self):
        """If already classified as thinking, upgrade_to_slow is not a signal."""
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="upgrade_to_slow",
        )

        # Not flagged because it was already thinking-difficulty
        assert result.is_correct


class TestSlowPathTrivialCompletion:
    """Signal 2: thinking classification with < 2 tool calls."""

    def test_trivial_slow_completion_detected(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            tool_count=1,
        )

        assert not result.is_correct
        assert result.suggested_correction == "immediate"
        assert result.confidence == 0.6
        assert result.reason == "slow_path_trivial_completion"

    def test_zero_tool_calls_also_detected(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            tool_count=0,
        )

        assert not result.is_correct
        assert result.suggested_correction == "immediate"

    def test_sufficient_tool_calls_not_flagged(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            tool_count=3,
        )

        assert result.is_correct

    def test_exactly_two_tool_calls_not_flagged(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            tool_count=2,
        )

        assert result.is_correct

    def test_thinking_not_complete_not_flagged(self):
        """Slow path that upgraded again should not trigger trivial signal."""
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="upgrade_to_slow",
            tool_count=0,
        )

        assert result.is_correct


class TestUserCorrection:
    """Signal 3: user follow-up suggesting misunderstanding."""

    @pytest.mark.parametrize("phrase", [
        "不是，我想查天气",
        "我是想问明天的行程",
        "其实我要的是提醒",
        "我的意思是帮我订票",
    ])
    def test_correction_detected(self, phrase):
        verifier = ClassificationVerifier()
        classification = _make_classification()

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            user_response=phrase,
        )

        assert not result.is_correct
        assert result.suggested_correction is None
        assert result.confidence == 0.7
        assert result.reason == "user_explicit_correction"

    def test_normal_followup_not_flagged(self):
        verifier = ClassificationVerifier()
        classification = _make_classification()

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            user_response="谢谢，还有别的问题",
        )

        assert result.is_correct


class TestNormalCompletion:
    """Normal cases that should not be flagged."""

    def test_immediate_complete(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.IMMEDIATE)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
        )

        assert result.is_correct
        assert result.suggested_correction is None
        assert result.confidence == 1.0
        assert result.reason == ""

    def test_thinking_complete_with_tools(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.THINKING)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            tool_count=5,
        )

        assert result.is_correct


class TestEdgeCases:
    """Edge cases: unsure difficulty, None user_response, etc."""

    def test_unsure_difficulty_complete(self):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.UNSURE)

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
        )

        assert result.is_correct

    def test_unsure_difficulty_upgrade(self):
        """Unsure + upgrade_to_slow should NOT trigger the immediate signal."""
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.UNSURE)

        result = verifier.verify(
            classification=classification,
            worker_status="upgrade_to_slow",
        )

        assert result.is_correct

    def test_none_user_response(self):
        verifier = ClassificationVerifier()
        classification = _make_classification()

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            user_response=None,
        )

        assert result.is_correct

    def test_empty_user_response(self):
        verifier = ClassificationVerifier()
        classification = _make_classification()

        result = verifier.verify(
            classification=classification,
            worker_status="complete",
            user_response="",
        )

        assert result.is_correct


class TestVerificationResultImmutability:
    """Verify that VerificationResult is a frozen dataclass."""

    def test_frozen(self):
        result = VerificationResult(is_correct=True)
        with pytest.raises(AttributeError):
            result.is_correct = False  # type: ignore[misc]


class TestLogging:
    """Verify that verification results are logged."""

    def test_logs_emitted(self, caplog):
        verifier = ClassificationVerifier()
        classification = _make_classification(difficulty=Difficulty.IMMEDIATE)

        with caplog.at_level(logging.INFO):
            verifier.verify(
                classification=classification,
                worker_status="upgrade_to_slow",
            )

        assert any("classification_verification" in r.message for r in caplog.records)

    def test_correct_classification_also_logged(self, caplog):
        verifier = ClassificationVerifier()
        classification = _make_classification()

        with caplog.at_level(logging.INFO):
            verifier.verify(
                classification=classification,
                worker_status="complete",
            )

        assert any("classification_verification" in r.message for r in caplog.records)
