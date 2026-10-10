"""
Unit tests for SidekickWorker.

Tests cover expiry checks, contextual relevance, injection rate limits,
recording, signal building, and the full evaluate_and_inject integration flow.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.ai_engine.workers.sidekick_worker import (
    INJECTION_PROMPT_TEMPLATE,
    SidekickWorker,
    _MAX_INJECTIONS_PER_SESSION,
    _MIN_INJECTION_INTERVAL_SECONDS,
    _COUNT_KEY_TTL_SECONDS,
)
from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionSignal,
    InterventionType,
    SessionStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def worker():
    return SidekickWorker()


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.scan = AsyncMock(return_value=(0, []))
    mock.publish = AsyncMock()
    mock.close = AsyncMock()
    pipe = AsyncMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.setex = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, True])
    mock.pipeline = MagicMock(return_value=pipe)
    return mock


def _make_insight(**overrides):
    """Build a minimal insight dict with optional overrides."""
    base = {
        "insight_type": "trip_correlation",
        "insight_text": "You have a meeting in Beijing next week.",
        "urgency": "medium",
        "source_system": "A",
        "context_entities": ["Beijing", "meeting"],
        "expires_at": None,
    }
    base.update(overrides)
    return base


def _future_iso(hours: int = 1) -> str:
    dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return dt.isoformat()


def _past_iso(hours: int = 1) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.isoformat()


# ===================================================================
# _is_expired
# ===================================================================


class TestIsExpired:
    def test_returns_false_when_no_expires_at(self, worker):
        insight = _make_insight(expires_at=None)
        assert worker._is_expired(insight) is False

    def test_returns_false_when_expires_at_in_future(self, worker):
        insight = _make_insight(expires_at=_future_iso(2))
        assert worker._is_expired(insight) is False

    def test_returns_true_when_expires_at_in_past(self, worker):
        insight = _make_insight(expires_at=_past_iso(2))
        assert worker._is_expired(insight) is True

    def test_returns_false_when_no_timezone_info(self, worker):
        # Naive datetime string (no timezone) -> code returns False
        naive_str = "2020-01-01T00:00:00"
        insight = _make_insight(expires_at=naive_str)
        assert worker._is_expired(insight) is False

    def test_handles_iso_string_with_z_suffix(self, worker):
        # Past time with Z suffix
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        insight = _make_insight(expires_at=past)
        assert worker._is_expired(insight) is True

    def test_handles_iso_string_with_z_suffix_future(self, worker):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        insight = _make_insight(expires_at=future)
        assert worker._is_expired(insight) is False

    def test_returns_false_on_invalid_date_format(self, worker):
        insight = _make_insight(expires_at="not-a-date")
        assert worker._is_expired(insight) is False

    def test_returns_false_on_empty_string(self, worker):
        insight = _make_insight(expires_at="")
        assert worker._is_expired(insight) is False

    def test_accepts_datetime_object_directly(self, worker):
        past_dt = datetime.now(timezone.utc) - timedelta(hours=1)
        insight = _make_insight(expires_at=past_dt)
        assert worker._is_expired(insight) is True

        future_dt = datetime.now(timezone.utc) + timedelta(hours=1)
        insight2 = _make_insight(expires_at=future_dt)
        assert worker._is_expired(insight2) is False


# ===================================================================
# _is_contextually_relevant
# ===================================================================


class TestIsContextuallyRelevant:
    """F2: Tests for multi-level contextual relevance matching."""

    # -- Level 1: Entity ID matching --

    def test_returns_true_when_person_ids_intersect(self, worker):
        insight = {"related_member_ids": ["id-1", "id-2"]}
        ctx = {"mentioned_person_ids": ["id-2", "id-3"], "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_returns_false_when_person_ids_disjoint(self, worker):
        insight = {"related_member_ids": ["id-1"]}
        ctx = {"mentioned_person_ids": ["id-2"], "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is False

    def test_handles_related_person_ids_key(self, worker):
        insight = {"related_person_ids": ["id-1"]}
        ctx = {"mentioned_person_ids": ["id-1"], "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_skips_level1_when_no_ids(self, worker):
        insight = {"insight_type": "trip_correlation"}
        ctx = {"mentioned_person_ids": [], "task_summary": ""}
        # No person IDs on insight side, should not match at level 1
        assert worker._is_contextually_relevant(insight, ctx) is False

    # -- Level 2: Event type affinity --

    def test_trip_correlation_matches_trip_action(self, worker):
        insight = {"insight_type": "trip_correlation"}
        ctx = {"action_category": "trip", "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_favor_reciprocation_matches_gift_action(self, worker):
        insight = {"insight_type": "favor_reciprocation"}
        ctx = {"action_category": "gift", "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_relationship_maintenance_matches_social(self, worker):
        insight = {"insight_type": "relationship_maintenance"}
        ctx = {"action_category": "social", "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_no_affinity_match(self, worker):
        insight = {"insight_type": "trip_correlation"}
        ctx = {"action_category": "gift", "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is False

    # -- Level 3: Location overlap --

    def test_location_match_from_insight_key(self, worker):
        insight = {"location": "Beijing"}
        ctx = {"mentioned_locations": ["Beijing", "Shanghai"], "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_location_match_from_extra_data(self, worker):
        insight = {"extra_data": {"location": "Beijing"}}
        ctx = {"mentioned_locations": ["Beijing"], "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_location_no_match(self, worker):
        insight = {"location": "Guangzhou"}
        ctx = {"mentioned_locations": ["Beijing"], "task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is False

    # -- Fallback: Legacy text containment --

    def test_fallback_text_containment_case_insensitive(self, worker):
        insight = {"context_entities": ["Beijing"]}
        ctx = {"task_summary": "Planning a trip to beijing next week"}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_fallback_text_containment_partial_match(self, worker):
        insight = {"context_entities": ["meeting"]}
        ctx = {"task_summary": "Team meeting scheduled for Friday"}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_fallback_returns_false_when_no_entities_match(self, worker):
        insight = {"context_entities": ["Shanghai"]}
        ctx = {"task_summary": "Planning a trip to Beijing"}
        assert worker._is_contextually_relevant(insight, ctx) is False

    def test_fallback_returns_false_when_entities_empty(self, worker):
        insight = {"context_entities": []}
        ctx = {"task_summary": "Any task summary"}
        assert worker._is_contextually_relevant(insight, ctx) is False

    def test_fallback_returns_false_when_task_summary_empty(self, worker):
        insight = {"context_entities": ["Beijing"]}
        ctx = {"task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is False

    def test_fallback_skips_empty_string_entities(self, worker):
        insight = {"context_entities": ["", ""]}
        ctx = {"task_summary": "Any task summary"}
        assert worker._is_contextually_relevant(insight, ctx) is False

    def test_fallback_mixed_empty_and_valid(self, worker):
        insight = {"context_entities": ["", "trip", ""]}
        ctx = {"task_summary": "Planning a trip"}
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_returns_false_when_all_empty(self, worker):
        insight = {}
        ctx = {"task_summary": ""}
        assert worker._is_contextually_relevant(insight, ctx) is False


# ===================================================================
# _check_injection_limits
# ===================================================================


class TestCheckInjectionLimits:
    @pytest.mark.asyncio
    async def test_returns_true_when_redis_is_none(self, worker):
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = None
            result = await worker._check_injection_limits("session-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_count_exceeds_max(
        self, worker, mock_redis
    ):
        mock_redis.get = AsyncMock(
            side_effect=lambda key: str(_MAX_INJECTIONS_PER_SESSION)
            if "count" in key
            else None
        )
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._check_injection_limits("session-1")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_last_key_exists_cooldown(
        self, worker, mock_redis
    ):
        # Count is below limit, but last key exists (cooldown active)
        def get_side_effect(key):
            if "count" in key:
                return "1"
            if "last" in key:
                return "1"
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._check_injection_limits("session-1")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_all_limits_pass(
        self, worker, mock_redis
    ):
        mock_redis.get = AsyncMock(return_value=None)
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._check_injection_limits("session-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_count_below_max(
        self, worker, mock_redis
    ):
        # Count exists but below max, no last key
        mock_redis.get = AsyncMock(
            side_effect=lambda key: "1" if "count" in key else None
        )
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._check_injection_limits("session-1")
            assert result is True


# ===================================================================
# _record_injection
# ===================================================================


class TestRecordInjection:
    @pytest.mark.asyncio
    async def test_calls_redis_pipeline_commands(self, worker, mock_redis):
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            await worker._record_injection("session-1")

            pipe = mock_redis.pipeline.return_value
            pipe.incr.assert_called_once()
            pipe.expire.assert_called_once()
            pipe.setex.assert_called_once()
            pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_uses_correct_keys_and_ttl(
        self, worker, mock_redis
    ):
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            await worker._record_injection("sess-abc")

            pipe = mock_redis.pipeline.return_value
            pipe.incr.assert_called_with("sidekick:count:sess-abc")
            pipe.expire.assert_called_with(
                "sidekick:count:sess-abc", _COUNT_KEY_TTL_SECONDS
            )
            pipe.setex.assert_called_with(
                "sidekick:last:sess-abc",
                _MIN_INJECTION_INTERVAL_SECONDS,
                "1",
            )

    @pytest.mark.asyncio
    async def test_returns_gracefully_when_redis_is_none(self, worker):
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = None
            # Should not raise
            await worker._record_injection("session-1")

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self, worker, mock_redis):
        pipe = mock_redis.pipeline.return_value
        pipe.execute = AsyncMock(side_effect=Exception("Redis down"))

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            # Should not raise
            await worker._record_injection("session-1")


# ===================================================================
# _build_signal
# ===================================================================


class TestBuildSignal:
    def test_creates_signal_with_sidekick_insight_type(self, worker):
        insight = _make_insight()
        signal = worker._build_signal(
            session_id="sess-1",
            job_id="job-1",
            user_id="user-1",
            insight=insight,
        )
        assert isinstance(signal, InterventionSignal)
        assert signal.type == InterventionType.SIDEKICK_INSIGHT.value

    def test_includes_injection_prompt_in_payload(self, worker):
        insight = _make_insight(insight_text="Important reminder about lunch")
        signal = worker._build_signal(
            session_id="sess-1",
            job_id="job-1",
            user_id="user-1",
            insight=insight,
        )
        expected_prompt = INJECTION_PROMPT_TEMPLATE.format(
            insight_text="Important reminder about lunch"
        )
        assert signal.payload["injection_prompt"] == expected_prompt

    def test_payload_contains_all_expected_fields(self, worker):
        insight = _make_insight(
            insight_type="favor_reciprocation",
            insight_text="Remember to thank Bob",
            urgency="high",
            source_system="B",
            context_entities=["Bob"],
            expires_at="2099-01-01T00:00:00+00:00",
        )
        signal = worker._build_signal(
            session_id="sess-1",
            job_id="job-1",
            user_id="user-1",
            insight=insight,
        )
        payload = signal.payload
        assert payload["insight_type"] == "favor_reciprocation"
        assert payload["insight_text"] == "Remember to thank Bob"
        assert payload["urgency"] == "high"
        assert payload["source_system"] == "B"
        assert payload["context_entities"] == ["Bob"]
        assert payload["expires_at"] == "2099-01-01T00:00:00+00:00"

    def test_signal_has_correct_session_and_user(self, worker):
        insight = _make_insight()
        signal = worker._build_signal(
            session_id="sess-42",
            job_id="job-42",
            user_id="user-42",
            insight=insight,
        )
        assert signal.session_id == "sess-42"
        assert signal.job_id == "job-42"
        assert signal.user_id == "user-42"

    def test_signal_id_is_uuid(self, worker):
        insight = _make_insight()
        signal = worker._build_signal(
            session_id="sess-1",
            job_id="job-1",
            user_id="user-1",
            insight=insight,
        )
        # Should be a valid UUID
        parsed = uuid.UUID(signal.signal_id)
        assert str(parsed) == signal.signal_id

    def test_defaults_for_missing_insight_fields(self, worker):
        insight = {}
        signal = worker._build_signal(
            session_id="s", job_id="j", user_id="u", insight=insight
        )
        assert signal.payload["insight_type"] == "unknown"
        assert signal.payload["insight_text"] == ""
        assert signal.payload["urgency"] == "low"
        assert signal.payload["source_system"] == ""
        assert signal.payload["context_entities"] == []
        assert signal.payload["expires_at"] is None


# ===================================================================
# evaluate_and_inject (integration)
# ===================================================================


def _active_session_status_json(
    job_id="job-1", task_summary="Planning Beijing trip"
):
    """Build a JSON-encoded SessionStatus for an active session."""
    status = SessionStatus(
        state=GenerationState.GENERATING.value,
        job_id=job_id,
        worker_id="worker-1",
        sdk_session_id="sdk-1",
        last_heartbeat=datetime.now(timezone.utc).isoformat(),
        task_summary=task_summary,
    )
    return json.dumps(status.to_dict())


class TestEvaluateAndInject:
    @pytest.mark.asyncio
    async def test_returns_false_when_insight_expired(self, worker):
        insight = _make_insight(expires_at=_past_iso(2))
        result = await worker.evaluate_and_inject("user-1", insight)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_active_session(
        self, worker, mock_redis
    ):
        # No reverse index, no matching session keys via SCAN
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.scan = AsyncMock(return_value=(0, []))
        insight = _make_insight()

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_not_contextually_relevant(
        self, worker, mock_redis
    ):
        # Session found via reverse index, but entities don't match task
        session_json = _active_session_status_json(
            task_summary="Buying groceries"
        )

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)
        insight = _make_insight(context_entities=["Shanghai"])

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_rate_limited_non_high_urgency(
        self, worker, mock_redis
    ):
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return session_json
            if "count" in key:
                return str(_MAX_INJECTIONS_PER_SESSION)
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        insight = _make_insight(
            urgency="medium",
            context_entities=["Beijing"],
        )

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_and_publishes_when_all_checks_pass(
        self, worker, mock_redis
    ):
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        insight = _make_insight(
            urgency="medium",
            context_entities=["Beijing"],
        )

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is True
            # Verify signal was published
            mock_redis.publish.assert_awaited_once()
            call_args = mock_redis.publish.call_args
            assert call_args[0][0] == "session:signal:sess-1"
            # Verify injection recorded
            mock_redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_high_urgency_bypasses_rate_limits(
        self, worker, mock_redis
    ):
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return session_json
            if "count" in key:
                return str(_MAX_INJECTIONS_PER_SESSION + 10)
            if "last" in key:
                return "1"
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        insight = _make_insight(
            urgency="high",
            context_entities=["Beijing"],
        )

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is True

    @pytest.mark.asyncio
    async def test_published_signal_is_valid_json(
        self, worker, mock_redis
    ):
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        insight = _make_insight(context_entities=["Beijing"])

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            await worker.evaluate_and_inject("user-1", insight)

            # Grab the published JSON and validate it parses back
            raw_json = mock_redis.publish.call_args[0][1]
            signal_dict = json.loads(raw_json)
            assert signal_dict["type"] == InterventionType.SIDEKICK_INSIGHT.value
            assert "session_id" in signal_dict
            assert "payload" in signal_dict
            assert signal_dict["payload"]["insight_text"] == insight["insight_text"]

    @pytest.mark.asyncio
    async def test_returns_false_when_redis_unavailable_for_session_scan(
        self, worker
    ):
        """When Redis client is None, _find_active_session returns None."""
        insight = _make_insight()
        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = None
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_session_is_idle(
        self, worker, mock_redis
    ):
        """IDLE sessions should not receive injections."""
        idle_status = SessionStatus(
            state=GenerationState.IDLE.value,
            job_id="job-1",
            worker_id="w-1",
            sdk_session_id="sdk-1",
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
            task_summary="Planning Beijing trip",
        )
        idle_json = json.dumps(idle_status.to_dict())

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return idle_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        insight = _make_insight(context_entities=["Beijing"])

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            assert result is False


# ===================================================================
# _find_active_session (reverse index)
# ===================================================================


class TestFindActiveSessionReverseIndex:
    """Tests for the O(1) reverse index path in _find_active_session."""

    @pytest.mark.asyncio
    async def test_uses_reverse_index_for_o1_lookup(self, worker, mock_redis):
        """When reverse index exists, returns session without SCAN."""
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-fast"
            if "session:status:sess-fast" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._find_active_session("user-1")

            assert result is not None
            assert result["session_id"] == "sess-fast"
            # SCAN should NOT be called
            mock_redis.scan.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_scan_when_no_reverse_index(
        self, worker, mock_redis
    ):
        """When reverse index is missing, falls back to SCAN."""
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return None
            if "session:status:" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)
        mock_redis.scan = AsyncMock(
            return_value=(0, ["session:status:sess-scan"])
        )

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._find_active_session("user-1")

            assert result is not None
            assert result["session_id"] == "sess-scan"
            mock_redis.scan.assert_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_scan_when_reverse_index_stale(
        self, worker, mock_redis
    ):
        """When reverse index points to a stale session, falls back to SCAN."""
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-stale"
            if "session:status:sess-stale" in key:
                return None  # session expired
            if "session:status:sess-scan" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)
        mock_redis.scan = AsyncMock(
            return_value=(0, ["session:status:sess-scan"])
        )

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._find_active_session("user-1")

            assert result is not None
            assert result["session_id"] == "sess-scan"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_sessions_anywhere(
        self, worker, mock_redis
    ):
        """Returns None when neither reverse index nor SCAN finds anything."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.scan = AsyncMock(return_value=(0, []))

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker._find_active_session("user-1")
            assert result is None


# ===================================================================
# PLAN-003: Gate 3 entity-ID matching activation
# ===================================================================


class TestGate3EntityIdMatching:
    """Tests that related_member_ids are correctly used for Gate 3."""

    def test_gate3_passes_when_member_id_matches(self, worker):
        """Insight with related_member_ids matching session person -> Gate 3 passes."""
        insight = {
            "related_member_ids": ["member-abc"],
            "insight_type": "relationship_maintenance",
        }
        ctx = {
            "mentioned_person_ids": ["member-abc", "member-def"],
            "task_summary": "unrelated text",
        }
        assert worker._is_contextually_relevant(insight, ctx) is True

    def test_gate3_blocks_when_member_id_not_in_session(self, worker):
        """Insight with related_member_ids not in session -> Gate 3 blocks."""
        insight = {
            "related_member_ids": ["member-xyz"],
            "insight_type": "relationship_maintenance",
        }
        ctx = {
            "mentioned_person_ids": ["member-abc"],
            "task_summary": "unrelated text",
        }
        assert worker._is_contextually_relevant(insight, ctx) is False

    def test_gate3_falls_through_to_other_levels_when_no_ids(self, worker):
        """Without member IDs, falls through to Level 2/3/fallback."""
        insight = {
            "insight_type": "trip_correlation",
            "context_entities": ["Beijing"],
        }
        ctx = {
            "mentioned_person_ids": [],
            "task_summary": "Planning Beijing trip",
            "action_category": "trip",
        }
        # Should match via Level 2 (affinity) or fallback
        assert worker._is_contextually_relevant(insight, ctx) is True


# ===================================================================
# PLAN-004: Gate 1 expired insight test
# ===================================================================


class TestGate1ExpiredInsight:
    """Tests that expires_at is correctly propagated and checked."""

    @pytest.mark.asyncio
    async def test_expired_insight_blocked_at_gate1(self, worker):
        """Insight with expires_at in the past -> Gate 1 blocks injection."""
        insight = _make_insight(
            expires_at=_past_iso(1),
            context_entities=["Beijing"],
        )
        result = await worker.evaluate_and_inject("user-1", insight)
        assert result is False

    @pytest.mark.asyncio
    async def test_non_expired_insight_passes_gate1(self, worker, mock_redis):
        """Insight with expires_at in the future -> passes Gate 1."""
        session_json = _active_session_status_json()

        def get_side_effect(key):
            if "active_session" in key:
                return "sess-1"
            if "session:status:" in key:
                return session_json
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        insight = _make_insight(
            expires_at=_future_iso(2),
            context_entities=["Beijing"],
        )

        with patch(
            "src.ai_engine.workers.sidekick_worker.redis_client"
        ) as mock_rc_mod:
            mock_rc_mod.client = mock_redis
            result = await worker.evaluate_and_inject("user-1", insight)
            # Should pass Gate 1 (not expired) and reach later checks
            assert result is True
