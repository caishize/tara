"""
Post-hoc misclassification detection for IntentRouter.

Phase 4 (observation-only): logs signals that suggest the router's
classification was incorrect, without altering routing behavior.

Signals detected:
1. Fast->Slow upgrade: "immediate" was likely wrong if FastWorker exhausted
   its tool budget and escalated to Slow Path.
2. Trivial slow completion: "thinking" was likely over-classified if the
   Slow Path finished with fewer than 2 tool calls.
3. User correction: explicit user follow-up phrases suggesting
   misunderstanding (e.g. "不是", "我是想", "其实我要").
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from .types import Difficulty, IntentClassification


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerificationResult:
    """Result of post-hoc classification verification.

    Attributes:
        is_correct: Whether the original classification appears correct.
        suggested_correction: Suggested difficulty if misclassified
            ("thinking" or "immediate"), or None if ambiguous.
        confidence: Confidence in the verification verdict (0-1).
        reason: Machine-readable reason string for logging/metrics.
    """
    is_correct: bool
    suggested_correction: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""


class ClassificationVerifier:
    """Detect likely misclassifications after a request has been processed.

    This is observation-only in Phase 4 -- it logs findings but does NOT
    alter routing decisions. Collected signals feed future router tuning.
    """

    _CORRECTION_PATTERNS = re.compile(
        r"(不是|我是想|其实我要|我的意思是)"
    )

    def verify(
        self,
        classification: IntentClassification,
        worker_status: str,
        tool_count: int = 0,
        user_response: Optional[str] = None,
    ) -> VerificationResult:
        """Verify whether a classification was correct after execution.

        Args:
            classification: The original IntentClassification from the router.
            worker_status: Outcome status -- "complete" or "upgrade_to_slow".
            tool_count: Number of tool calls made during execution.
            user_response: Optional follow-up message from the user.

        Returns:
            VerificationResult with diagnosis.
        """
        # Signal 1: Fast->Slow upgrade suggests "immediate" was wrong
        if (
            classification.difficulty == Difficulty.IMMEDIATE
            and worker_status == "upgrade_to_slow"
        ):
            result = VerificationResult(
                is_correct=False,
                suggested_correction="thinking",
                confidence=0.85,
                reason="fast_path_exhausted_upgraded_to_slow",
            )
            self._log_verification(classification, result)
            return result

        # Signal 2: Slow path finished with < 2 tool calls -> over-classified
        if (
            classification.difficulty == Difficulty.THINKING
            and worker_status == "complete"
            and tool_count < 2
        ):
            result = VerificationResult(
                is_correct=False,
                suggested_correction="immediate",
                confidence=0.6,
                reason="slow_path_trivial_completion",
            )
            self._log_verification(classification, result)
            return result

        # Signal 3: User correction in follow-up message
        if user_response and self._CORRECTION_PATTERNS.search(user_response):
            result = VerificationResult(
                is_correct=False,
                suggested_correction=None,
                confidence=0.7,
                reason="user_explicit_correction",
            )
            self._log_verification(classification, result)
            return result

        result = VerificationResult(is_correct=True)
        self._log_verification(classification, result)
        return result

    @staticmethod
    def _log_verification(
        classification: IntentClassification,
        result: VerificationResult,
    ) -> None:
        """Log verification outcome for metrics collection."""
        logger.info(
            "classification_verification",
            extra={
                "difficulty": classification.difficulty.value,
                "action": classification.action.value,
                "route_type": classification.route_type.value,
                "is_correct": result.is_correct,
                "suggested_correction": result.suggested_correction,
                "confidence": result.confidence,
                "reason": result.reason,
            },
        )
