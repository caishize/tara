"""
Unit tests for TaskQueue and TaskPayload — the Redis Streams task queue.

Tests cover:
- TaskPayload serialization / deserialization (to_dict / from_dict)
- TaskQueue enqueue/dequeue with fakeredis
- Consumer group creation
- Acknowledgment
- Dead letter queue
"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_engine.queue.task_queue import TaskPayload, TaskQueue


# ---------------------------------------------------------------------------
# TaskPayload — serialization
# ---------------------------------------------------------------------------

class TestTaskPayload:
    def test_to_dict_basic(self):
        payload = TaskPayload(
            job_id="j1",
            user_id="u1",
            family_id="f1",
            user_input="你好",
            route_type="slow",
        )
        d = payload.to_dict()
        assert d["job_id"] == "j1"
        assert d["user_id"] == "u1"
        assert d["family_id"] == "f1"
        assert d["user_input"] == "你好"
        assert d["route_type"] == "slow"
        assert "session_id" not in d  # None is omitted

    def test_to_dict_with_session_id(self):
        payload = TaskPayload(
            job_id="j1",
            user_id="u1",
            family_id="f1",
            user_input="你好",
            route_type="slow",
            session_id="s123",
        )
        d = payload.to_dict()
        assert d["session_id"] == "s123"

    def test_to_dict_serializes_context_as_json(self):
        payload = TaskPayload(
            job_id="j1",
            user_id="u1",
            family_id="f1",
            user_input="查天气",
            route_type="fast",
            context_snapshot={"location": "北京"},
        )
        d = payload.to_dict()
        assert json.loads(d["context_snapshot"]) == {"location": "北京"}

    def test_to_dict_serializes_metadata_as_json(self):
        payload = TaskPayload(
            job_id="j1",
            user_id="u1",
            family_id="f1",
            user_input="查天气",
            route_type="fast",
            metadata={"key": "value"},
        )
        d = payload.to_dict()
        assert json.loads(d["metadata"]) == {"key": "value"}

    def test_from_dict_basic(self):
        data = {
            "job_id": "j1",
            "user_id": "u1",
            "family_id": "f1",
            "user_input": "你好",
            "route_type": "slow",
            "context_snapshot": "{}",
            "metadata": "{}",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        payload = TaskPayload.from_dict(data)
        assert payload.job_id == "j1"
        assert payload.user_id == "u1"
        assert payload.route_type == "slow"
        assert payload.context_snapshot == {}
        assert payload.metadata == {}

    def test_from_dict_parses_json_context(self):
        data = {
            "job_id": "j1",
            "user_id": "u1",
            "family_id": "f1",
            "user_input": "查天气",
            "route_type": "fast",
            "context_snapshot": '{"location": "北京"}',
            "metadata": "{}",
        }
        payload = TaskPayload.from_dict(data)
        assert payload.context_snapshot == {"location": "北京"}

    def test_from_dict_handles_invalid_json_gracefully(self):
        data = {
            "job_id": "j1",
            "user_id": "u1",
            "family_id": "f1",
            "user_input": "你好",
            "route_type": "slow",
            "context_snapshot": "not-valid-json",
            "metadata": "not-valid-json",
        }
        payload = TaskPayload.from_dict(data)
        assert payload.context_snapshot == {}
        assert payload.metadata == {}

    def test_from_dict_handles_dict_context_directly(self):
        data = {
            "job_id": "j1",
            "user_id": "u1",
            "family_id": "f1",
            "user_input": "你好",
            "route_type": "slow",
            "context_snapshot": {"already": "parsed"},
            "metadata": {"key": "val"},
        }
        payload = TaskPayload.from_dict(data)
        assert payload.context_snapshot == {"already": "parsed"}
        assert payload.metadata == {"key": "val"}

    def test_from_dict_defaults_route_type(self):
        data = {
            "job_id": "j1",
            "user_id": "u1",
            "family_id": "f1",
            "user_input": "你好",
        }
        payload = TaskPayload.from_dict(data)
        assert payload.route_type == "slow"

    def test_roundtrip(self):
        original = TaskPayload(
            job_id="j1",
            user_id="u1",
            family_id="f1",
            user_input="帮我规划行程",
            route_type="slow",
            session_id="s1",
            context_snapshot={"location": "上海"},
            metadata={"priority": "high"},
        )
        restored = TaskPayload.from_dict(original.to_dict())
        assert restored.job_id == original.job_id
        assert restored.user_id == original.user_id
        assert restored.family_id == original.family_id
        assert restored.user_input == original.user_input
        assert restored.route_type == original.route_type
        assert restored.session_id == original.session_id
        assert restored.context_snapshot == original.context_snapshot
        assert restored.metadata == original.metadata


# ---------------------------------------------------------------------------
# TaskQueue — with mocked Redis client
# ---------------------------------------------------------------------------

class TestTaskQueueEnqueue:
    @pytest.fixture
    def mock_redis(self):
        client = AsyncMock()
        client.xadd = AsyncMock(return_value="1234567890-0")
        client.xgroup_create = AsyncMock()
        return client

    @pytest.fixture
    def queue(self, mock_redis):
        q = TaskQueue()
        q._client = mock_redis
        return q

    @pytest.mark.asyncio
    async def test_enqueue_calls_xadd(self, queue, mock_redis):
        payload = TaskPayload(
            job_id="j1",
            user_id="u1",
            family_id="f1",
            user_input="你好",
            route_type="slow",
        )
        message_id = await queue.enqueue(payload)

        assert message_id == "1234567890-0"
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == TaskQueue.STREAM_KEY

    @pytest.mark.asyncio
    async def test_enqueue_auto_connects(self):
        q = TaskQueue()
        assert q._client is None
        with patch.object(q, "connect", new_callable=AsyncMock) as mock_connect:
            # After connect, set _client to a mock
            async def set_client():
                q._client = AsyncMock()
                q._client.xadd = AsyncMock(return_value="1-0")
            mock_connect.side_effect = set_client

            payload = TaskPayload(
                job_id="j1", user_id="u1", family_id="f1",
                user_input="你好", route_type="slow",
            )
            await q.enqueue(payload)
            mock_connect.assert_called_once()


class TestTaskQueueDequeue:
    @pytest.fixture
    def mock_redis(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def queue(self, mock_redis):
        q = TaskQueue()
        q._client = mock_redis
        return q

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_empty(self, queue, mock_redis):
        mock_redis.xreadgroup.return_value = None
        mock_redis.xpending_range.return_value = []

        result = await queue.dequeue("agent_workers", "worker_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_returns_task_payload(self, queue, mock_redis):
        mock_redis.xpending_range.return_value = []
        mock_redis.xreadgroup.return_value = [
            ("agent:tasks", [
                ("1234-0", {
                    "job_id": "j1",
                    "user_id": "u1",
                    "family_id": "f1",
                    "user_input": "查日程",
                    "route_type": "fast",
                    "context_snapshot": "{}",
                    "metadata": "{}",
                    "created_at": "2026-01-01T00:00:00+00:00",
                })
            ])
        ]

        result = await queue.dequeue("agent_workers", "worker_1")

        assert result is not None
        assert result.job_id == "j1"
        assert result.user_input == "查日程"
        assert result.metadata["_stream_message_id"] == "1234-0"

    @pytest.mark.asyncio
    async def test_dequeue_empty_messages_returns_none(self, queue, mock_redis):
        mock_redis.xpending_range.return_value = []
        mock_redis.xreadgroup.return_value = [("agent:tasks", [])]

        result = await queue.dequeue("agent_workers", "worker_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_prioritizes_claimed_stale_messages(self, queue, mock_redis):
        stale = TaskPayload(
            job_id="stale-job",
            user_id="u1",
            family_id="f1",
            user_input="补偿处理",
            route_type="slow",
            metadata={"_stream_message_id": "9999-0"},
        )
        queue._claim_stale_messages = AsyncMock(return_value=[stale])  # type: ignore[attr-defined]

        result = await queue.dequeue("agent_workers", "worker_1")

        assert result is not None
        assert result.job_id == "stale-job"
        # Claimed task should be returned directly; no new-message read needed.
        mock_redis.xreadgroup.assert_not_called()

    @pytest.mark.asyncio
    async def test_dequeue_buffers_remaining_claimed_messages(self, queue, mock_redis):
        stale_1 = TaskPayload(
            job_id="stale-1",
            user_id="u1",
            family_id="f1",
            user_input="a",
            route_type="slow",
            metadata={"_stream_message_id": "9001-0"},
        )
        stale_2 = TaskPayload(
            job_id="stale-2",
            user_id="u1",
            family_id="f1",
            user_input="b",
            route_type="slow",
            metadata={"_stream_message_id": "9002-0"},
        )
        queue._claim_stale_messages = AsyncMock(return_value=[stale_1, stale_2])  # type: ignore[attr-defined]

        first = await queue.dequeue("agent_workers", "worker_1")
        second = await queue.dequeue("agent_workers", "worker_1")

        assert first is not None and first.job_id == "stale-1"
        assert second is not None and second.job_id == "stale-2"
        # Second dequeue should drain in-memory buffer before claiming/reading.
        assert queue._claim_stale_messages.await_count == 1  # type: ignore[attr-defined]
        mock_redis.xreadgroup.assert_not_called()


class TestTaskQueueAck:
    @pytest.fixture
    def mock_redis(self):
        client = AsyncMock()
        client.xack = AsyncMock(return_value=1)
        return client

    @pytest.fixture
    def queue(self, mock_redis):
        q = TaskQueue()
        q._client = mock_redis
        return q

    @pytest.mark.asyncio
    async def test_ack_success(self, queue, mock_redis):
        result = await queue.ack("j1", message_id="1234-0")
        assert result is True
        mock_redis.xack.assert_called_once_with(
            TaskQueue.STREAM_KEY,
            TaskQueue.CONSUMER_GROUP,
            "1234-0",
        )

    @pytest.mark.asyncio
    async def test_ack_no_message_id_returns_false(self, queue):
        result = await queue.ack("j1", message_id=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_ack_no_client_returns_false(self):
        q = TaskQueue()
        q._client = None
        result = await q.ack("j1", message_id="1234-0")
        assert result is False

    @pytest.mark.asyncio
    async def test_ack_failure_returns_false(self, queue, mock_redis):
        mock_redis.xack = AsyncMock(return_value=0)
        result = await queue.ack("j1", message_id="1234-0")
        assert result is False


class TestTaskQueueClaimStale:
    @pytest.fixture
    def mock_redis(self):
        client = AsyncMock()
        client.xpending_range = AsyncMock()
        client.exists = AsyncMock()
        client.xclaim = AsyncMock()
        client.hgetall = AsyncMock(return_value={})
        client.hdel = AsyncMock()
        return client

    @pytest.fixture
    def queue(self, mock_redis):
        q = TaskQueue()
        q._client = mock_redis
        return q

    @pytest.mark.asyncio
    async def test_claim_stale_skips_alive_owner(self, queue, mock_redis):
        mock_redis.xpending_range.return_value = [
            {
                "message_id": "100-0",
                "consumer": "worker-a",
                "time_since_delivered": queue._claim_timeout_ms + 1,
                "times_delivered": 1,
            }
        ]
        mock_redis.exists.return_value = 1

        claimed = await queue._claim_stale_messages("agent_workers", "worker-b")

        assert claimed == []
        mock_redis.xclaim.assert_not_called()

    @pytest.mark.asyncio
    async def test_claim_stale_reclaims_dead_owner(self, queue, mock_redis):
        mock_redis.xpending_range.return_value = [
            {
                "message_id": "101-0",
                "consumer": "worker-dead",
                "time_since_delivered": queue._claim_timeout_ms + 1,
                "times_delivered": 1,
            }
        ]
        mock_redis.exists.return_value = 0
        mock_redis.xclaim.return_value = [
            (
                "101-0",
                {
                    "job_id": "j1",
                    "user_id": "u1",
                    "family_id": "f1",
                    "user_input": "你好",
                    "route_type": "slow",
                    "context_snapshot": "{}",
                    "metadata": "{}",
                },
            )
        ]

        claimed = await queue._claim_stale_messages("agent_workers", "worker-b")

        assert len(claimed) == 1
        assert claimed[0].job_id == "j1"
        assert claimed[0].metadata["_stream_message_id"] == "101-0"
        assert claimed[0].metadata["_claimed_from"] == "worker-dead"
        assert claimed[0].metadata["_times_delivered"] == 2
        mock_redis.xclaim.assert_called_once()

    @pytest.mark.asyncio
    async def test_claim_stale_moves_poison_message_to_dlq(self, queue, mock_redis):
        """Messages exceeding max_delivery_count should be moved to DLQ."""
        mock_redis.xpending_range.return_value = [
            {
                "message_id": "200-0",
                "consumer": "worker-dead",
                "time_since_delivered": queue._claim_timeout_ms + 1,
                "times_delivered": queue._max_delivery_count,  # At the limit
            }
        ]
        mock_redis.exists.return_value = 0
        # xclaim for the DLQ move path (_move_pending_to_dlq)
        mock_redis.xclaim.return_value = [
            (
                "200-0",
                {
                    "job_id": "poison-job",
                    "user_id": "u1",
                    "family_id": "f1",
                    "user_input": "bad input",
                    "route_type": "slow",
                    "context_snapshot": "{}",
                    "metadata": "{}",
                },
            )
        ]
        mock_redis.xadd = AsyncMock()
        mock_redis.xack = AsyncMock(return_value=1)

        claimed = await queue._claim_stale_messages("agent_workers", "worker-b")

        # Poison message should NOT be returned as claimed
        assert claimed == []
        # It should have been moved to DLQ via xadd
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == TaskQueue.DLQ_STREAM_KEY


class TestTaskQueueDeregisterWorker:
    @pytest.mark.asyncio
    async def test_deregister_worker_cleans_up_keys(self):
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.hdel = AsyncMock()
        mock_client.hgetall = AsyncMock(return_value={
            "session-1": "worker-dying",
            "session-2": "worker-other",
            "session-3": "worker-dying",
        })

        q = TaskQueue()
        q._client = mock_client
        await q.deregister_worker("worker-dying")

        # Should delete heartbeat key
        mock_client.delete.assert_any_call("worker:heartbeat:worker-dying")
        # Should remove from registry
        mock_client.hdel.assert_any_call(TaskQueue.WORKER_REGISTRY_KEY, "worker-dying")
        # Should clean affinity for sessions pointing to this worker
        mock_client.hdel.assert_any_call(TaskQueue.AFFINITY_KEY, "session-1")
        mock_client.hdel.assert_any_call(TaskQueue.AFFINITY_KEY, "session-3")


class TestTaskQueueConsumerGroup:
    @pytest.mark.asyncio
    async def test_ensure_consumer_group_creates_group(self):
        mock_client = AsyncMock()
        mock_client.xgroup_create = AsyncMock()

        q = TaskQueue()
        q._client = mock_client
        await q._ensure_consumer_group()

        mock_client.xgroup_create.assert_called_once_with(
            TaskQueue.STREAM_KEY,
            TaskQueue.CONSUMER_GROUP,
            id="0",
            mkstream=True,
        )

    @pytest.mark.asyncio
    async def test_ensure_consumer_group_ignores_busygroup(self):
        import redis.asyncio as redis_lib
        mock_client = AsyncMock()
        mock_client.xgroup_create = AsyncMock(
            side_effect=redis_lib.ResponseError("BUSYGROUP Consumer Group name already exists")
        )

        q = TaskQueue()
        q._client = mock_client
        # Should not raise
        await q._ensure_consumer_group()
