"""
Tests for JobExecution and related models.
"""
import pytest
from datetime import datetime, timedelta
from uuid import UUID

from src.core.scheduler.execution import (
    JobExecutionStatus,
    TriggerType,
    JobPriority,
    JobExecution,
)


class TestJobExecutionStatus:
    """Tests for JobExecutionStatus enum."""

    def test_status_values(self):
        """Test all status values are accessible."""
        assert JobExecutionStatus.PENDING.value == "pending"
        assert JobExecutionStatus.RUNNING.value == "running"
        assert JobExecutionStatus.COMPLETED.value == "completed"
        assert JobExecutionStatus.FAILED.value == "failed"
        assert JobExecutionStatus.CANCELLED.value == "cancelled"
        assert JobExecutionStatus.TIMEOUT.value == "timeout"

    def test_status_from_string(self):
        """Test creating status from string value."""
        assert JobExecutionStatus("pending") == JobExecutionStatus.PENDING
        assert JobExecutionStatus("completed") == JobExecutionStatus.COMPLETED


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_trigger_values(self):
        """Test all trigger type values."""
        assert TriggerType.SCHEDULED.value == "scheduled"
        assert TriggerType.MANUAL.value == "manual"


class TestJobPriority:
    """Tests for JobPriority enum."""

    def test_priority_values(self):
        """Test all priority values."""
        assert JobPriority.HIGH.value == "high"
        assert JobPriority.NORMAL.value == "normal"
        assert JobPriority.LOW.value == "low"

    def test_priority_comparison(self):
        """Test priority comparison for sorting."""
        assert JobPriority.HIGH < JobPriority.NORMAL
        assert JobPriority.NORMAL < JobPriority.LOW
        assert not (JobPriority.LOW < JobPriority.HIGH)

    def test_priority_sorting(self):
        """Test sorting jobs by priority."""
        priorities = [JobPriority.LOW, JobPriority.HIGH, JobPriority.NORMAL]
        sorted_priorities = sorted(priorities)
        assert sorted_priorities == [JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]


class TestJobExecution:
    """Tests for JobExecution dataclass."""

    def test_creation_defaults(self):
        """Test creating execution with defaults."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        assert execution.job_name == "test_job"
        assert execution.scheduler_name == "test_scheduler"
        assert execution.status == JobExecutionStatus.PENDING
        assert execution.trigger_type == TriggerType.SCHEDULED
        assert isinstance(execution.id, UUID)
        assert execution.started_at is None
        assert execution.completed_at is None
        assert execution.duration_ms is None
        assert execution.error_message is None
        assert execution.error_traceback is None
        assert execution.result_summary is None
        assert isinstance(execution.created_at, datetime)

    def test_start(self):
        """Test starting an execution."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        execution.start()

        assert execution.status == JobExecutionStatus.RUNNING
        assert execution.started_at is not None
        assert isinstance(execution.started_at, datetime)

    def test_complete_success(self):
        """Test completing an execution successfully."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        execution.start()
        result = {"items_processed": 10}
        execution.complete(result_summary=result)

        assert execution.status == JobExecutionStatus.COMPLETED
        assert execution.completed_at is not None
        assert execution.duration_ms is not None
        assert execution.duration_ms >= 0
        assert execution.result_summary == result

    def test_fail(self):
        """Test failing an execution."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        execution.start()
        execution.fail("Something went wrong", "Traceback: ...")

        assert execution.status == JobExecutionStatus.FAILED
        assert execution.completed_at is not None
        assert execution.duration_ms is not None
        assert execution.error_message == "Something went wrong"
        assert execution.error_traceback == "Traceback: ..."

    def test_cancel(self):
        """Test cancelling an execution."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        execution.start()
        execution.cancel()

        assert execution.status == JobExecutionStatus.CANCELLED
        assert execution.completed_at is not None
        assert execution.duration_ms is not None

    def test_timeout(self):
        """Test timing out an execution."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        execution.start()
        execution.timeout()

        assert execution.status == JobExecutionStatus.TIMEOUT
        assert execution.completed_at is not None
        assert execution.duration_ms is not None

    def test_duration_calculation(self):
        """Test duration is calculated correctly."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        # Manually set times for testing
        execution.started_at = datetime.now()
        import time
        time.sleep(0.1)  # Sleep 100ms
        execution.complete()

        # Duration should be approximately 100ms
        assert execution.duration_ms >= 100
        assert execution.duration_ms < 500  # Should not take more than 500ms

    def test_to_dict(self):
        """Test converting execution to dictionary."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler",
            trigger_type=TriggerType.MANUAL
        )

        execution.start()
        execution.complete({"result": "success"})

        data = execution.to_dict()

        assert data["job_name"] == "test_job"
        assert data["scheduler_name"] == "test_scheduler"
        assert data["status"] == "completed"
        assert data["trigger_type"] == "manual"
        assert "id" in data
        assert "started_at" in data
        assert "completed_at" in data
        assert "duration_ms" in data
        assert data["result_summary"] == {"result": "success"}

    def test_complete_without_start(self):
        """Test completing without starting - duration should be None."""
        execution = JobExecution(
            job_name="test_job",
            scheduler_name="test_scheduler"
        )

        execution.complete()

        assert execution.status == JobExecutionStatus.COMPLETED
        assert execution.completed_at is not None
        assert execution.duration_ms is None  # No start time, so no duration
