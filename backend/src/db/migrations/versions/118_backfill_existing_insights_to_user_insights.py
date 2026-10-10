"""Backfill existing active MemoryInsights and EventAssociations into user_insights.

Revision ID: 118
Revises: 117

One-time data migration: promotes all active memory_insights and person-type
event_associations into user_insights (the SSOT), then marks the originals
as promoted. This ensures historical data is visible through the unified
read layer immediately after deployment, rather than waiting for the daily
pipeline to gradually sweep them in.

Idempotent: uses ON CONFLICT DO NOTHING on the unique partial index
(uq_user_insights_active_dedup) and checks is_promoted/promoted_at
to skip already-migrated rows.
"""

from alembic import op
import sqlalchemy as sa


revision = "118"
down_revision = "117"


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 1: Backfill active MemoryInsights → user_insights
    # ------------------------------------------------------------------
    # Type mapping (mirrors _MEMORY_INSIGHT_TYPE_MAP + _PROACTIVE_INSIGHT_TYPE_MAP):
    #   correlation → memory,  reminder → time,  observation → health,
    #   suggestion → favor,    followup → memory,
    #   relationship_maintenance → relationship,  favor_reminder → favor,
    #   pattern_observation → health,  event_preparation → time
    #   (all others → memory)
    #
    # importance_score = LEAST(100, priority * 10)
    # urgency_score = CASE urgency: high→90, normal→60, low→30
    # semantic_dedup_key = mapped_type || ':memory:' || mi.id
    # expires_at = COALESCE(mi.expires_at, mi.created_at + 14 days)
    conn.execute(sa.text("""
        INSERT INTO user_insights (
            id, user_id, family_id,
            insight_type, title, content,
            importance_score, urgency_score,
            related_trip_id,
            status, suggested_action,
            extra_data, expires_at, semantic_dedup_key,
            source_type, source_id, promoted_at,
            created_at
        )
        SELECT
            gen_random_uuid(),
            mi.user_id,
            mi.family_id,
            -- Type mapping
            CASE mi.insight_type
                WHEN 'correlation' THEN 'memory'
                WHEN 'reminder' THEN 'time'
                WHEN 'observation' THEN 'health'
                WHEN 'suggestion' THEN 'favor'
                WHEN 'followup' THEN 'memory'
                WHEN 'relationship_maintenance' THEN 'relationship'
                WHEN 'favor_reminder' THEN 'favor'
                WHEN 'pattern_observation' THEN 'health'
                WHEN 'event_preparation' THEN 'time'
                ELSE 'memory'
            END,
            mi.title,
            mi.content,
            LEAST(100, mi.priority * 10),
            CASE mi.urgency
                WHEN 'high' THEN 90
                WHEN 'low' THEN 30
                ELSE 60
            END,
            -- related_trip_id: first element of related_trip_ids array
            mi.related_trip_ids[1],
            'pending',
            -- suggested_action: first element of action_options array
            mi.action_options[1],
            -- extra_data: preserve source info
            jsonb_build_object(
                'source', 'memory',
                'source_memory_id', mi.source_memory_id::text,
                'action_data', COALESCE(mi.action_data, '{}'::jsonb),
                'migrated_from', 'migration_118'
            ),
            COALESCE(mi.expires_at, mi.created_at + INTERVAL '14 days'),
            -- semantic_dedup_key: type:memory:id (unique per MI)
            CASE mi.insight_type
                WHEN 'correlation' THEN 'memory'
                WHEN 'reminder' THEN 'time'
                WHEN 'observation' THEN 'health'
                WHEN 'suggestion' THEN 'favor'
                WHEN 'followup' THEN 'memory'
                WHEN 'relationship_maintenance' THEN 'relationship'
                WHEN 'favor_reminder' THEN 'favor'
                WHEN 'pattern_observation' THEN 'health'
                WHEN 'event_preparation' THEN 'time'
                ELSE 'memory'
            END || ':memory:' || mi.id::text,
            'memory',
            mi.id,
            NOW(),
            mi.created_at
        FROM memory_insights mi
        WHERE mi.status IN ('pending', 'shown')
          AND mi.is_promoted = false
          AND (mi.expires_at IS NULL OR mi.expires_at > NOW())
        ON CONFLICT (user_id, semantic_dedup_key)
            WHERE semantic_dedup_key IS NOT NULL
              AND status NOT IN ('dismissed', 'actioned')
        DO NOTHING
    """))

    # Mark backfilled MIs as promoted
    conn.execute(sa.text("""
        UPDATE memory_insights
        SET is_promoted = true
        WHERE status IN ('pending', 'shown')
          AND is_promoted = false
          AND (expires_at IS NULL OR expires_at > NOW())
    """))

    # ------------------------------------------------------------------
    # Step 2: Backfill person-type EventAssociations → user_insights
    # ------------------------------------------------------------------
    # Only non-dismissed, person-type associations linked to non-cancelled events.
    # Joins curated_events for trip_id, normalized_start, and event title.
    #
    # importance_score: strongly_recommend→80, convenient→50, optional→30
    # urgency_score: strongly_recommend→70, else→50
    # semantic_dedup_key: ea:target_id:association_type:COALESCE(trip_id, event_id)
    # expires_at: event.normalized_start + 7 days, or NOW() + 7 days
    conn.execute(sa.text("""
        INSERT INTO user_insights (
            id, user_id, family_id,
            insight_type, title, content,
            importance_score, urgency_score,
            related_trip_id,
            status,
            extra_data, expires_at, semantic_dedup_key,
            source_type, source_id, promoted_at,
            created_at
        )
        SELECT
            gen_random_uuid(),
            ce.user_id,
            ea.family_id,
            -- Map EA association_type to valid user_insights insight_type
            CASE ea.association_type
                WHEN 'location' THEN 'relationship'
                WHEN 'temporal' THEN 'time'
                WHEN 'person' THEN 'relationship'
                WHEN 'semantic' THEN 'memory'
                WHEN 'memory' THEN 'memory'
                ELSE 'relationship'
            END,
            ea.title,
            COALESCE(ea.reason, ea.title),
            CASE ea.priority
                WHEN 'strongly_recommend' THEN 80
                WHEN 'convenient' THEN 50
                WHEN 'optional' THEN 30
                ELSE 50
            END,
            CASE WHEN ea.priority = 'strongly_recommend' THEN 70 ELSE 50 END,
            ce.trip_id,
            'pending',
            jsonb_build_object(
                'source', 'association',
                'source_ea_id', ea.id::text,
                'target_member_id', ea.target_id,
                'event_title', ce.title,
                'person', ea.target_id,
                'migrated_from', 'migration_118'
            ),
            COALESCE(
                ce.normalized_start + INTERVAL '7 days',
                NOW() + INTERVAL '7 days'
            ),
            'ea:' || ea.target_id || ':' || ea.association_type
                || ':' || COALESCE(ce.trip_id::text, ce.id::text),
            'association',
            ea.id,
            NOW(),
            ea.created_at
        FROM event_associations ea
        JOIN curated_events ce ON ea.source_event_id = ce.id
        WHERE ea.target_type = 'person'
          AND ea.is_dismissed = false
          AND ea.promoted_at IS NULL
          AND ce.status != 'cancelled'
          AND ce.user_id IS NOT NULL
          -- Skip self-associations where target_id = user_id
          AND ea.target_id != ce.user_id::text
        ON CONFLICT (user_id, semantic_dedup_key)
            WHERE semantic_dedup_key IS NOT NULL
              AND status NOT IN ('dismissed', 'actioned')
        DO NOTHING
    """))

    # Mark backfilled EAs as promoted and link to the new UserInsight
    # We match by source_id in user_insights to find the promoted_insight_id
    conn.execute(sa.text("""
        UPDATE event_associations ea
        SET promoted_at = NOW(),
            promoted_insight_id = ui.id
        FROM user_insights ui
        WHERE ui.source_type = 'association'
          AND ui.source_id = ea.id
          AND ea.promoted_at IS NULL
          AND ea.target_type = 'person'
          AND ea.is_dismissed = false
    """))

    # Also link MI → promoted UserInsight
    conn.execute(sa.text("""
        UPDATE memory_insights mi
        SET promoted_insight_id = ui.id
        FROM user_insights ui
        WHERE ui.source_type = 'memory'
          AND ui.source_id = mi.id
          AND mi.is_promoted = true
          AND mi.promoted_insight_id IS NULL
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove backfilled user_insights (identifiable by migrated_from marker)
    conn.execute(sa.text("""
        DELETE FROM user_insights
        WHERE extra_data->>'migrated_from' = 'migration_118'
    """))

    # Reset promotion flags on memory_insights
    conn.execute(sa.text("""
        UPDATE memory_insights
        SET is_promoted = false, promoted_insight_id = NULL
        WHERE is_promoted = true
    """))

    # Reset promotion tracking on event_associations
    conn.execute(sa.text("""
        UPDATE event_associations
        SET promoted_at = NULL, promoted_insight_id = NULL
        WHERE promoted_at IS NOT NULL
    """))
