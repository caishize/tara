"""
Unit tests for IntentRouter — the dual-brain routing core.

Tests cover:
- Route resolution logic (two-axis → route)
- Parsing helpers (difficulty, action, lookup_target)
- Confirmation detection
- Classify end-to-end with mocked Anthropic API (unified single-call)
- Error handling / fallback behaviour
- Unified classifier: single LLM call, missing field defaults, context entity extraction
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.ai_engine.router.intent_router import IntentRouter
from src.ai_engine.router.types import (
    RouteType,
    Difficulty,
    ActionType,
    LookupTarget,
    IntentCategory,
    IntentClassification,
    resolve_route,
    map_to_intent_category,
)


# ---------------------------------------------------------------------------
# resolve_route (pure function)
# ---------------------------------------------------------------------------

class TestResolveRoute:
    def test_immediate_no_enhance_returns_fast(self):
        assert resolve_route(Difficulty.IMMEDIATE, False) == RouteType.FAST

    def test_immediate_with_enhance_returns_hybrid(self):
        assert resolve_route(Difficulty.IMMEDIATE, True) == RouteType.HYBRID

    def test_thinking_returns_slow(self):
        assert resolve_route(Difficulty.THINKING, False) == RouteType.SLOW

    def test_thinking_with_enhance_still_slow(self):
        assert resolve_route(Difficulty.THINKING, True) == RouteType.SLOW

    def test_unsure_returns_slow(self):
        assert resolve_route(Difficulty.UNSURE, False) == RouteType.SLOW


# ---------------------------------------------------------------------------
# map_to_intent_category (pure function)
# ---------------------------------------------------------------------------

class TestToLegacyIntent:
    def test_greeting(self):
        result = map_to_intent_category(Difficulty.IMMEDIATE, ActionType.GREET, False)
        assert result == IntentCategory.GREETING

    def test_weather_with_enhance(self):
        result = map_to_intent_category(Difficulty.IMMEDIATE, ActionType.WEATHER, True)
        assert result == IntentCategory.WEATHER_WITH_ADVICE

    def test_lookup_with_enhance(self):
        result = map_to_intent_category(Difficulty.IMMEDIATE, ActionType.LOOKUP, True)
        assert result == IntentCategory.SCHEDULE_WITH_SUGGESTIONS

    def test_thinking_plan(self):
        result = map_to_intent_category(Difficulty.THINKING, ActionType.PLAN, False)
        assert result == IntentCategory.TRIP_PLANNING

    def test_unknown_combo_returns_unknown(self):
        result = map_to_intent_category(Difficulty.UNSURE, ActionType.TIME, False)
        assert result == IntentCategory.UNKNOWN


# ---------------------------------------------------------------------------
# IntentRouter — parsing helpers
# ---------------------------------------------------------------------------

class TestIntentRouterParsing:
    @pytest.fixture
    def router(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return IntentRouter(
                client=AsyncMock(),
                model="test-model",
            )

    def test_parse_difficulty_valid(self, router):
        assert router._parse_difficulty("immediate") == Difficulty.IMMEDIATE
        assert router._parse_difficulty("thinking") == Difficulty.THINKING

    def test_parse_difficulty_none(self, router):
        assert router._parse_difficulty(None) == Difficulty.UNSURE

    def test_parse_difficulty_unknown(self, router):
        assert router._parse_difficulty("invalid") == Difficulty.UNSURE

    def test_parse_difficulty_case_insensitive(self, router):
        assert router._parse_difficulty("IMMEDIATE") == Difficulty.IMMEDIATE

    def test_parse_action_valid(self, router):
        assert router._parse_action("lookup") == ActionType.LOOKUP
        assert router._parse_action("create") == ActionType.CREATE

    def test_parse_action_none(self, router):
        assert router._parse_action(None) == ActionType.CHAT

    def test_parse_action_unknown(self, router):
        assert router._parse_action("nonexistent") == ActionType.CHAT

    def test_parse_lookup_target_valid(self, router):
        assert router._parse_lookup_target("task") == LookupTarget.TASK
        assert router._parse_lookup_target("trip") == LookupTarget.TRIP

    def test_parse_lookup_target_none(self, router):
        assert router._parse_lookup_target(None) is None

    def test_parse_lookup_target_unknown(self, router):
        assert router._parse_lookup_target("nonexistent") == LookupTarget.UNKNOWN


# ---------------------------------------------------------------------------
# IntentRouter — confirmation detection
# ---------------------------------------------------------------------------

class TestConfirmationRequired:
    @pytest.fixture
    def router(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return IntentRouter(
                client=AsyncMock(),
                model="test-model",
            )

    def test_transact_always_requires_confirmation(self, router):
        assert router._check_confirmation_required(ActionType.TRANSACT, "随便说")

    def test_purchase_keyword_requires_confirmation(self, router):
        assert router._check_confirmation_required(ActionType.CREATE, "帮我买一个AirPods")

    def test_booking_keyword_requires_confirmation(self, router):
        assert router._check_confirmation_required(ActionType.CREATE, "预订明天去北京的机票")

    def test_normal_input_no_confirmation(self, router):
        assert not router._check_confirmation_required(ActionType.LOOKUP, "查看今天的日程")

    def test_payment_keyword_requires_confirmation(self, router):
        assert router._check_confirmation_required(ActionType.CREATE, "支付这笔订单")


# ---------------------------------------------------------------------------
# IntentRouter.classify — end-to-end with mocked Anthropic
# ---------------------------------------------------------------------------

class TestClassifyEndToEnd:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def router(self, mock_client):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return IntentRouter(client=mock_client, model="test-model")

    def _make_response(self, payload: dict):
        """Build a fake Anthropic API response."""
        content_block = MagicMock()
        content_block.text = json.dumps(payload)
        response = MagicMock()
        response.content = [content_block]
        return response

    @pytest.mark.asyncio
    async def test_classify_greeting(self, router, mock_client):
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "greet",
            "enhance": False,
            "confidence": 0.95,
            "lookup_target": "unknown",
            "lookup_filter": None,
            "reasoning": "Simple greeting",
        })

        result = await router.classify("你好", user_id="u1")

        assert result.route_type == RouteType.FAST
        assert result.difficulty == Difficulty.IMMEDIATE
        assert result.action == ActionType.GREET
        assert result.intent_category == IntentCategory.GREETING
        assert result.confidence == 0.95
        assert not result.requires_confirmation

    @pytest.mark.asyncio
    async def test_classify_lookup(self, router, mock_client):
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "lookup",
            "enhance": False,
            "confidence": 0.9,
            "lookup_target": "schedule",
            "lookup_filter": None,
            "reasoning": "User wants to check schedule",
        })

        result = await router.classify("查看今天的日程", user_id="u1")

        assert result.route_type == RouteType.FAST
        assert result.action == ActionType.LOOKUP
        assert result.lookup_target == LookupTarget.SCHEDULE

    @pytest.mark.asyncio
    async def test_classify_complex_plan_goes_slow(self, router, mock_client):
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "thinking",
            "action": "plan",
            "enhance": False,
            "confidence": 0.85,
            "lookup_target": "unknown",
            "lookup_filter": None,
            "reasoning": "Complex trip planning",
        })

        result = await router.classify("帮我规划下周去北京的出差行程", user_id="u1")

        assert result.route_type == RouteType.SLOW
        assert result.difficulty == Difficulty.THINKING
        assert result.action == ActionType.PLAN

    @pytest.mark.asyncio
    @patch("src.ai_engine.router.intent_router.redis_client")
    async def test_classify_hybrid_with_enhance(self, mock_redis, router, mock_client):
        mock_redis.exists.return_value = False
        mock_redis.set = AsyncMock()

        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "weather",
            "enhance": True,
            "confidence": 0.9,
            "lookup_target": "unknown",
            "lookup_filter": "北京",
            "reasoning": "Weather query with implicit advice need",
        })

        result = await router.classify("北京天气怎么样", user_id="u1")

        assert result.route_type == RouteType.HYBRID
        assert result.enhance is True
        assert result.intent_category == IntentCategory.WEATHER_WITH_ADVICE

    @pytest.mark.asyncio
    async def test_classify_transact_requires_confirmation(self, router, mock_client):
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "thinking",
            "action": "transact",
            "enhance": False,
            "confidence": 0.92,
            "lookup_target": "unknown",
            "lookup_filter": None,
            "reasoning": "Purchase request",
        })

        result = await router.classify("帮我买一个AirPods Pro", user_id="u1")

        assert result.route_type == RouteType.SLOW
        assert result.requires_confirmation is True
        assert result.action == ActionType.TRANSACT

    @pytest.mark.asyncio
    async def test_classify_api_error_returns_slow_fallback(self, router, mock_client):
        mock_client.messages.create.side_effect = RuntimeError("API down")

        result = await router.classify("你好", user_id="u1")

        assert result.route_type == RouteType.SLOW
        assert result.intent_category == IntentCategory.UNKNOWN
        assert result.confidence == 0.0
        assert result.difficulty == Difficulty.UNSURE

    @pytest.mark.asyncio
    async def test_classify_invalid_json_returns_fallback(self, router, mock_client):
        content_block = MagicMock()
        content_block.text = "not valid json {{"
        response = MagicMock()
        response.content = [content_block]
        mock_client.messages.create.return_value = response

        result = await router.classify("你好", user_id="u1")

        # Should still get a valid result (fallback from JSONDecodeError)
        assert result.route_type in (RouteType.FAST, RouteType.SLOW, RouteType.HYBRID)

    @pytest.mark.asyncio
    async def test_classify_markdown_json_is_handled(self, router, mock_client):
        content_block = MagicMock()
        content_block.text = '```json\n{"difficulty":"immediate","action":"greet","enhance":false,"confidence":0.9,"lookup_target":"unknown","lookup_filter":null,"reasoning":"greeting"}\n```'
        response = MagicMock()
        response.content = [content_block]
        mock_client.messages.create.return_value = response

        result = await router.classify("你好", user_id="u1")

        assert result.difficulty == Difficulty.IMMEDIATE
        assert result.action == ActionType.GREET


# ---------------------------------------------------------------------------
# IntentClassification.to_dict
# ---------------------------------------------------------------------------

class TestIntentClassificationToDict:
    def test_to_dict_contains_all_fields(self):
        c = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.GREETING,
            confidence=0.9,
            difficulty=Difficulty.IMMEDIATE,
            action=ActionType.GREET,
        )
        d = c.to_dict()
        assert d["route_type"] == "fast"
        assert d["intent_category"] == "greeting"
        assert d["confidence"] == 0.9
        assert d["difficulty"] == "immediate"
        assert d["action"] == "greet"
        assert d["enhance"] is False
        assert d["lookup_target"] is None

    def test_to_dict_with_lookup_target(self):
        c = IntentClassification(
            route_type=RouteType.FAST,
            intent_category=IntentCategory.DATA_LOOKUP,
            confidence=0.8,
            action=ActionType.LOOKUP,
            lookup_target=LookupTarget.SCHEDULE,
            lookup_filter="明天",
        )
        d = c.to_dict()
        assert d["lookup_target"] == "schedule"
        assert d["lookup_filter"] == "明天"


# ---------------------------------------------------------------------------
# Unified classifier — single LLM call tests
# ---------------------------------------------------------------------------

class TestUnifiedClassifier:
    """Tests specific to the V8 unified single-call classification."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def router(self, mock_client):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return IntentRouter(client=mock_client, model="test-model")

    def _make_response(self, payload: dict):
        content_block = MagicMock()
        content_block.text = json.dumps(payload, ensure_ascii=False)
        response = MagicMock()
        response.content = [content_block]
        return response

    @pytest.mark.asyncio
    async def test_single_llm_call_only(self, router, mock_client):
        """Verify classify() makes exactly ONE LLM call (no recovery call)."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "lookup",
            "enhance": False,
            "confidence": 0.9,
            "lookup_target": "schedule",
            "lookup_filter": "明天",
            "reasoning": "User checks schedule",
        })

        await router.classify("查看明天的日程", user_id="u1")

        assert mock_client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_single_call_even_with_missing_lookup_target(self, router, mock_client):
        """Even when lookup_target is unknown, no second LLM call is made."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "lookup",
            "enhance": False,
            "confidence": 0.7,
            "lookup_target": "unknown",
            "lookup_filter": None,
            "reasoning": "Ambiguous lookup",
        })

        result = await router.classify("查看一下", user_id="u1")

        assert mock_client.messages.create.call_count == 1
        assert result.action == ActionType.LOOKUP

    @pytest.mark.asyncio
    async def test_unified_returns_all_fields(self, router, mock_client):
        """All fields from unified response are properly extracted."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "weather",
            "enhance": True,
            "confidence": 0.92,
            "lookup_target": "unknown",
            "lookup_filter": "深圳",
            "reasoning": "天气查询带建议",
        })

        # Patch redis for hybrid frequency check
        with patch("src.ai_engine.router.intent_router.redis_client") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=False)
            mock_redis.set = AsyncMock()
            result = await router.classify("深圳天气怎么样", user_id="u1")

        assert result.difficulty == Difficulty.IMMEDIATE
        assert result.action == ActionType.WEATHER
        assert result.enhance is True
        assert result.confidence == 0.92
        assert result.lookup_filter == "深圳"
        assert result.reasoning == "天气查询带建议"

    @pytest.mark.asyncio
    async def test_missing_fields_get_defaults(self, router, mock_client):
        """Partial JSON response fills missing fields with safe defaults."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "greet",
        })

        result = await router.classify("嗨", user_id="u1")

        assert result.difficulty == Difficulty.IMMEDIATE
        assert result.action == ActionType.GREET
        # Low-confidence (0.5 < 0.8) FAST gets upgraded to HYBRID with enhance=True
        assert result.enhance is True
        assert result.confidence == 0.5
        assert result.lookup_filter is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_safe_fallback(self, router, mock_client):
        """Malformed JSON returns safe defaults without crashing."""
        content_block = MagicMock()
        content_block.text = "这不是JSON"
        response = MagicMock()
        response.content = [content_block]
        mock_client.messages.create.return_value = response

        result = await router.classify("你好", user_id="u1")

        # Fallback from JSONDecodeError in _call_unified_classifier
        assert result.difficulty == Difficulty.UNSURE
        assert result.action == ActionType.CHAT
        assert result.confidence == 0.5
        assert result.reasoning == "JSON parse error"

    @pytest.mark.asyncio
    async def test_lookup_filter_normalized_null_string(self, router, mock_client):
        """lookup_filter with 'null' string is normalized to None."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "weather",
            "enhance": False,
            "confidence": 0.8,
            "lookup_target": "unknown",
            "lookup_filter": "null",
            "reasoning": "Weather query",
        })

        result = await router.classify("天气如何", user_id="u1")

        assert result.lookup_filter is None

    @pytest.mark.asyncio
    async def test_context_is_passed_to_unified_prompt(self, router, mock_client):
        """When context is loaded, it is included in the single prompt."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "weather",
            "enhance": False,
            "confidence": 0.9,
            "lookup_target": "unknown",
            "lookup_filter": "南澳",
            "reasoning": "Context-inferred entity",
        })

        # Mock _load_context to simulate conversation context
        with patch.object(router, "_load_context", return_value="用户: 南澳行程怎么安排\n助手: 已为您规划南澳三日游"):
            result = await router.classify("天气怎样", user_id="u1")

        assert result.lookup_filter == "南澳"
        # Verify context was included in the prompt
        call_kwargs = mock_client.messages.create.call_args
        system_prompt = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system", "")
        assert "南澳行程" in system_prompt

    @pytest.mark.asyncio
    async def test_weather_with_context_filter_single_call(self, router, mock_client):
        """Weather query with context-inferred filter uses exactly one call."""
        mock_client.messages.create.return_value = self._make_response({
            "difficulty": "immediate",
            "action": "weather",
            "enhance": False,
            "confidence": 0.85,
            "lookup_target": "unknown",
            "lookup_filter": "北京",
            "reasoning": "Inferred from context",
        })

        with patch.object(router, "_load_context", return_value="用户: 下周去北京出差"):
            result = await router.classify("那边天气如何", user_id="u1")

        assert mock_client.messages.create.call_count == 1
        assert result.lookup_filter == "北京"

    @pytest.mark.asyncio
    async def test_thinking_block_before_text_block(self, router, mock_client):
        """When API returns ThinkingBlock + TextBlock, text is extracted correctly."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        del thinking_block.text  # ThinkingBlock has no .text attribute

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = json.dumps({
            "difficulty": "immediate",
            "action": "greet",
            "enhance": False,
            "confidence": 0.95,
            "lookup_target": "unknown",
            "lookup_filter": None,
            "reasoning": "Greeting",
        })

        response = MagicMock()
        response.content = [thinking_block, text_block]
        mock_client.messages.create.return_value = response

        result = await router.classify("你好", user_id="u1")

        assert result.difficulty == Difficulty.IMMEDIATE
        assert result.action == ActionType.GREET
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_only_thinking_blocks_no_text(self, router, mock_client):
        """When API returns only ThinkingBlock(s) with no TextBlock, fallback gracefully."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        del thinking_block.text

        response = MagicMock()
        response.content = [thinking_block]
        mock_client.messages.create.return_value = response

        result = await router.classify("你好", user_id="u1")

        # Should fall back to SLOW/UNKNOWN since no text could be extracted
        assert result.route_type == RouteType.SLOW
        assert result.confidence == 0.0
