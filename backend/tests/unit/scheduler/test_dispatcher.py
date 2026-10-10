"""
Tests for the unified dispatcher and task registry.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.core.scheduler.dispatcher import (
    TASK_CONFIGS,
    register_task,
)
from src.core.scheduler.redis_scheduler import (
    TaskScheduleConfig,
    ScheduleType,
)


class TestTaskRegistry:

    def test_all_expected_tasks_registered(self):
        expected = [
            "secretary.prepare_daily_content",
            "secretary.curate_family",
            "assistant.consolidate_user_memories",
            "assistant.generate_user_secretary_notes",
            "secretary.run_family_hygiene",
            "reminder.send_single",
            "gift.process_single_task",
        ]
        for name in expected:
            assert name in TASK_CONFIGS, f"{name} not registered"

    def test_daily_content_config(self):
        cfg = TASK_CONFIGS["secretary.prepare_daily_content"]
        assert cfg.entity_type == "user"
        assert cfg.schedule_type == ScheduleType.DAILY
        assert cfg.default_hour == 6
        assert cfg.default_minute == 0
        assert cfg.queue == "secretary"

    def test_curation_config(self):
        cfg = TASK_CONFIGS["secretary.curate_family"]
        assert cfg.entity_type == "family"
        assert cfg.schedule_type == ScheduleType.INTERVAL
        assert cfg.default_interval_minutes == 60

    def test_reminder_is_once(self):
        cfg = TASK_CONFIGS["reminder.send_single"]
        assert cfg.schedule_type == ScheduleType.ONCE

    def test_gift_is_once(self):
        cfg = TASK_CONFIGS["gift.process_single_task"]
        assert cfg.schedule_type == ScheduleType.ONCE

    def test_register_custom_task(self):
        custom = TaskScheduleConfig(
            task_name="test.custom_task",
            entity_type="test",
            schedule_type=ScheduleType.DAILY,
            default_hour=12,
        )
        register_task(custom)
        assert "test.custom_task" in TASK_CONFIGS
        assert TASK_CONFIGS["test.custom_task"].default_hour == 12

        # Clean up
        del TASK_CONFIGS["test.custom_task"]


class TestDispatchDueTasks:

    @patch("src.core.cache.get_redis_client")
    def test_dispatch_skips_when_redis_unavailable(self, mock_get_redis):
        from src.core.scheduler.dispatcher import dispatch_due_tasks

        mock_get_redis.return_value = None
        result = dispatch_due_tasks()
        assert result == {"error": "redis_unavailable"}

    @patch("src.celery_app.celery_app")
    @patch("src.core.cache.get_redis_client")
    def test_dispatch_sends_tasks(self, mock_get_redis, mock_celery):
        from src.core.scheduler.dispatcher import dispatch_due_tasks

        fake_redis = MagicMock()
        mock_get_redis.return_value = fake_redis

        # The dispatcher now uses SyncRedisScheduleStore.pop_due which calls
        # script_load + evalsha. Mock evalsha to return items only for briefing.
        fake_redis.script_load.return_value = "fake_sha"

        def fake_evalsha(sha, numkeys, key, *args):
            if key == "schedule:secretary.prepare_daily_content":
                return ["user-1", "user-2"]
            return []

        fake_redis.evalsha.side_effect = fake_evalsha

        result = dispatch_due_tasks()

        assert result["dispatched"] == 2
        assert mock_celery.send_task.call_count == 2
        mock_celery.send_task.assert_any_call(
            "secretary.prepare_daily_content",
            args=["user-1"],
            queue="secretary",
        )


class TestRescheduleSync:

    @patch("src.core.cache.get_redis_client")
    def test_reschedule_sync_daily(self, mock_get_redis):
        from src.core.scheduler.reschedule import reschedule_sync

        fake_redis = MagicMock()
        mock_get_redis.return_value = fake_redis
        fake_redis.zadd.return_value = 1

        result = reschedule_sync("secretary.prepare_daily_content", "user-1")

        assert result is True
        fake_redis.zadd.assert_called_once()
        call_args = fake_redis.zadd.call_args
        key = call_args[0][0]
        assert key == "schedule:secretary.prepare_daily_content"

    def test_reschedule_once_skipped(self):
        from src.core.scheduler.reschedule import reschedule_sync

        result = reschedule_sync("reminder.send_single", "reminder-1")
        assert result is False

    def test_reschedule_unknown_task(self):
        from src.core.scheduler.reschedule import reschedule_sync

        result = reschedule_sync("nonexistent.task", "entity-1")
        assert result is False


class TestLifecycle:

    @pytest.mark.asyncio
    async def test_on_user_activated(self):
        from uuid import uuid4
        from src.core.scheduler.lifecycle import on_user_activated, _task_names_for
        from tests.unit.scheduler.test_redis_scheduler import FakeAsyncRedis

        fake_redis = FakeAsyncRedis()
        uid = uuid4()
        added = await on_user_activated(uid, redis_client=fake_redis)
        assert added == len(_task_names_for("user"))

    @pytest.mark.asyncio
    async def test_on_user_deactivated(self):
        from uuid import uuid4
        from src.core.scheduler.lifecycle import (
            on_user_activated,
            on_user_deactivated,
            _task_names_for,
        )
        from tests.unit.scheduler.test_redis_scheduler import FakeAsyncRedis

        fake_redis = FakeAsyncRedis()
        uid = uuid4()
        await on_user_activated(uid, redis_client=fake_redis)
        removed = await on_user_deactivated(uid, redis_client=fake_redis)
        assert removed == len(_task_names_for("user"))

    @pytest.mark.asyncio
    async def test_on_family_activated(self):
        from uuid import uuid4
        from src.core.scheduler.lifecycle import on_family_activated, _task_names_for
        from tests.unit.scheduler.test_redis_scheduler import FakeAsyncRedis

        fake_redis = FakeAsyncRedis()
        fid = uuid4()
        added = await on_family_activated(fid, redis_client=fake_redis)
        assert added == len(_task_names_for("family"))
