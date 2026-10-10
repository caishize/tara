"""Tests for timeline life-secretary presentation helpers.

Covers: _generate_day_summary, _find_focus_event, DayTheme propagation,
        _pick_highlight_event, _build_life_context_hint

Note: _compute_day_mood was deleted in favour of consuming DayTheme from
SecretaryOrchestrator (single source of truth).  See test_day_theme_propagation.
"""
from datetime import date, datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

from src.modules.curation.services.orchestrator import DayTheme
from src.modules.views.kanban_schemas import TimelineEventItem
from src.modules.views.services.timeline_service import TimelineService


def _make_event(
    *,
    id: str = "1",
    title: str = "Test Event",
    event_type: str = "other",
    start_time: datetime = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
    status: str = "pending",
    priority: str = "normal",
    location: Optional[str] = None,
    visibility_tier: str = "standard",
    trip_label: Optional[str] = None,
    trip_id: Optional[str] = None,
) -> TimelineEventItem:
    return TimelineEventItem(
        id=id,
        title=title,
        event_type=event_type,
        start_time=start_time,
        status=status,
        priority=priority,
        location=location,
        visibility_tier=visibility_tier,
        trip_label=trip_label,
        trip_id=trip_id,
    )


# -- Helper: mock CuratedEvent for _group_by_date ---------------------------


def _make_mock_curated_event(
    *,
    id: str = "1",
    title: str = "Test Event",
    event_type: str = "other",
    normalized_start: datetime = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
    normalized_end=None,
    status: str = "pending",
    priority: str = "normal",
    location=None,
    notes=None,
    trip_id=None,
    visibility_tier: str = "standard",
    life_context_hint=None,
    trip_label=None,
):
    """Build a mock CuratedEvent suitable for _group_by_date."""
    ev = MagicMock()
    ev.id = id
    ev.title = title
    ev.event_type = event_type
    ev.normalized_start = normalized_start
    ev.normalized_end = normalized_end
    ev.status = status
    ev.priority = priority
    ev.location = location
    ev.notes = notes
    ev.trip_id = trip_id
    ev.visibility_tier = visibility_tier
    ev.life_context_hint = life_context_hint
    ev.get_trip_label = MagicMock(return_value=trip_label)
    return ev


# ── DayTheme propagation (replaces _compute_day_mood) ──────────────


class TestDayThemePropagation:
    """Verify that DayTheme from the orchestrator flows into day_mood."""

    def setup_method(self):
        self.service = TimelineService(None)

    def test_day_theme_title_becomes_day_mood(self):
        """When a DayTheme is provided, its title is used as day_mood."""
        theme = DayTheme(
            title="丽江之旅",
            primary_event_id=None,
            focus="今天的重点：去丽江",
        )
        groups = self.service._group_by_date(
            events=[_make_mock_curated_event(
                id="1", title="去丽江", event_type="trip",
            )],
            today=date(2026, 3, 1),
            direction="future",
            day_themes={date(2026, 3, 1): theme},
        )
        assert len(groups) == 1
        assert groups[0].day_mood == "丽江之旅"

    def test_no_theme_gives_none_mood(self):
        """Without a DayTheme, day_mood is None."""
        groups = self.service._group_by_date(
            events=[_make_mock_curated_event(
                id="2", title="写报告", event_type="task",
                normalized_start=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
            )],
            today=date(2026, 3, 2),
            direction="future",
            day_themes={},
        )
        assert len(groups) == 1
        assert groups[0].day_mood is None

    def test_multiple_days_with_mixed_themes(self):
        """Only dates with a theme get a day_mood; others stay None."""
        theme_march1 = DayTheme(
            title="出行日",
            primary_event_id=None,
            focus="今天出发",
        )
        groups = self.service._group_by_date(
            events=[
                _make_mock_curated_event(
                    id="1", title="出发",
                    normalized_start=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
                ),
                _make_mock_curated_event(
                    id="2", title="开会",
                    normalized_start=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
                ),
            ],
            today=date(2026, 3, 1),
            direction="future",
            day_themes={date(2026, 3, 1): theme_march1},
        )
        assert len(groups) == 2
        march1_group = next(g for g in groups if g.date == date(2026, 3, 1))
        march2_group = next(g for g in groups if g.date == date(2026, 3, 2))
        assert march1_group.day_mood == "出行日"
        assert march2_group.day_mood is None

    def test_compute_day_mood_removed(self):
        """_compute_day_mood method no longer exists on TimelineService."""
        assert not hasattr(TimelineService, "_compute_day_mood")

    def test_day_theme_flows_into_summary(self):
        """DayTheme.title used as day_mood is included in day summary."""
        theme = DayTheme(
            title="忙碌的一天",
            primary_event_id=None,
            focus="今天事情比较多",
        )
        groups = self.service._group_by_date(
            events=[
                _make_mock_curated_event(id=str(i), title=f"事{i}")
                for i in range(5)
            ],
            today=date(2026, 3, 1),
            direction="future",
            day_themes={date(2026, 3, 1): theme},
        )
        assert len(groups) == 1
        assert "忙碌的一天" in groups[0].summary


# ── _find_focus_event ─────────────────────────────────────────────


class TestFindFocusEvent:
    def test_special_occasion_takes_precedence(self):
        events = [
            _make_event(id="1", event_type="task", title="普通"),
            _make_event(id="2", event_type="birthday", title="生日"),
        ]
        result = TimelineService._find_focus_event(events)
        assert result is not None
        assert result.id == "2"

    def test_focus_tier_before_travel(self):
        events = [
            _make_event(id="1", event_type="trip", title="出差"),
            _make_event(
                id="2", event_type="task", title="重要会议",
                visibility_tier="focus",
            ),
        ]
        result = TimelineService._find_focus_event(events)
        assert result is not None
        assert result.id == "2"

    def test_travel_before_high_priority(self):
        events = [
            _make_event(id="1", event_type="task", title="重要", priority="high"),
            _make_event(id="2", event_type="travel", title="去北京"),
        ]
        result = TimelineService._find_focus_event(events)
        assert result is not None
        assert result.id == "2"

    def test_high_priority_before_default(self):
        events = [
            _make_event(id="1", event_type="task", title="普通"),
            _make_event(id="2", event_type="task", title="紧急", priority="high"),
        ]
        result = TimelineService._find_focus_event(events)
        assert result is not None
        assert result.id == "2"

    def test_defaults_to_first_event(self):
        events = [
            _make_event(id="1", event_type="task", title="第一个"),
            _make_event(id="2", event_type="task", title="第二个"),
        ]
        result = TimelineService._find_focus_event(events)
        assert result is not None
        assert result.id == "1"

    def test_empty_returns_none(self):
        result = TimelineService._find_focus_event([])
        assert result is None


# ── _generate_day_summary ────────────────────────────────────────


class TestGenerateDaySummary:
    def setup_method(self):
        self.service = TimelineService(None)

    def test_empty_events(self):
        result = self.service._generate_day_summary([])
        assert result == ""

    def test_single_event_title(self):
        events = [_make_event(title="团队午餐")]
        result = self.service._generate_day_summary(events)
        assert result == "团队午餐"

    def test_single_event_with_location(self):
        events = [_make_event(title="体检", location="协和医院")]
        result = self.service._generate_day_summary(events)
        assert result == "体检，在协和医院"

    def test_single_completed_event(self):
        events = [_make_event(title="买菜", status="completed")]
        result = self.service._generate_day_summary(events)
        assert result == "买菜，已完成"

    def test_special_event_anchors_summary(self):
        events = [
            _make_event(id="1", event_type="birthday", title="妈妈生日"),
            _make_event(id="2", event_type="task", title="买蛋糕"),
        ]
        result = self.service._generate_day_summary(events)
        assert "妈妈生日" in result
        assert "1件事" in result

    def test_travel_event_with_trip_label(self):
        events = [
            _make_event(
                id="1", event_type="travel", title="出发",
                trip_label="三亚", location="三亚",
            ),
            _make_event(id="2", event_type="task", title="收拾行李"),
        ]
        result = self.service._generate_day_summary(events)
        assert "三亚" in result

    def test_two_events_focus_plus_count(self):
        events = [
            _make_event(id="1", event_type="task", title="开会"),
            _make_event(id="2", event_type="task", title="写报告"),
        ]
        result = self.service._generate_day_summary(events)
        assert "开会" in result
        assert "一件事" in result

    def test_three_events_with_count(self):
        events = [
            _make_event(id="1", title="A"),
            _make_event(id="2", title="B"),
            _make_event(id="3", title="C"),
        ]
        result = self.service._generate_day_summary(events)
        assert "3件事" in result

    def test_many_events_weekend(self):
        events = [
            _make_event(id=str(i), title=f"事{i}")
            for i in range(5)
        ]
        result = self.service._generate_day_summary(
            events, date(2026, 2, 28),  # Saturday
        )
        assert "5件事" in result

    def test_all_completed_suffix(self):
        events = [
            _make_event(id="1", title="A", status="completed"),
            _make_event(id="2", title="B", status="completed"),
        ]
        result = self.service._generate_day_summary(events)
        assert "都已完成" in result

    def test_day_mood_in_summary(self):
        events = [
            _make_event(id=str(i), title=f"事{i}")
            for i in range(5)
        ]
        result = self.service._generate_day_summary(
            events, date(2026, 3, 2), day_mood="充实的一天",
        )
        assert "充实的一天" in result


# ── _pick_highlight_event ────────────────────────────────────────


class TestPickHighlightEvent:
    def test_focus_tier_highlighted(self):
        events = [
            _make_event(id="1", title="普通"),
            _make_event(id="2", title="重点", visibility_tier="focus"),
        ]
        result = TimelineService._pick_highlight_event(events)
        assert result == "2"

    def test_special_event_highlighted(self):
        events = [
            _make_event(id="1", event_type="task", title="普通"),
            _make_event(id="2", event_type="birthday", title="生日"),
        ]
        result = TimelineService._pick_highlight_event(events)
        assert result == "2"

    def test_no_highlight_for_regular_events(self):
        events = [
            _make_event(id="1", event_type="task", title="普通"),
        ]
        result = TimelineService._pick_highlight_event(events)
        assert result is None

    def test_empty_returns_none(self):
        result = TimelineService._pick_highlight_event([])
        assert result is None


# ── _build_life_context_hint ─────────────────────────────────────


def _make_curated_event(
    *,
    event_type: str = "other",
    location: Optional[str] = None,
    tags: Optional[list] = None,
    life_context_hint: Optional[str] = None,
):
    ev = MagicMock()
    ev.event_type = event_type
    ev.location = location
    ev.tags = tags or []
    ev.life_context_hint = life_context_hint
    return ev


class TestBuildLifeContextHint:
    def test_birthday_suggests_gift(self):
        ev = _make_curated_event(event_type="birthday")
        result = TimelineService._build_life_context_hint(ev)
        assert result is not None
        assert "\u793c\u7269" in result

    def test_anniversary_hint(self):
        ev = _make_curated_event(event_type="anniversary")
        result = TimelineService._build_life_context_hint(ev)
        assert result is not None

    def test_medical_mentions_documents(self):
        ev = _make_curated_event(event_type="medical")
        result = TimelineService._build_life_context_hint(ev)
        assert "\u8bc1\u4ef6" in result

    def test_travel_with_location_shows_destination(self):
        ev = _make_curated_event(event_type="travel", location="\u4e09\u4e9a")
        result = TimelineService._build_life_context_hint(ev)
        assert "\u4e09\u4e9a" in result

    def test_travel_without_location_returns_none(self):
        ev = _make_curated_event(event_type="travel")
        result = TimelineService._build_life_context_hint(ev)
        assert result is None

    def test_favor_hint(self):
        ev = _make_curated_event(event_type="favor")
        result = TimelineService._build_life_context_hint(ev)
        assert "\u4eba\u60c5" in result

    def test_regular_event_returns_none(self):
        ev = _make_curated_event(event_type="task")
        result = TimelineService._build_life_context_hint(ev)
        assert result is None

    def test_pre_generated_hint_takes_precedence(self):
        ev = _make_curated_event(
            event_type="birthday",
            life_context_hint="LLM生成的温暖提示",
        )
        result = TimelineService._build_life_context_hint(ev)
        assert result == "LLM生成的温暖提示"

    def test_pre_generated_hint_for_unknown_type(self):
        ev = _make_curated_event(
            event_type="unknown_type",
            life_context_hint="自定义提示",
        )
        result = TimelineService._build_life_context_hint(ev)
        assert result == "自定义提示"
