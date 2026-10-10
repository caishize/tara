from unittest.mock import AsyncMock

import pytest
from uuid import UUID

from src.ai_engine.router.types import (
    ActionType,
    Difficulty,
    IntentCategory,
    IntentClassification,
    RouteType,
)
from src.ai_engine.tools.registry import ToolExecutionContext
from src.ai_engine.workers.fast_worker import FastWorker


async def _collect(async_iter):
    items = []
    async for item in async_iter:
        items.append(item)
    return items


async def _fake_stream(_prompt: str):
    yield {"type": "content", "content": "ok", "is_final": True}


def _weather_intent(lookup_filter: str | None) -> IntentClassification:
    return IntentClassification(
        route_type=RouteType.FAST,
        intent_category=IntentCategory.WEATHER_QUERY,
        confidence=0.95,
        difficulty=Difficulty.IMMEDIATE,
        action=ActionType.WEATHER,
        lookup_filter=lookup_filter,
    )


@pytest.mark.asyncio
async def test_handle_weather_city_query_ignores_context_coordinates():
    worker = FastWorker(model="test-model")
    worker._fetch_weather = AsyncMock(  # type: ignore[method-assign]
        return_value={"location": "揭阳", "temperature": "17°C", "condition": "晴"}
    )
    worker._stream_llm_response = _fake_stream  # type: ignore[method-assign]

    context = {
        "location_name": "上海",
        "latitude": 31.2304,
        "longitude": 121.4737,
    }

    events = await _collect(
        worker._handle_weather("揭阳天气怎样", _weather_intent("揭阳"), context)
    )

    worker._fetch_weather.assert_awaited_once_with(  # type: ignore[attr-defined]
        location="揭阳",
        latitude=None,
        longitude=None,
    )
    tool_start = next(event for event in events if event.get("type") == "tool_start")
    assert "latitude" not in tool_start["arguments"]
    assert "longitude" not in tool_start["arguments"]


@pytest.mark.asyncio
async def test_execute_weather_tool_with_explicit_city_does_not_inject_context_geo():
    worker = FastWorker(model="test-model")
    worker._fetch_weather = AsyncMock(  # type: ignore[method-assign]
        return_value={"location": "揭阳", "temperature": "17°C", "condition": "晴"}
    )

    request_context = {
        "location_name": "上海",
        "latitude": 31.2304,
        "longitude": 121.4737,
    }
    await worker._execute_weather_tool({"location": "揭阳"}, request_context)

    worker._fetch_weather.assert_awaited_once_with(  # type: ignore[attr-defined]
        location="揭阳",
        latitude=None,
        longitude=None,
        progress_cb=None,
    )


@pytest.mark.asyncio
async def test_execute_weather_tool_emits_progress_events():
    worker = FastWorker(model="test-model")
    worker._fetch_weather = AsyncMock(  # type: ignore[method-assign]
        return_value={"location": "揭阳", "temperature": "17°C", "condition": "晴"}
    )

    seen: list[tuple[str, str]] = []
    tool_ctx = ToolExecutionContext(
        family_id=UUID(int=0),
        user_id=UUID(int=0),
        session_id="s",
        progress_callback=lambda stage, message: seen.append((stage, message)),
    )
    await worker._execute_weather_tool(
        {"location": "揭阳"},
        request_context=None,
        tool_context=tool_ctx,
    )

    assert any(stage == "weather_prepare" for stage, _ in seen)
    assert any(stage == "weather_fetch" for stage, _ in seen)
    assert any(stage == "weather_done" for stage, _ in seen)
