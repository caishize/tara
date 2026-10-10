from src.modules.trip.services.trip_query_policy import resolve_trip_query_policy


def test_past_planned_defaults_to_include_history_true():
    policy = resolve_trip_query_policy({"query_scene": "past_planned"})
    assert policy.scene == "past_planned"
    assert policy.include_history is True
    assert policy.date_scope == "past_only"
    assert set(policy.status_include) == {"planning", "confirmed", "in_progress"}


def test_past_planned_respects_explicit_include_history_false():
    policy = resolve_trip_query_policy(
        {"query_scene": "past_planned", "include_history": False}
    )
    assert policy.scene == "past_planned"
    assert policy.include_history is False


def test_past_executed_uses_deterministic_status_window():
    policy = resolve_trip_query_policy({"query_scene": "past_executed"})
    assert policy.scene == "past_executed"
    assert policy.date_scope == "past_only"
    assert set(policy.status_include) == {"completed", "confirmed", "in_progress"}


def test_current_plan_excludes_terminal_statuses():
    policy = resolve_trip_query_policy({"query_scene": "current_plan"})
    assert policy.scene == "current_plan"
    assert policy.date_scope == "current_or_future"
    assert set(policy.status_exclude) == {"cancelled", "completed"}


def test_unknown_scene_falls_back_to_default():
    policy = resolve_trip_query_policy({"query_scene": "foo"})
    assert policy.scene == "default"
    assert policy.date_scope == "all"
    assert policy.include_history is False
