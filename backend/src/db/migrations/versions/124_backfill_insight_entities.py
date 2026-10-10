"""Backfill missing insight_entities from action_options and source_context.

Migration 121 copied entity associations from legacy scalar FK columns,
but many were NULL.  This migration reconstructs associations from:
  1. action_options[].action_payload  -> person (recipient_member_id, member_id)
  2. source_context.legacy_extra_data.action_data.person -> person
  3. source_context.legacy_extra_data.source_memory_id   -> memory (source)
  4. source_context.person_profile_ids[]                 -> person (related)
  5. action_options[].action_payload.related_trip_id      -> trip (related)

Also backfills action_options for any insight that has NULL action_options.

Idempotent: all INSERTs use ON CONFLICT DO NOTHING.

Revision ID: 124
Revises: 123
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa


revision = "124"
down_revision = "123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ==================================================================
    # 1. Person entities from action_options payloads (recipient_member_id)
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT DISTINCT
            i.id,
            'person',
            (elem->>'recipient_member_id')::uuid,
            'primary'
        FROM insights i,
             jsonb_array_elements(i.action_options) AS elem
        WHERE i.action_options IS NOT NULL
          AND jsonb_array_length(i.action_options) > 0
          AND elem->>'recipient_member_id' IS NOT NULL
          AND (elem->>'recipient_member_id') ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 2. Person entities from action_options payloads (member_id)
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT DISTINCT
            i.id,
            'person',
            (elem->>'member_id')::uuid,
            'primary'
        FROM insights i,
             jsonb_array_elements(i.action_options) AS elem
        WHERE i.action_options IS NOT NULL
          AND jsonb_array_length(i.action_options) > 0
          AND elem->>'member_id' IS NOT NULL
          AND (elem->>'member_id') ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 3. Person entities from action_options payloads (person_id)
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT DISTINCT
            i.id,
            'person',
            (elem->>'person_id')::uuid,
            'related'
        FROM insights i,
             jsonb_array_elements(i.action_options) AS elem
        WHERE i.action_options IS NOT NULL
          AND jsonb_array_length(i.action_options) > 0
          AND elem->>'person_id' IS NOT NULL
          AND (elem->>'person_id') ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 4. Trip entities from action_options payloads (related_trip_id)
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT DISTINCT
            i.id,
            'trip',
            (elem->>'related_trip_id')::uuid,
            'related'
        FROM insights i,
             jsonb_array_elements(i.action_options) AS elem
        WHERE i.action_options IS NOT NULL
          AND jsonb_array_length(i.action_options) > 0
          AND elem->>'related_trip_id' IS NOT NULL
          AND (elem->>'related_trip_id') ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 5. Person entities from legacy source_context action_data.person
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT
            i.id,
            'person',
            (i.source_context->'legacy_extra_data'->'action_data'->>'person')::uuid,
            'primary'
        FROM insights i
        WHERE i.source_context ? 'legacy_extra_data'
          AND i.source_context->'legacy_extra_data' ? 'action_data'
          AND i.source_context->'legacy_extra_data'->'action_data'->>'person' IS NOT NULL
          AND (i.source_context->'legacy_extra_data'->'action_data'->>'person') ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 6. Memory entities from legacy source_context source_memory_id
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT
            i.id,
            'memory',
            (i.source_context->>'legacy_source_memory_id')::uuid,
            'source'
        FROM insights i
        WHERE i.source_context->>'legacy_source_memory_id' IS NOT NULL
          AND (i.source_context->>'legacy_source_memory_id') ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 7. Person entities from source_context.person_profile_ids[]
    # ==================================================================
    conn.execute(sa.text("""
        INSERT INTO insight_entities (insight_id, entity_type, entity_id, role)
        SELECT DISTINCT
            i.id,
            'person',
            pid::uuid,
            'related'
        FROM insights i,
             jsonb_array_elements_text(i.source_context->'person_profile_ids') AS pid
        WHERE i.source_context ? 'person_profile_ids'
          AND jsonb_typeof(i.source_context->'person_profile_ids') = 'array'
          AND jsonb_array_length(i.source_context->'person_profile_ids') > 0
          AND pid ~ '^[0-9a-f]{8}-'
        ON CONFLICT (insight_id, entity_type, entity_id) DO NOTHING
    """))

    # ==================================================================
    # 8. Backfill NULL action_options with default "了解" action
    # ==================================================================
    conn.execute(sa.text("""
        UPDATE insights
        SET action_options = '[{"label": "了解", "action_type": "open_detail"}]'::jsonb
        WHERE action_options IS NULL
          AND status NOT IN ('dismissed', 'acted', 'expired')
    """))

    # ==================================================================
    # Verification
    # ==================================================================
    orphaned = conn.execute(sa.text("""
        SELECT COUNT(DISTINCT i.id)
        FROM insights i
        LEFT JOIN insight_entities ie ON i.id = ie.insight_id
        WHERE ie.insight_id IS NULL
          AND i.status NOT IN ('dismissed', 'acted', 'expired')
    """)).scalar()

    total_entities = conn.execute(sa.text("""
        SELECT COUNT(*) FROM insight_entities
    """)).scalar()

    null_options = conn.execute(sa.text("""
        SELECT COUNT(*) FROM insights
        WHERE action_options IS NULL
          AND status NOT IN ('dismissed', 'acted', 'expired')
    """)).scalar()

    print(f"[migration-124] Orphaned active insights (no entities): {orphaned}")
    print(f"[migration-124] Total insight_entities rows: {total_entities}")
    print(f"[migration-124] Active insights with NULL action_options: {null_options}")


def downgrade() -> None:
    # This migration only adds rows via ON CONFLICT DO NOTHING and
    # sets NULL action_options to a default. Reverting would require
    # tracking which rows were added, which is not practical.
    # The changes are safe to leave in place on downgrade.
    pass
