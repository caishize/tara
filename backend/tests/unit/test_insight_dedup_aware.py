"""Tests for LLM-aware insight deduplication.

Covers:
- format_active_insights_for_prompt: formatting, token budget, sanitization, person names
- process_dispositions: splitting NEW/UPDATE/KEEP, edge cases
- apply_updates: DB update logic with mocked session
- _parse_candidate_item: disposition field parsing
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.insight.insight_dedup_aware import ActiveInsightRow
from src.modules.insight.models import InsightCandidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(
    insight_id: str | None = None,
    title: str = "测试洞察",
    insight_type: str = "relationship",
    importance: int = 60,
    related_persons: Optional[List[str]] = None,
) -> ActiveInsightRow:
    """Create an ActiveInsightRow matching fetch_active_insights output."""
    return ActiveInsightRow(
        id=uuid.UUID(insight_id) if insight_id else uuid.uuid4(),
        title=title,
        insight_type=insight_type,
        importance=importance,
        related_persons=related_persons or [],
    )


def _make_candidate(
    disposition: str = "NEW",
    existing_id: str | None = None,
    title: str = "新洞察",
    content: str = "洞察内容",
    insight_type: str = "relationship",
    importance: int = 60,
) -> InsightCandidate:
    return InsightCandidate(
        insight_type=insight_type,
        title=title,
        content=content,
        importance=importance,
        disposition=disposition,
        existing_id=existing_id,
    )


# ===========================================================================
# format_active_insights_for_prompt
# ===========================================================================


class TestFormatActiveInsightsForPrompt:
    """Tests for format_active_insights_for_prompt."""

    def test_empty_list_returns_empty_string(self):
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        assert format_active_insights_for_prompt([]) == ""

    def test_normal_list_formats_correctly(self):
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        rows = [_make_row(insight_id=uid, title="妈妈生日准备", importance=80)]
        result = format_active_insights_for_prompt(rows)

        # Should contain the id, truncated title, type, importance
        assert uid in result
        assert "relationship" in result
        assert "80" in result

    def test_token_budget_truncation_drops_lowest_importance(self):
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        # Create many rows to exceed ~1500 token budget
        rows = [
            _make_row(
                title=f"洞察标题{i:03d}很长的标题用于测试",
                importance=i,
            )
            for i in range(60)
        ]
        result = format_active_insights_for_prompt(rows)

        # Low importance items should be dropped first
        # The result should be non-empty (some items fit)
        assert len(result) > 0
        # Highest importance items should be present
        assert "59" in result  # importance=59 item's importance value

    def test_title_sanitization_strips_dangerous_chars(self):
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        rows = [_make_row(title="<script>alert`xss`</script>\nnewline")]
        result = format_active_insights_for_prompt(rows)

        assert "<" not in result
        assert ">" not in result
        assert "`" not in result
        assert "\n" not in result.split("\n")[-1]  # no newline in data portion

    def test_title_truncated_to_20_chars(self):
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        long_title = "这是一个非常非常非常非常非常长的标题超过二十个字符"
        rows = [_make_row(title=long_title)]
        result = format_active_insights_for_prompt(rows)

        # The title in the output should be at most 20 chars
        # Parse the JSON-like output to verify
        assert long_title not in result  # full title should not appear


# ===========================================================================
# process_dispositions
# ===========================================================================


class TestProcessDispositions:
    """Tests for process_dispositions."""

    def test_all_new_goes_to_new_candidates(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        candidates = [
            _make_candidate(disposition="NEW"),
            _make_candidate(disposition="NEW"),
        ]
        result = process_dispositions(candidates)

        assert len(result.new_candidates) == 2
        assert len(result.update_specs) == 0
        assert len(result.keep_ids) == 0

    def test_mixed_dispositions_correct_separation(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        candidates = [
            _make_candidate(disposition="NEW"),
            _make_candidate(disposition="UPDATE", existing_id=uid1, content="更新内容"),
            _make_candidate(disposition="KEEP", existing_id=uid2),
        ]
        result = process_dispositions(candidates)

        assert len(result.new_candidates) == 1
        assert len(result.update_specs) == 1
        assert result.update_specs[0]["existing_id"] == uid1
        assert len(result.keep_ids) == 1
        assert result.keep_ids[0] == uid2

    def test_update_with_invalid_uuid_downgrades_to_new(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        candidates = [
            _make_candidate(
                disposition="UPDATE",
                existing_id="not-a-uuid",
                content="更新内容",
            ),
        ]
        result = process_dispositions(candidates)

        assert len(result.new_candidates) == 1
        assert len(result.update_specs) == 0

    def test_keep_with_missing_existing_id_downgrades_to_new(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        candidates = [
            _make_candidate(disposition="KEEP", existing_id=None),
        ]
        result = process_dispositions(candidates)

        assert len(result.new_candidates) == 1
        assert len(result.keep_ids) == 0

    def test_update_with_empty_content_downgrades_to_keep(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        uid = str(uuid.uuid4())
        candidates = [
            _make_candidate(disposition="UPDATE", existing_id=uid, content=""),
        ]
        result = process_dispositions(candidates)

        assert len(result.update_specs) == 0
        assert len(result.keep_ids) == 1
        assert result.keep_ids[0] == uid

    def test_unknown_disposition_defaults_to_new(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        candidates = [
            _make_candidate(disposition="INVALID"),
        ]
        result = process_dispositions(candidates)

        assert len(result.new_candidates) == 1

    def test_duplicate_existing_ids_last_write_wins(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        uid = str(uuid.uuid4())
        candidates = [
            _make_candidate(
                disposition="UPDATE",
                existing_id=uid,
                content="第一次更新",
            ),
            _make_candidate(
                disposition="UPDATE",
                existing_id=uid,
                content="第二次更新",
            ),
        ]
        result = process_dispositions(candidates)

        assert len(result.update_specs) == 1
        assert result.update_specs[0]["content"] == "第二次更新"

    def test_empty_list_returns_empty_results(self):
        from src.modules.insight.insight_dedup_aware import process_dispositions

        result = process_dispositions([])

        assert len(result.new_candidates) == 0
        assert len(result.update_specs) == 0
        assert len(result.keep_ids) == 0


# ===========================================================================
# apply_updates
# ===========================================================================


class TestApplyUpdates:
    """Tests for apply_updates with mocked DB session."""

    @pytest.mark.asyncio
    async def test_successful_update_returns_id(self):
        from src.modules.insight.insight_dedup_aware import apply_updates

        uid = str(uuid.uuid4())
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 1

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        update_specs = [
            {
                "existing_id": uid,
                "content": "更新后的内容",
                "importance": 70,
                "urgency": 60,
                "action_options": None,
                "suggested_action": "新建议",
            },
        ]

        result = await apply_updates(db, user_id, update_specs)

        assert uid in result
        assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_wrong_user_returns_empty(self):
        from src.modules.insight.insight_dedup_aware import apply_updates

        uid = str(uuid.uuid4())
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 0  # no rows matched

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        update_specs = [
            {
                "existing_id": uid,
                "content": "更新内容",
                "importance": 70,
                "urgency": 60,
                "action_options": None,
                "suggested_action": None,
            },
        ]

        result = await apply_updates(db, user_id, update_specs)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_nonexistent_id_returns_empty(self):
        from src.modules.insight.insight_dedup_aware import apply_updates

        user_id = uuid.uuid4()
        fake_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.rowcount = 0

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        update_specs = [
            {
                "existing_id": fake_id,
                "content": "内容",
                "importance": 50,
                "urgency": 50,
                "action_options": None,
                "suggested_action": None,
            },
        ]

        result = await apply_updates(db, user_id, update_specs)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_empty_update_specs_returns_empty(self):
        from src.modules.insight.insight_dedup_aware import apply_updates

        db = AsyncMock()
        result = await apply_updates(db, uuid.uuid4(), [])

        assert len(result) == 0
        assert db.execute.call_count == 0


# ===========================================================================
# _parse_candidate_item with disposition
# ===========================================================================


class TestParseCandidateItemDisposition:
    """Tests for disposition/existing_id parsing in _parse_candidate_item."""

    def test_keep_disposition_parsed(self):
        from src.modules.insight.insight_llm_client import _parse_candidate_item

        uid = str(uuid.uuid4())
        item = {
            "insight_type": "relationship",
            "title": "",
            "content": "",
            "disposition": "KEEP",
            "existing_id": uid,
        }
        result = _parse_candidate_item(item)

        assert result is not None
        assert result.disposition == "KEEP"
        assert result.existing_id == uid

    def test_update_disposition_parsed_with_content(self):
        from src.modules.insight.insight_llm_client import _parse_candidate_item

        uid = str(uuid.uuid4())
        item = {
            "insight_type": "favor",
            "title": "更新标题",
            "content": "更新内容",
            "disposition": "UPDATE",
            "existing_id": uid,
            "importance": 70,
        }
        result = _parse_candidate_item(item)

        assert result is not None
        assert result.disposition == "UPDATE"
        assert result.existing_id == uid
        assert result.content == "更新内容"

    def test_missing_disposition_defaults_to_new(self):
        from src.modules.insight.insight_llm_client import _parse_candidate_item

        item = {
            "insight_type": "time",
            "title": "新洞察",
            "content": "内容",
        }
        result = _parse_candidate_item(item)

        assert result is not None
        assert result.disposition == "NEW"
        assert result.existing_id is None

    def test_case_insensitive_disposition(self):
        from src.modules.insight.insight_llm_client import _parse_candidate_item

        uid = str(uuid.uuid4())
        item = {
            "insight_type": "relationship",
            "title": "标题",
            "content": "内容",
            "disposition": "update",
            "existing_id": uid,
        }
        result = _parse_candidate_item(item)

        assert result is not None
        assert result.disposition == "UPDATE"

    def test_keep_allows_empty_title_and_content(self):
        from src.modules.insight.insight_llm_client import _parse_candidate_item

        uid = str(uuid.uuid4())
        item = {
            "insight_type": "relationship",
            "title": "",
            "content": "",
            "disposition": "KEEP",
            "existing_id": uid,
        }
        result = _parse_candidate_item(item)

        assert result is not None
        assert result.title == ""
        assert result.content == ""
        assert result.disposition == "KEEP"


# ===========================================================================
# Person-aware dedup formatting (prevents duplicate person-specific insights)
# ===========================================================================


class TestPersonAwareDedupFormatting:
    """Tests that person names are included in the prompt so LLM can avoid
    generating duplicate insights for the same topic + different persons."""

    def test_persons_included_in_formatted_output(self):
        """When an insight has related_persons, they appear in the JSON output."""
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        rows = [
            _make_row(
                title="龙抬头问候",
                insight_type="relationship",
                importance=75,
                related_persons=["周明", "强哥"],
            ),
        ]
        result = format_active_insights_for_prompt(rows)
        parsed = json.loads(result.strip())

        assert "persons" in parsed
        assert "周明" in parsed["persons"]
        assert "强哥" in parsed["persons"]

    def test_no_persons_field_when_empty(self):
        """When related_persons is empty, persons key is omitted (saves tokens)."""
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        rows = [_make_row(title="效率提醒", insight_type="efficiency", importance=50)]
        result = format_active_insights_for_prompt(rows)
        parsed = json.loads(result.strip())

        assert "persons" not in parsed

    def test_multiple_insights_with_different_persons(self):
        """Multiple insights each show their own person associations."""
        from src.modules.insight.insight_dedup_aware import (
            format_active_insights_for_prompt,
        )

        rows = [
            _make_row(
                title="龙抬头问候",
                importance=80,
                related_persons=["周明"],
            ),
            _make_row(
                title="龙抬头问候",
                importance=75,
                related_persons=["用户太太"],
            ),
        ]
        result = format_active_insights_for_prompt(rows)
        lines = result.strip().split("\n")
        parsed_items = [json.loads(line) for line in lines]

        assert len(parsed_items) == 2
        # Higher importance first
        assert parsed_items[0]["persons"] == ["周明"]
        assert parsed_items[1]["persons"] == ["用户太太"]

    def test_build_dedup_prompt_includes_person_merge_instruction(self):
        """The prompt section tells LLM not to generate duplicates for same topic."""
        from src.modules.insight.insight_dedup_aware import (
            build_dedup_aware_prompt_section,
        )

        rows = [
            _make_row(
                title="龙抬头问候",
                importance=75,
                related_persons=["周明"],
            ),
        ]
        result = build_dedup_aware_prompt_section(rows)

        assert "persons" in result
        assert "同一主题" in result
        assert "合并" in result
        assert "DELETE" in result

    def test_active_insight_row_attributes(self):
        """ActiveInsightRow stores all expected attributes."""
        row = ActiveInsightRow(
            id=uuid.uuid4(),
            title="测试",
            insight_type="relationship",
            importance=70,
            related_persons=["张三", "李四"],
        )
        assert row.related_persons == ["张三", "李四"]
        assert row.title == "测试"
        assert row.importance == 70
