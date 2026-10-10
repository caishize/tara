"""
Unit tests for src.ai_engine.intervention.types module.

Covers enums, constants, all dataclasses (serialization, factories, immutability),
and Redis key helpers.
"""

import json
import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.ai_engine.intervention.types import (
    ClassificationResult,
    GenerationState,
    InterventionBudget,
    InterventionSignal,
    InterventionType,
    INTERVENTION_PRIORITIES,
    NON_INTERRUPTIBLE_TOOLS,
    SessionStatus,
    StitchingContext,
    session_signal_channel,
    session_status_key,
    session_stitch_key,
)


# ---------------------------------------------------------------------------
# GenerationState enum
# ---------------------------------------------------------------------------

class TestGenerationState:
    def test_all_values_exist(self):
        assert GenerationState.IDLE == "IDLE"
        assert GenerationState.GENERATING == "GENERATING"
        assert GenerationState.TOOL_EXECUTING == "TOOL_EXECUTING"
        assert GenerationState.WAITING_USER == "WAITING_USER"

    def test_is_str_subclass(self):
        assert isinstance(GenerationState.IDLE, str)

    def test_member_count(self):
        assert len(GenerationState) == 4


# ---------------------------------------------------------------------------
# InterventionType enum
# ---------------------------------------------------------------------------

class TestInterventionType:
    def test_all_values_exist(self):
        assert InterventionType.CORRECTION.value == "correction"
        assert InterventionType.ADDITIVE.value == "additive"
        assert InterventionType.CANCEL.value == "cancel"
        assert InterventionType.CONFIRM.value == "confirm"
        assert InterventionType.DIGRESSION.value == "digression"
        assert InterventionType.SIDEKICK_INSIGHT.value == "sidekick_insight"

    def test_is_str_subclass(self):
        assert isinstance(InterventionType.CANCEL, str)

    def test_case_sensitivity_lowercase_values(self):
        for member in InterventionType:
            assert member.value == member.value.lower()

    def test_member_count(self):
        assert len(InterventionType) == 6


# ---------------------------------------------------------------------------
# INTERVENTION_PRIORITIES
# ---------------------------------------------------------------------------

class TestInterventionPriorities:
    def test_cancel_priority_1(self):
        assert INTERVENTION_PRIORITIES["cancel"] == 1

    def test_correction_priority_1(self):
        assert INTERVENTION_PRIORITIES["correction"] == 1

    def test_additive_priority_2(self):
        assert INTERVENTION_PRIORITIES["additive"] == 2

    def test_confirm_priority_2(self):
        assert INTERVENTION_PRIORITIES["confirm"] == 2

    def test_digression_priority_3(self):
        assert INTERVENTION_PRIORITIES["digression"] == 3

    def test_sidekick_insight_priority_3(self):
        assert INTERVENTION_PRIORITIES["sidekick_insight"] == 3

    def test_covers_all_intervention_types(self):
        for member in InterventionType:
            assert member.value in INTERVENTION_PRIORITIES


# ---------------------------------------------------------------------------
# NON_INTERRUPTIBLE_TOOLS
# ---------------------------------------------------------------------------

class TestNonInterruptibleTools:
    EXPECTED_TOOLS = {
        "create_trip",
        "book_ticket",
        "send_message",
        "checkout",
        "create_task",
        "confirm_action",
    }

    def test_is_frozenset(self):
        assert isinstance(NON_INTERRUPTIBLE_TOOLS, frozenset)

    def test_contains_all_expected_tools(self):
        assert NON_INTERRUPTIBLE_TOOLS == self.EXPECTED_TOOLS

    def test_count(self):
        assert len(NON_INTERRUPTIBLE_TOOLS) == 6

    def test_immutable(self):
        with pytest.raises(AttributeError):
            NON_INTERRUPTIBLE_TOOLS.add("evil_tool")


# ---------------------------------------------------------------------------
# InterventionSignal
# ---------------------------------------------------------------------------

_FAKE_NOW_ISO = "2026-02-21T10:00:00+00:00"
_FAKE_NOW = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
_FAKE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_signal(**overrides):
    defaults = {
        "signal_id": _FAKE_UUID,
        "type": InterventionType.CORRECTION.value,
        "session_id": "sess-1",
        "job_id": "job-1",
        "user_id": "user-1",
        "timestamp": _FAKE_NOW_ISO,
        "payload": {"msg": "hello"},
        "priority": 1,
    }
    defaults.update(overrides)
    return InterventionSignal(**defaults)


class TestInterventionSignal:

    def test_to_dict_shape(self):
        sig = _make_signal()
        d = sig.to_dict()
        assert d == {
            "signal_id": _FAKE_UUID,
            "type": "correction",
            "session_id": "sess-1",
            "job_id": "job-1",
            "user_id": "user-1",
            "timestamp": _FAKE_NOW_ISO,
            "payload": {"msg": "hello"},
            "priority": 1,
        }

    def test_to_json_produces_valid_json(self):
        sig = _make_signal()
        raw = sig.to_json()
        parsed = json.loads(raw)
        assert parsed["signal_id"] == _FAKE_UUID

    def test_from_dict_round_trip(self):
        sig = _make_signal()
        restored = InterventionSignal.from_dict(sig.to_dict())
        assert restored == sig

    def test_from_json_round_trip(self):
        sig = _make_signal()
        restored = InterventionSignal.from_json(sig.to_json())
        assert restored == sig

    def test_from_dict_defaults_missing_optional_fields(self):
        minimal = {
            "type": "additive",
            "session_id": "s1",
            "job_id": "j1",
            "user_id": "u1",
        }
        with patch("src.ai_engine.intervention.types.utc_now", return_value=_FAKE_NOW):
            sig = InterventionSignal.from_dict(minimal)
        assert sig.payload == {}
        assert sig.priority == 2  # additive -> priority 2
        assert sig.timestamp == _FAKE_NOW_ISO

    @patch("src.ai_engine.intervention.types.utc_now", return_value=_FAKE_NOW)
    @patch("src.ai_engine.intervention.types.uuid.uuid4", return_value=uuid.UUID(_FAKE_UUID))
    def test_create_factory_generates_id_and_timestamp(self, _mock_uuid, _mock_now):
        sig = InterventionSignal.create(
            signal_type="cancel",
            session_id="sess-2",
            job_id="job-2",
            user_id="user-2",
        )
        assert sig.signal_id == _FAKE_UUID
        assert sig.timestamp == _FAKE_NOW_ISO
        assert sig.payload == {}

    @patch("src.ai_engine.intervention.types.utc_now", return_value=_FAKE_NOW)
    @patch("src.ai_engine.intervention.types.uuid.uuid4", return_value=uuid.UUID(_FAKE_UUID))
    def test_create_factory_sets_priority_from_mapping(self, _mock_uuid, _mock_now):
        cancel_sig = InterventionSignal.create(
            signal_type="cancel",
            session_id="s", job_id="j", user_id="u",
        )
        assert cancel_sig.priority == 1

        additive_sig = InterventionSignal.create(
            signal_type="additive",
            session_id="s", job_id="j", user_id="u",
        )
        assert additive_sig.priority == 2

        digression_sig = InterventionSignal.create(
            signal_type="digression",
            session_id="s", job_id="j", user_id="u",
        )
        assert digression_sig.priority == 3

    @patch("src.ai_engine.intervention.types.utc_now", return_value=_FAKE_NOW)
    @patch("src.ai_engine.intervention.types.uuid.uuid4", return_value=uuid.UUID(_FAKE_UUID))
    def test_create_factory_unknown_type_defaults_priority_2(self, _mock_uuid, _mock_now):
        sig = InterventionSignal.create(
            signal_type="unknown_type",
            session_id="s", job_id="j", user_id="u",
        )
        assert sig.priority == 2

    @patch("src.ai_engine.intervention.types.utc_now", return_value=_FAKE_NOW)
    @patch("src.ai_engine.intervention.types.uuid.uuid4", return_value=uuid.UUID(_FAKE_UUID))
    def test_create_factory_with_payload(self, _mock_uuid, _mock_now):
        payload = {"corrected_text": "foo"}
        sig = InterventionSignal.create(
            signal_type="correction",
            session_id="s", job_id="j", user_id="u",
            payload=payload,
        )
        assert sig.payload == payload

    def test_frozen_immutable(self):
        sig = _make_signal()
        with pytest.raises(FrozenInstanceError):
            sig.type = "additive"


# ---------------------------------------------------------------------------
# StitchingContext
# ---------------------------------------------------------------------------

def _make_stitching(**overrides):
    defaults = {
        "partial_text": "some partial output",
        "partial_thinking": "some thinking",
        "interrupted_at": _FAKE_NOW,
        "reason": "correction",
        "original_input": "user said something",
        "completed_tools": ["query_tasks"],
        "partial_tool": {"name": "web_search", "status": "running"},
    }
    defaults.update(overrides)
    return StitchingContext(**defaults)


class TestStitchingContext:

    def test_post_init_truncates_partial_text_at_construction(self):
        long_text = "a" * 500
        ctx = _make_stitching(partial_text=long_text)
        assert len(ctx.partial_text) == 200
        assert ctx.partial_text == long_text[-200:]

    def test_post_init_truncates_partial_thinking_at_construction(self):
        long_thinking = "b" * 300
        ctx = _make_stitching(partial_thinking=long_thinking)
        assert len(ctx.partial_thinking) == 100
        assert ctx.partial_thinking == long_thinking[-100:]

    def test_post_init_no_truncation_for_short_values(self):
        ctx = _make_stitching(partial_text="short", partial_thinking="brief")
        assert ctx.partial_text == "short"
        assert ctx.partial_thinking == "brief"

    def test_post_init_no_truncation_for_empty_strings(self):
        ctx = _make_stitching(partial_text="", partial_thinking="")
        assert ctx.partial_text == ""
        assert ctx.partial_thinking == ""

    def test_to_dict_truncates_partial_text_to_200_chars(self):
        long_text = "x" * 500
        ctx = _make_stitching(partial_text=long_text)
        d = ctx.to_dict()
        assert len(d["partial_text"]) == 200
        assert d["partial_text"] == long_text[-200:]

    def test_to_dict_does_not_truncate_short_partial_text(self):
        short_text = "short"
        ctx = _make_stitching(partial_text=short_text)
        d = ctx.to_dict()
        assert d["partial_text"] == short_text

    def test_to_dict_truncates_partial_thinking_to_100_chars(self):
        long_thinking = "t" * 300
        ctx = _make_stitching(partial_thinking=long_thinking)
        d = ctx.to_dict()
        assert len(d["partial_thinking"]) == 100
        assert d["partial_thinking"] == long_thinking[-100:]

    def test_to_dict_does_not_truncate_short_partial_thinking(self):
        short_thinking = "brief"
        ctx = _make_stitching(partial_thinking=short_thinking)
        d = ctx.to_dict()
        assert d["partial_thinking"] == short_thinking

    def test_to_dict_includes_all_fields(self):
        ctx = _make_stitching()
        d = ctx.to_dict()
        expected_keys = {
            "partial_text", "partial_thinking", "interrupted_at",
            "reason", "original_input", "completed_tools", "partial_tool",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_serializes_datetime_as_iso(self):
        ctx = _make_stitching()
        d = ctx.to_dict()
        assert d["interrupted_at"] == _FAKE_NOW.isoformat()

    def test_to_json_produces_valid_json(self):
        ctx = _make_stitching()
        raw = ctx.to_json()
        parsed = json.loads(raw)
        assert parsed["reason"] == "correction"

    def test_from_dict_round_trip(self):
        ctx = _make_stitching()
        d = ctx.to_dict()
        restored = StitchingContext.from_dict(d)
        # After round-trip, partial_text/thinking may be truncated, so compare via to_dict
        assert restored.to_dict() == d

    def test_from_json_round_trip(self):
        ctx = _make_stitching()
        raw = ctx.to_json()
        restored = StitchingContext.from_json(raw)
        assert restored.to_dict() == ctx.to_dict()

    def test_from_dict_handles_string_datetime(self):
        d = {
            "partial_text": "text",
            "partial_thinking": "",
            "interrupted_at": "2026-02-21T10:00:00+00:00",
            "reason": "cancel",
            "original_input": "stop",
        }
        ctx = StitchingContext.from_dict(d)
        assert isinstance(ctx.interrupted_at, datetime)
        assert ctx.interrupted_at.isoformat() == "2026-02-21T10:00:00+00:00"

    def test_from_dict_handles_datetime_object(self):
        d = {
            "partial_text": "text",
            "partial_thinking": "",
            "interrupted_at": _FAKE_NOW,
            "reason": "cancel",
            "original_input": "stop",
        }
        ctx = StitchingContext.from_dict(d)
        assert ctx.interrupted_at == _FAKE_NOW

    def test_from_dict_defaults_missing_optional_fields(self):
        d = {
            "interrupted_at": _FAKE_NOW,
        }
        ctx = StitchingContext.from_dict(d)
        assert ctx.partial_text == ""
        assert ctx.partial_thinking == ""
        assert ctx.reason == ""
        assert ctx.original_input == ""
        assert ctx.completed_tools == []
        assert ctx.partial_tool is None

    def test_frozen_immutable(self):
        ctx = _make_stitching()
        with pytest.raises(FrozenInstanceError):
            ctx.reason = "digression"

    def test_completed_tools_is_copied_to_list(self):
        ctx = _make_stitching(completed_tools=["a", "b"])
        d = ctx.to_dict()
        # Modifying the dict output should not affect the original
        d["completed_tools"].append("c")
        assert "c" not in ctx.completed_tools


# ---------------------------------------------------------------------------
# InterventionBudget
# ---------------------------------------------------------------------------

class TestInterventionBudget:

    def test_default_values(self):
        budget = InterventionBudget()
        assert budget.max_interventions_per_session == 5
        assert budget.max_additive_per_turn == 2
        assert budget.max_correction_per_session == 3
        assert budget.context_compression_threshold == 3

    def test_custom_values(self):
        budget = InterventionBudget(
            max_interventions_per_session=10,
            max_additive_per_turn=4,
            max_correction_per_session=6,
            context_compression_threshold=5,
        )
        assert budget.max_interventions_per_session == 10
        assert budget.max_additive_per_turn == 4

    def test_frozen_immutable(self):
        budget = InterventionBudget()
        with pytest.raises(FrozenInstanceError):
            budget.max_interventions_per_session = 99


# ---------------------------------------------------------------------------
# SessionStatus
# ---------------------------------------------------------------------------

def _make_session_status(**overrides):
    defaults = {
        "state": GenerationState.GENERATING.value,
        "job_id": "job-1",
        "worker_id": "worker-1",
        "sdk_session_id": "sdk-1",
        "last_heartbeat": _FAKE_NOW_ISO,
        "task_summary": "answering user query",
        "active_tool": "web_search",
    }
    defaults.update(overrides)
    return SessionStatus(**defaults)


class TestSessionStatus:

    def test_is_active_generating(self):
        status = _make_session_status(state=GenerationState.GENERATING.value)
        assert status.is_active() is True

    def test_is_active_tool_executing(self):
        status = _make_session_status(state=GenerationState.TOOL_EXECUTING.value)
        assert status.is_active() is True

    def test_is_active_waiting_user(self):
        status = _make_session_status(state=GenerationState.WAITING_USER.value)
        assert status.is_active() is True

    def test_is_active_idle(self):
        status = _make_session_status(state=GenerationState.IDLE.value)
        assert status.is_active() is False

    def test_to_dict(self):
        status = _make_session_status()
        d = status.to_dict()
        assert d["state"] == "GENERATING"
        assert d["job_id"] == "job-1"
        assert d["active_tool"] == "web_search"
        assert d["user_id"] == ""

    def test_to_dict_active_tool_none(self):
        status = _make_session_status(active_tool=None)
        d = status.to_dict()
        assert d["active_tool"] is None

    def test_to_dict_with_user_id(self):
        status = _make_session_status(user_id="user-42")
        d = status.to_dict()
        assert d["user_id"] == "user-42"

    def test_from_dict_round_trip(self):
        status = _make_session_status()
        restored = SessionStatus.from_dict(status.to_dict())
        assert restored == status

    def test_from_dict_defaults_missing_optional(self):
        minimal = {"state": "IDLE", "job_id": "j1"}
        status = SessionStatus.from_dict(minimal)
        assert status.worker_id == ""
        assert status.sdk_session_id == ""
        assert status.last_heartbeat == ""
        assert status.task_summary == ""
        assert status.active_tool is None
        assert status.user_id == ""

    def test_from_dict_with_user_id(self):
        data = {
            "state": "GENERATING",
            "job_id": "j1",
            "user_id": "user-99",
        }
        status = SessionStatus.from_dict(data)
        assert status.user_id == "user-99"

    def test_to_json_produces_valid_json(self):
        status = _make_session_status()
        raw = status.to_json()
        parsed = json.loads(raw)
        assert parsed["state"] == "GENERATING"

    def test_from_json_round_trip(self):
        status = _make_session_status()
        restored = SessionStatus.from_json(status.to_json())
        assert restored == status

    def test_from_json_empty_string_returns_none(self):
        assert SessionStatus.from_json("") is None

    def test_frozen_immutable(self):
        status = _make_session_status()
        with pytest.raises(FrozenInstanceError):
            status.state = "IDLE"


# ---------------------------------------------------------------------------
# ClassificationResult
# ---------------------------------------------------------------------------

class TestClassificationResult:

    def test_effective_type_correction_low_confidence_becomes_digression(self):
        result = ClassificationResult(type="correction", confidence=0.50)
        assert result.effective_type == InterventionType.DIGRESSION.value

    def test_effective_type_cancel_low_confidence_becomes_additive(self):
        result = ClassificationResult(type="cancel", confidence=0.0)
        assert result.effective_type == "additive"

    def test_effective_type_correction_just_below_threshold_becomes_digression(self):
        result = ClassificationResult(type="correction", confidence=0.599)
        assert result.effective_type == "digression"

    def test_effective_type_digression_low_confidence_stays_digression(self):
        result = ClassificationResult(type="digression", confidence=0.40)
        assert result.effective_type == "digression"

    def test_effective_type_additive_low_confidence_stays_additive(self):
        result = ClassificationResult(type="additive", confidence=0.40)
        assert result.effective_type == "additive"

    def test_effective_type_confirm_low_confidence_stays_additive(self):
        result = ClassificationResult(type="confirm", confidence=0.40)
        assert result.effective_type == "additive"

    def test_effective_type_returns_original_at_threshold(self):
        result = ClassificationResult(type="correction", confidence=0.60)
        assert result.effective_type == "correction"

    def test_effective_type_returns_original_above_threshold(self):
        result = ClassificationResult(type="cancel", confidence=0.95)
        assert result.effective_type == "cancel"

    def test_requires_audit_true_at_lower_bound(self):
        result = ClassificationResult(type="correction", confidence=0.60)
        assert result.requires_audit is True

    def test_requires_audit_true_in_band(self):
        result = ClassificationResult(type="correction", confidence=0.75)
        assert result.requires_audit is True

    def test_requires_audit_true_just_below_upper(self):
        result = ClassificationResult(type="correction", confidence=0.849)
        assert result.requires_audit is True

    def test_requires_audit_false_below_lower_bound(self):
        result = ClassificationResult(type="correction", confidence=0.59)
        assert result.requires_audit is False

    def test_requires_audit_false_at_upper_bound(self):
        result = ClassificationResult(type="correction", confidence=0.85)
        assert result.requires_audit is False

    def test_requires_audit_false_above_upper_bound(self):
        result = ClassificationResult(type="correction", confidence=0.99)
        assert result.requires_audit is False

    def test_default_latency_ms(self):
        result = ClassificationResult(type="cancel", confidence=0.9)
        assert result.latency_ms == 0

    def test_custom_latency_ms(self):
        result = ClassificationResult(type="cancel", confidence=0.9, latency_ms=42)
        assert result.latency_ms == 42

    def test_frozen_immutable(self):
        result = ClassificationResult(type="cancel", confidence=0.9)
        with pytest.raises(FrozenInstanceError):
            result.confidence = 0.1


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

class TestRedisKeyHelpers:

    def test_session_status_key(self):
        assert session_status_key("abc-123") == "session:status:abc-123"

    def test_session_signal_channel(self):
        assert session_signal_channel("abc-123") == "session:signal:abc-123"

    def test_session_stitch_key(self):
        assert session_stitch_key("abc-123") == "session:stitch:abc-123"

    def test_keys_with_uuid(self):
        sid = "550e8400-e29b-41d4-a716-446655440000"
        assert session_status_key(sid) == f"session:status:{sid}"
        assert session_signal_channel(sid) == f"session:signal:{sid}"
        assert session_stitch_key(sid) == f"session:stitch:{sid}"
