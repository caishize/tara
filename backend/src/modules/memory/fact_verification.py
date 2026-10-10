"""Fact Verification Gate - Validates LLM-extracted facts before L1 write.

Prevents hallucination contamination of the L1 fact base (secretary_notes)
by verifying extracted facts against source evidence and existing notes.

Verification dimensions:
1. Evidence tracing - facts must be traceable to source conversation messages
2. Contradiction detection - new facts checked against existing L1 notes
3. Confidence thresholds - low-confidence facts enter pending or reject status
4. High-risk category override - health/allergy/payment always require confirmation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ...config.logging import get_logger
from .secretary_note_model import SecretaryNote, NoteCategory

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class VerificationAction(str, Enum):
    """Result action from the verification gate."""
    ACCEPT = "accept"    # Auto-write to L1
    PENDING = "pending"  # Queue for user confirmation
    REJECT = "reject"    # Discard


@dataclass(frozen=True)
class NoteCandidate:
    """A candidate fact extracted by LLM, pending verification."""
    content: str
    category: str
    confidence: float
    title: str = ""
    source_messages: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationResult:
    """Output of the verification gate."""
    action: VerificationAction
    reason: str
    conflicts: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Categories that always require user confirmation regardless of confidence
HIGH_RISK_CATEGORIES = frozenset({
    NoteCategory.IMPORTANT.value,
    "health",
    "allergy",
    "payment",
    "medical",
})

# Keywords that signal high-risk content within any category
HIGH_RISK_KEYWORDS = frozenset({
    "过敏", "禁忌", "糖尿病", "高血压", "药物", "手术",
    "支付", "转账", "银行", "密码", "账号",
    "allergy", "medication", "diabetes", "surgery",
})

# Minimum token overlap ratio for evidence tracing
EVIDENCE_OVERLAP_THRESHOLD = 0.3

# Minimum Jaccard overlap ratio for contradiction detection
CONTRADICTION_OVERLAP_THRESHOLD = 0.40


# ---------------------------------------------------------------------------
# FactVerificationGate
# ---------------------------------------------------------------------------


class FactVerificationGate:
    """Verifies LLM-extracted facts before writing to L1 (secretary_notes).

    Thresholds:
    - >= 0.85 confidence + evidence found: auto-accept
    - >= 0.60 confidence: pending (queue for user confirmation)
    - < 0.60 confidence: reject/discard
    - High-risk categories always go to PENDING regardless of confidence
    """

    CONFIDENCE_AUTO_ACCEPT = 0.85
    CONFIDENCE_PENDING = 0.60

    def verify(
        self,
        candidate: NoteCandidate,
        existing_notes: List[SecretaryNote],
        source_messages: Optional[List[str]] = None,
    ) -> VerificationResult:
        """Verify a note candidate and return the verification result.

        Args:
            candidate: The extracted fact to verify.
            existing_notes: Current active L1 notes for the user.
            source_messages: Original conversation messages that the fact
                was extracted from.

        Returns:
            VerificationResult with action, reason, and any conflicts found.
        """
        messages = source_messages or candidate.source_messages or []

        # Rule 1: Reject low-confidence facts immediately
        if candidate.confidence < self.CONFIDENCE_PENDING:
            return VerificationResult(
                action=VerificationAction.REJECT,
                reason=f"Confidence {candidate.confidence:.2f} below threshold {self.CONFIDENCE_PENDING}",
            )

        # Rule 2: High-risk categories always require confirmation
        if self._is_high_risk(candidate):
            return VerificationResult(
                action=VerificationAction.PENDING,
                reason="High-risk category requires user confirmation",
            )

        # Rule 3: Evidence tracing
        has_evidence = self._check_evidence(candidate.content, messages)

        # Rule 4: Contradiction detection
        conflicts = self._detect_contradictions(candidate, existing_notes)

        if conflicts:
            return VerificationResult(
                action=VerificationAction.PENDING,
                reason="Contradicts existing notes",
                conflicts=conflicts,
            )

        if not has_evidence and messages:
            return VerificationResult(
                action=VerificationAction.PENDING,
                reason="Insufficient evidence in source messages",
            )

        # High confidence + evidence + no conflicts: auto-accept
        if candidate.confidence >= self.CONFIDENCE_AUTO_ACCEPT:
            return VerificationResult(
                action=VerificationAction.ACCEPT,
                reason="High confidence with supporting evidence",
            )

        # Medium confidence: pending
        return VerificationResult(
            action=VerificationAction.PENDING,
            reason=f"Medium confidence {candidate.confidence:.2f}, awaiting user confirmation",
        )

    def _is_high_risk(self, candidate: NoteCandidate) -> bool:
        """Check if the candidate involves a high-risk category or content."""
        if candidate.category in HIGH_RISK_CATEGORIES:
            return True

        content_lower = candidate.content.lower()
        return any(kw in content_lower for kw in HIGH_RISK_KEYWORDS)

    @staticmethod
    def _check_evidence(
        fact_content: str,
        source_messages: List[str],
    ) -> bool:
        """Check if fact content has supporting evidence in source messages.

        Uses character-level overlap: extracts meaningful tokens from the fact
        and checks what fraction appear in the concatenated source messages.
        """
        if not source_messages:
            return True  # No messages to check against — assume OK

        fact_tokens = _extract_tokens(fact_content)
        if not fact_tokens:
            return True  # Nothing to match

        combined_sources = " ".join(source_messages).lower()
        matched = sum(1 for t in fact_tokens if t in combined_sources)
        overlap_ratio = matched / len(fact_tokens)

        return overlap_ratio >= EVIDENCE_OVERLAP_THRESHOLD

    @staticmethod
    def _detect_contradictions(
        candidate: NoteCandidate,
        existing_notes: List[SecretaryNote],
    ) -> List[str]:
        """Detect potential contradictions between candidate and existing notes.

        Phase 2 uses simple keyword overlap heuristic (not full embedding search).
        A contradiction is flagged when two notes share the same category and
        significant keyword overlap but have semantically opposing signals.
        """
        if not existing_notes:
            return []

        candidate_tokens = set(_extract_tokens(candidate.content))
        if not candidate_tokens:
            return []

        conflicts = []
        for note in existing_notes:
            # Only check notes in the same category
            if note.category != candidate.category:
                continue

            note_tokens = set(_extract_tokens(note.content or ""))
            if not note_tokens:
                continue

            # Check keyword overlap (Jaccard-style using union for normalization)
            intersection = candidate_tokens & note_tokens
            union_size = len(candidate_tokens | note_tokens)
            if union_size == 0:
                continue

            overlap = len(intersection) / union_size

            if overlap >= CONTRADICTION_OVERLAP_THRESHOLD:
                # High overlap in same category — potential update/contradiction
                conflicts.append(
                    f"Overlaps with existing note: '{note.title}' "
                    f"(overlap={overlap:.0%})"
                )

        return conflicts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_tokens(text: str) -> List[str]:
    """Extract meaningful tokens from text for overlap comparison.

    Handles both Chinese (character bigrams) and English (whitespace-split words).
    Chinese text uses sliding-window bigrams since we don't depend on a segmenter.
    """
    import re

    text_lower = text.lower().strip()
    if not text_lower:
        return []

    # Chinese: extract all CJK character spans, then create bigrams
    cjk_spans = re.findall(r'[\u4e00-\u9fff]+', text_lower)
    cn_tokens = []
    for span in cjk_spans:
        if len(span) >= 2:
            for i in range(len(span) - 1):
                cn_tokens.append(span[i:i + 2])

    # English tokens: words of 3+ characters
    en_tokens = re.findall(r'[a-z]{3,}', text_lower)

    return cn_tokens + en_tokens
