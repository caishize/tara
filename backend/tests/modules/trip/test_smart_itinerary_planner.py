"""
Unit tests for SmartItineraryPlanner service.

Tests cover:
- T048: _analyze_family_constraints()
- T049: _merge_style_configs()
- T050: generate_smart_itinerary() integration
- T051: adjust_itinerary()
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import date, timedelta

from src.modules.trip.services.smart_itinerary_planner import (
    SmartItineraryPlanner,
    ItineraryStyle,
    STYLE_CONFIGS
)


class TestFamilyConstraints:
    """Test _analyze_family_constraints method (T048)."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_db = MagicMock()
        self.mock_llm = MagicMock()
        self.planner = SmartItineraryPlanner(self.mock_db, self.mock_llm)

    def test_empty_family_returns_defaults(self):
        """Empty family should return default constraints."""
        result = self.planner._analyze_family_constraints({})

        assert result["has_children"] is False
        assert result["has_toddlers"] is False
        assert result["has_elderly"] is False
        assert result["needs_nap_time"] is False
        assert result["max_walking_km"] == 15
        assert result["activity_hours"] == 10

    def test_toddler_triggers_strict_constraints(self):
        """Toddler (0-3 years) should trigger strictest constraints."""
        family = {
            "children": [{"age": 2, "name": "小宝"}]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["has_children"] is True
        assert result["has_toddlers"] is True
        assert result["needs_nap_time"] is True
        assert result["max_walking_km"] == 5
        assert result["activity_hours"] == 6

    def test_young_child_triggers_moderate_constraints(self):
        """Young child (4-6 years) should trigger moderate constraints."""
        family = {
            "children": [{"age": 5, "name": "小明"}]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["has_children"] is True
        assert result["has_young_children"] is True
        assert result["needs_nap_time"] is True
        assert result["max_walking_km"] == 8
        assert result["activity_hours"] == 7

    def test_older_child_minimal_constraints(self):
        """Older child (7+) should have minimal constraints."""
        family = {
            "children": [{"age": 10, "name": "小红"}]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["has_children"] is True
        assert result["has_toddlers"] is False
        assert result["has_young_children"] is False
        assert result["needs_nap_time"] is False
        assert result["max_walking_km"] == 15  # Default

    def test_elderly_70plus_strict_constraints(self):
        """Elderly 70+ should have strict constraints."""
        family = {
            "elderly": [{"age": 75, "name": "爷爷"}]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["has_elderly"] is True
        assert result["max_walking_km"] == 6
        assert result["activity_hours"] == 6

    def test_elderly_65to70_moderate_constraints(self):
        """Elderly 65-70 should have moderate constraints."""
        family = {
            "elderly": [{"age": 67, "name": "奶奶"}]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["has_elderly"] is True
        assert result["max_walking_km"] == 8
        assert result["activity_hours"] == 7

    def test_mixed_family_uses_strictest_constraints(self):
        """Mixed family should use strictest constraints from all members."""
        family = {
            "children": [{"age": 3, "name": "小宝"}, {"age": 10, "name": "大宝"}],
            "elderly": [{"age": 72, "name": "爷爷"}]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["has_children"] is True
        assert result["has_toddlers"] is True
        assert result["has_elderly"] is True
        assert result["needs_nap_time"] is True
        # Should use minimum of all constraints
        assert result["max_walking_km"] == 5  # From toddler
        assert result["activity_hours"] == 6  # From both toddler and elderly 70+

    def test_special_needs_preserved(self):
        """Special needs should be preserved in constraints."""
        family = {
            "special_needs": ["wheelchair", "vegetarian"]
        }

        result = self.planner._analyze_family_constraints(family)

        assert result["special_needs"] == ["wheelchair", "vegetarian"]


class TestStyleConfigs:
    """Test _merge_style_configs method (T049)."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_db = MagicMock()
        self.mock_llm = MagicMock()
        self.planner = SmartItineraryPlanner(self.mock_db, self.mock_llm)

    def test_single_style_returns_primary(self):
        """Single style should return that style as primary."""
        styles = [ItineraryStyle.RELAXED]

        result = self.planner._merge_style_configs(styles)

        assert result["primary_style"] == "relaxed"
        assert result["style_names"] == ["轻松型"]
        assert result["description"] == "轻松型"

    def test_empty_styles_defaults_to_relaxed(self):
        """Empty styles should default to relaxed."""
        result = self.planner._merge_style_configs([])

        assert result["primary_style"] == "relaxed"

    def test_multiple_styles_merged(self):
        """Multiple styles should be merged."""
        styles = [ItineraryStyle.RELAXED, ItineraryStyle.CULTURAL]

        result = self.planner._merge_style_configs(styles)

        assert result["primary_style"] == "relaxed"
        assert "轻松型" in result["style_names"]
        assert "文化型" in result["style_names"]
        assert "轻松型" in result["description"]
        assert "文化型" in result["description"]

    def test_constraints_merged_and_deduplicated(self):
        """Constraints from all styles should be merged and deduplicated."""
        styles = [ItineraryStyle.BUDGET, ItineraryStyle.CULTURAL]

        result = self.planner._merge_style_configs(styles)

        # Should contain constraints from both styles
        assert len(result["constraints"]) > 0
        # Should be deduplicated
        assert len(result["constraints"]) == len(set(result["constraints"]))

    def test_time_uses_most_relaxed_schedule(self):
        """Wake/end times should use the most relaxed schedule."""
        styles = [ItineraryStyle.INTENSIVE, ItineraryStyle.RELAXED]

        result = self.planner._merge_style_configs(styles)

        # Should use latest wake time (relaxed: 09:00 vs intensive: 07:30)
        assert result["wake_time"] == "09:00"
        # Should use earliest end time (relaxed: 19:00 vs intensive: 21:00)
        assert result["end_time"] == "19:00"

    def test_three_styles_all_included(self):
        """Three styles should all be included."""
        styles = [ItineraryStyle.RELAXED, ItineraryStyle.BUDGET, ItineraryStyle.CULTURAL]

        result = self.planner._merge_style_configs(styles)

        assert len(result["style_names"]) == 3
        assert "轻松型" in result["style_names"]
        assert "经济型" in result["style_names"]
        assert "文化型" in result["style_names"]


class TestStyleConfigsIntegrity:
    """Test that STYLE_CONFIGS has all required fields."""

    def test_all_styles_have_required_fields(self):
        """All styles should have all required configuration fields."""
        required_fields = ["name", "daily_attractions", "pace", "wake_time", "end_time", "constraints", "description"]

        for style in ItineraryStyle:
            config = STYLE_CONFIGS.get(style)
            assert config is not None, f"Missing config for {style}"

            for field in required_fields:
                assert field in config, f"Missing field '{field}' in {style} config"

    def test_all_six_styles_exist(self):
        """All six styles should be defined."""
        expected_styles = {
            ItineraryStyle.INTENSIVE,
            ItineraryStyle.RELAXED,
            ItineraryStyle.BUDGET,
            ItineraryStyle.LUXURY,
            ItineraryStyle.ADVENTURE,
            ItineraryStyle.CULTURAL
        }

        assert set(STYLE_CONFIGS.keys()) == expected_styles


class TestGenerateSmartItinerary:
    """Test generate_smart_itinerary method (T050)."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_db = AsyncMock()
        self.mock_llm = AsyncMock()
        self.planner = SmartItineraryPlanner(self.mock_db, self.mock_llm)

    @pytest.mark.asyncio
    async def test_generate_returns_structured_response(self):
        """Generate should return properly structured response."""
        # Mock LLM to return valid JSON
        valid_response = '''
        {
            "trip_design_rationale": {
                "planning_philosophy": "Test philosophy",
                "route_logic": "Test route",
                "highlights": ["Test highlight"],
                "backup_plans": [{"scenario": "下雨", "alternative": "室内活动"}],
                "local_tips": ["Test tip"]
            },
            "budget_allocation": {
                "transportation": {"amount": 500, "percentage": 20},
                "accommodation": {"amount": 900, "percentage": 35},
                "food": {"amount": 600, "percentage": 25},
                "tickets": {"amount": 400, "percentage": 15},
                "other": {"amount": 100, "percentage": 5},
                "total": 2500
            },
            "daily_schedules": [
                {
                    "day": 1,
                    "date_label": "第1天",
                    "theme": "探索之旅",
                    "summary": "精彩的一天",
                    "activities": [
                        {
                            "time": "09:00",
                            "duration_minutes": 120,
                            "activity_type": "attraction",
                            "title": "测试景点",
                            "location": "测试地点",
                            "description": "测试描述",
                            "estimated_cost": 50,
                            "professional_advice": {
                                "why_chosen": "因为很棒",
                                "best_experience": "上午去",
                                "time_tips": "2小时",
                                "cost_tips": "网上买票",
                                "warnings": ["人多"]
                            },
                            "alternatives": []
                        }
                    ],
                    "day_summary": {
                        "total_cost": 50,
                        "walking_distance_km": 5,
                        "activity_count": 1,
                        "energy_level": "轻松"
                    }
                }
            ]
        }
        '''
        self.mock_llm.generate_text = AsyncMock(return_value=valid_response)

        # Mock database operations
        self.mock_db.execute = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()

        result = await self.planner.generate_smart_itinerary(
            trip_id=uuid4(),
            destination="杭州",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            styles=[ItineraryStyle.RELAXED],
            family_composition={},
            budget=5000
        )

        # Verify structure
        assert "trip_id" in result
        assert "destination" in result
        assert "duration_days" in result
        assert "styles" in result
        assert "trip_design_rationale" in result
        assert "budget_allocation" in result
        assert "daily_schedules" in result

        # Verify content
        assert result["destination"] == "杭州"
        assert result["duration_days"] == 4
        assert len(result["daily_schedules"]) >= 1

    @pytest.mark.asyncio
    async def test_generate_handles_llm_failure(self):
        """Generate should raise RuntimeError on LLM failure (no mock fallback)."""
        # Mock LLM to raise exception
        self.mock_llm.generate_text = AsyncMock(side_effect=Exception("LLM error"))

        # Mock database operations
        self.mock_db.execute = AsyncMock()

        with pytest.raises(RuntimeError, match="智能行程生成失败"):
            await self.planner.generate_smart_itinerary(
                trip_id=uuid4(),
                destination="杭州",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=2),
                styles=[ItineraryStyle.RELAXED],
                family_composition={},
                budget=None
            )

    @pytest.mark.asyncio
    async def test_generate_parses_malformed_json(self):
        """Generate should raise RuntimeError on malformed LLM JSON (no mock fallback)."""
        # Mock LLM to return invalid JSON
        self.mock_llm.generate_text = AsyncMock(return_value="This is not JSON")

        # Mock database operations
        self.mock_db.execute = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()

        with pytest.raises(RuntimeError, match="智能行程生成失败"):
            await self.planner.generate_smart_itinerary(
                trip_id=uuid4(),
                destination="杭州",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=1),
                styles=[ItineraryStyle.RELAXED],
                family_composition={},
                budget=None
            )


class TestAdjustItinerary:
    """Test adjust_itinerary method (T051)."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_db = AsyncMock()
        self.mock_llm = AsyncMock()
        self.planner = SmartItineraryPlanner(self.mock_db, self.mock_llm)

    @pytest.mark.asyncio
    async def test_adjust_returns_suggestions(self):
        """Adjust should return structured suggestions."""
        # Mock existing itinerary query
        mock_itinerary = MagicMock()
        mock_itinerary.day_number = 1
        mock_itinerary.schedule = [{"time": "09:00", "title": "西湖"}]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_itinerary]
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock LLM response
        adjustment_response = '''
        {
            "understanding": "您想轻松一点",
            "suggestions": [
                {
                    "option": "轻松调整",
                    "description": "减少活动",
                    "changes": ["取消下午景点"],
                    "impact": "可以明天补"
                }
            ],
            "recommended": "轻松调整",
            "reason": "适合带孩子"
        }
        '''
        self.mock_llm.generate_text = AsyncMock(return_value=adjustment_response)

        result = await self.planner.adjust_itinerary(
            trip_id=uuid4(),
            adjustment_request="今天想轻松一点",
            current_day=1
        )

        assert "understanding" in result
        assert "suggestions" in result
        assert "recommended" in result
        assert len(result["suggestions"]) >= 1

    @pytest.mark.asyncio
    async def test_adjust_handles_no_itinerary(self):
        """Adjust should return error when no itinerary exists."""
        # Mock empty query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        result = await self.planner.adjust_itinerary(
            trip_id=uuid4(),
            adjustment_request="今天想轻松一点",
            current_day=1
        )

        assert "error" in result
        assert result["error"] == "未找到行程数据"

    @pytest.mark.asyncio
    async def test_adjust_handles_llm_failure(self):
        """Adjust should raise RuntimeError on LLM failure."""
        # Mock existing itinerary
        mock_itinerary = MagicMock()
        mock_itinerary.day_number = 1
        mock_itinerary.schedule = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_itinerary]
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock LLM failure
        self.mock_llm.generate_text = AsyncMock(side_effect=Exception("LLM error"))

        with pytest.raises(RuntimeError, match="行程调整失败"):
            await self.planner.adjust_itinerary(
                trip_id=uuid4(),
                adjustment_request="今天想轻松一点",
                current_day=1
            )


class TestPromptBuilding:
    """Test _build_smart_prompt method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_db = MagicMock()
        self.mock_llm = MagicMock()
        self.planner = SmartItineraryPlanner(self.mock_db, self.mock_llm)

    def test_prompt_includes_destination(self):
        """Prompt should include destination."""
        style_config = self.planner._merge_style_configs([ItineraryStyle.RELAXED])
        family_constraints = self.planner._analyze_family_constraints({})

        prompt = self.planner._build_smart_prompt(
            destination="杭州",
            duration_days=4,
            style_config=style_config,
            family_constraints=family_constraints,
            budget=5000,
            preferences=None
        )

        assert "杭州" in prompt
        assert "4天" in prompt or "4" in prompt

    def test_prompt_includes_budget(self):
        """Prompt should include budget when provided."""
        style_config = self.planner._merge_style_configs([ItineraryStyle.RELAXED])
        family_constraints = self.planner._analyze_family_constraints({})

        prompt = self.planner._build_smart_prompt(
            destination="杭州",
            duration_days=4,
            style_config=style_config,
            family_constraints=family_constraints,
            budget=5000,
            preferences=None
        )

        assert "5000" in prompt

    def test_prompt_includes_family_constraints(self):
        """Prompt should include family constraints when present."""
        style_config = self.planner._merge_style_configs([ItineraryStyle.RELAXED])
        family_constraints = self.planner._analyze_family_constraints({
            "children": [{"age": 4}],
            "elderly": [{"age": 70}]
        })

        prompt = self.planner._build_smart_prompt(
            destination="杭州",
            duration_days=4,
            style_config=style_config,
            family_constraints=family_constraints,
            budget=None,
            preferences=None
        )

        # Should mention child and elderly constraints
        assert "儿童" in prompt or "小孩" in prompt or "4-6岁" in prompt
        assert "老人" in prompt or "65岁" in prompt

    def test_prompt_requests_json_output(self):
        """Prompt should request JSON output format."""
        style_config = self.planner._merge_style_configs([ItineraryStyle.RELAXED])
        family_constraints = self.planner._analyze_family_constraints({})

        prompt = self.planner._build_smart_prompt(
            destination="杭州",
            duration_days=4,
            style_config=style_config,
            family_constraints=family_constraints,
            budget=None,
            preferences=None
        )

        assert "JSON" in prompt or "json" in prompt
