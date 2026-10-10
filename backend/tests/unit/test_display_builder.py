"""Unit tests for the unified PendingAction display_data builder."""

import pytest

from src.modules.conversation.display_builder import (
    ACTION_DISPLAY_TITLES,
    build_display_data,
)


class TestBuildDisplayDataStructure:
    """Every call must return title + description + details."""

    def test_output_keys(self):
        result = build_display_data("purchase", {"item_name": "花"})
        assert set(result.keys()) == {"title", "description", "details"}

    def test_unknown_action_type_falls_back(self):
        result = build_display_data("unknown_action", {})
        assert result["title"] == "确认操作"
        assert result["details"] == []

    def test_description_defaults_to_empty(self):
        result = build_display_data("purchase", {"item_name": "花"})
        assert result["description"] == ""

    def test_description_falls_back_to_reason(self):
        result = build_display_data("purchase", {"item_name": "花", "reason": "生日"})
        assert result["description"] == "生日"

    def test_explicit_description_overrides_reason(self):
        result = build_display_data(
            "purchase",
            {"item_name": "花", "reason": "生日"},
            description="特别的",
        )
        assert result["description"] == "特别的"


class TestAllActionTypesHaveTitles:
    """Every ActionType enum value should have a display title."""

    @pytest.mark.parametrize("action_type", [
        "purchase", "book_ticket", "transfer_money", "cancel_booking",
        "delete_event", "send_message", "create_event", "reschedule_event",
        "suggest_meeting", "suggest_greeting", "suggest_gift", "suggest_defer",
    ])
    def test_action_type_has_title(self, action_type):
        assert action_type in ACTION_DISPLAY_TITLES


class TestPurchaseDetails:
    def test_basic(self):
        result = build_display_data("purchase", {
            "item_name": "鲜花",
            "quantity": 2,
            "price": 99,
        })
        assert result["title"] == "确认购买"
        labels = [d["label"] for d in result["details"]]
        assert labels == ["商品", "数量", "价格"]
        assert result["details"][0]["value"] == "鲜花"
        assert result["details"][1]["value"] == "2"
        assert result["details"][2]["value"] == "¥99"

    def test_defaults(self):
        result = build_display_data("purchase", {})
        assert result["details"][0]["value"] == "未知"


class TestBookTicketDetails:
    def test_basic(self):
        result = build_display_data("book_ticket", {
            "from": "北京",
            "to": "上海",
            "date": "2026-04-01",
        })
        assert result["title"] == "确认预订"
        assert len(result["details"]) == 3


class TestTransferMoneyDetails:
    def test_with_note(self):
        result = build_display_data("transfer_money", {
            "recipient": "张三",
            "amount": 500,
            "note": "生日快乐",
        })
        assert len(result["details"]) == 3
        assert result["details"][2]["value"] == "生日快乐"

    def test_without_note(self):
        result = build_display_data("transfer_money", {
            "recipient": "张三",
            "amount": 500,
        })
        assert len(result["details"]) == 2


class TestRescheduleEventDetails:
    def test_agent_pattern(self):
        """Agent path: event_name + new_start."""
        result = build_display_data("reschedule_event", {
            "event_name": "团建",
            "new_start": "2026-04-05 10:00",
            "reason": "天气不好",
        })
        assert result["title"] == "确认调整日程"
        assert result["description"] == "天气不好"
        labels = [d["label"] for d in result["details"]]
        assert "事件" in labels
        assert "新时间" in labels

    def test_cascade_pattern(self):
        """Cascade path: event_title + impact_type + detail."""
        result = build_display_data(
            "reschedule_event",
            {
                "event_title": "午餐会",
                "impact_type": "time_conflict",
                "detail": "与新时间冲突",
            },
            description="日程级联影响 - 午餐会",
        )
        labels = [d["label"] for d in result["details"]]
        assert "影响事件" in labels
        assert "影响类型" in labels
        assert "详情" in labels

    def test_new_end_optional(self):
        result = build_display_data("reschedule_event", {
            "event_name": "会议",
            "new_start": "10:00",
            "new_end": "11:00",
        })
        labels = [d["label"] for d in result["details"]]
        assert "结束时间" in labels


class TestSuggestSocialDetails:
    @pytest.mark.parametrize("action_type", [
        "suggest_meeting", "suggest_greeting", "suggest_gift",
    ])
    def test_full_context(self, action_type):
        result = build_display_data(action_type, {
            "member_name": "岳母",
            "trip_label": "三亚旅行",
            "date_range": "03月10日~03月15日",
            "location": "三亚",
            "draft_content": "路过的时候去看看",
        })
        labels = [d["label"] for d in result["details"]]
        assert "联系人" in labels
        assert "关联行程" in labels
        assert "出行时间" in labels
        assert "目的地" in labels
        assert "建议消息" in labels

    def test_minimal_context(self, ):
        result = build_display_data("suggest_meeting", {})
        assert result["title"] == "建议会面"
        assert result["details"] == []

    def test_occasion_field(self):
        """trigger_dispatcher passes occasion instead of trip_label."""
        result = build_display_data("suggest_meeting", {
            "trip_label": "厦门出差",
            "occasion": "顺路看望张阿姨",
        })
        labels = [d["label"] for d in result["details"]]
        assert "场合" in labels

    def test_reason_field(self):
        """association_service passes reason for insight context."""
        result = build_display_data("suggest_greeting", {
            "member_name": "张阿姨",
            "reason": "即将过生日",
        })
        labels = [d["label"] for d in result["details"]]
        assert "洞察原因" in labels
        values = {d["label"]: d["value"] for d in result["details"]}
        assert values["洞察原因"] == "即将过生日"


class TestSuggestDeferDetails:
    def test_basic(self):
        result = build_display_data(
            "suggest_defer",
            {
                "event_title": "健身课",
                "suggested_date_display": "03月20日",
            },
            description="今天日程太满",
        )
        assert result["title"] == "建议推迟"
        assert result["description"] == "今天日程太满"
        labels = [d["label"] for d in result["details"]]
        assert "事件" in labels
        assert "建议日期" in labels
        assert result["details"][0]["value"] == "健身课"
        assert result["details"][1]["value"] == "03月20日"


class TestSendMessageDetails:
    def test_content_truncation(self):
        long_content = "A" * 200
        result = build_display_data("send_message", {
            "recipient": "李四",
            "content": long_content,
        })
        assert len(result["details"][1]["value"]) == 80

    def test_external_variant(self):
        result = build_display_data("send_message_external", {
            "recipient": "外部联系人",
            "content": "hello",
        })
        assert result["title"] == "确认发送消息"


class TestDeleteEventDetails:
    def test_with_date(self):
        result = build_display_data("delete_event", {
            "event_name": "周会",
            "event_date": "2026-04-01",
        })
        assert len(result["details"]) == 2

    def test_title_fallback(self):
        result = build_display_data("delete_event", {"title": "周会"})
        assert result["details"][0]["value"] == "周会"


class TestCreateEventDetails:
    def test_with_location(self):
        result = build_display_data("create_event", {
            "title": "生日派对",
            "start": "2026-04-01 18:00",
            "location": "家里",
        })
        assert len(result["details"]) == 3

    def test_calendar_event_variant(self):
        result = build_display_data("create_calendar_event", {
            "title": "会议",
            "start_time": "09:00",
        })
        assert result["title"] == "确认创建日程"
        assert result["details"][1]["value"] == "09:00"


class TestCancelBookingDetails:
    def test_with_reason(self):
        result = build_display_data(
            "cancel_booking",
            {"booking_name": "万豪酒店"},
            description="行程变更",
        )
        assert result["details"][0]["value"] == "万豪酒店"
        assert result["description"] == "行程变更"


class TestImmutability:
    """Builder must not mutate input context."""

    def test_context_not_mutated(self):
        ctx = {"item_name": "花", "quantity": 1, "price": 50}
        original = dict(ctx)
        build_display_data("purchase", ctx)
        assert ctx == original
