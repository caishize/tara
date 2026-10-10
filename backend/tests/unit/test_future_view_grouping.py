"""Tests for Future View suggestion grouping (group_key computation)."""
import pytest
from src.modules.views.services.kanban_service import KanbanService
from src.modules.views.kanban_schemas import InsightFeedItem


class TestSuggestionGroupKey:
    """Test _suggestion_group_key static method."""

    def test_group_key_event_based(self):
        """event_id in action_data -> 'event:{id}'"""
        item = InsightFeedItem(
            id="ins-1", title="准备会议", content="", insight_type="event_preparation",
            action_data={"event_id": "evt-123"},
        )
        assert KanbanService._suggestion_group_key(item) == "event:evt-123"

    def test_group_key_person_based(self):
        """person in action_data -> 'person:{name_lower}:{type}'"""
        item = InsightFeedItem(
            id="ins-2", title="Grace生日", content="", insight_type="relationship_maintenance",
            action_data={"person": "Grace"},
        )
        assert KanbanService._suggestion_group_key(item) == "person:grace:relationship_maintenance"

    def test_group_key_trip_based(self):
        """location+date in action_data -> 'trip:{loc}:{date}:{type}'"""
        item = InsightFeedItem(
            id="ins-3", title="清明节出行", content="", insight_type="event_preparation",
            action_data={"location": "杭州", "trip_start_date": "2026-04-04"},
        )
        assert KanbanService._suggestion_group_key(item) == "trip:杭州:2026-04-04:event_preparation"

    def test_group_key_title_fallback(self):
        """No action_data entity -> title-based grouping."""
        item = InsightFeedItem(
            id="ins-4", title="一般建议", content="", insight_type="observation",
        )
        assert KanbanService._suggestion_group_key(item) == "title:一般建议:observation"

    def test_group_key_empty_title_fallback(self):
        """No action_data entity and empty title -> 'id:{insight_id}'."""
        item = InsightFeedItem(
            id="ins-4b", title="", content="", insight_type="observation",
        )
        assert KanbanService._suggestion_group_key(item) == "id:ins-4b"

    def test_group_key_same_person_same_key(self):
        """Two insights about the same person get the same group_key."""
        item_a = InsightFeedItem(
            id="ins-5a", title="给Grace打电话", content="", insight_type="relationship_maintenance",
            action_data={"person": "Grace"},
        )
        item_b = InsightFeedItem(
            id="ins-5b", title="Grace的生日礼物", content="", insight_type="relationship_maintenance",
            action_data={"person": "grace"},  # lowercase
        )
        assert KanbanService._suggestion_group_key(item_a) == KanbanService._suggestion_group_key(item_b)

    def test_group_key_none_action_data(self):
        """action_data is None -> title-based fallback."""
        item = InsightFeedItem(
            id="ins-6", title="无数据", content="", insight_type="observation",
            action_data=None,
        )
        assert KanbanService._suggestion_group_key(item) == "title:无数据:observation"

    def test_group_key_empty_action_data(self):
        """action_data is empty dict -> title-based fallback."""
        item = InsightFeedItem(
            id="ins-7", title="空数据", content="", insight_type="observation",
            action_data={},
        )
        assert KanbanService._suggestion_group_key(item) == "title:空数据:observation"

    def test_group_key_whitespace_person(self):
        """Whitespace-only person -> title-based fallback."""
        item = InsightFeedItem(
            id="ins-8", title="空人名", content="", insight_type="relationship_maintenance",
            action_data={"person": "  "},
        )
        assert KanbanService._suggestion_group_key(item) == "title:空人名:relationship_maintenance"

    def test_group_key_trip_with_date_field(self):
        """Falls back to 'date' field if 'trip_start_date' missing."""
        item = InsightFeedItem(
            id="ins-9", title="出行", content="", insight_type="event_preparation",
            action_data={"location": "北京", "date": "2026-05-01"},
        )
        assert KanbanService._suggestion_group_key(item) == "trip:北京:2026-05-01:event_preparation"

    def test_group_key_person_case_insensitive(self):
        """Person names are case-insensitive for grouping."""
        item_upper = InsightFeedItem(
            id="ins-10a", title="联系张伟", content="", insight_type="followup",
            action_data={"person": "ZHANG Wei"},
        )
        item_lower = InsightFeedItem(
            id="ins-10b", title="联系张伟2", content="", insight_type="followup",
            action_data={"person": "zhang wei"},
        )
        assert KanbanService._suggestion_group_key(item_upper) == KanbanService._suggestion_group_key(item_lower)


    def test_group_key_same_title_same_key(self):
        """DB insights with same title+type should group together."""
        item_a = InsightFeedItem(
            id="ins-a", title="Grace生日快到了", content="内容A",
            insight_type="memory", action_data=None,
        )
        item_b = InsightFeedItem(
            id="ins-b", title="Grace生日快到了", content="内容B",
            insight_type="memory", action_data=None,
        )
        key_a = KanbanService._suggestion_group_key(item_a)
        key_b = KanbanService._suggestion_group_key(item_b)
        assert key_a == key_b
        assert key_a == "title:grace生日快到了:memory"

    def test_group_key_different_title_different_key(self):
        """Different titles should NOT group even with same type."""
        item_a = InsightFeedItem(
            id="ins-c", title="Grace生日快到了", content="",
            insight_type="memory", action_data=None,
        )
        item_b = InsightFeedItem(
            id="ins-d", title="老张的人情要还", content="",
            insight_type="memory", action_data=None,
        )
        assert KanbanService._suggestion_group_key(item_a) != KanbanService._suggestion_group_key(item_b)

    def test_group_key_person_name_matching(self):
        """Different titles mentioning same person should group via member_names."""
        member_names = ["Grace", "老张"]
        item_a = InsightFeedItem(
            id="ins-e", title="Grace生日快到了", content="",
            insight_type="memory", action_data=None,
        )
        item_b = InsightFeedItem(
            id="ins-f", title="春分后要准备生日", content="Grace的生日是4月3日",
            insight_type="time", action_data=None,
        )
        key_a = KanbanService._suggestion_group_key(item_a, member_names)
        key_b = KanbanService._suggestion_group_key(item_b, member_names)
        assert key_a == key_b
        assert key_a == "person_name:grace"

    def test_group_key_different_persons_different_key(self):
        """Insights about different people should NOT group."""
        member_names = ["Grace", "老张"]
        item_a = InsightFeedItem(
            id="ins-g", title="Grace生日快到了", content="",
            insight_type="memory", action_data=None,
        )
        item_b = InsightFeedItem(
            id="ins-h", title="老张人情要还", content="",
            insight_type="favor", action_data=None,
        )
        key_a = KanbanService._suggestion_group_key(item_a, member_names)
        key_b = KanbanService._suggestion_group_key(item_b, member_names)
        assert key_a != key_b
        assert key_a == "person_name:grace"
        assert key_b == "person_name:老张"

    def test_group_key_no_member_names_fallback_to_title(self):
        """Without member_names, falls back to title-based grouping."""
        item = InsightFeedItem(
            id="ins-i", title="Grace生日快到了", content="",
            insight_type="memory", action_data=None,
        )
        key = KanbanService._suggestion_group_key(item, member_names=None)
        assert key == "title:grace生日快到了:memory"


class TestGroupLabelAssignment:
    """Test that group_label is set to first suggestion's title per group."""

    def test_group_label_set_to_first_title(self):
        """group_label should equal the title of the first suggestion with same group_key."""
        suggestions = [
            {"group_key": "person:grace:relationship_maintenance", "title": "Grace生日快到了", "group_label": ""},
            {"group_key": "person:grace:relationship_maintenance", "title": "给Grace准备礼物", "group_label": ""},
            {"group_key": "id:ins-99", "title": "一般建议", "group_label": ""},
        ]
        KanbanService._assign_group_labels(suggestions)
        assert suggestions[0]["group_label"] == "Grace生日快到了"
        assert suggestions[1]["group_label"] == "Grace生日快到了"
        assert suggestions[2]["group_label"] == "一般建议"
