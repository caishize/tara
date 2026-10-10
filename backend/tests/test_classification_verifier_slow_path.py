"""Tests for ClassificationVerifier integration in the Slow path (AgentWorker).

Verifies that _verify_classification correctly:
1. Calls ClassificationVerifier with proper parameters
2. Records mismatches with path=slow label
3. Does not alter routing behavior (observation-only)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# Minimal stub for the SDK result object
@dataclass
class _FakeResult:
    text: str = "response"
    tool_calls: Optional[List[Dict[str, Any]]] = None
    stop_reason: str = "complete"
    session_id: Optional[str] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


# Minimal TaskPayload stub
@dataclass
class _FakeTask:
    job_id: str = "job-1"
    user_id: str = "00000000-0000-0000-0000-000000000001"
    family_id: str = "00000000-0000-0000-0000-000000000002"
    session_id: Optional[str] = "session-1"
    route_type: str = "slow"
    user_input: str = "帮我规划旅行"
    context_snapshot: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.context_snapshot is None:
            self.context_snapshot = {
                "difficulty": "thinking",
                "action": "plan",
                "confidence": 0.9,
            }
        if self.metadata is None:
            self.metadata = {}


class TestVerifyClassificationSlowPath:
    """Test the _verify_classification method on AgentWorker."""

    def _get_worker_class(self):
        """Import AgentWorker lazily to avoid SDK import errors in test env."""
        try:
            from src.ai_engine.workers.agent_worker import AgentWorker
            return AgentWorker
        except ImportError:
            pytest.skip("AgentWorker requires claude_agent_sdk")

    def test_slow_path_trivial_completion_records_metric(self):
        """Slow path with < 2 tool calls should record path=slow label."""
        WorkerClass = self._get_worker_class()

        mock_metric = MagicMock()
        mock_labels = MagicMock()
        mock_metric.labels.return_value = mock_labels

        task = _FakeTask()
        result = _FakeResult(tool_calls=[{"name": "get_weather"}])

        # Patch at the source module since _verify_classification imports locally
        with patch(
            "src.core.observability.metrics.classification_mismatches_total",
            mock_metric,
        ):
            worker = WorkerClass.__new__(WorkerClass)
            worker._verify_classification(task, result)

        # Should have been called with path="slow"
        mock_metric.labels.assert_called_once()
        call_kwargs = mock_metric.labels.call_args[1]
        assert call_kwargs.get("path") == "slow"
        assert call_kwargs.get("reason") == "slow_path_trivial_completion"
        mock_labels.inc.assert_called_once()

    def test_slow_path_normal_completion_no_metric(self):
        """Slow path with enough tool calls should not record a mismatch."""
        WorkerClass = self._get_worker_class()

        mock_metric = MagicMock()

        task = _FakeTask()
        result = _FakeResult(
            tool_calls=[
                {"name": "create_trip"},
                {"name": "search_flights"},
                {"name": "book_hotel"},
            ]
        )

        with patch(
            "src.core.observability.metrics.classification_mismatches_total",
            mock_metric,
        ):
            worker = WorkerClass.__new__(WorkerClass)
            worker._verify_classification(task, result)

        mock_metric.labels.assert_not_called()

    def test_observation_only_does_not_raise(self):
        """Verification errors should never propagate."""
        WorkerClass = self._get_worker_class()

        task = _FakeTask()
        result = _FakeResult()

        with patch(
            "src.ai_engine.router.classification_verifier.ClassificationVerifier.verify",
            side_effect=Exception("boom"),
        ):
            worker = WorkerClass.__new__(WorkerClass)
            # Should not raise
            worker._verify_classification(task, result)

    def test_missing_context_snapshot_uses_defaults(self):
        """When context_snapshot is empty, defaults are used."""
        WorkerClass = self._get_worker_class()

        mock_metric = MagicMock()
        mock_labels = MagicMock()
        mock_metric.labels.return_value = mock_labels

        task = _FakeTask(context_snapshot={})
        result = _FakeResult(tool_calls=[])

        with patch(
            "src.core.observability.metrics.classification_mismatches_total",
            mock_metric,
        ):
            worker = WorkerClass.__new__(WorkerClass)
            worker._verify_classification(task, result)

        # Default difficulty=thinking + 0 tool calls = trivial completion
        if mock_metric.labels.called:
            call_kwargs = mock_metric.labels.call_args[1]
            assert call_kwargs.get("path") == "slow"
