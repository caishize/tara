"""Integration tests for insight dedup-aware prompt → LLM → disposition pipeline.

Verifies the full chain:
1. Active insights with person names are formatted correctly
2. The prompt section includes person info and merge instructions
3. LLM response with dispositions is parsed correctly
4. process_dispositions correctly splits KEEP/UPDATE/NEW

Key scenario: "龙抬头问候" exists for [周明], signals mention 周明+强哥+用户太太
→ LLM should UPDATE the existing one (merge all persons), NOT generate 3 separate NEW insights.
"""

from __future__ import annotations

import json
import uuid
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.insight.insight_dedup_aware import (
    ActiveInsightRow,
    build_dedup_aware_prompt_section,
    format_active_insights_for_prompt,
    process_dispositions,
)
from src.modules.insight.insight_llm_client import _parse_candidate_item
from src.modules.insight.models import InsightCandidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_active_row(
    title: str,
    insight_type: str = "relationship",
    importance: int = 75,
    related_persons: list | None = None,
    insight_id: str | None = None,
) -> ActiveInsightRow:
    return ActiveInsightRow(
        id=uuid.UUID(insight_id) if insight_id else uuid.uuid4(),
        title=title,
        insight_type=insight_type,
        importance=importance,
        related_persons=related_persons or [],
    )


def _make_llm_response(items: list) -> MagicMock:
    """Build mock Anthropic response with JSON array text."""
    block = MagicMock()
    block.text = json.dumps(items, ensure_ascii=False)
    response = MagicMock()
    response.content = [block]
    return response


# ===========================================================================
# Test: Prompt contains person info so LLM can decide correctly
# ===========================================================================


class TestPromptContainsPersonInfo:
    """Verify that the prompt sent to LLM includes enough context
    to prevent person-specific duplicate generation."""

    def test_existing_insight_with_persons_appears_in_prompt(self):
        """The prompt section includes person names for each existing insight."""
        existing_id = str(uuid.uuid4())
        rows = [
            _make_active_row(
                title="龙抬头问候",
                insight_id=existing_id,
                related_persons=["周明"],
            ),
        ]
        section = build_dedup_aware_prompt_section(rows)

        # Must contain the insight ID so LLM can reference it
        assert existing_id in section
        # Must contain person name so LLM knows who this insight covers
        assert "周明" in section
        # Must contain merge instruction
        assert "UPDATE" in section
        assert "合并" in section

    def test_multiple_existing_insights_same_topic_shown_to_llm(self):
        """If duplicates already exist in DB, LLM sees all of them
        and can decide to merge via UPDATE."""
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        rows = [
            _make_active_row(
                title="龙抬头问候",
                insight_id=id1,
                importance=80,
                related_persons=["周明"],
            ),
            _make_active_row(
                title="龙抬头问候",
                insight_id=id2,
                importance=75,
                related_persons=["用户太太"],
            ),
        ]
        section = build_dedup_aware_prompt_section(rows)

        # Both IDs and person names present
        assert id1 in section
        assert id2 in section
        assert "周明" in section
        assert "用户太太" in section

    def test_insight_without_persons_has_no_persons_field(self):
        """Insights without person associations don't have 'persons' key."""
        rows = [
            _make_active_row(
                title="效率提醒",
                insight_type="efficiency",
                related_persons=[],
            ),
        ]
        formatted = format_active_insights_for_prompt(rows)
        parsed = json.loads(formatted.strip())

        assert "persons" not in parsed


# ===========================================================================
# Test: Simulated LLM dedup response parsing
# ===========================================================================


class TestSimulatedLLMDedupResponse:
    """Simulate what a well-behaved LLM should return when given existing
    insights with person info, and verify the disposition pipeline handles it."""

    def test_llm_returns_keep_for_existing_insight(self):
        """When existing insight is still valid, LLM returns KEEP."""
        existing_id = str(uuid.uuid4())

        llm_output = {
            "insight_type": "relationship",
            "title": "",
            "content": "",
            "disposition": "KEEP",
            "existing_id": existing_id,
        }
        candidate = _parse_candidate_item(llm_output)

        assert candidate is not None
        assert candidate.disposition == "KEEP"
        assert candidate.existing_id == existing_id

    def test_llm_returns_update_to_merge_persons(self):
        """When existing insight should be expanded to cover more persons,
        LLM returns UPDATE with merged content."""
        existing_id = str(uuid.uuid4())

        llm_output = {
            "insight_type": "relationship",
            "title": "龙抬头问候",
            "content": "龙抬头将至，建议向周明、强哥、太太送上问候",
            "importance": 80,
            "urgency": 70,
            "disposition": "UPDATE",
            "existing_id": existing_id,
            "suggested_action": "发送祝福消息",
            "action_options": [
                {"label": "生成祝福语", "action_type": "open_chat", "action_payload": {}},
            ],
        }
        candidate = _parse_candidate_item(llm_output)

        assert candidate is not None
        assert candidate.disposition == "UPDATE"
        assert candidate.existing_id == existing_id
        assert "周明" in candidate.content
        assert "强哥" in candidate.content

    def test_disposition_pipeline_splits_correctly(self):
        """Full pipeline: LLM returns mix of KEEP/UPDATE/NEW → correct split."""
        existing_id_1 = str(uuid.uuid4())
        existing_id_2 = str(uuid.uuid4())

        candidates = [
            # KEEP an existing insight
            InsightCandidate(
                insight_type="relationship",
                title="",
                content="",
                importance=75,
                disposition="KEEP",
                existing_id=existing_id_1,
            ),
            # UPDATE another to merge persons
            InsightCandidate(
                insight_type="relationship",
                title="龙抬头问候",
                content="龙抬头将至，建议向周明、强哥送上问候",
                importance=80,
                urgency=70,
                disposition="UPDATE",
                existing_id=existing_id_2,
                suggested_action="发送祝福",
                action_options=[{"label": "生成祝福语", "action_type": "open_chat"}],
            ),
            # NEW insight (unrelated topic)
            InsightCandidate(
                insight_type="time",
                title="出差准备",
                content="后天出差，记得收拾行李",
                importance=60,
                urgency=50,
                disposition="NEW",
            ),
        ]

        result = process_dispositions(candidates)

        assert len(result.keep_ids) == 1
        assert result.keep_ids[0] == existing_id_1
        assert len(result.update_specs) == 1
        assert result.update_specs[0]["existing_id"] == existing_id_2
        assert "周明" in result.update_specs[0]["content"]
        assert len(result.new_candidates) == 1
        assert result.new_candidates[0].title == "出差准备"


# ===========================================================================
# Test: End-to-end mock LLM call → disposition processing
# ===========================================================================


class TestEndToEndDedupWithMockLLM:
    """Simulate the full path: build prompt → mock LLM returns dispositions →
    process_dispositions splits correctly. Ensures no duplicates survive."""

    @pytest.mark.asyncio
    async def test_dragon_head_greeting_dedup_scenario(self):
        """Exact reproduction of the bug: '龙抬头问候' with 3 person variants.

        Given: existing insight '龙抬头问候' for [周明]
        Signal: 龙抬头 approaching, relevant persons: 周明, 强哥, 用户太太
        Expected: LLM should UPDATE existing insight, NOT create 3 NEW ones.
        """
        existing_id = str(uuid.uuid4())

        # Step 1: Build prompt section with existing insights
        active_rows = [
            _make_active_row(
                title="龙抬头问候",
                insight_id=existing_id,
                importance=75,
                related_persons=["周明"],
            ),
        ]
        dedup_section = build_dedup_aware_prompt_section(active_rows)

        # Verify prompt contains the right info
        assert existing_id in dedup_section
        assert "周明" in dedup_section

        # Step 2: Simulate correct LLM response (UPDATE existing, not NEW*3)
        correct_llm_response = [
            {
                "insight_type": "relationship",
                "title": "龙抬头问候",
                "content": "龙抬头将至，建议向周明、强哥和太太送上问候",
                "importance": 80,
                "urgency": 70,
                "disposition": "UPDATE",
                "existing_id": existing_id,
                "suggested_action": "发送祝福消息",
                "action_options": [
                    {"label": "生成祝福语", "action_type": "open_chat", "action_payload": {}},
                ],
                "source_signal_ids": ["signal-1"],
            },
        ]

        # Step 3: Parse LLM response
        candidates = [
            c for item in correct_llm_response
            if (c := _parse_candidate_item(item)) is not None
        ]

        assert len(candidates) == 1
        assert candidates[0].disposition == "UPDATE"
        assert candidates[0].existing_id == existing_id

        # Step 4: Process dispositions
        result = process_dispositions(candidates)

        assert len(result.new_candidates) == 0, "Should have 0 NEW (all merged into UPDATE)"
        assert len(result.update_specs) == 1, "Should have 1 UPDATE"
        assert result.update_specs[0]["existing_id"] == existing_id

    @pytest.mark.asyncio
    async def test_buggy_llm_response_generates_duplicates(self):
        """Demonstrate what happens when LLM ignores dedup and creates 3 NEW.

        This is the BUG scenario — all 3 pass as NEW candidates.
        The fix should make this scenario impossible by providing person info.
        """
        existing_id = str(uuid.uuid4())

        # Buggy LLM response: 3 NEW instead of 1 UPDATE
        buggy_response = [
            {
                "insight_type": "relationship",
                "title": "龙抬头问候: 周明",
                "content": "龙抬头将至，建议向周明送上问候",
                "importance": 75,
                "urgency": 70,
                "disposition": "NEW",
                "source_signal_ids": ["s1"],
            },
            {
                "insight_type": "relationship",
                "title": "龙抬头问候: 强哥",
                "content": "龙抬头将至，建议向强哥送上问候",
                "importance": 75,
                "urgency": 70,
                "disposition": "NEW",
                "source_signal_ids": ["s2"],
            },
            {
                "insight_type": "relationship",
                "title": "龙抬头问候: 太太",
                "content": "龙抬头将至，建议向太太送上问候",
                "importance": 75,
                "urgency": 70,
                "disposition": "NEW",
                "source_signal_ids": ["s3"],
            },
        ]

        candidates = [
            c for item in buggy_response
            if (c := _parse_candidate_item(item)) is not None
        ]

        result = process_dispositions(candidates)

        # BUG: all 3 are NEW, 0 updates — this is what we DON'T want
        assert len(result.new_candidates) == 3
        assert len(result.update_specs) == 0

    def test_prompt_with_persons_prevents_blind_spot(self):
        """Verify the prompt section provides enough info for LLM to avoid
        generating duplicates — the prompt must show WHO each insight covers."""
        existing_id = str(uuid.uuid4())

        rows = [
            _make_active_row(
                title="龙抬头问候",
                insight_id=existing_id,
                importance=75,
                related_persons=["周明"],
            ),
        ]

        section = build_dedup_aware_prompt_section(rows)

        # Parse the JSON entry from the prompt
        # The section contains instructions + JSON entries
        lines = section.strip().split("\n")
        json_lines = [l for l in lines if l.startswith("{")]
        assert len(json_lines) == 1

        entry = json.loads(json_lines[0])
        assert entry["id"] == existing_id
        assert entry["title"] == "龙抬头问候"
        assert entry["persons"] == ["周明"]
        assert entry["type"] == "relationship"

    def test_prompt_without_persons_creates_blind_spot(self):
        """When persons are absent, the LLM only sees the title and can't
        determine which persons an insight already covers — creating duplicates."""
        rows = [
            _make_active_row(
                title="龙抬头问候",
                importance=75,
                related_persons=[],  # no person info!
            ),
        ]

        formatted = format_active_insights_for_prompt(rows)
        entry = json.loads(formatted.strip())

        # Without persons, LLM has no way to know which people this covers
        assert "persons" not in entry
        # Title alone is ambiguous — "龙抬头问候" could be for anyone


# ===========================================================================
# Test: Real LLM call (requires ANTHROPIC_API_KEY, skipped in CI)
# ===========================================================================


@pytest.mark.skipif(
    True,  # Set to False to run manually with API key
    reason="Requires ANTHROPIC_API_KEY; run manually",
)
class TestRealLLMDedup:
    """Call the actual LLM to verify dedup behavior.

    To run: set the skipif condition to False and ensure ANTHROPIC_API_KEY is set.
    """

    @pytest.mark.asyncio
    async def test_real_llm_dedup_dragon_head(self):
        from src.modules.insight.insight_llm_client import call_llm_and_parse
        from src.modules.insight.constants import SECRETARY_PERSONA_PROMPT

        existing_id = str(uuid.uuid4())

        system_prompt = SECRETARY_PERSONA_PROMPT + """你的任务是根据以下信号为用户生成洞察提醒。

## 规则
1. 每条洞察必须基于至少一条信号，不要编造
2. 标题10字以内，内容50字以内
3. 合并同类义务：不要为同一主题的不同人物分别生成独立洞察

## 输出格式（严格JSON数组）
[{"insight_type":"relationship","title":"标题","content":"内容","importance":50,"urgency":50,"suggested_action":"建议","disposition":"NEW|KEEP|UPDATE","existing_id":"如果UPDATE/KEEP则提供","source_signal_ids":[]}]

## 去重处理协议 (Disposition)
如果用户消息中包含"现有活跃洞察"列表，请对每条输出标注 disposition 字段:
- "KEEP": 该洞察仍然有效，无需变更（需提供 existing_id）
- "UPDATE": 该洞察需要更新内容（需提供 existing_id 和新的 content/importance/urgency）
- "NEW": 全新洞察（默认，无需 existing_id）

如果没有提供现有洞察列表，所有输出默认为 "NEW"。"""

        active_rows = [
            _make_active_row(
                title="龙抬头问候",
                insight_id=existing_id,
                importance=75,
                related_persons=["周明"],
            ),
        ]
        dedup_section = build_dedup_aware_prompt_section(active_rows)

        signals = """
[信号] 重要日期: 龙抬头 (二月二), 2026-03-21, 关联人物: 周明, 强哥, 用户太太
[信号] 人物关系: 周明 (朋友), 强哥 (朋友), 用户太太 (配偶)
"""
        user_prompt = f"今天是 2026-03-19。\n\n以下是收集到的信号：\n{signals}{dedup_section}"

        candidates = await call_llm_and_parse(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_attempts=2,
        )

        # LLM should NOT generate 3 separate NEW insights
        new_count = sum(1 for c in candidates if c.disposition == "NEW"
                        and "龙抬头" in c.title)
        update_count = sum(1 for c in candidates if c.disposition == "UPDATE"
                           and c.existing_id == existing_id)

        # Either: 1 UPDATE (merge all into existing) or at most 1 NEW (combined)
        assert update_count >= 1 or new_count <= 1, (
            f"LLM generated {new_count} separate NEW '龙抬头' insights "
            f"instead of updating existing. Candidates: "
            f"{[(c.disposition, c.title, c.existing_id) for c in candidates]}"
        )
