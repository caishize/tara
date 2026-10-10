"""
Unit tests for InterventionClassifier — sub-150ms Haiku-based
message classification for the intervention system.

Tests cover:
- Constructor: custom client/model, settings fallback, missing model error
- Lazy client creation via property
- classify(): successful classification, API error fallback, JSON error fallback
- _call_classifier(): prompt construction, active_tool handling, empty response
- _strip_markdown_fence(): fence stripping and passthrough
- _parse_type(): valid types, unknown types, None/empty
- _parse_confidence(): valid float, clamping, None, invalid input
- get_intervention_classifier(): singleton behaviour
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_engine.intervention.classifier import (
    InterventionClassifier,
    CLASSIFICATION_PROMPT,
    _DEFAULT_TYPE,
    _DEFAULT_CONFIDENCE,
    get_intervention_classifier,
)
from src.ai_engine.intervention.types import (
    ClassificationResult,
    InterventionType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages.create() response with a single TextBlock."""
    mock_block = MagicMock()
    mock_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    return mock_response


def _make_empty_response() -> MagicMock:
    """Build a mock response with no TextBlock (e.g. only tool_use blocks)."""
    mock_block = MagicMock(spec=[])  # spec=[] means no attributes at all
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    return mock_response


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_accepts_custom_client_and_model(self):
        client = MagicMock()
        clf = InterventionClassifier(client=client, model="claude-haiku-4")
        assert clf._custom_client is client
        assert clf._model == "claude-haiku-4"

    @patch("src.ai_engine.intervention.classifier.settings")
    def test_uses_settings_model_when_not_provided(self, mock_settings):
        mock_settings.intent_router_model = "claude-3-haiku-from-settings"
        clf = InterventionClassifier(client=MagicMock())
        assert clf._model == "claude-3-haiku-from-settings"

    @patch("src.ai_engine.intervention.classifier.settings")
    def test_raises_value_error_when_no_model(self, mock_settings):
        mock_settings.intent_router_model = ""
        with pytest.raises(ValueError, match="model not configured"):
            InterventionClassifier(client=MagicMock())

    @patch("src.ai_engine.intervention.classifier.settings")
    def test_raises_value_error_when_model_is_none(self, mock_settings):
        mock_settings.intent_router_model = None
        with pytest.raises(ValueError, match="model not configured"):
            InterventionClassifier(client=MagicMock())


# ---------------------------------------------------------------------------
# Lazy client property
# ---------------------------------------------------------------------------

class TestClientProperty:
    @patch("src.ai_engine.intervention.classifier.get_haiku_client")
    @patch("src.ai_engine.intervention.classifier.settings")
    def test_uses_shared_haiku_client_when_none(self, mock_settings, mock_get_client):
        mock_settings.intent_router_model = "claude-haiku-4"
        mock_shared = MagicMock()
        mock_get_client.return_value = mock_shared

        clf = InterventionClassifier()
        client = clf.client

        mock_get_client.assert_called_once()
        assert client is mock_shared

    @patch("src.ai_engine.intervention.classifier.settings")
    def test_returns_existing_client(self, mock_settings):
        mock_settings.intent_router_model = "claude-haiku-4"
        existing_client = MagicMock()
        clf = InterventionClassifier(client=existing_client)

        assert clf.client is existing_client
        assert clf.client is existing_client  # second access returns same


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------

class TestClassify:
    @pytest.mark.asyncio
    async def test_successful_classification(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "CORRECTION", "confidence": 0.92}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="Planning a trip to Beijing",
            last_user_message="Help me plan a trip",
            new_user_message="Actually, change to Shanghai",
        )

        assert isinstance(result, ClassificationResult)
        assert result.type == "correction"
        assert result.confidence == 0.92
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_returns_correct_effective_type_high_confidence(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "CANCEL", "confidence": 0.95}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="Searching for gifts",
            last_user_message="Find gifts for mom",
            new_user_message="Stop, forget it",
        )

        assert result.type == "cancel"
        assert result.effective_type == "cancel"

    @pytest.mark.asyncio
    async def test_effective_type_degrades_below_threshold(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "CORRECTION", "confidence": 0.5}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="new msg",
        )

        assert result.type == "correction"
        assert result.confidence == 0.5
        assert result.effective_type == "digression"  # degraded: correction at low confidence → digression

    @pytest.mark.asyncio
    async def test_falls_back_on_api_error(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=RuntimeError("API connection refused")
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="new msg",
        )

        assert result.type == _DEFAULT_TYPE
        assert result.confidence == _DEFAULT_CONFIDENCE
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_falls_back_on_json_decode_error(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response("not valid json at all {{{")
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="new msg",
        )

        # _call_classifier catches JSONDecodeError and returns defaults,
        # so classify() gets a valid dict — result should be defaults
        assert result.type == _DEFAULT_TYPE
        assert result.confidence == _DEFAULT_CONFIDENCE

    @pytest.mark.asyncio
    async def test_latency_ms_is_populated(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "ADDITIVE", "confidence": 0.7}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="new msg",
        )

        assert isinstance(result.latency_ms, int)
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_classify_with_active_tool(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "CONFIRM", "confidence": 0.88}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf.classify(
            current_task_summary="Booking a ticket",
            last_user_message="Book a flight",
            new_user_message="Yes, confirm",
            active_tool="book_ticket",
        )

        assert result.type == "confirm"
        assert result.confidence == 0.88


# ---------------------------------------------------------------------------
# _call_classifier()
# ---------------------------------------------------------------------------

class TestCallClassifier:
    @pytest.mark.asyncio
    async def test_constructs_prompt_with_all_fields(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "ADDITIVE", "confidence": 0.7}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        await clf._call_classifier(
            current_task_summary="Planning trip",
            last_user_message="Plan Beijing trip",
            new_user_message="Also include Shanghai",
            active_tool=None,
        )

        call_args = mock_client.messages.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "Planning trip" in prompt_content
        assert "Plan Beijing trip" in prompt_content
        assert "Also include Shanghai" in prompt_content

    @pytest.mark.asyncio
    async def test_includes_active_tool_line(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "CANCEL", "confidence": 0.9}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        await clf._call_classifier(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="stop",
            active_tool="create_trip",
        )

        call_args = mock_client.messages.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "正在执行的工具: create_trip" in prompt_content

    @pytest.mark.asyncio
    async def test_shows_no_tool_in_agent_state_when_none(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "ADDITIVE", "confidence": 0.6}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        await clf._call_classifier(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="more info",
            active_tool=None,
        )

        call_args = mock_client.messages.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "正在执行的工具: 无" in prompt_content

    @pytest.mark.asyncio
    async def test_handles_markdown_fence_stripping(self):
        fenced_json = '```json\n{"type": "DIGRESSION", "confidence": 0.85}\n```'
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response(fenced_json)
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf._call_classifier(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="what about dinner",
            active_tool=None,
        )

        assert result["type"] == "DIGRESSION"
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_handles_empty_response_no_text_block(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_empty_response()
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf._call_classifier(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="new msg",
            active_tool=None,
        )

        assert result["type"] == _DEFAULT_TYPE
        assert result["confidence"] == _DEFAULT_CONFIDENCE

    @pytest.mark.asyncio
    async def test_handles_json_decode_error(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response("I cannot parse this as JSON")
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf._call_classifier(
            current_task_summary="task",
            last_user_message="msg",
            new_user_message="new",
            active_tool=None,
        )

        assert result["type"] == _DEFAULT_TYPE
        assert result["confidence"] == _DEFAULT_CONFIDENCE

    @pytest.mark.asyncio
    async def test_uses_correct_model_and_max_tokens(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{"type": "ADDITIVE", "confidence": 0.5}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        await clf._call_classifier("task", "msg", "new", None)

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-haiku-4"
        assert call_args.kwargs["max_tokens"] == 80

    @pytest.mark.asyncio
    async def test_missing_fields_in_response_use_defaults(self):
        """When API returns JSON without type/confidence, defaults are used."""
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_api_response('{}')
        )
        clf = InterventionClassifier(client=mock_client, model="claude-haiku-4")

        result = await clf._call_classifier("task", "msg", "new", None)

        assert result["type"] == _DEFAULT_TYPE
        assert result["confidence"] == _DEFAULT_CONFIDENCE


# ---------------------------------------------------------------------------
# _strip_markdown_fence()
# ---------------------------------------------------------------------------

class TestStripMarkdownFence:
    def test_strips_json_fence(self):
        content = '```json\n{"type": "CANCEL"}\n```'
        result = InterventionClassifier._strip_markdown_fence(content)
        assert result == '{"type": "CANCEL"}'

    def test_strips_plain_fence(self):
        content = '```\n{"type": "CANCEL"}\n```'
        result = InterventionClassifier._strip_markdown_fence(content)
        assert result == '{"type": "CANCEL"}'

    def test_returns_unchanged_without_fence(self):
        content = '{"type": "CANCEL", "confidence": 0.9}'
        result = InterventionClassifier._strip_markdown_fence(content)
        assert result == content

    def test_handles_empty_string(self):
        result = InterventionClassifier._strip_markdown_fence("")
        assert result == ""

    def test_handles_whitespace_content(self):
        content = '```json\n  {"type": "ADDITIVE"}  \n```'
        result = InterventionClassifier._strip_markdown_fence(content)
        assert result == '{"type": "ADDITIVE"}'

    def test_strips_surrounding_whitespace(self):
        content = '  {"type": "CANCEL"}  '
        result = InterventionClassifier._strip_markdown_fence(content)
        assert result == '{"type": "CANCEL"}'


# ---------------------------------------------------------------------------
# _parse_type()
# ---------------------------------------------------------------------------

class TestParseType:
    def test_valid_correction(self):
        assert InterventionClassifier._parse_type("CORRECTION") == "correction"

    def test_valid_additive(self):
        assert InterventionClassifier._parse_type("ADDITIVE") == "additive"

    def test_valid_cancel(self):
        assert InterventionClassifier._parse_type("CANCEL") == "cancel"

    def test_valid_confirm(self):
        assert InterventionClassifier._parse_type("CONFIRM") == "confirm"

    def test_valid_digression(self):
        assert InterventionClassifier._parse_type("DIGRESSION") == "digression"

    def test_valid_lowercase_input(self):
        assert InterventionClassifier._parse_type("correction") == "correction"

    def test_valid_mixed_case(self):
        assert InterventionClassifier._parse_type("Correction") == "correction"

    def test_valid_with_whitespace(self):
        assert InterventionClassifier._parse_type("  CANCEL  ") == "cancel"

    def test_unknown_type_returns_default(self):
        assert InterventionClassifier._parse_type("UNKNOWN") == _DEFAULT_TYPE

    def test_garbage_returns_default(self):
        assert InterventionClassifier._parse_type("foobar") == _DEFAULT_TYPE

    def test_none_returns_default(self):
        assert InterventionClassifier._parse_type(None) == _DEFAULT_TYPE

    def test_empty_string_returns_default(self):
        assert InterventionClassifier._parse_type("") == _DEFAULT_TYPE

    def test_sidekick_insight_valid(self):
        assert InterventionClassifier._parse_type("SIDEKICK_INSIGHT") == "sidekick_insight"


# ---------------------------------------------------------------------------
# _parse_confidence()
# ---------------------------------------------------------------------------

class TestParseConfidence:
    def test_valid_float(self):
        assert InterventionClassifier._parse_confidence(0.85) == 0.85

    def test_valid_int(self):
        assert InterventionClassifier._parse_confidence(1) == 1.0

    def test_valid_string_float(self):
        assert InterventionClassifier._parse_confidence("0.72") == 0.72

    def test_clamps_above_one(self):
        assert InterventionClassifier._parse_confidence(1.5) == 1.0

    def test_clamps_below_zero(self):
        assert InterventionClassifier._parse_confidence(-0.3) == 0.0

    def test_zero_value(self):
        assert InterventionClassifier._parse_confidence(0.0) == 0.0

    def test_exactly_one(self):
        assert InterventionClassifier._parse_confidence(1.0) == 1.0

    def test_none_returns_default(self):
        assert InterventionClassifier._parse_confidence(None) == _DEFAULT_CONFIDENCE

    def test_invalid_string_returns_default(self):
        assert InterventionClassifier._parse_confidence("not a number") == _DEFAULT_CONFIDENCE

    def test_empty_string_returns_default(self):
        assert InterventionClassifier._parse_confidence("") == _DEFAULT_CONFIDENCE

    def test_boolean_true_treated_as_one(self):
        # float(True) == 1.0, which is valid
        assert InterventionClassifier._parse_confidence(True) == 1.0

    def test_boolean_false_treated_as_zero(self):
        # float(False) == 0.0, which is valid
        assert InterventionClassifier._parse_confidence(False) == 0.0


# ---------------------------------------------------------------------------
# ClassificationResult properties (verify integration with classifier output)
# ---------------------------------------------------------------------------

class TestClassificationResultProperties:
    def test_requires_audit_in_band(self):
        result = ClassificationResult(type="correction", confidence=0.75, latency_ms=42)
        assert result.requires_audit is True

    def test_no_audit_above_band(self):
        result = ClassificationResult(type="correction", confidence=0.90, latency_ms=42)
        assert result.requires_audit is False

    def test_no_audit_below_band(self):
        result = ClassificationResult(type="correction", confidence=0.50, latency_ms=42)
        assert result.requires_audit is False

    def test_effective_type_high_confidence(self):
        result = ClassificationResult(type="cancel", confidence=0.85, latency_ms=10)
        assert result.effective_type == "cancel"

    def test_effective_type_cancel_low_confidence_degrades_to_additive(self):
        result = ClassificationResult(type="cancel", confidence=0.55, latency_ms=10)
        assert result.effective_type == "additive"

    def test_effective_type_at_threshold_boundary(self):
        result = ClassificationResult(type="correction", confidence=0.60, latency_ms=10)
        assert result.effective_type == "correction"

    def test_effective_type_correction_below_threshold_becomes_digression(self):
        result = ClassificationResult(type="correction", confidence=0.59, latency_ms=10)
        assert result.effective_type == "digression"


# ---------------------------------------------------------------------------
# get_intervention_classifier() singleton
# ---------------------------------------------------------------------------

class TestGetInterventionClassifier:
    @patch("src.ai_engine.intervention.classifier._classifier", None)
    @patch("src.ai_engine.intervention.classifier.settings")
    def test_returns_instance(self, mock_settings):
        mock_settings.intent_router_model = "claude-haiku-4"
        clf = get_intervention_classifier()
        assert isinstance(clf, InterventionClassifier)

    @patch("src.ai_engine.intervention.classifier._classifier", None)
    @patch("src.ai_engine.intervention.classifier.settings")
    def test_returns_same_instance(self, mock_settings):
        mock_settings.intent_router_model = "claude-haiku-4"
        clf1 = get_intervention_classifier()
        clf2 = get_intervention_classifier()
        assert clf1 is clf2

    @patch("src.ai_engine.intervention.classifier._classifier", None)
    @patch("src.ai_engine.intervention.classifier.settings")
    def test_raises_when_no_model(self, mock_settings):
        mock_settings.intent_router_model = ""
        with pytest.raises(ValueError, match="model not configured"):
            get_intervention_classifier()


# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_type_is_additive(self):
        assert _DEFAULT_TYPE == InterventionType.ADDITIVE.value
        assert _DEFAULT_TYPE == "additive"

    def test_default_confidence_is_half(self):
        assert _DEFAULT_CONFIDENCE == 0.5
