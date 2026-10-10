"""Tests for HybridPriorityEngine -- rule-based scoring + LLM calibration."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.curation.services.priority_score import PriorityScore
from src.modules.curation.services.priority_engine import (
    CalibrationResult,
    EnhancedPriorityScore,
    HybridPriorityEngine,
    MIN_CALIBRATION_CONFIDENCE,
    _apply_severity_override,
    _clamp,
    _event_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_base_score(
    urgency=0.5, severity=0.5, stakeholder=0.5, irrecoverability=0.5,
    **weight_overrides,
) -> PriorityScore:
    return PriorityScore(
        urgency=urgency,
        severity=severity,
        stakeholder_weight=stakeholder,
        irrecoverability=irrecoverability,
        w_urgency_override=weight_overrides.get("w_urgency"),
        w_severity_override=weight_overrides.get("w_severity"),
        w_stakeholder_override=weight_overrides.get("w_stakeholder"),
        w_irrecoverability_override=weight_overrides.get("w_irrecoverability"),
    )


def _make_cal_result(event_id="ev1", confidence=0.8, **kwargs) -> CalibrationResult:
    return CalibrationResult(
        event_id=event_id,
        severity=kwargs.get("severity", 0.7),
        stakeholder=kwargs.get("stakeholder", 0.6),
        irrecoverability=kwargs.get("irrecoverability", 0.8),
        preparation_hours=kwargs.get("preparation_hours", 2.0),
        secretary_note=kwargs.get("secretary_note", None),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# _needs_calibration
# ---------------------------------------------------------------------------

class TestNeedsCalibration:

    def test_ambiguous_zone_triggers(self):
        score = _make_base_score(urgency=0.5, severity=0.5, stakeholder=0.5, irrecoverability=0.5)
        # composite = 0.5 -> in [0.42, 0.58]
        assert HybridPriorityEngine._needs_calibration(score, {}) is True

    def test_clearly_high_does_not_trigger(self):
        score = _make_base_score(urgency=0.9, severity=0.9, stakeholder=0.9, irrecoverability=0.9)
        # composite = 0.9 -> outside [0.42, 0.58]
        assert HybridPriorityEngine._needs_calibration(score, {}) is False

    def test_clearly_low_does_not_trigger(self):
        score = _make_base_score(urgency=0.1, severity=0.1, stakeholder=0.1, irrecoverability=0.1)
        # composite = 0.1 -> outside [0.42, 0.58]
        assert HybridPriorityEngine._needs_calibration(score, {}) is False

    def test_high_association_count_triggers(self):
        score = _make_base_score(urgency=0.9, severity=0.9, stakeholder=0.9, irrecoverability=0.9)
        assert HybridPriorityEngine._needs_calibration(
            score, {"association_count": 3},
        ) is True

    def test_low_association_count_no_trigger(self):
        score = _make_base_score(urgency=0.9, severity=0.9, stakeholder=0.9, irrecoverability=0.9)
        assert HybridPriorityEngine._needs_calibration(
            score, {"association_count": 2},
        ) is False

    def test_boundary_0_42(self):
        # F3: narrowed lower boundary from 0.35 to 0.42
        score = _make_base_score(urgency=0.42, severity=0.42, stakeholder=0.42, irrecoverability=0.42)
        assert HybridPriorityEngine._needs_calibration(score, {}) is True

    def test_boundary_0_58(self):
        # F3: narrowed upper boundary from 0.65 to 0.58
        score = _make_base_score(urgency=0.58, severity=0.58, stakeholder=0.58, irrecoverability=0.58)
        assert HybridPriorityEngine._needs_calibration(score, {}) is True

    def test_old_boundary_0_35_no_longer_triggers(self):
        # F3: 0.35 is now outside the narrowed fuzzy band
        score = _make_base_score(urgency=0.35, severity=0.35, stakeholder=0.35, irrecoverability=0.35)
        assert HybridPriorityEngine._needs_calibration(score, {}) is False

    def test_old_boundary_0_65_no_longer_triggers(self):
        # F3: 0.65 is now outside the narrowed fuzzy band
        score = _make_base_score(urgency=0.65, severity=0.65, stakeholder=0.65, irrecoverability=0.65)
        assert HybridPriorityEngine._needs_calibration(score, {}) is False


# ---------------------------------------------------------------------------
# _apply_severity_override
# ---------------------------------------------------------------------------

class TestApplySeverityOverride:

    def test_critical_mapping(self):
        result = _apply_severity_override(
            {"event_type": "meeting", "priority": "normal"},
            {"meeting": 0.95},
        )
        assert result["priority"] == "critical"

    def test_high_mapping(self):
        result = _apply_severity_override(
            {"event_type": "meeting", "priority": "normal"},
            {"meeting": 0.75},
        )
        assert result["priority"] == "high"

    def test_standard_passthrough(self):
        result = _apply_severity_override(
            {"event_type": "meeting", "priority": "normal"},
            {"meeting": 0.5},
        )
        assert result["priority"] == "normal"

    def test_missing_event_type_passthrough(self):
        result = _apply_severity_override(
            {"event_type": "webinar", "priority": "low"},
            {"meeting": 0.95},
        )
        assert result["priority"] == "low"

    def test_no_overrides_passthrough(self):
        original = {"event_type": "meeting", "priority": "high"}
        result = _apply_severity_override(original, {})
        assert result["priority"] == "high"

    def test_immutability_of_original(self):
        original = {"event_type": "meeting", "priority": "normal"}
        result = _apply_severity_override(original, {"meeting": 0.95})
        assert original["priority"] == "normal"
        assert result["priority"] == "critical"


# ---------------------------------------------------------------------------
# EnhancedPriorityScore
# ---------------------------------------------------------------------------

class TestEnhancedPriorityScore:

    def test_composite_without_calibration(self):
        base = _make_base_score(urgency=0.8, severity=0.6, stakeholder=0.4, irrecoverability=0.2)
        enh = EnhancedPriorityScore(base=base)
        assert enh.composite == pytest.approx(base.composite)

    def test_composite_with_calibration(self):
        base = _make_base_score(urgency=0.8)
        cal = _make_cal_result(severity=0.9, stakeholder=0.7, irrecoverability=0.6)
        enh = EnhancedPriorityScore(base=base, calibration=cal)
        # Uses base urgency but calibrated dimensions
        expected = (
            0.8 * PriorityScore.W_URGENCY
            + 0.9 * PriorityScore.W_SEVERITY
            + 0.7 * PriorityScore.W_STAKEHOLDER
            + 0.6 * PriorityScore.W_IRRECOVERABLE
        )
        assert enh.composite == pytest.approx(expected)

    def test_priority_level_p0(self):
        base = _make_base_score(urgency=1.0, severity=1.0, stakeholder=1.0, irrecoverability=1.0)
        enh = EnhancedPriorityScore(base=base)
        assert enh.priority_level == "P0"

    def test_priority_level_p1(self):
        base = _make_base_score(urgency=0.7, severity=0.6, stakeholder=0.6, irrecoverability=0.5)
        enh = EnhancedPriorityScore(base=base)
        assert 0.6 <= enh.composite < 0.8
        assert enh.priority_level == "P1"

    def test_priority_level_p2(self):
        base = _make_base_score(urgency=0.4, severity=0.4, stakeholder=0.3, irrecoverability=0.3)
        enh = EnhancedPriorityScore(base=base)
        assert 0.3 <= enh.composite < 0.6
        assert enh.priority_level == "P2"

    def test_priority_level_p3(self):
        base = _make_base_score(urgency=0.1, severity=0.1, stakeholder=0.1, irrecoverability=0.1)
        enh = EnhancedPriorityScore(base=base)
        assert enh.composite < 0.3
        assert enh.priority_level == "P3"

    def test_to_dict_structure(self):
        base = _make_base_score()
        enh = EnhancedPriorityScore(base=base, fallback=True)
        d = enh.to_dict()
        assert "composite" in d
        assert "priority_level" in d
        assert d["fallback"] is True
        assert d["calibrated"] is False

    def test_frozen_dataclass(self):
        base = _make_base_score()
        enh = EnhancedPriorityScore(base=base)
        with pytest.raises(FrozenInstanceError):
            enh.fallback = True


# ---------------------------------------------------------------------------
# score / score_batch -- integration with mock LLM
# ---------------------------------------------------------------------------

class TestScoreBatch:

    @pytest.mark.asyncio
    async def test_clear_high_priority_no_calibration(self):
        engine = HybridPriorityEngine(calibration_enabled=True)
        event = {
            "event_id": "ev1",
            "event_type": "flight",
            "priority": "critical",
            "normalized_start": "2026-02-23T08:00:00+00:00",
            "has_booking": True,
        }
        # Flight + critical = high scores, composite > 0.65 -> no calibration
        with patch(
            "src.modules.curation.services.priority_engine.get_haiku_client",
        ) as mock_client:
            results = await engine.score_batch(
                [event], uuid4(), family_prefs=None,
            )
            mock_client.assert_not_called()
        assert len(results) == 1
        assert results[0].calibration is None
        assert results[0].fallback is False

    @pytest.mark.asyncio
    async def test_ambiguous_triggers_calibration(self):
        engine = HybridPriorityEngine(calibration_enabled=True)
        # F3: Use "meeting" type to land composite in narrowed fuzzy band [0.42, 0.58]
        event = {
            "event_id": "ev-ambig",
            "event_type": "meeting",
            "priority": "normal",
            "association_count": 0,
        }
        # Mock the LLM call to return calibration
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='[{"event_id":"ev-ambig","severity":0.7,"stakeholder":0.5,"irrecoverability":0.6,"preparation_hours":1.0,"secretary_note":"test","confidence":0.85}]'),
        ]
        mock_response.content[0].text = mock_response.content[0].text

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "src.modules.curation.services.priority_engine.get_haiku_client",
            return_value=mock_client,
        ), patch(
            "src.modules.curation.services.priority_engine.redis_client",
            new=AsyncMock(get=AsyncMock(return_value=None), set=AsyncMock()),
        ):
            results = await engine.score_batch(
                [event], uuid4(), family_prefs=None,
            )

        assert len(results) == 1
        assert results[0].calibration is not None
        assert results[0].secretary_note == "test"

    @pytest.mark.asyncio
    async def test_calibration_low_confidence_uses_base(self):
        engine = HybridPriorityEngine(calibration_enabled=True)
        # F3: Use "meeting" type to land composite in narrowed fuzzy band [0.42, 0.58]
        event = {
            "event_id": "ev-low-conf",
            "event_type": "meeting",
            "priority": "normal",
        }
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text='[{"event_id":"ev-low-conf","severity":0.7,"stakeholder":0.5,"irrecoverability":0.6,"preparation_hours":1.0,"secretary_note":"note","confidence":0.3}]'),
        ]
        mock_response.content[0].text = mock_response.content[0].text

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "src.modules.curation.services.priority_engine.get_haiku_client",
            return_value=mock_client,
        ), patch(
            "src.modules.curation.services.priority_engine.redis_client",
            new=AsyncMock(get=AsyncMock(return_value=None), set=AsyncMock()),
        ):
            results = await engine.score_batch(
                [event], uuid4(), family_prefs=None,
            )

        assert results[0].calibration is None
        assert results[0].fallback is True

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back(self):
        engine = HybridPriorityEngine(calibration_enabled=True)
        # F3: Use "meeting" type to land composite in narrowed fuzzy band [0.42, 0.58]
        event = {
            "event_id": "ev-fail",
            "event_type": "meeting",
            "priority": "normal",
        }
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch(
            "src.modules.curation.services.priority_engine.get_haiku_client",
            return_value=mock_client,
        ), patch(
            "src.modules.curation.services.priority_engine.redis_client",
            new=AsyncMock(get=AsyncMock(return_value=None), set=AsyncMock()),
        ):
            results = await engine.score_batch(
                [event], uuid4(), family_prefs=None,
            )

        assert results[0].calibration is None
        assert results[0].fallback is True

    @pytest.mark.asyncio
    async def test_calibration_disabled(self):
        engine = HybridPriorityEngine(calibration_enabled=False)
        event = {
            "event_id": "ev-no-cal",
            "event_type": "reminder",
            "priority": "normal",
        }
        with patch(
            "src.modules.curation.services.priority_engine.get_haiku_client",
        ) as mock_client:
            results = await engine.score_batch(
                [event], uuid4(), family_prefs=None,
            )
            mock_client.assert_not_called()
        assert results[0].calibration is None
        assert results[0].fallback is False


# ---------------------------------------------------------------------------
# Run cache
# ---------------------------------------------------------------------------

class TestRunCache:

    @pytest.mark.asyncio
    async def test_run_cache_hit(self):
        engine = HybridPriorityEngine(calibration_enabled=True)
        cal = _make_cal_result("ev-cached", confidence=0.9)
        engine._run_cache["ev-cached"] = cal

        # F3: Use "meeting" type to land composite in narrowed fuzzy band [0.42, 0.58]
        event = {
            "event_id": "ev-cached",
            "event_type": "meeting",
            "priority": "normal",
        }

        with patch(
            "src.modules.curation.services.priority_engine.get_haiku_client",
        ) as mock_client:
            results = await engine.score_batch(
                [event], uuid4(), family_prefs=None,
            )
            mock_client.assert_not_called()

        assert results[0].calibration is not None
        assert results[0].calibration.event_id == "ev-cached"

    def test_clear_run_cache(self):
        engine = HybridPriorityEngine()
        engine._run_cache["x"] = _make_cal_result()
        engine.clear_run_cache()
        assert len(engine._run_cache) == 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_event_id_with_event_id_key(self):
        assert _event_id({"event_id": "abc"}) == "abc"

    def test_event_id_with_id_key(self):
        assert _event_id({"id": "def"}) == "def"

    def test_event_id_fallback(self):
        assert _event_id({}) == "unknown"

    def test_clamp_normal(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_below(self):
        assert _clamp(-0.1) == 0.0

    def test_clamp_above(self):
        assert _clamp(1.5) == 1.0
