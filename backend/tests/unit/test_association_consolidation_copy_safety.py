import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.curation.models import EventAssociation
from src.modules.curation.services.association_service import CurationAssociationMixin


class _FakeLLM:
    def __init__(self, payload: dict):
        self._payload = payload

    async def chat(self, *args, **kwargs):
        return SimpleNamespace(text=json.dumps(self._payload, ensure_ascii=False))


class _Harness(CurationAssociationMixin):
    def __init__(self, payload: dict):
        self.llm = _FakeLLM(payload)

    @staticmethod
    def _strip_markdown_json(text: str) -> str:
        return text


@pytest.mark.asyncio
async def test_consolidation_does_not_overwrite_reason_with_internal_language() -> None:
    family_id = uuid4()
    source_event_id = uuid4()
    assoc_keep = EventAssociation(
        family_id=family_id,
        source_event_id=source_event_id,
        target_id=str(uuid4()),
        target_type="person",
        association_type="person",
        title="在揭阳期间探望父母",
        reason="父母在揭阳，行程重合，适合提前安排见面。",
        priority="strongly_recommend",
        confidence=0.92,
    )
    assoc_dup = EventAssociation(
        family_id=family_id,
        source_event_id=source_event_id,
        target_id=str(uuid4()),
        target_type="person",
        association_type="person",
        title="探望爸妈",
        reason="与春节安排接近，可合并处理。",
        priority="convenient",
        confidence=0.8,
    )

    harness = _Harness(
        payload={
            "groups": [
                {
                    "keep_index": 0,
                    "dismiss_indices": [1],
                    "merged_title": "在揭阳期间看望父母",
                    "merged_reason": "index 0 保留，priority 更高（strongly_recommend）",
                }
            ],
            "standalone_indices": [],
        }
    )

    result = await harness._consolidate_associations([assoc_keep, assoc_dup])

    assert len(result) == 1
    assert result[0].title == "在揭阳期间看望父母"
    assert result[0].reason == "父母在揭阳，行程重合，适合提前安排见面。"
