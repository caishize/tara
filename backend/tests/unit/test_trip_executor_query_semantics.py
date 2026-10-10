from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.ai_engine.tools.executors.trip_executor import TripToolExecutor


def _empty_result():
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_query_trips_past_planned_defaults_to_include_history_true():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_result())
    executor = TripToolExecutor(db)

    response = await executor.query_trips(
        args={"query_scene": "past_planned"},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert response["success"] is True
    assert response["include_history"] is True
    assert response["query_scene"] == "past_planned"


@pytest.mark.asyncio
async def test_query_trips_default_excludes_history():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_result())
    executor = TripToolExecutor(db)

    response = await executor.query_trips(
        args={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert response["success"] is True
    assert response["include_history"] is False
    assert response["query_scene"] == "default"
