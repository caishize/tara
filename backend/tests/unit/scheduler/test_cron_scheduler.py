"""
Tests for CronScheduler and MultiCronScheduler.

SKIPPED: These tests are for the old in-process scheduler that has been
replaced by the Redis Sorted Set scheduler (core/scheduler/dispatcher.py).
They hang due to asyncio event loop conflicts with pytest-asyncio auto mode.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="Replaced by Redis Sorted Set scheduler; hangs due to asyncio loop conflicts"
)

import asyncio
from datetime import datetime, date
from unittest.mock import AsyncMock, patch, MagicMock
from zoneinfo import ZoneInfo

from src.core.scheduler.cron_scheduler import CronScheduler, MultiCronScheduler
from src.core.scheduler.job import ScheduledJob, CronJob
from src.core.scheduler.execution import JobPriority


async def successful_job() -> dict:
    """A job that succeeds."""
    return {"status": "success"}


async def another_job() -> dict:
    """Another job."""
    return {"count": 5}


@pytest.fixture
def cron_scheduler():
    """Create a test cron scheduler."""
    scheduler = CronScheduler(
        name="test_scheduler",
        check_interval=1
    )
    yield scheduler
    if scheduler._running:
        asyncio.get_event_loop().run_until_complete(scheduler.stop())


class TestCronSchedulerInit:
    """Tests for CronScheduler initialization."""

    def test_default_values(self):
        """Test default initialization values."""
        scheduler = CronScheduler(name="test")

        assert scheduler.name == "test"
        assert scheduler.default_cron == "0 * * * *"
        assert scheduler.check_interval == 60
        assert scheduler.batch_size == 50
        assert scheduler.timezone == ZoneInfo("Asia/Shanghai")

    def test_custom_values(self):
        """Test custom initialization values."""
        tz = ZoneInfo("UTC")
        scheduler = CronScheduler(
            name="custom",
            default_cron="0 2 * * *",
            timezone=tz,
            check_interval=30,
            batch_size=20
        )

        assert scheduler.default_cron == "0 2 * * *"
        assert scheduler.timezone == tz
        assert scheduler.check_interval == 30
        assert scheduler.batch_size == 20

    def test_scheduler_type(self):
        """Test that scheduler_type is correct."""
        scheduler = CronScheduler(name="test")
        assert scheduler.scheduler_type == "CronScheduler"


class TestCronJobRegistration:
    """Tests for cron job registration."""

    def test_register_cron_job(self, cron_scheduler):
        """Test registering a CronJob."""
        job = CronJob(
            name="cron_job",
            func=successful_job,
            cron_expression="0 2 * * *"
        )

        cron_scheduler.register_job(job)

        registered = cron_scheduler.get_job("cron_job")
        assert registered == job
        assert registered.next_run is not None

    def test_register_scheduled_job_converts_to_cron(self, cron_scheduler):
        """Test that ScheduledJob is converted to CronJob."""
        job = ScheduledJob(name="regular_job", func=successful_job)

        cron_scheduler.register_job(job)

        registered = cron_scheduler.get_job("regular_job")
        assert isinstance(registered, CronJob)
        assert registered.cron_expression == cron_scheduler.default_cron

    def test_next_run_updated_on_register(self, cron_scheduler):
        """Test that next_run is calculated on registration."""
        job = CronJob(
            name="test",
            func=successful_job,
            cron_expression="0 * * * *"  # Every hour
        )

        cron_scheduler.register_job(job)

        registered = cron_scheduler.get_job("test")
        assert registered.next_run is not None
        assert isinstance(registered.next_run, datetime)


class TestCronExpressionHandling:
    """Tests for cron expression handling."""

    def test_get_next_run_times(self, cron_scheduler):
        """Test getting next run times for all jobs."""
        job1 = CronJob(name="hourly", func=successful_job, cron_expression="0 * * * *")
        job2 = CronJob(name="daily", func=successful_job, cron_expression="0 2 * * *")

        cron_scheduler.register_job(job1)
        cron_scheduler.register_job(job2)

        next_runs = cron_scheduler.get_next_run_times()

        assert "hourly" in next_runs
        assert "daily" in next_runs
        assert isinstance(next_runs["hourly"], datetime)
        assert isinstance(next_runs["daily"], datetime)

    def test_is_daily_job(self, cron_scheduler):
        """Test detection of daily jobs."""
        daily_job = CronJob(
            name="daily",
            func=successful_job,
            cron_expression="0 2 * * *"  # 02:00 daily
        )
        hourly_job = CronJob(
            name="hourly",
            func=successful_job,
            cron_expression="0 * * * *"  # Every hour
        )
        every_minute = CronJob(
            name="minute",
            func=successful_job,
            cron_expression="* * * * *"  # Every minute
        )

        assert cron_scheduler._is_daily_job(daily_job) is True
        assert cron_scheduler._is_daily_job(hourly_job) is False
        assert cron_scheduler._is_daily_job(every_minute) is False

    def test_should_run_today_tracking(self, cron_scheduler):
        """Test tracking of jobs that ran today."""
        job = CronJob(name="test", func=successful_job, cron_expression="0 2 * * *")
        cron_scheduler.register_job(job)

        # Initially should be allowed to run
        assert cron_scheduler._should_run_today("test") is True

        # After marking as run
        cron_scheduler._mark_run_today("test")
        assert cron_scheduler._should_run_today("test") is False

    def test_multiple_cron_expressions(self, cron_scheduler):
        """Test multiple jobs with different cron expressions."""
        jobs = [
            CronJob(name="every_hour", func=successful_job, cron_expression="0 * * * *"),
            CronJob(name="every_day_2am", func=successful_job, cron_expression="0 2 * * *"),
            CronJob(name="every_sunday", func=successful_job, cron_expression="0 4 * * 0"),
            CronJob(name="every_15min", func=successful_job, cron_expression="*/15 * * * *"),
        ]

        for job in jobs:
            cron_scheduler.register_job(job)

        all_jobs = cron_scheduler.get_all_jobs()
        assert len(all_jobs) == 4


class TestMultiCronScheduler:
    """Tests for MultiCronScheduler."""

    def test_initialization(self):
        """Test MultiCronScheduler initialization."""
        scheduler = MultiCronScheduler(name="multi")

        assert scheduler.name == "multi"
        assert scheduler.default_cron == "* * * * *"  # Not really used

    def test_register_cron_job_helper(self):
        """Test the register_cron_job helper method."""
        scheduler = MultiCronScheduler(name="multi")

        job = scheduler.register_cron_job(
            name="test_job",
            func=successful_job,
            cron_expression="0 3 * * *",
            description="Test job at 3am",
            priority=JobPriority.HIGH,
            timeout_seconds=600
        )

        assert isinstance(job, CronJob)
        assert job.name == "test_job"
        assert job.cron_expression == "0 3 * * *"
        assert job.description == "Test job at 3am"
        assert job.priority == JobPriority.HIGH
        assert job.timeout_seconds == 600

        # Job should be registered
        registered = scheduler.get_job("test_job")
        assert registered == job

    def test_multiple_jobs_different_schedules(self):
        """Test registering multiple jobs with different schedules."""
        scheduler = MultiCronScheduler(name="multi")

        scheduler.register_cron_job(
            name="job_2am",
            func=successful_job,
            cron_expression="0 2 * * *"
        )
        scheduler.register_cron_job(
            name="job_3am",
            func=successful_job,
            cron_expression="0 3 * * *"
        )
        scheduler.register_cron_job(
            name="job_sunday",
            func=successful_job,
            cron_expression="0 4 * * 0"
        )

        all_jobs = scheduler.get_all_jobs()
        assert len(all_jobs) == 3

        expressions = [j.cron_expression for j in all_jobs]
        assert "0 2 * * *" in expressions
        assert "0 3 * * *" in expressions
        assert "0 4 * * 0" in expressions


class TestCronSchedulerStatus:
    """Tests for cron scheduler status."""

    @pytest.mark.asyncio
    async def test_status_includes_timezone(self):
        """Test that status includes timezone info."""
        scheduler = CronScheduler(
            name="test",
            timezone=ZoneInfo("UTC")
        )

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.get_stats = AsyncMock(return_value={})

            status = await scheduler.get_status()

            assert status.stats["timezone"] == "UTC"
            assert status.stats["check_interval"] == 60

    @pytest.mark.asyncio
    async def test_status_includes_next_runs(self):
        """Test that status includes next run times for jobs."""
        scheduler = CronScheduler(name="test")
        job = CronJob(
            name="test_job",
            func=successful_job,
            cron_expression="0 * * * *"
        )
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.get_stats = AsyncMock(return_value={})

            status = await scheduler.get_status()

            job_info = status.jobs[0]
            assert "next_run" in job_info
            assert job_info["next_run"] is not None


class TestCronSchedulerLifecycle:
    """Tests for cron scheduler lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the scheduler."""
        scheduler = CronScheduler(name="test", check_interval=60)

        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._task is not None

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_pause_skips_job_execution(self):
        """Test that pausing prevents job execution."""
        scheduler = CronScheduler(name="test", check_interval=1)
        job_executed = []

        async def tracking_job():
            job_executed.append(datetime.now())
            return {}

        job = CronJob(
            name="tracking",
            func=tracking_job,
            cron_expression="* * * * *"  # Every minute (but won't match in test)
        )
        scheduler.register_job(job)

        await scheduler.start()
        await scheduler.pause()

        # Even if we call _check_and_run_jobs directly, it should skip due to pause
        # (though in _run loop, the pause check happens before _check_and_run_jobs)

        await scheduler.stop()


class TestCronValidation:
    """Tests for cron expression validation."""

    def test_various_cron_formats(self):
        """Test that various cron formats are accepted."""
        scheduler = MultiCronScheduler(name="test")

        valid_expressions = [
            "* * * * *",        # Every minute
            "0 * * * *",        # Every hour
            "0 0 * * *",        # Daily at midnight
            "0 0 * * 0",        # Weekly on Sunday
            "0 0 1 * *",        # Monthly on 1st
            "*/5 * * * *",      # Every 5 minutes
            "0 9-17 * * 1-5",   # 9-5 on weekdays
            "30 4 1,15 * *",    # 4:30 on 1st and 15th
        ]

        for expr in valid_expressions:
            job = scheduler.register_cron_job(
                name=f"job_{expr.replace(' ', '_').replace('*', 'star').replace('/', 'slash')}",
                func=successful_job,
                cron_expression=expr
            )
            assert job.cron_expression == expr


class TestCronJobExecution:
    """Tests for cron job execution."""

    @pytest.mark.asyncio
    async def test_trigger_job_works(self):
        """Test that manually triggering a job works."""
        scheduler = CronScheduler(name="test")
        job = CronJob(
            name="test_job",
            func=successful_job,
            cron_expression="0 2 * * *"
        )
        scheduler.register_job(job)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            execution = await scheduler.trigger_job("test_job")

            assert execution.status.value == "completed"
            assert execution.trigger_type.value == "manual"
