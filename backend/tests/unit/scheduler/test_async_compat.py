import asyncio

import pytest

from src.core.scheduler._async_compat import run_async, shutdown_worker_event_loop


@pytest.mark.unit
class TestAsyncCompat:
    def teardown_method(self):
        shutdown_worker_event_loop()

    def test_run_async_returns_result(self):
        async def _coro():
            return 42

        assert run_async(_coro()) == 42

    def test_run_async_reuses_worker_loop(self):
        async def _loop_id():
            return id(asyncio.get_running_loop())

        first = run_async(_loop_id())
        second = run_async(_loop_id())
        assert first == second

    def test_shutdown_resets_loop(self):
        async def _loop_obj():
            return asyncio.get_running_loop()

        first = run_async(_loop_obj())
        shutdown_worker_event_loop()
        assert first.is_closed() is True
        second = run_async(_loop_obj())
        assert second is not first

    def test_run_async_cleans_up_spawned_tasks(self):
        events = []

        async def _spawn_background():
            async def _bg():
                try:
                    await asyncio.sleep(3600)
                finally:
                    events.append("cancelled")

            asyncio.create_task(_bg())
            return "ok"

        assert run_async(_spawn_background()) == "ok"
        assert "cancelled" in events
