"""
Tests for SchedulerManager.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.scheduler.manager import SchedulerManager
from src.core.scheduler.interval_scheduler import IntervalScheduler
from src.core.scheduler.cron_scheduler import CronScheduler, MultiCronScheduler
from src.core.scheduler.job import ScheduledJob


async def sample_job() -> dict:
    """Sample job for testing."""
    return {"status": "ok"}


@pytest.fixture
def manager():
    """Create a fresh SchedulerManager for each test."""
    # Reset singleton for testing
    SchedulerManager._instance = None
    mgr = SchedulerManager()
    yield mgr
    # Cleanup
    if mgr._started:
        asyncio.get_event_loop().run_until_complete(mgr.stop_all())
    mgr.reset()
    SchedulerManager._instance = None


class TestSchedulerManagerSingleton:
    """Tests for singleton pattern."""

    def test_singleton_pattern(self):
        """Test that SchedulerManager is a singleton."""
        SchedulerManager._instance = None

        mgr1 = SchedulerManager()
        mgr2 = SchedulerManager()

        assert mgr1 is mgr2

        SchedulerManager._instance = None

    def test_singleton_preserves_state(self):
        """Test that singleton preserves state across instances."""
        SchedulerManager._instance = None

        mgr1 = SchedulerManager()
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        mgr1.register("test", scheduler)

        mgr2 = SchedulerManager()
        assert mgr2.get("test") is scheduler

        SchedulerManager._instance = None


class TestSchedulerRegistration:
    """Tests for scheduler registration."""

    def test_register_scheduler(self, manager):
        """Test registering a scheduler."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        manager.register("test", scheduler)

        assert manager.get("test") is scheduler

    def test_register_duplicate_raises(self, manager):
        """Test that registering duplicate raises error."""
        scheduler1 = IntervalScheduler(name="test1", interval_seconds=60)
        scheduler2 = IntervalScheduler(name="test2", interval_seconds=60)

        manager.register("test", scheduler1)

        with pytest.raises(ValueError, match="already registered"):
            manager.register("test", scheduler2)

    def test_unregister_scheduler(self, manager):
        """Test unregistering a scheduler."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        manager.register("test", scheduler)

        removed = manager.unregister("test")

        assert removed is scheduler
        assert manager.get("test") is None

    def test_unregister_nonexistent(self, manager):
        """Test unregistering non-existent scheduler returns None."""
        result = manager.unregister("nonexistent")
        assert result is None

    def test_get_all_schedulers(self, manager):
        """Test getting all registered schedulers."""
        scheduler1 = IntervalScheduler(name="interval", interval_seconds=60)
        scheduler2 = CronScheduler(name="cron")

        manager.register("interval", scheduler1)
        manager.register("cron", scheduler2)

        all_schedulers = manager.get_all()

        assert len(all_schedulers) == 2
        assert all_schedulers["interval"] is scheduler1
        assert all_schedulers["cron"] is scheduler2

    def test_get_all_returns_copy(self, manager):
        """Test that get_all returns a copy."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        manager.register("test", scheduler)

        all_schedulers = manager.get_all()
        all_schedulers["new"] = None  # Modify the copy

        # Original should not be affected
        assert "new" not in manager.get_all()


class TestBulkOperations:
    """Tests for bulk start/stop operations."""

    @pytest.mark.asyncio
    async def test_start_all(self, manager):
        """Test starting all schedulers."""
        scheduler1 = IntervalScheduler(name="s1", interval_seconds=60)
        scheduler2 = CronScheduler(name="s2")

        manager.register("s1", scheduler1)
        manager.register("s2", scheduler2)

        await manager.start_all()

        assert scheduler1._running is True
        assert scheduler2._running is True
        assert manager.is_started is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_all_when_already_started(self, manager):
        """Test that starting again is a no-op."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        manager.register("test", scheduler)

        await manager.start_all()
        await manager.start_all()  # Should not raise

        assert manager.is_started is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_stop_all(self, manager):
        """Test stopping all schedulers."""
        scheduler1 = IntervalScheduler(name="s1", interval_seconds=60)
        scheduler2 = CronScheduler(name="s2")

        manager.register("s1", scheduler1)
        manager.register("s2", scheduler2)

        await manager.start_all()
        await manager.stop_all()

        assert scheduler1._running is False
        assert scheduler2._running is False
        assert manager.is_started is False

    @pytest.mark.asyncio
    async def test_stop_all_when_not_started(self, manager):
        """Test that stopping when not started is safe."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        manager.register("test", scheduler)

        # Should not raise
        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_pause_all(self, manager):
        """Test pausing all schedulers."""
        scheduler1 = IntervalScheduler(name="s1", interval_seconds=60)
        scheduler2 = CronScheduler(name="s2")

        manager.register("s1", scheduler1)
        manager.register("s2", scheduler2)

        await manager.start_all()
        await manager.pause_all()

        assert scheduler1._paused is True
        assert scheduler2._paused is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_resume_all(self, manager):
        """Test resuming all schedulers."""
        scheduler1 = IntervalScheduler(name="s1", interval_seconds=60)
        scheduler2 = CronScheduler(name="s2")

        manager.register("s1", scheduler1)
        manager.register("s2", scheduler2)

        await manager.start_all()
        await manager.pause_all()
        await manager.resume_all()

        assert scheduler1._paused is False
        assert scheduler2._paused is False

        await manager.stop_all()


class TestJobTriggering:
    """Tests for manual job triggering."""

    @pytest.mark.asyncio
    async def test_trigger_job(self, manager):
        """Test triggering a job through the manager."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        job = ScheduledJob(name="test_job", func=sample_job)
        scheduler.register_job(job)
        manager.register("test", scheduler)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            execution = await manager.trigger_job("test", "test_job")

            assert execution.status.value == "completed"

    @pytest.mark.asyncio
    async def test_trigger_job_scheduler_not_found(self, manager):
        """Test triggering job with non-existent scheduler raises error."""
        with pytest.raises(ValueError, match="not found"):
            await manager.trigger_job("nonexistent", "job")

    @pytest.mark.asyncio
    async def test_trigger_job_job_not_found(self, manager):
        """Test triggering non-existent job raises error."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        manager.register("test", scheduler)

        with pytest.raises(ValueError, match="not found"):
            await manager.trigger_job("test", "nonexistent")


class TestJobRunningStatus:
    """Tests for checking job running status."""

    @pytest.mark.asyncio
    async def test_is_job_running(self, manager):
        """Test checking if a job is running."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)

        async def slow_job():
            await asyncio.sleep(10)
            return {}

        job = ScheduledJob(name="slow", func=slow_job)
        scheduler.register_job(job)
        manager.register("test", scheduler)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.save = AsyncMock()

            # Start job execution
            task = asyncio.create_task(scheduler._execute_job(job))
            await asyncio.sleep(0.1)

            assert manager.is_job_running("test", "slow") is True

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def test_is_job_running_scheduler_not_found(self, manager):
        """Test is_job_running returns False for non-existent scheduler."""
        assert manager.is_job_running("nonexistent", "job") is False


class TestStatusAggregation:
    """Tests for status aggregation."""

    @pytest.mark.asyncio
    async def test_get_all_status(self, manager):
        """Test getting status of all schedulers."""
        scheduler1 = IntervalScheduler(name="interval", interval_seconds=60)
        scheduler2 = CronScheduler(name="cron")

        job1 = ScheduledJob(name="job1", func=sample_job)
        scheduler1.register_job(job1)

        manager.register("interval", scheduler1)
        manager.register("cron", scheduler2)

        with patch('src.core.scheduler.base.execution_store') as mock_store:
            mock_store.get_stats = AsyncMock(return_value={
                "total_executions": 10,
                "success_count": 8,
                "failed_count": 2,
            })

            statuses = await manager.get_all_status()

            assert len(statuses) == 2

            names = [s.name for s in statuses]
            assert "interval" in names
            assert "cron" in names


class TestReset:
    """Tests for manager reset functionality."""

    def test_reset_clears_schedulers(self, manager):
        """Test that reset clears all schedulers."""
        scheduler = IntervalScheduler(name="test", interval_seconds=60)
        manager.register("test", scheduler)

        manager.reset()

        assert manager.get("test") is None
        assert len(manager.get_all()) == 0
        assert manager.is_started is False


class TestMixedSchedulerTypes:
    """Tests for managing different scheduler types."""

    @pytest.mark.asyncio
    async def test_mixed_scheduler_types(self, manager):
        """Test managing IntervalScheduler and CronScheduler together."""
        interval = IntervalScheduler(name="interval", interval_seconds=60)
        cron = CronScheduler(name="cron")
        multi = MultiCronScheduler(name="multi")

        manager.register("interval", interval)
        manager.register("cron", cron)
        manager.register("multi", multi)

        await manager.start_all()

        assert interval._running is True
        assert cron._running is True
        assert multi._running is True

        await manager.stop_all()

        assert interval._running is False
        assert cron._running is False
        assert multi._running is False
