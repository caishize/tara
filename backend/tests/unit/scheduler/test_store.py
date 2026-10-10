"""
Tests for JobExecutionStore.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.scheduler.store import JobExecutionStore
from src.core.scheduler.execution import JobExecution, JobExecutionStatus, TriggerType


def create_execution(
    job_name: str = "test_job",
    scheduler_name: str = "test_scheduler",
    status: JobExecutionStatus = JobExecutionStatus.COMPLETED,
    duration_ms: int = 100,
    created_at: datetime = None
) -> JobExecution:
    """Helper to create test executions."""
    execution = JobExecution(
        job_name=job_name,
        scheduler_name=scheduler_name,
    )
    execution.status = status
    execution.duration_ms = duration_ms
    if created_at:
        execution.created_at = created_at
    return execution


@pytest.fixture
def store():
    """Create a fresh store for each test."""
    return JobExecutionStore(max_in_memory=100)


class TestJobExecutionStoreInit:
    """Tests for store initialization."""

    def test_default_values(self):
        """Test default initialization."""
        store = JobExecutionStore()

        assert store.max_in_memory == 1000
        assert len(store._executions) == 0
        assert len(store._stats) == 0

    def test_custom_max_in_memory(self):
        """Test custom max_in_memory value."""
        store = JobExecutionStore(max_in_memory=50)
        assert store.max_in_memory == 50


class TestSaveExecution:
    """Tests for saving executions."""

    @pytest.mark.asyncio
    async def test_save_execution(self, store):
        """Test saving an execution."""
        execution = create_execution()

        await store.save(execution)

        assert len(store._executions) == 1
        assert store._executions[0] == execution

    @pytest.mark.asyncio
    async def test_save_multiple_executions(self, store):
        """Test saving multiple executions."""
        for i in range(5):
            execution = create_execution(job_name=f"job_{i}")
            await store.save(execution)

        assert len(store._executions) == 5

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test that old executions are evicted when max is reached."""
        store = JobExecutionStore(max_in_memory=3)

        exec1 = create_execution(job_name="job_1")
        exec2 = create_execution(job_name="job_2")
        exec3 = create_execution(job_name="job_3")
        exec4 = create_execution(job_name="job_4")

        await store.save(exec1)
        await store.save(exec2)
        await store.save(exec3)
        await store.save(exec4)

        assert len(store._executions) == 3
        # First one should be evicted
        assert exec1 not in store._executions
        assert exec2 in store._executions
        assert exec3 in store._executions
        assert exec4 in store._executions

    @pytest.mark.asyncio
    async def test_save_updates_stats(self, store):
        """Test that saving updates statistics."""
        execution = create_execution(
            scheduler_name="scheduler1",
            job_name="job1",
            status=JobExecutionStatus.COMPLETED,
            duration_ms=100
        )

        await store.save(execution)

        key = "scheduler1:job1"
        assert store._stats[key]["total"] == 1
        assert store._stats[key]["success"] == 1
        assert store._stats[key]["total_duration_ms"] == 100

    @pytest.mark.asyncio
    async def test_save_updates_stats_for_failures(self, store):
        """Test that failures are tracked in stats."""
        execution = create_execution(status=JobExecutionStatus.FAILED)
        await store.save(execution)

        execution2 = create_execution(status=JobExecutionStatus.TIMEOUT)
        await store.save(execution2)

        execution3 = create_execution(status=JobExecutionStatus.CANCELLED)
        await store.save(execution3)

        key = "test_scheduler:test_job"
        assert store._stats[key]["total"] == 3
        assert store._stats[key]["failed"] == 1
        assert store._stats[key]["timeout"] == 1
        assert store._stats[key]["cancelled"] == 1


class TestGetRecentExecutions:
    """Tests for querying recent executions."""

    @pytest.mark.asyncio
    async def test_get_recent_executions(self, store):
        """Test getting recent executions."""
        for i in range(5):
            await store.save(create_execution(job_name=f"job_{i}"))

        executions = await store.get_recent_executions()

        assert len(executions) == 5
        # Should be in reverse order (most recent first)
        assert executions[0].job_name == "job_4"
        assert executions[4].job_name == "job_0"

    @pytest.mark.asyncio
    async def test_filter_by_job_name(self, store):
        """Test filtering by job name."""
        await store.save(create_execution(job_name="job_a"))
        await store.save(create_execution(job_name="job_b"))
        await store.save(create_execution(job_name="job_a"))

        executions = await store.get_recent_executions(job_name="job_a")

        assert len(executions) == 2
        assert all(e.job_name == "job_a" for e in executions)

    @pytest.mark.asyncio
    async def test_filter_by_scheduler_name(self, store):
        """Test filtering by scheduler name."""
        await store.save(create_execution(scheduler_name="scheduler_1"))
        await store.save(create_execution(scheduler_name="scheduler_2"))
        await store.save(create_execution(scheduler_name="scheduler_1"))

        executions = await store.get_recent_executions(scheduler_name="scheduler_1")

        assert len(executions) == 2
        assert all(e.scheduler_name == "scheduler_1" for e in executions)

    @pytest.mark.asyncio
    async def test_filter_by_status(self, store):
        """Test filtering by status."""
        await store.save(create_execution(status=JobExecutionStatus.COMPLETED))
        await store.save(create_execution(status=JobExecutionStatus.FAILED))
        await store.save(create_execution(status=JobExecutionStatus.COMPLETED))

        executions = await store.get_recent_executions(status=JobExecutionStatus.FAILED)

        assert len(executions) == 1
        assert executions[0].status == JobExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_limit_and_offset(self, store):
        """Test limit and offset pagination."""
        for i in range(10):
            await store.save(create_execution(job_name=f"job_{i}"))

        # Get first 3
        page1 = await store.get_recent_executions(limit=3, offset=0)
        assert len(page1) == 3
        assert page1[0].job_name == "job_9"  # Most recent

        # Get next 3
        page2 = await store.get_recent_executions(limit=3, offset=3)
        assert len(page2) == 3
        assert page2[0].job_name == "job_6"

    @pytest.mark.asyncio
    async def test_combined_filters(self, store):
        """Test combining multiple filters."""
        await store.save(create_execution(
            job_name="job_a",
            scheduler_name="scheduler_1",
            status=JobExecutionStatus.COMPLETED
        ))
        await store.save(create_execution(
            job_name="job_a",
            scheduler_name="scheduler_1",
            status=JobExecutionStatus.FAILED
        ))
        await store.save(create_execution(
            job_name="job_b",
            scheduler_name="scheduler_1",
            status=JobExecutionStatus.COMPLETED
        ))

        executions = await store.get_recent_executions(
            job_name="job_a",
            scheduler_name="scheduler_1",
            status=JobExecutionStatus.COMPLETED
        )

        assert len(executions) == 1
        assert executions[0].job_name == "job_a"
        assert executions[0].status == JobExecutionStatus.COMPLETED


class TestGetStats:
    """Tests for getting statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, store):
        """Test getting stats with no executions."""
        stats = await store.get_stats("nonexistent")

        assert stats["total_executions"] == 0
        assert stats["success_count"] == 0
        assert stats["failed_count"] == 0
        assert stats["avg_duration_ms"] == 0
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, store):
        """Test getting stats with executions."""
        # 3 successful, 1 failed, 1 timeout
        for _ in range(3):
            await store.save(create_execution(
                scheduler_name="test",
                status=JobExecutionStatus.COMPLETED,
                duration_ms=100
            ))

        await store.save(create_execution(
            scheduler_name="test",
            status=JobExecutionStatus.FAILED,
            duration_ms=50
        ))

        await store.save(create_execution(
            scheduler_name="test",
            status=JobExecutionStatus.TIMEOUT,
            duration_ms=300
        ))

        stats = await store.get_stats("test")

        assert stats["total_executions"] == 5
        assert stats["success_count"] == 3
        assert stats["failed_count"] == 1
        assert stats["timeout_count"] == 1
        # avg_duration = total_duration / total_executions = (3*100 + 50 + 300) / 5 = 650 / 5 = 130
        assert stats["avg_duration_ms"] == 130
        assert stats["success_rate"] == 60.0  # 3/5 = 60%

    @pytest.mark.asyncio
    async def test_get_stats_multiple_jobs(self, store):
        """Test that stats aggregate across all jobs in a scheduler."""
        await store.save(create_execution(
            scheduler_name="test",
            job_name="job_a",
            status=JobExecutionStatus.COMPLETED
        ))
        await store.save(create_execution(
            scheduler_name="test",
            job_name="job_b",
            status=JobExecutionStatus.COMPLETED
        ))
        await store.save(create_execution(
            scheduler_name="other",
            job_name="job_c",
            status=JobExecutionStatus.COMPLETED
        ))

        stats = await store.get_stats("test")

        assert stats["total_executions"] == 2
        assert stats["success_count"] == 2


class TestGetLastExecution:
    """Tests for getting last execution."""

    @pytest.mark.asyncio
    async def test_get_last_execution(self, store):
        """Test getting the last execution for a job."""
        exec1 = create_execution(job_name="job", scheduler_name="sched")
        exec2 = create_execution(job_name="job", scheduler_name="sched")
        exec3 = create_execution(job_name="job", scheduler_name="sched")

        await store.save(exec1)
        await store.save(exec2)
        await store.save(exec3)

        last = await store.get_last_execution("job", "sched")

        assert last == exec3

    @pytest.mark.asyncio
    async def test_get_last_execution_not_found(self, store):
        """Test getting last execution when none exist."""
        last = await store.get_last_execution("nonexistent", "sched")
        assert last is None


class TestCleanupOldExecutions:
    """Tests for cleaning up old executions."""

    @pytest.mark.asyncio
    async def test_cleanup_old_executions(self, store):
        """Test cleaning up old executions."""
        # Create old and new executions
        old_time = datetime.now() - timedelta(days=60)
        new_time = datetime.now() - timedelta(days=10)

        old_exec = create_execution(job_name="old", created_at=old_time)
        new_exec = create_execution(job_name="new", created_at=new_time)

        await store.save(old_exec)
        await store.save(new_exec)

        deleted = await store.cleanup_old_executions(days=30)

        assert deleted == 1
        assert len(store._executions) == 1
        assert store._executions[0].job_name == "new"

    @pytest.mark.asyncio
    async def test_cleanup_no_old_executions(self, store):
        """Test cleanup when no old executions exist."""
        recent = create_execution(created_at=datetime.now())
        await store.save(recent)

        deleted = await store.cleanup_old_executions(days=30)

        assert deleted == 0
        assert len(store._executions) == 1


class TestConcurrentAccess:
    """Tests for concurrent access to the store."""

    @pytest.mark.asyncio
    async def test_concurrent_saves(self, store):
        """Test that concurrent saves don't cause issues."""
        async def save_batch(start: int, count: int):
            for i in range(count):
                await store.save(create_execution(job_name=f"job_{start + i}"))

        # Run multiple save batches concurrently
        await asyncio.gather(
            save_batch(0, 10),
            save_batch(10, 10),
            save_batch(20, 10),
        )

        assert len(store._executions) == 30

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self, store):
        """Test concurrent reads and writes."""
        async def writer():
            for i in range(20):
                await store.save(create_execution(job_name=f"job_{i}"))
                await asyncio.sleep(0.01)

        async def reader():
            for _ in range(20):
                await store.get_recent_executions()
                await asyncio.sleep(0.01)

        # Should not raise any errors
        await asyncio.gather(writer(), reader())
