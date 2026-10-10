"""Tests for FactVerificationGate."""

from unittest.mock import MagicMock

import pytest

from src.modules.memory.fact_verification import (
    FactVerificationGate,
    NoteCandidate,
    VerificationAction,
    VerificationResult,
    _extract_tokens,
    EVIDENCE_OVERLAP_THRESHOLD,
    CONTRADICTION_OVERLAP_THRESHOLD,
    HIGH_RISK_CATEGORIES,
    HIGH_RISK_KEYWORDS,
)
from src.modules.memory.secretary_note_model import (
    NoteCategory,
    NoteStatus,
    SecretaryNote,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note(title, content, category=NoteCategory.PREFERENCE.value):
    note = MagicMock(spec=SecretaryNote)
    note.title = title
    note.content = content
    note.category = category
    note.status = NoteStatus.ACTIVE.value
    return note


# ---------------------------------------------------------------------------
# _extract_tokens
# ---------------------------------------------------------------------------


class TestExtractTokens:
    def test_chinese_bigrams(self):
        tokens = _extract_tokens("用户喜欢靠窗座位")
        # Should produce bigrams: 用户, 户喜, 喜欢, 欢靠, 靠窗, 窗座, 座位
        assert "用户" in tokens
        assert "喜欢" in tokens
        assert "靠窗" in tokens
        assert "座位" in tokens
        assert len(tokens) == 7

    def test_english_tokens(self):
        tokens = _extract_tokens("user prefers aisle seat")
        assert "user" in tokens
        assert "prefers" in tokens
        assert "aisle" in tokens
        assert "seat" in tokens

    def test_mixed_tokens(self):
        tokens = _extract_tokens("用户 prefers 靠窗座位")
        cn = [t for t in tokens if any('\u4e00' <= c <= '\u9fff' for c in t)]
        en = [t for t in tokens if t.isascii()]
        assert len(cn) > 0
        assert len(en) > 0

    def test_empty_string(self):
        assert _extract_tokens("") == []

    def test_short_english_filtered(self):
        tokens = _extract_tokens("I am a dog")
        # "am" and "a" are < 3 chars, filtered out
        assert "dog" in tokens
        assert "am" not in tokens

    def test_single_cjk_char_no_bigram(self):
        tokens = _extract_tokens("我")
        cn = [t for t in tokens if any('\u4e00' <= c <= '\u9fff' for c in t)]
        assert len(cn) == 0


# ---------------------------------------------------------------------------
# FactVerificationGate.verify — confidence thresholds
# ---------------------------------------------------------------------------


class TestConfidenceThresholds:
    def setup_method(self):
        self.gate = FactVerificationGate()

    def test_high_confidence_auto_accept(self):
        candidate = NoteCandidate(
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
            source_messages=["用户说我喜欢靠窗座位，每次都要选靠窗"],
        )
        result = self.gate.verify(candidate, existing_notes=[], source_messages=None)
        assert result.action == VerificationAction.ACCEPT

    def test_medium_confidence_pending(self):
        candidate = NoteCandidate(
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.70,
            source_messages=["用户说我喜欢靠窗座位"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.PENDING

    def test_low_confidence_reject(self):
        candidate = NoteCandidate(
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.50,
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.REJECT
        assert "below threshold" in result.reason.lower() or "confidence" in result.reason.lower()

    def test_exactly_at_auto_accept_threshold(self):
        candidate = NoteCandidate(
            content="用户喜欢日料",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.85,
            source_messages=["用户喜欢吃日料"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.ACCEPT

    def test_exactly_at_pending_threshold(self):
        candidate = NoteCandidate(
            content="用户喜欢日料",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.60,
            source_messages=["用户喜欢吃日料"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.PENDING

    def test_just_below_pending_threshold(self):
        candidate = NoteCandidate(
            content="用户喜欢日料",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.59,
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.REJECT


# ---------------------------------------------------------------------------
# High-risk category override
# ---------------------------------------------------------------------------


class TestHighRiskOverride:
    def setup_method(self):
        self.gate = FactVerificationGate()

    def test_important_category_always_pending(self):
        candidate = NoteCandidate(
            content="父亲血型是O型",
            category=NoteCategory.IMPORTANT.value,
            confidence=0.95,
            source_messages=["我爸是O型血"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.PENDING
        assert "high-risk" in result.reason.lower()

    def test_health_keyword_triggers_pending(self):
        candidate = NoteCandidate(
            content="公公有糖尿病，不能吃甜食",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.95,
            source_messages=["公公有糖尿病"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.PENDING

    def test_allergy_keyword_triggers_pending(self):
        candidate = NoteCandidate(
            content="用户对花生过敏",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.99,
            source_messages=["我对花生过敏"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.PENDING

    def test_payment_keyword_triggers_pending(self):
        candidate = NoteCandidate(
            content="每月15号自动转账给父母",
            category=NoteCategory.ROUTINE.value,
            confidence=0.90,
            source_messages=["每月15号给爸妈转账"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.PENDING

    def test_non_high_risk_passes_through(self):
        candidate = NoteCandidate(
            content="用户喜欢喝咖啡",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
            source_messages=["用户喜欢每天喝咖啡"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.ACCEPT


# ---------------------------------------------------------------------------
# Evidence tracing
# ---------------------------------------------------------------------------


class TestEvidenceTracing:
    def setup_method(self):
        self.gate = FactVerificationGate()

    def test_evidence_present(self):
        candidate = NoteCandidate(
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
        )
        result = self.gate.verify(
            candidate,
            existing_notes=[],
            source_messages=["用户说喜欢靠窗座位，坐飞机都选靠窗"],
        )
        assert result.action == VerificationAction.ACCEPT

    def test_no_evidence_goes_pending(self):
        candidate = NoteCandidate(
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
        )
        result = self.gate.verify(
            candidate,
            existing_notes=[],
            source_messages=["今天天气真好，适合出去散步"],
        )
        assert result.action == VerificationAction.PENDING
        assert "evidence" in result.reason.lower()

    def test_no_source_messages_assumes_ok(self):
        candidate = NoteCandidate(
            content="用户喜欢日料",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
        )
        result = self.gate.verify(
            candidate, existing_notes=[], source_messages=[]
        )
        assert result.action == VerificationAction.ACCEPT


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    def setup_method(self):
        self.gate = FactVerificationGate()

    def test_contradiction_with_existing_note(self):
        existing = _make_note(
            title="用户喜欢靠窗座位",
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
        )
        candidate = NoteCandidate(
            content="用户喜欢靠走道座位",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
            source_messages=["我现在喜欢靠走道的座位"],
        )
        result = self.gate.verify(
            candidate,
            existing_notes=[existing],
        )
        assert result.action == VerificationAction.PENDING
        assert len(result.conflicts) > 0
        assert "overlap" in result.conflicts[0].lower() or "Overlaps" in result.conflicts[0]

    def test_no_contradiction_different_category(self):
        existing = _make_note(
            title="用户喜欢靠窗座位",
            content="用户喜欢靠窗座位",
            category=NoteCategory.PREFERENCE.value,
        )
        candidate = NoteCandidate(
            content="用户每天早上七点起床",
            category=NoteCategory.ROUTINE.value,
            confidence=0.90,
            source_messages=["用户每天早上七点起床"],
        )
        result = self.gate.verify(
            candidate,
            existing_notes=[existing],
        )
        # Different category, so no conflict
        assert result.action == VerificationAction.ACCEPT
        assert len(result.conflicts) == 0

    def test_no_contradiction_different_content(self):
        existing = _make_note(
            title="用户喜欢日料",
            content="用户喜欢吃日料",
            category=NoteCategory.PREFERENCE.value,
        )
        candidate = NoteCandidate(
            content="用户喜欢喝咖啡",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
            source_messages=["用户喜欢每天喝咖啡"],
        )
        result = self.gate.verify(
            candidate,
            existing_notes=[existing],
        )
        # No significant overlap
        assert result.action == VerificationAction.ACCEPT

    def test_no_existing_notes(self):
        candidate = NoteCandidate(
            content="用户喜欢日料",
            category=NoteCategory.PREFERENCE.value,
            confidence=0.90,
            source_messages=["用户喜欢吃日料"],
        )
        result = self.gate.verify(candidate, existing_notes=[])
        assert result.action == VerificationAction.ACCEPT
        assert len(result.conflicts) == 0


# ---------------------------------------------------------------------------
# VerificationResult dataclass
# ---------------------------------------------------------------------------


class TestVerificationResult:
    def test_result_is_frozen(self):
        result = VerificationResult(
            action=VerificationAction.ACCEPT,
            reason="test",
        )
        with pytest.raises(AttributeError):
            result.action = VerificationAction.REJECT

    def test_default_conflicts_empty(self):
        result = VerificationResult(
            action=VerificationAction.ACCEPT,
            reason="test",
        )
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# NoteCandidate dataclass
# ---------------------------------------------------------------------------


class TestNoteCandidate:
    def test_candidate_is_frozen(self):
        candidate = NoteCandidate(
            content="test",
            category="preference",
            confidence=0.9,
        )
        with pytest.raises(AttributeError):
            candidate.content = "modified"

    def test_default_source_messages_empty(self):
        candidate = NoteCandidate(
            content="test",
            category="preference",
            confidence=0.9,
        )
        assert candidate.source_messages == []
