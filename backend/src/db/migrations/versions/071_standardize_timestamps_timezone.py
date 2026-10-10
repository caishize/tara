"""standardize all datetime columns to use timezone

Revision ID: 071
Revises: 070
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=:t"
        ),
        {"t": table},
    )
    return result.scalar() is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def _alter_to_tz(table: str, column: str, nullable: bool) -> None:
    if not _table_exists(table) or not _column_exists(table, column):
        return
    op.alter_column(
        table,
        column,
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=nullable,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def _alter_from_tz(table: str, column: str, nullable: bool) -> None:
    if not _table_exists(table) or not _column_exists(table, column):
        return
    op.alter_column(
        table,
        column,
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=nullable,
    )


def upgrade() -> None:
    # --- conversation_memories ---
    _alter_to_tz("conversation_memories", "expires_at", nullable=True)
    _alter_to_tz("conversation_memories", "last_triggered_at", nullable=True)
    _alter_to_tz("conversation_memories", "created_at", nullable=False)
    _alter_to_tz("conversation_memories", "updated_at", nullable=False)
    _alter_to_tz("conversation_memories", "last_recalled_at", nullable=True)

    # --- memory_insights ---
    _alter_to_tz("memory_insights", "shown_at", nullable=True)
    _alter_to_tz("memory_insights", "acted_at", nullable=True)
    _alter_to_tz("memory_insights", "dismissed_at", nullable=True)
    # Drop function index before altering created_at type, then recreate it
    if _table_exists("memory_insights") and _column_exists("memory_insights", "created_at"):
        op.drop_index("ix_memory_insights_user_type_date", table_name="memory_insights")
        _alter_to_tz("memory_insights", "created_at", nullable=False)
        op.execute(
            "CREATE INDEX ix_memory_insights_user_type_date "
            "ON memory_insights (user_id, insight_type, date(created_at AT TIME ZONE 'UTC'))"
        )
    _alter_to_tz("memory_insights", "expires_at", nullable=True)

    # --- memory_associations ---
    _alter_to_tz("memory_associations", "created_at", nullable=False)

    # --- insight_feedbacks --- (table does not exist, skipped)

    # --- secretary_notes ---
    _alter_to_tz("secretary_notes", "created_at", nullable=False)
    _alter_to_tz("secretary_notes", "updated_at", nullable=False)
    _alter_to_tz("secretary_notes", "last_surfaced_at", nullable=True)

    # --- chinese_holiday_plans ---
    _alter_to_tz("chinese_holiday_plans", "adopted_at", nullable=True)
    _alter_to_tz("chinese_holiday_plans", "created_at", nullable=False)
    _alter_to_tz("chinese_holiday_plans", "updated_at", nullable=False)

    # --- user_insight_settings ---
    _alter_to_tz("user_insight_settings", "created_at", nullable=False)
    _alter_to_tz("user_insight_settings", "updated_at", nullable=False)

    # --- today_items ---
    _alter_to_tz("today_items", "due_datetime", nullable=True)
    _alter_to_tz("today_items", "completed_at", nullable=True)
    _alter_to_tz("today_items", "created_at", nullable=False)
    _alter_to_tz("today_items", "updated_at", nullable=False)

    # --- ai_suggestions ---
    _alter_to_tz("ai_suggestions", "valid_until", nullable=True)
    _alter_to_tz("ai_suggestions", "dismissed_at", nullable=True)
    _alter_to_tz("ai_suggestions", "acted_upon_at", nullable=True)
    _alter_to_tz("ai_suggestions", "created_at", nullable=False)

    # --- preparation_plans ---
    _alter_to_tz("preparation_plans", "adopted_at", nullable=True)
    _alter_to_tz("preparation_plans", "notified_at", nullable=True)
    _alter_to_tz("preparation_plans", "created_at", nullable=False)
    _alter_to_tz("preparation_plans", "updated_at", nullable=False)

    # --- preparation_tasks ---
    _alter_to_tz("preparation_tasks", "completed_at", nullable=True)
    _alter_to_tz("preparation_tasks", "created_at", nullable=False)
    _alter_to_tz("preparation_tasks", "updated_at", nullable=False)

    # --- person_profiles ---
    _alter_to_tz("person_profiles", "last_mentioned_at", nullable=True)
    _alter_to_tz("person_profiles", "created_at", nullable=False)
    _alter_to_tz("person_profiles", "updated_at", nullable=False)

    # --- relationship_edges ---
    _alter_to_tz("relationship_edges", "created_at", nullable=False)
    _alter_to_tz("relationship_edges", "updated_at", nullable=False)

    # --- proactive_insights ---
    _alter_to_tz("proactive_insights", "shown_at", nullable=True)
    _alter_to_tz("proactive_insights", "acted_at", nullable=True)
    _alter_to_tz("proactive_insights", "dismissed_at", nullable=True)
    _alter_to_tz("proactive_insights", "scheduled_for", nullable=True)
    _alter_to_tz("proactive_insights", "expires_at", nullable=True)
    _alter_to_tz("proactive_insights", "created_at", nullable=False)

    # --- memory_summaries ---
    _alter_to_tz("memory_summaries", "period_start", nullable=True)
    _alter_to_tz("memory_summaries", "period_end", nullable=True)
    _alter_to_tz("memory_summaries", "last_updated_at", nullable=False)
    _alter_to_tz("memory_summaries", "created_at", nullable=False)
    _alter_to_tz("memory_summaries", "updated_at", nullable=False)

    # --- smart_reminders ---
    _alter_to_tz("smart_reminders", "last_sent_at", nullable=True)
    _alter_to_tz("smart_reminders", "next_send_at", nullable=True)
    _alter_to_tz("smart_reminders", "acknowledged_at", nullable=True)
    _alter_to_tz("smart_reminders", "created_at", nullable=False)
    _alter_to_tz("smart_reminders", "updated_at", nullable=False)

    # --- user_activity_patterns ---
    _alter_to_tz("user_activity_patterns", "last_analyzed_at", nullable=True)
    _alter_to_tz("user_activity_patterns", "created_at", nullable=False)
    _alter_to_tz("user_activity_patterns", "updated_at", nullable=False)

    # --- family_tasks ---
    _alter_to_tz("family_tasks", "completed_at", nullable=True)
    _alter_to_tz("family_tasks", "created_at", nullable=False)
    _alter_to_tz("family_tasks", "updated_at", nullable=False)

    # --- notebooks ---
    _alter_to_tz("notebooks", "created_at", nullable=False)
    _alter_to_tz("notebooks", "updated_at", nullable=False)

    # --- notebook_sources ---
    _alter_to_tz("notebook_sources", "created_at", nullable=False)
    _alter_to_tz("notebook_sources", "updated_at", nullable=False)

    # --- research_sessions ---
    _alter_to_tz("research_sessions", "created_at", nullable=False)
    _alter_to_tz("research_sessions", "updated_at", nullable=False)

    # --- date_occurrences ---
    _alter_to_tz("date_occurrences", "occurrence_date", nullable=False)
    _alter_to_tz("date_occurrences", "response_at", nullable=True)
    _alter_to_tz("date_occurrences", "created_at", nullable=False)
    _alter_to_tz("date_occurrences", "updated_at", nullable=False)

    # --- date_reminders (created_at/updated_at only; reminder_time etc done in 063) ---
    _alter_to_tz("date_reminders", "created_at", nullable=False)
    _alter_to_tz("date_reminders", "updated_at", nullable=False)

    # --- family_activities ---
    _alter_to_tz("family_activities", "activity_date", nullable=False)
    _alter_to_tz("family_activities", "created_at", nullable=False)
    _alter_to_tz("family_activities", "updated_at", nullable=False)

    # --- violation_records ---
    _alter_to_tz("violation_records", "violation_time", nullable=False)
    _alter_to_tz("violation_records", "created_at", nullable=False)
    _alter_to_tz("violation_records", "updated_at", nullable=False)

    # --- gift_conversation_context ---
    _alter_to_tz("gift_conversation_context", "expires_at", nullable=True)
    _alter_to_tz("gift_conversation_context", "mentioned_at", nullable=False)
    _alter_to_tz("gift_conversation_context", "created_at", nullable=False)
    _alter_to_tz("gift_conversation_context", "updated_at", nullable=False)

    # --- member_gift_memory ---
    _alter_to_tz("member_gift_memory", "last_gift_date", nullable=True)
    _alter_to_tz("member_gift_memory", "last_recommendation_date", nullable=True)
    _alter_to_tz("member_gift_memory", "last_conversation_update", nullable=True)
    _alter_to_tz("member_gift_memory", "created_at", nullable=False)
    _alter_to_tz("member_gift_memory", "updated_at", nullable=False)

    # --- gift_history ---
    _alter_to_tz("gift_history", "feedback_collected_at", nullable=True)
    _alter_to_tz("gift_history", "created_at", nullable=False)
    _alter_to_tz("gift_history", "updated_at", nullable=False)


def downgrade() -> None:
    # --- gift_history ---
    _alter_from_tz("gift_history", "updated_at", nullable=False)
    _alter_from_tz("gift_history", "created_at", nullable=False)
    _alter_from_tz("gift_history", "feedback_collected_at", nullable=True)

    # --- member_gift_memory ---
    _alter_from_tz("member_gift_memory", "updated_at", nullable=False)
    _alter_from_tz("member_gift_memory", "created_at", nullable=False)
    _alter_from_tz("member_gift_memory", "last_conversation_update", nullable=True)
    _alter_from_tz("member_gift_memory", "last_recommendation_date", nullable=True)
    _alter_from_tz("member_gift_memory", "last_gift_date", nullable=True)

    # --- gift_conversation_context ---
    _alter_from_tz("gift_conversation_context", "updated_at", nullable=False)
    _alter_from_tz("gift_conversation_context", "created_at", nullable=False)
    _alter_from_tz("gift_conversation_context", "mentioned_at", nullable=False)
    _alter_from_tz("gift_conversation_context", "expires_at", nullable=True)

    # --- violation_records ---
    _alter_from_tz("violation_records", "updated_at", nullable=False)
    _alter_from_tz("violation_records", "created_at", nullable=False)
    _alter_from_tz("violation_records", "violation_time", nullable=False)

    # --- family_activities ---
    _alter_from_tz("family_activities", "updated_at", nullable=False)
    _alter_from_tz("family_activities", "created_at", nullable=False)
    _alter_from_tz("family_activities", "activity_date", nullable=False)

    # --- date_reminders ---
    _alter_from_tz("date_reminders", "updated_at", nullable=False)
    _alter_from_tz("date_reminders", "created_at", nullable=False)

    # --- date_occurrences ---
    _alter_from_tz("date_occurrences", "updated_at", nullable=False)
    _alter_from_tz("date_occurrences", "created_at", nullable=False)
    _alter_from_tz("date_occurrences", "response_at", nullable=True)
    _alter_from_tz("date_occurrences", "occurrence_date", nullable=False)

    # --- research_sessions ---
    _alter_from_tz("research_sessions", "updated_at", nullable=False)
    _alter_from_tz("research_sessions", "created_at", nullable=False)

    # --- notebook_sources ---
    _alter_from_tz("notebook_sources", "updated_at", nullable=False)
    _alter_from_tz("notebook_sources", "created_at", nullable=False)

    # --- notebooks ---
    _alter_from_tz("notebooks", "updated_at", nullable=False)
    _alter_from_tz("notebooks", "created_at", nullable=False)

    # --- family_tasks ---
    _alter_from_tz("family_tasks", "updated_at", nullable=False)
    _alter_from_tz("family_tasks", "created_at", nullable=False)
    _alter_from_tz("family_tasks", "completed_at", nullable=True)

    # --- user_activity_patterns ---
    _alter_from_tz("user_activity_patterns", "updated_at", nullable=False)
    _alter_from_tz("user_activity_patterns", "created_at", nullable=False)
    _alter_from_tz("user_activity_patterns", "last_analyzed_at", nullable=True)

    # --- smart_reminders ---
    _alter_from_tz("smart_reminders", "updated_at", nullable=False)
    _alter_from_tz("smart_reminders", "created_at", nullable=False)
    _alter_from_tz("smart_reminders", "acknowledged_at", nullable=True)
    _alter_from_tz("smart_reminders", "next_send_at", nullable=True)
    _alter_from_tz("smart_reminders", "last_sent_at", nullable=True)

    # --- memory_summaries ---
    _alter_from_tz("memory_summaries", "updated_at", nullable=False)
    _alter_from_tz("memory_summaries", "created_at", nullable=False)
    _alter_from_tz("memory_summaries", "last_updated_at", nullable=False)
    _alter_from_tz("memory_summaries", "period_end", nullable=True)
    _alter_from_tz("memory_summaries", "period_start", nullable=True)

    # --- proactive_insights ---
    _alter_from_tz("proactive_insights", "created_at", nullable=False)
    _alter_from_tz("proactive_insights", "expires_at", nullable=True)
    _alter_from_tz("proactive_insights", "scheduled_for", nullable=True)
    _alter_from_tz("proactive_insights", "dismissed_at", nullable=True)
    _alter_from_tz("proactive_insights", "acted_at", nullable=True)
    _alter_from_tz("proactive_insights", "shown_at", nullable=True)

    # --- relationship_edges ---
    _alter_from_tz("relationship_edges", "updated_at", nullable=False)
    _alter_from_tz("relationship_edges", "created_at", nullable=False)

    # --- person_profiles ---
    _alter_from_tz("person_profiles", "updated_at", nullable=False)
    _alter_from_tz("person_profiles", "created_at", nullable=False)
    _alter_from_tz("person_profiles", "last_mentioned_at", nullable=True)

    # --- preparation_tasks ---
    _alter_from_tz("preparation_tasks", "updated_at", nullable=False)
    _alter_from_tz("preparation_tasks", "created_at", nullable=False)
    _alter_from_tz("preparation_tasks", "completed_at", nullable=True)

    # --- preparation_plans ---
    _alter_from_tz("preparation_plans", "updated_at", nullable=False)
    _alter_from_tz("preparation_plans", "created_at", nullable=False)
    _alter_from_tz("preparation_plans", "notified_at", nullable=True)
    _alter_from_tz("preparation_plans", "adopted_at", nullable=True)

    # --- ai_suggestions ---
    _alter_from_tz("ai_suggestions", "created_at", nullable=False)
    _alter_from_tz("ai_suggestions", "acted_upon_at", nullable=True)
    _alter_from_tz("ai_suggestions", "dismissed_at", nullable=True)
    _alter_from_tz("ai_suggestions", "valid_until", nullable=True)

    # --- today_items ---
    _alter_from_tz("today_items", "updated_at", nullable=False)
    _alter_from_tz("today_items", "created_at", nullable=False)
    _alter_from_tz("today_items", "completed_at", nullable=True)
    _alter_from_tz("today_items", "due_datetime", nullable=True)

    # --- user_insight_settings ---
    _alter_from_tz("user_insight_settings", "updated_at", nullable=False)
    _alter_from_tz("user_insight_settings", "created_at", nullable=False)

    # --- chinese_holiday_plans ---
    _alter_from_tz("chinese_holiday_plans", "updated_at", nullable=False)
    _alter_from_tz("chinese_holiday_plans", "created_at", nullable=False)
    _alter_from_tz("chinese_holiday_plans", "adopted_at", nullable=True)

    # --- secretary_notes ---
    _alter_from_tz("secretary_notes", "last_surfaced_at", nullable=True)
    _alter_from_tz("secretary_notes", "updated_at", nullable=False)
    _alter_from_tz("secretary_notes", "created_at", nullable=False)

    # --- insight_feedbacks --- (table does not exist, skipped)

    # --- memory_associations ---
    _alter_from_tz("memory_associations", "created_at", nullable=False)

    # --- memory_insights ---
    _alter_from_tz("memory_insights", "expires_at", nullable=True)
    # Drop function index before altering created_at type back, then recreate it
    if _table_exists("memory_insights") and _column_exists("memory_insights", "created_at"):
        op.drop_index("ix_memory_insights_user_type_date", table_name="memory_insights")
        _alter_from_tz("memory_insights", "created_at", nullable=False)
        op.execute(
            "CREATE INDEX ix_memory_insights_user_type_date "
            "ON memory_insights (user_id, insight_type, date(created_at))"
        )
    _alter_from_tz("memory_insights", "dismissed_at", nullable=True)
    _alter_from_tz("memory_insights", "acted_at", nullable=True)
    _alter_from_tz("memory_insights", "shown_at", nullable=True)

    # --- conversation_memories ---
    _alter_from_tz("conversation_memories", "last_recalled_at", nullable=True)
    _alter_from_tz("conversation_memories", "updated_at", nullable=False)
    _alter_from_tz("conversation_memories", "created_at", nullable=False)
    _alter_from_tz("conversation_memories", "last_triggered_at", nullable=True)
    _alter_from_tz("conversation_memories", "expires_at", nullable=True)
