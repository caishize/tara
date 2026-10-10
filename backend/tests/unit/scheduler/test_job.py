"""
Tests for ScheduledJob and CronJob.
"""
import pytest
from datetime import datetime

from src.core.scheduler.job import ScheduledJob, CronJob
from src.core.scheduler.execution import JobPriority


async def sample_job_func() -> dict:
    """Sample job function for testing."""
    return {"status": "completed"}


async def another_job_func() -> dict:
    """Another sample job function."""
    return {"items": 5}


class TestScheduledJob:
    """Tests for ScheduledJob dataclass."""

    def test_creation_with_defaults(self):
        """Test creating a job with default values."""
        job = ScheduledJob(
            name="test_job",
            func=sample_job_func
        )

        assert job.name == "test_job"
        assert job.func == sample_job_func
        assert job.description == ""
        assert job.priority == JobPriority.NORMAL
        assert job.timeout_seconds == 300
        assert job.max_retries == 3
        assert job.retry_delay_seconds == 60
        assert job.enabled is True
        assert job.depends_on == []
        assert job.tags == []
        assert job.last_run is None
        assert job.last_status is None
        assert job.next_run is None
        assert job.consecutive_failures == 0

    def test_creation_with_custom_values(self):
        """Test creating a job with custom values."""
        job = ScheduledJob(
            name="custom_job",
            func=sample_job_func,
            description="A custom job",
            priority=JobPriority.HIGH,
            timeout_seconds=600,
            max_retries=5,
            retry_delay_seconds=120,
            enabled=False,
            depends_on=["other_job"],
            tags=["daily", "important"]
        )

        assert job.name == "custom_job"
        assert job.description == "A custom job"
        assert job.priority == JobPriority.HIGH
        assert job.timeout_seconds == 600
        assert job.max_retries == 5
        assert job.retry_delay_seconds == 120
        assert job.enabled is False
        assert job.depends_on == ["other_job"]
        assert job.tags == ["daily", "important"]

    def test_validation_empty_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Job name cannot be empty"):
            ScheduledJob(name="", func=sample_job_func)

    def test_validation_non_callable_func(self):
        """Test that non-callable func raises ValueError."""
        with pytest.raises(ValueError, match="Job func must be callable"):
            ScheduledJob(name="test", func="not_callable")

    def test_validation_invalid_timeout(self):
        """Test that invalid timeout raises ValueError."""
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            ScheduledJob(name="test", func=sample_job_func, timeout_seconds=0)

        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            ScheduledJob(name="test", func=sample_job_func, timeout_seconds=-10)

    def test_validation_invalid_retries(self):
        """Test that invalid max_retries raises ValueError."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            ScheduledJob(name="test", func=sample_job_func, max_retries=-1)

    def test_validation_invalid_retry_delay(self):
        """Test that invalid retry_delay raises ValueError."""
        with pytest.raises(ValueError, match="retry_delay_seconds must be non-negative"):
            ScheduledJob(name="test", func=sample_job_func, retry_delay_seconds=-1)

    def test_record_success(self):
        """Test recording a successful execution."""
        job = ScheduledJob(name="test", func=sample_job_func)
        job.consecutive_failures = 3  # Had some failures before

        job.record_success()

        assert job.last_run is not None
        assert job.last_status == "completed"
        assert job.consecutive_failures == 0

    def test_record_failure(self):
        """Test recording a failed execution."""
        job = ScheduledJob(name="test", func=sample_job_func)

        job.record_failure()
        assert job.consecutive_failures == 1

        job.record_failure()
        assert job.consecutive_failures == 2

        assert job.last_run is not None
        assert job.last_status == "failed"

    def test_should_retry(self):
        """Test retry determination based on failure count."""
        job = ScheduledJob(name="test", func=sample_job_func, max_retries=3)

        assert job.should_retry() is True  # 0 < 3

        job.consecutive_failures = 2
        assert job.should_retry() is True  # 2 < 3

        job.consecutive_failures = 3
        assert job.should_retry() is False  # 3 >= 3

    def test_get_retry_delay_exponential(self):
        """Test exponential backoff for retry delays."""
        job = ScheduledJob(
            name="test",
            func=sample_job_func,
            retry_delay_seconds=60
        )

        # First retry (1 failure): 60 * 2^0 = 60
        job.consecutive_failures = 1
        assert job.get_retry_delay() == 60

        # Second retry (2 failures): 60 * 2^1 = 120
        job.consecutive_failures = 2
        assert job.get_retry_delay() == 120

        # Third retry (3 failures): 60 * 2^2 = 240
        job.consecutive_failures = 3
        assert job.get_retry_delay() == 240

    def test_to_dict(self):
        """Test converting job to dictionary."""
        job = ScheduledJob(
            name="test_job",
            func=sample_job_func,
            description="Test description",
            priority=JobPriority.HIGH,
            tags=["test", "unit"]
        )

        data = job.to_dict()

        assert data["name"] == "test_job"
        assert data["description"] == "Test description"
        assert data["priority"] == "high"
        assert data["timeout_seconds"] == 300
        assert data["max_retries"] == 3
        assert data["enabled"] is True
        assert data["tags"] == ["test", "unit"]
        assert "func" not in data  # Function should not be serialized

    def test_to_dict_with_runtime_state(self):
        """Test to_dict includes runtime state."""
        job = ScheduledJob(name="test", func=sample_job_func)
        job.record_success()
        job.next_run = datetime.now()

        data = job.to_dict()

        assert data["last_run"] is not None
        assert data["last_status"] == "completed"
        assert data["next_run"] is not None
        assert data["consecutive_failures"] == 0


class TestCronJob:
    """Tests for CronJob dataclass."""

    def test_creation_with_defaults(self):
        """Test creating a cron job with defaults."""
        job = CronJob(
            name="cron_test",
            func=sample_job_func
        )

        assert job.name == "cron_test"
        assert job.cron_expression == "0 * * * *"  # Default: every hour

    def test_creation_with_custom_cron(self):
        """Test creating a cron job with custom expression."""
        job = CronJob(
            name="daily_job",
            func=sample_job_func,
            cron_expression="0 2 * * *"  # 02:00 daily
        )

        assert job.cron_expression == "0 2 * * *"

    def test_validation_empty_cron(self):
        """Test that empty cron expression raises ValueError."""
        with pytest.raises(ValueError, match="cron_expression cannot be empty"):
            CronJob(name="test", func=sample_job_func, cron_expression="")

    def test_inherits_scheduled_job_validation(self):
        """Test that CronJob inherits ScheduledJob validation."""
        with pytest.raises(ValueError, match="Job name cannot be empty"):
            CronJob(name="", func=sample_job_func)

        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            CronJob(name="test", func=sample_job_func, timeout_seconds=0)

    def test_to_dict_includes_cron(self):
        """Test that to_dict includes cron_expression."""
        job = CronJob(
            name="cron_job",
            func=sample_job_func,
            cron_expression="30 4 * * 0"  # 04:30 on Sundays
        )

        data = job.to_dict()

        assert data["cron_expression"] == "30 4 * * 0"
        assert data["name"] == "cron_job"

    def test_full_cron_expression(self):
        """Test various cron expression formats."""
        # Minute, Hour, Day of Month, Month, Day of Week
        expressions = [
            "* * * * *",      # Every minute
            "0 * * * *",      # Every hour
            "0 0 * * *",      # Every day at midnight
            "0 0 * * 0",      # Every Sunday at midnight
            "0 0 1 * *",      # First day of every month
            "*/15 * * * *",   # Every 15 minutes
            "0 9-17 * * 1-5", # Every hour 9-17 on weekdays
        ]

        for expr in expressions:
            job = CronJob(name="test", func=sample_job_func, cron_expression=expr)
            assert job.cron_expression == expr


class TestJobPrioritySorting:
    """Tests for sorting jobs by priority."""

    def test_sort_jobs_by_priority(self):
        """Test that jobs can be sorted by priority."""
        job_low = ScheduledJob(name="low", func=sample_job_func, priority=JobPriority.LOW)
        job_high = ScheduledJob(name="high", func=sample_job_func, priority=JobPriority.HIGH)
        job_normal = ScheduledJob(name="normal", func=sample_job_func, priority=JobPriority.NORMAL)

        jobs = [job_low, job_high, job_normal]
        sorted_jobs = sorted(jobs, key=lambda j: j.priority)

        assert sorted_jobs[0].name == "high"
        assert sorted_jobs[1].name == "normal"
        assert sorted_jobs[2].name == "low"
