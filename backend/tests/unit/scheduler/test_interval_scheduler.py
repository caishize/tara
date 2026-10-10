"""
Tests for IntervalScheduler.

SKIPPED: These tests are for the old in-process scheduler that has been
replaced by the Redis Sorted Set scheduler (core/scheduler/dispatcher.py).
They hang due to asyncio event loop conflicts with pytest-asyncio auto mode.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="Replaced by Redis Sorted Set scheduler; hangs due to asyncio loop conflicts"
)

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.scheduler.interval_scheduler import IntervalScheduler, ConditionalIntervalScheduler
from src.core.scheduler.job import ScheduledJob
from src.core.scheduler.execution import JobPriority, JobExecutionStatus


async def successful_job() -> dict:
    """A job that succeeds."""
    return {"status": "success", "count": 10}


async def failing_job() -> dict:
    """A job that fails."""
    raise ValueError("Job failed intentionally")


async def slow_job() -> dict:
    """A job that takes time."""
    await asyncio.sleep(0.5)
    return {"status": "completed"}


@pytest.fixture
def interval_scheduler():
    """Create a test interval scheduler."""
    scheduler = IntervalScheduler(
        name="test_scheduler",
        interval_seconds=1,
        batch_size=10
    )
    yield scheduler
    # Cleanup
    if scheduler._running:
        asyncio.get_event_loop().run_until_complete(scheduler.stop())


class TestIntervalSchedulerInit:
    """Tests for IntervalScheduler initialization."""

    def test_default_values(self):
        """Test default initialization values."""
        scheduler = IntervalScheduler(name="test")

        assert scheduler.name == "test"
        assert scheduler.interval_seconds == 60
        assert scheduler.batch_size == 50
        assert scheduler.run_immediately is False
        assert scheduler._running is False
        assert scheduler._paused is False

    def test_custom_values(self):
        """Test custom initialization values."""
        scheduler = IntervalScheduler(
            name="custom",
            interval_seconds=30,
            batch_size=20,
            run_immediately=True
        )

        assert scheduler.interval_seconds == 30
        assert scheduler.batch_size == 20
        assert scheduler.run_immediately is True

    def test_scheduler_type(self):
        """Test that scheduler_type is correct."""
        scheduler = IntervalScheduler(name="test")
        assert scheduler.scheduler_type == "IntervalScheduler"


class TestJobRegistration:
    """Tests for job registration."""

    def test_register_job(self, interval_scheduler):
        """Test registering a job."""
        job = ScheduledJob(name="test_job", func=successful_job)

        interval_scheduler.register_job(job)

        assert "test_job" in interval_scheduler._jobs
        assert interval_scheduler.get_job("test_job") == job

    def test_register_duplicate_raises(self, interval_scheduler):
        """Test that registering duplicate job raises error."""
        job = ScheduledJob(name="test_job", func=successful_job)
        interval_scheduler.register_job(job)

        with pytest.raises(ValueError, match="already registered"):
            interval_scheduler.register_job(job)

    def test_unregister_job(self, interval_scheduler):
        """Test unregistering a job."""
        job = ScheduledJob(name="test_job", func=successful_job)
        interval_scheduler.register_job(job)

        removed = interval_scheduler.unregister_job("test_job")

        assert removed == job
        assert interval_scheduler.get_job("test_job") is None

    def test_unregister_nonexistent(self, interval_scheduler):
        """Test unregistering non-existent job returns None."""
        result = interval_scheduler.unregister_job("nonexistent")
        assert result is None

    def test_get_all_jobs(self, interval_scheduler):
        """Test getting all jobs."""
        job1 = ScheduledJob(name="job1", func=successful_job)
        job2 = ScheduledJob(name="job2", func=successful_job)

        interval_scheduler.register_job(job1)
        interval_scheduler.register_job(job2)

        all_jobs = interval_scheduler.get_all_jobs()

        assert len(all_jobs) == 2
        assert job1 in all_jobs
        assert job2 in all_jobs

    def test_get_enabled_jobs_sorted(self, interval_scheduler):
        """Test getting enabled jobs sorted by priority."""
        job_low = ScheduledJob(name="low", func=successful_job, priority=JobPriority.LOW)
        job_high = ScheduledJob(name="high", func=successful_job, priority=JobPriority.HIGH)
        job_disabled = ScheduledJob(name="disabled", func=successful_job, enabled=False)
        job_normal = ScheduledJob(name="normal", func=successful_job, priority=JobPriority.NORMAL)

        interval_scheduler.register_job(job_low)
        interval_scheduler.register_job(job_high)
        interval_scheduler.register_job(job_disabled)
        interval_scheduler.register_job(job_normal)

        enabled_jobs = interval_scheduler.get_enabled_jobs()

        assert len(enabled_jobs) == 3  # Excludes disabled
        assert enabled_jobs[0].name == "high"
        assert enabled_jobs[1].name == "normal"
        assert enabled_jobs[2].name == "low"


class TestSchedulerLifecycle:
    """Tests for scheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test basic start and stop."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        await scheduler.start()

        assert scheduler._running is True
        assert scheduler._started_at is not None
        assert scheduler._task is not None

        await scheduler.stop()

        assert scheduler._running is False
        assert scheduler._task is None

    @pytest.mark.asyncio
    async def test_start_when_already_running(self):
        """Test that starting again is a no-op."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        await scheduler.start()
        task1 = scheduler._task

        await scheduler.start()  # Should not create new task
        task2 = scheduler._task

        assert task1 == task2  # Same task

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test that stopping non-running scheduler is safe."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        # Should not raise
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        """Test pause and resume functionality."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        await scheduler.start()

        await scheduler.pause()
        assert scheduler._paused is True

        await scheduler.resume()
        assert scheduler._paused is False

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_pause_when_not_running(self):
        """Test that pausing non-running scheduler logs warning."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        # Should not raise, just log warning
        await scheduler.pause()
        assert scheduler._paused is False


class TestJobExecution:
    """Tests for job execution."""

    @pytest.mark.asyncio
    async def test_execute_successful_job(self):
        """Test executing a successful job."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        job = ScheduledJob(name="test_job", func=successful_job)
        scheduler.register_job(job)

        # Mock the execution store
        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            execution = await scheduler._execute_job(job)

            assert execution.status == JobExecutionStatus.COMPLETED
            assert execution.result_summary == {"status": "success", "count": 10}
            assert execution.error_message is None
            mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_failing_job(self):
        """Test executing a failing job."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        job = ScheduledJob(name="failing_job", func=failing_job)
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            execution = await scheduler._execute_job(job)

            assert execution.status == JobExecutionStatus.FAILED
            assert "Job failed intentionally" in execution.error_message
            assert execution.error_traceback is not None

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Test job timeout handling."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        job = ScheduledJob(
            name="slow_job",
            func=slow_job,
            timeout_seconds=0.1  # Very short timeout
        )
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            execution = await scheduler._execute_job(job)

            assert execution.status == JobExecutionStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_duplicate_execution_prevention(self):
        """Test that duplicate executions are prevented."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        async def blocking_job():
            await asyncio.sleep(1)
            return {"status": "done"}

        job = ScheduledJob(name="blocking", func=blocking_job)
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            # Start first execution (don't await)
            task1 = asyncio.create_task(scheduler._execute_job(job))

            # Wait a bit for it to start
            await asyncio.sleep(0.1)

            # Try second execution while first is running
            execution2 = await scheduler._execute_job(job)

            # Second should be cancelled
            assert execution2.status == JobExecutionStatus.CANCELLED
            assert "already running" in execution2.error_message

            # Cancel the first task
            task1.cancel()
            try:
                await task1
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_trigger_job_manually(self):
        """Test manually triggering a job."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        job = ScheduledJob(name="test_job", func=successful_job)
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            execution = await scheduler.trigger_job("test_job")

            assert execution.status == JobExecutionStatus.COMPLETED
            assert execution.trigger_type.value == "manual"

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_job(self):
        """Test triggering non-existent job raises error."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        with pytest.raises(ValueError, match="not found"):
            await scheduler.trigger_job("nonexistent")


class TestConditionalIntervalScheduler:
    """Tests for ConditionalIntervalScheduler."""

    def test_default_condition(self):
        """Test that default condition always returns True."""
        scheduler = ConditionalIntervalScheduler(name="test", interval_seconds=60)
        assert scheduler._condition_func() is True

    def test_custom_condition(self):
        """Test custom condition function."""
        condition_calls = []

        def custom_condition():
            condition_calls.append(1)
            return len(condition_calls) <= 2

        scheduler = ConditionalIntervalScheduler(
            name="test",
            interval_seconds=60,
            condition_func=custom_condition
        )

        assert scheduler._condition_func() is True
        assert scheduler._condition_func() is True
        assert scheduler._condition_func() is False

    def test_set_condition(self):
        """Test setting condition after init."""
        scheduler = ConditionalIntervalScheduler(name="test", interval_seconds=60)

        scheduler.set_condition(lambda: False)

        assert scheduler._condition_func() is False

    def test_scheduler_type(self):
        """Test scheduler_type is correct."""
        scheduler = ConditionalIntervalScheduler(name="test", interval_seconds=60)
        assert scheduler.scheduler_type == "ConditionalIntervalScheduler"


class TestSchedulerStatus:
    """Tests for scheduler status."""

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting scheduler status."""
        scheduler = IntervalScheduler(name="test", interval_seconds=30)
        job = ScheduledJob(name="job1", func=successful_job)
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.get_stats = AsyncMock(return_value={
                "total_executions": 10,
                "success_count": 8,
                "failed_count": 2,
            })

            status = await scheduler.get_status()

            assert status.name == "test"
            assert status.scheduler_type == "IntervalScheduler"
            assert status.is_running is False
            assert len(status.jobs) == 1
            assert status.stats["interval_seconds"] == 30

    @pytest.mark.asyncio
    async def test_status_shows_running_jobs(self):
        """Test that status shows which jobs are running."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        async def blocking_job():
            await asyncio.sleep(10)
            return {}

        job = ScheduledJob(name="blocking", func=blocking_job)
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.get_stats = AsyncMock(return_value={})
            mock_store.save = AsyncMock()

            # Start job execution
            task = asyncio.create_task(scheduler._execute_job(job))
            await asyncio.sleep(0.1)

            status = await scheduler.get_status()

            # Job should show as running
            job_info = status.jobs[0]
            assert job_info["is_running"] is True

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
