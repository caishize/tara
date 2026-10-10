from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.rule_engine import RuleBasedAssociationEngine


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.mark.asyncio
async def test_find_date_based_associations_skips_self_source_date():
    family_id = uuid4()
    date_id = uuid4()
    event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="妈妈生日",
        event_type="birthday",
        normalized_start=datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc),
        original_event_ids=[str(date_id)],
        source_types=["important_date"],
    )
    important_date = SimpleNamespace(
        id=date_id,
        title="妈妈生日",
        solar_date=event.normalized_start.date(),
        date_type="birthday",
    )

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult([important_date]))
    engine = RuleBasedAssociationEngine(session=session)

    associations = await engine._find_date_based_associations(family_id, event)
    assert associations == []
