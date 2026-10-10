"""Tests for intervention routing in chat API.

Covers:
- _get_session_status helper
- _build_signal_payload helper
- _try_intervention_routing end-to-end flow
- SignalAcceptedResponse model
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_engine.intervention.types import (
    ClassificationResult,
    GenerationState,
    InterventionType,
    SessionStatus,
)
from src.api.v1.chat import (
    SignalAcceptedResponse,
    _build_signal_payload,
    _get_session_status,
    _try_intervention_routing,
)


# ---------------------------------------------------------------------------
# _build_signal_payload tests
# ---------------------------------------------------------------------------


class TestBuildSignalPayload:
    @pytest.mark.asyncio
    async def test_correction_payload(self):
        payload = await _build_signal_payload(
            "correction", "改成去上海", "帮我查北京的天气"
        )
        assert payload["corrected_input"] == "改成去上海"
        assert payload["original_input"] == "帮我查北京的天气"
        assert payload["intent_class"] == "correction"

    @pytest.mark.asyncio
    async def test_additive_payload(self):
        payload = await _build_signal_payload(
            "additive", "顺便查下明天的", ""
        )
        assert payload["additional_input"] == "顺便查下明天的"
        assert payload["intent_class"] == "additive"

    @pytest.mark.asyncio
    async def test_cancel_payload(self):
        payload = await _build_signal_payload("cancel", "算了不要了", "")
        assert payload["reason"] == "user_initiated"
        assert "text" not in payload

    @pytest.mark.asyncio
    async def test_confirm_payload_approve(self):
        payload = await _build_signal_payload("confirm", "确认", "")
        assert payload["confirmation"] == "approve"
        assert payload["intent_class"] == "confirm"
        assert payload["text"] == "确认"
        assert "input" not in payload  # M10: removed redundant input key

    @pytest.mark.asyncio
    async def test_confirm_payload_reject(self):
        payload = await _build_signal_payload("confirm", "不要了", "")
        assert payload["confirmation"] == "reject"
        assert payload["intent_class"] == "confirm"

    @pytest.mark.asyncio
    async def test_confirm_payload_reject_keywords(self):
        for keyword in ["不要", "不行", "不用", "取消", "no", "reject", "拒绝", "算了", "cancel"]:
            payload = await _build_signal_payload("confirm", keyword, "")
            assert payload["confirmation"] == "reject", f"Expected reject for keyword: {keyword}"

    @pytest.mark.asyncio
    async def test_confirm_payload_approve_keywords(self):
        for keyword in ["好", "是", "确认", "ok", "yes", "approve", "确定", "同意", "可以", "行"]:
            payload = await _build_signal_payload("confirm", keyword, "")
            assert payload["confirmation"] == "approve", f"Expected approve for keyword: {keyword}"

    @pytest.mark.asyncio
    async def test_confirm_payload_approve_overrides(self):
        """Compound words like '不错' should be approved, not rejected."""
        for keyword in ["不错", "好的", "是的", "行的", "可以的"]:
            payload = await _build_signal_payload("confirm", keyword, "")
            assert payload["confirmation"] == "approve", f"Expected approve for override: {keyword}"

    @pytest.mark.asyncio
    async def test_confirm_payload_defaults_to_approve_on_ambiguous(self):
        """W4: Ambiguous input defaults to approve AND sets is_ambiguous flag."""
        payload = await _build_signal_payload("confirm", "我看看", "")
        assert payload["confirmation"] == "approve"
        assert payload.get("is_ambiguous") is True

    @pytest.mark.asyncio
    async def test_confirm_payload_no_ambiguous_flag_on_explicit_approve(self):
        """W4: Explicit approve keywords should NOT set is_ambiguous."""
        payload = await _build_signal_payload("confirm", "确认", "")
        assert payload["confirmation"] == "approve"
        assert "is_ambiguous" not in payload

    @pytest.mark.asyncio
    async def test_confirm_payload_no_ambiguous_flag_on_reject(self):
        """W4: Reject confirmation should NOT set is_ambiguous."""
        payload = await _build_signal_payload("confirm", "不要了", "")
        assert payload["confirmation"] == "reject"
        assert "is_ambiguous" not in payload

    @pytest.mark.asyncio
    async def test_digression_payload(self):
        payload = await _build_signal_payload(
            "digression", "今天吃什么", ""
        )
        assert payload["new_input"] == "今天吃什么"
        assert payload["intent_class"] == "digression"

    @pytest.mark.asyncio
    async def test_unknown_type_fallback(self):
        payload = await _build_signal_payload("unknown", "hello", "")
        assert payload["input"] == "hello"


# ---------------------------------------------------------------------------
# _get_session_status tests
# ---------------------------------------------------------------------------


class TestGetSessionStatus:
    @pytest.mark.asyncio
    async def test_returns_none_for_empty_session_id(self):
        result = await _get_session_status(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_string(self):
        result = await _get_session_status("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_redis_data(self):
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        with patch("src.core.cache.redis_client", mock_redis):
            result = await _get_session_status("some-session-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_session_status_from_redis(self):
        status_data = {
            "state": GenerationState.GENERATING.value,
            "job_id": "job-1",
            "worker_id": "w-1",
            "sdk_session_id": "sdk-1",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "task_summary": "Looking up weather",
        }
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(status_data))
        with patch("src.core.cache.redis_client", mock_redis):
            result = await _get_session_status("session-123")
        assert result is not None
        assert result.state == GenerationState.GENERATING.value
        assert result.job_id == "job-1"
        assert result.is_active() is True

    @pytest.mark.asyncio
    async def test_returns_none_on_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        with patch("src.core.cache.redis_client", mock_redis):
            result = await _get_session_status("session-123")
        assert result is None


# ---------------------------------------------------------------------------
# _try_intervention_routing tests
# ---------------------------------------------------------------------------


class TestTryInterventionRouting:
    @pytest.fixture
    def mock_request(self):
        req = MagicMock()
        req.message = "改成去上海"
        req.session_id = str(uuid.uuid4())
        return req

    @pytest.fixture
    def active_status(self):
        return SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="job-123",
            worker_id="w-1",
            sdk_session_id="sdk-1",
            last_heartbeat="2026-02-21T00:00:00+00:00",
            task_summary="查北京天气",
            active_tool=None,
        )

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_session(self, mock_request):
        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=None,
        ):
            mock_db = AsyncMock()
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_session_idle(self, mock_request):
        idle_status = SessionStatus(
            state=GenerationState.IDLE.value,
            job_id="old-job",
            worker_id="w-1",
            sdk_session_id="sdk-1",
            last_heartbeat="2026-02-21T00:00:00+00:00",
            task_summary="",
        )
        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=idle_status,
        ):
            mock_db = AsyncMock()
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_intervention_routing(
        self, mock_request, active_status,
    ):
        classification = ClassificationResult(
            type=InterventionType.CORRECTION.value,
            confidence=0.92,
            latency_ms=45,
        )

        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(return_value=classification)

        mock_redis_client = AsyncMock()

        mock_msg_svc = AsyncMock()
        mock_msg_svc.save_user_message = AsyncMock()

        mock_db = AsyncMock()

        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=active_status,
        ), patch(
            "src.api.v1.chat._get_last_user_message",
            new_callable=AsyncMock,
            return_value="帮我查北京的天气",
        ), patch(
            "src.core.cache.redis_client",
        ) as mock_redis_mod, patch(
            "src.ai_engine.intervention.classifier.get_intervention_classifier",
            return_value=mock_classifier,
        ), patch(
            "src.modules.conversation.MessageService",
            return_value=mock_msg_svc,
        ):
            mock_redis_mod.client = mock_redis_client
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )

        assert result is not None
        assert isinstance(result, SignalAcceptedResponse)
        assert result.signal_type == "correction"
        assert result.classification_confidence == 0.92
        assert result.status == "signal_accepted"

    @pytest.mark.asyncio
    async def test_falls_back_on_classifier_error(
        self, mock_request, active_status,
    ):
        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=active_status,
        ), patch(
            "src.ai_engine.intervention.classifier.get_intervention_classifier",
            side_effect=Exception("Classifier crashed"),
        ):
            mock_db = AsyncMock()
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_low_confidence_correction_degrades_to_digression(
        self, mock_request, active_status,
    ):
        classification = ClassificationResult(
            type=InterventionType.CORRECTION.value,
            confidence=0.45,  # Below 0.60 threshold
            latency_ms=50,
        )

        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(return_value=classification)

        mock_redis_client = AsyncMock()

        mock_msg_svc = AsyncMock()
        mock_msg_svc.save_user_message = AsyncMock()

        mock_db = AsyncMock()

        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=active_status,
        ), patch(
            "src.api.v1.chat._get_last_user_message",
            new_callable=AsyncMock,
            return_value="prev msg",
        ), patch(
            "src.core.cache.redis_client",
        ) as mock_redis_mod, patch(
            "src.ai_engine.intervention.classifier.get_intervention_classifier",
            return_value=mock_classifier,
        ), patch(
            "src.modules.conversation.MessageService",
            return_value=mock_msg_svc,
        ):
            mock_redis_mod.client = mock_redis_client
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )

        assert result is not None
        # effective_type should be "digression" due to low confidence correction
        assert result.signal_type == "digression"

    @pytest.mark.asyncio
    async def test_cancel_intervention_routing(
        self, mock_request, active_status,
    ):
        """Classifier returns CANCEL -> signal built with type=cancel and published."""
        mock_request.message = "算了不要了"

        classification = ClassificationResult(
            type=InterventionType.CANCEL.value,
            confidence=0.95,
            latency_ms=30,
        )

        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(return_value=classification)

        mock_redis_client = AsyncMock()

        mock_msg_svc = AsyncMock()
        mock_msg_svc.save_user_message = AsyncMock()

        mock_db = AsyncMock()

        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=active_status,
        ), patch(
            "src.api.v1.chat._get_last_user_message",
            new_callable=AsyncMock,
            return_value="帮我查北京的天气",
        ), patch(
            "src.core.cache.redis_client",
        ) as mock_redis_mod, patch(
            "src.ai_engine.intervention.classifier.get_intervention_classifier",
            return_value=mock_classifier,
        ), patch(
            "src.modules.conversation.MessageService",
            return_value=mock_msg_svc,
        ):
            mock_redis_mod.client = mock_redis_client
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )

        assert result is not None
        assert isinstance(result, SignalAcceptedResponse)
        assert result.signal_type == "cancel"
        assert result.classification_confidence == 0.95
        assert result.status == "signal_accepted"

    @pytest.mark.asyncio
    async def test_digression_intervention_routing(
        self, mock_request, active_status,
    ):
        """Classifier returns DIGRESSION -> signal built with type=digression and published."""
        mock_request.message = "今天吃什么"

        classification = ClassificationResult(
            type=InterventionType.DIGRESSION.value,
            confidence=0.88,
            latency_ms=40,
        )

        mock_classifier = AsyncMock()
        mock_classifier.classify = AsyncMock(return_value=classification)

        mock_redis_client = AsyncMock()

        mock_msg_svc = AsyncMock()
        mock_msg_svc.save_user_message = AsyncMock()

        mock_db = AsyncMock()

        with patch(
            "src.api.v1.chat._get_session_status",
            new_callable=AsyncMock,
            return_value=active_status,
        ), patch(
            "src.api.v1.chat._get_last_user_message",
            new_callable=AsyncMock,
            return_value="帮我订去上海的机票",
        ), patch(
            "src.core.cache.redis_client",
        ) as mock_redis_mod, patch(
            "src.ai_engine.intervention.classifier.get_intervention_classifier",
            return_value=mock_classifier,
        ), patch(
            "src.modules.conversation.MessageService",
            return_value=mock_msg_svc,
        ):
            mock_redis_mod.client = mock_redis_client
            result = await _try_intervention_routing(
                mock_request, mock_db, uuid.uuid4(), uuid.uuid4()
            )

        assert result is not None
        assert isinstance(result, SignalAcceptedResponse)
        assert result.signal_type == "digression"
        assert result.classification_confidence == 0.88
        assert result.status == "signal_accepted"


# ---------------------------------------------------------------------------
# SignalAcceptedResponse model tests
# ---------------------------------------------------------------------------


class TestSignalAcceptedResponse:
    def test_default_status(self):
        resp = SignalAcceptedResponse(
            signal_id="sig-1",
            signal_type="correction",
            classification_confidence=0.9,
        )
        assert resp.status == "signal_accepted"

    def test_all_fields(self):
        resp = SignalAcceptedResponse(
            signal_id="sig-2",
            signal_type="additive",
            classification_confidence=0.75,
        )
        data = resp.model_dump()
        assert data["status"] == "signal_accepted"
        assert data["signal_id"] == "sig-2"
        assert data["signal_type"] == "additive"
        assert data["classification_confidence"] == 0.75
