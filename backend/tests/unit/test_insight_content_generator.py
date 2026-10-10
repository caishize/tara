"""Tests for insight_content_generator.py - LLM content generation functions."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.insight.insight_content_generator import (
    generate_insight_content,
    generate_stress_suggestion,
    generate_summary_text,
)


def _make_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages response with a single text block."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def _make_empty_response() -> MagicMock:
    """Build a mock response with no text blocks."""
    block = MagicMock(spec=[])  # no .text attribute
    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# generate_insight_content
# ---------------------------------------------------------------------------


class TestGenerateInsightContent:

    @pytest.mark.asyncio
    async def test_valid_json_response(self):
        """Returns parsed title and content from valid LLM JSON."""
        payload = json.dumps({"title": "提醒一下", "content": "记得今天联系朋友"})
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_response(payload))

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content("<ctx/>", "holiday")

        assert result["title"] == "提醒一下"
        assert result["content"] == "记得今天联系朋友"

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_fallback(self):
        """Non-JSON LLM output falls back to provided defaults."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_response("not valid json at all")
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content(
                "<ctx/>",
                "birthday",
                fallback_title="默认标题",
                fallback_content="默认内容",
            )

        assert result["title"] == "默认标题"
        assert result["content"] == "默认内容"

    @pytest.mark.asyncio
    async def test_llm_exception_returns_fallback(self):
        """LLM API exception falls back gracefully."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=RuntimeError("API timeout")
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content(
                "<ctx/>",
                "stress",
                fallback_title="备用标题",
                fallback_content="备用内容",
            )

        assert result["title"] == "备用标题"
        assert result["content"] == "备用内容"

    @pytest.mark.asyncio
    async def test_empty_text_blocks_returns_fallback(self):
        """When no text blocks in response, fallback is returned."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_empty_response()
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content("<ctx/>", "follow_up")

        assert result["title"] == "温馨提醒"
        assert result["content"] == "有件事想提醒你一下。"

    @pytest.mark.asyncio
    async def test_missing_json_keys_use_fallback(self):
        """JSON with missing keys falls back to defaults for those keys."""
        payload = json.dumps({"title": "只有标题"})
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_response(payload))

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_insight_content(
                "<ctx/>",
                "test",
                fallback_content="默认content",
            )

        assert result["title"] == "只有标题"
        assert result["content"] == "默认content"

    @pytest.mark.asyncio
    async def test_custom_system_prompt_passed_through(self):
        """Custom system_prompt is forwarded to LLM call."""
        payload = json.dumps({"title": "t", "content": "c"})
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_response(payload))

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            await generate_insight_content(
                "<ctx/>",
                "test",
                system_prompt="custom system prompt",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "custom system prompt"


# ---------------------------------------------------------------------------
# generate_summary_text
# ---------------------------------------------------------------------------


class TestGenerateSummaryText:

    @pytest.mark.asyncio
    async def test_valid_response_returns_text(self):
        """Returns stripped text from LLM response."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_response("  今天有三件事需要处理。  ")
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_summary_text("<ctx/>")

        assert result == "今天有三件事需要处理。"

    @pytest.mark.asyncio
    async def test_exception_returns_fallback(self):
        """API exception returns the fallback string."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("network error"))

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_summary_text(
                "<ctx/>", fallback="备用摘要文字"
            )

        assert result == "备用摘要文字"

    @pytest.mark.asyncio
    async def test_empty_text_blocks_returns_fallback(self):
        """No text blocks → fallback."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_empty_response()
        )

        with patch(
            "src.core.llm.haiku_client.get_haiku_client",
            return_value=mock_client,
        ):
            result = await generate_summary_text("<ctx/>")

        assert result == "今天的安排已经为你整理好了。"


# ---------------------------------------------------------------------------
# generate_stress_suggestion
# ---------------------------------------------------------------------------


class TestGenerateStressSuggestion:

    @pytest.mark.asyncio
    async def test_delegates_to_generate_insight_content(self):
        """generate_stress_suggestion is a thin wrapper over generate_insight_content."""
        expected = {"title": "注意休息", "content": "最近安排挺多的，多照顾自己。"}

        with patch(
            "src.modules.insight.insight_content_generator.generate_insight_content",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_gen:
            result = await generate_stress_suggestion("<stress_ctx/>")

        mock_gen.assert_awaited_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["insight_type"] == "stress_suggestion"
        assert call_kwargs["context_xml"] == "<stress_ctx/>"
        assert result == expected

    @pytest.mark.asyncio
    async def test_custom_fallbacks_forwarded(self):
        """Custom fallback values are forwarded to the underlying function."""
        with patch(
            "src.modules.insight.insight_content_generator.generate_insight_content",
            new_callable=AsyncMock,
            return_value={"title": "t", "content": "c"},
        ) as mock_gen:
            await generate_stress_suggestion(
                "<ctx/>",
                fallback_title="自定义标题",
                fallback_content="自定义内容",
            )

        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["fallback_title"] == "自定义标题"
        assert call_kwargs["fallback_content"] == "自定义内容"
