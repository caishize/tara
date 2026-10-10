"""Migrate existing insight data to unified insights + insight_entities tables.

Revision ID: 121
Revises: 120

Data-only migration (no DDL changes). Copies active rows from:
  - user_insights  -> insights + insight_entities
  - memory_insights -> insights + insight_entities

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING and tracks origin
in source_context->>'migrated_from' for safe re-runs and rollback.
"""

from alembic import op
import sqlalchemy as sa


revision = "121"
down_revision = "120"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Batch size for array-expansion queries (memory_insights entity arrays)
# ---------------------------------------------------------------------------
_BATCH_SIZE = 500


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Temporary GIN index for JSONB path queries during migration
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tmp_insights_source_ctx "
        "ON insights USING gin (source_context)"
    )

    # ------------------------------------------------------------------
    # Pre-flight: verify source tables exist
    # ------------------------------------------------------------------
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    has_user_insights = "user_insights" in existing_tables
    has_memory_insights = "memory_insights" in existing_tables

    if "insights" not in existing_tables:
        raise RuntimeError(
            "Target table 'insights' does not exist. "
            "Run migration 120 first."
        )

    # ==================================================================
    # Step 1: Migrate user_insights -> insights + insight_entities
    # ==================================================================
    if has_user_insights:
        conn.execute(sa.text("""
            INSERT INTO insights (
                id, user_id, family_id, insight_type, title, content,
                importance, urgency, source, source_context, status,
                feedback, feedback_at, suggested_action, action_options,
                dedup_key, shown_at, delivered_via_briefing,
                expires_at, created_at, pushed_at, read_at
            )
            SELECT
                gen_random_uuid(),
                ui.user_id,
                COALESCE(ui.family_id, '00000000-0000-0000-0000-000000000000'::uuid),
                ui.insight_type,
                ui.title,
                ui.content,
                COALESCE(ui.importance_score, 50),
                COALESCE(ui.urgency_score, 50),
                CASE ui.source_type
                    WHEN 'briefing'    THEN 'scheduled'
                    WHEN 'association' THEN 'scheduled'
                    WHEN 'trip'        THEN 'trip_event'
                    WHEN 'memory'      THEN 'reflection'
                    ELSE 'scheduled'
                END,
                jsonb_build_object(
                    'migrated_from', 'user_insights',
                    'legacy_id', ui.id::text,
                    'legacy_source_id', ui.source_id::text,
                    'legacy_extra_data', COALESCE(ui.extra_data, '{}'::jsonb)
                ),
                CASE ui.status
                    WHEN 'pending' THEN 'pending'
                    WHEN 'pushed'  THEN 'active'
                    WHEN 'read'    THEN 'active'
                    ELSE 'pending'
                END,
                CASE ui.feedback
                    WHEN 'useful'      THEN 'useful'
                    WHEN 'ignored'     THEN 'not_useful'
                    WHEN 'never_again' THEN 'never'
                    ELSE ui.feedback
                END,
                ui.feedback_at,
                ui.suggested_action,
                ui.action_options::jsonb,
                ui.semantic_dedup_key,
                ui.push_time,
                true,
                ui.expires_at,
                ui.created_at,
                ui.push_time,
                ui.read_time
            FROM user_insights ui
            WHERE ui.status NOT IN ('dismissed', 'actioned')
              AND (ui.expires_at IS NULL OR ui.expires_at > NOW())
              AND NOT EXISTS (
                  SELECT 1 FROM insights i
                  WHERE i.source_context->>'migrated_from' = 'user_insights'
                    AND i.source_context->>'legacy_id' = ui.id::text
              )
        """))

        # --- insight_entities from user_insights scalar FK columns ---

        # related_person_id -> entity_type='person', role='primary'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'person', ui.related_person_id, 'primary'
            FROM insights i
            JOIN user_insights ui
              ON i.source_context->>'migrated_from' = 'user_insights'
             AND i.source_context->>'legacy_id' = ui.id::text
            WHERE ui.related_person_id IS NOT NULL
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # related_event_id -> entity_type='event', role='related'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'event', ui.related_event_id, 'related'
            FROM insights i
            JOIN user_insights ui
              ON i.source_context->>'migrated_from' = 'user_insights'
             AND i.source_context->>'legacy_id' = ui.id::text
            WHERE ui.related_event_id IS NOT NULL
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # related_trip_id -> entity_type='trip', role='related'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'trip', ui.related_trip_id, 'related'
            FROM insights i
            JOIN user_insights ui
              ON i.source_context->>'migrated_from' = 'user_insights'
             AND i.source_context->>'legacy_id' = ui.id::text
            WHERE ui.related_trip_id IS NOT NULL
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # related_important_date_id -> entity_type='important_date', role='related'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'important_date', ui.related_important_date_id, 'related'
            FROM insights i
            JOIN user_insights ui
              ON i.source_context->>'migrated_from' = 'user_insights'
             AND i.source_context->>'legacy_id' = ui.id::text
            WHERE ui.related_important_date_id IS NOT NULL
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # source_id with source_type='association' -> entity_type='event_association', role='source'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'event_association', ui.source_id, 'source'
            FROM insights i
            JOIN user_insights ui
              ON i.source_context->>'migrated_from' = 'user_insights'
             AND i.source_context->>'legacy_id' = ui.id::text
            WHERE ui.source_id IS NOT NULL
              AND ui.source_type = 'association'
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

    # ==================================================================
    # Step 2: Migrate memory_insights -> insights + insight_entities
    # ==================================================================
    if has_memory_insights:
        conn.execute(sa.text("""
            INSERT INTO insights (
                id, user_id, family_id, insight_type, title, content,
                importance, urgency, source, source_context, status,
                dedup_key, shown_at, expires_at, created_at
            )
            SELECT
                gen_random_uuid(),
                mi.user_id,
                mi.family_id,
                mi.insight_type,
                mi.title,
                mi.content,
                COALESCE(mi.priority, 5) * 10,
                CASE mi.urgency
                    WHEN 'critical' THEN 90
                    WHEN 'high'     THEN 70
                    WHEN 'normal'   THEN 50
                    WHEN 'low'      THEN 30
                    ELSE 50
                END,
                'scheduled',
                jsonb_build_object(
                    'migrated_from', 'memory_insights',
                    'legacy_id', mi.id::text,
                    'legacy_source_memory_id', mi.source_memory_id::text
                ),
                'pending',
                NULL,
                mi.shown_at,
                mi.expires_at,
                mi.created_at
            FROM memory_insights mi
            WHERE mi.status = 'pending'
              AND mi.is_promoted = false
              AND (mi.expires_at IS NULL OR mi.expires_at > NOW())
              AND NOT EXISTS (
                  SELECT 1 FROM insights i
                  WHERE i.source_context->>'migrated_from' = 'memory_insights'
                    AND i.source_context->>'legacy_id' = mi.id::text
              )
        """))

        # --- insight_entities from memory_insights array columns ---

        # related_member_ids UUID[] -> entity_type='person', role='related'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'person', member_id, 'related'
            FROM insights i
            JOIN memory_insights mi
              ON i.source_context->>'migrated_from' = 'memory_insights'
             AND i.source_context->>'legacy_id' = mi.id::text
            CROSS JOIN LATERAL unnest(mi.related_member_ids) AS member_id
            WHERE mi.related_member_ids IS NOT NULL
              AND array_length(mi.related_member_ids, 1) > 0
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # related_event_ids UUID[] -> entity_type='event', role='related'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'event', event_id, 'related'
            FROM insights i
            JOIN memory_insights mi
              ON i.source_context->>'migrated_from' = 'memory_insights'
             AND i.source_context->>'legacy_id' = mi.id::text
            CROSS JOIN LATERAL unnest(mi.related_event_ids) AS event_id
            WHERE mi.related_event_ids IS NOT NULL
              AND array_length(mi.related_event_ids, 1) > 0
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # related_trip_ids UUID[] -> entity_type='trip', role='related'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'trip', trip_id, 'related'
            FROM insights i
            JOIN memory_insights mi
              ON i.source_context->>'migrated_from' = 'memory_insights'
             AND i.source_context->>'legacy_id' = mi.id::text
            CROSS JOIN LATERAL unnest(mi.related_trip_ids) AS trip_id
            WHERE mi.related_trip_ids IS NOT NULL
              AND array_length(mi.related_trip_ids, 1) > 0
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

        # source_memory_id -> entity_type='memory', role='source'
        conn.execute(sa.text("""
            INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
            SELECT i.id, 'memory', mi.source_memory_id, 'source'
            FROM insights i
            JOIN memory_insights mi
              ON i.source_context->>'migrated_from' = 'memory_insights'
             AND i.source_context->>'legacy_id' = mi.id::text
            WHERE mi.source_memory_id IS NOT NULL
            ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
        """))

    # ==================================================================
    # Verification: log migration counts
    # ==================================================================
    row_ui = conn.execute(sa.text("""
        SELECT COUNT(*) FROM insights
        WHERE source_context->>'migrated_from' = 'user_insights'
    """)).scalar()

    row_mi = conn.execute(sa.text("""
        SELECT COUNT(*) FROM insights
        WHERE source_context->>'migrated_from' = 'memory_insights'
    """)).scalar()

    row_entities = conn.execute(sa.text("""
        SELECT COUNT(*) FROM insight_entities
    """)).scalar()

    print(f"[migration-121] user_insights migrated:   {row_ui}")
    print(f"[migration-121] memory_insights migrated: {row_mi}")
    print(f"[migration-121] insight_entities created:  {row_entities}")

    # ------------------------------------------------------------------
    # Drop temporary GIN index
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS ix_tmp_insights_source_ctx")


def downgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Temporary GIN index for JSONB path queries during downgrade
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tmp_insights_source_ctx "
        "ON insights USING gin (source_context)"
    )

    # Delete insight_entities that belong to migrated insights (cascade
    # would handle this, but be explicit for safety).
    conn.execute(sa.text("""
        DELETE FROM insight_entities
        WHERE insight_id IN (
            SELECT id FROM insights
            WHERE source_context->>'migrated_from' IN ('user_insights', 'memory_insights')
        )
    """))

    # Delete migrated insight rows.
    conn.execute(sa.text("""
        DELETE FROM insights
        WHERE source_context->>'migrated_from' IN ('user_insights', 'memory_insights')
    """))

    # ------------------------------------------------------------------
    # Drop temporary GIN index
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS ix_tmp_insights_source_ctx")
