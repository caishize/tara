"""Add user-created event support.

Revision ID: 058_add_user_event_support
Revises: 057_consolidate_trip_tables
Create Date: 2026-01-30

This migration adds:
1. GIN index on curated_events.source_types for efficient user_created filtering
2. Index on curated_events.status for efficient cancelled event exclusion
3. Comment updates for new target_types (favor, history)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '058_add_user_event_support'
down_revision = '057_consolidate_trip_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. GIN index on source_types JSONB for efficient filtering
    # Enables fast queries like: WHERE source_types @> '["user_created"]'
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_curated_events_source_types_gin "
        "ON curated_events USING gin (source_types)"
    )

    # 2. Index on status for efficient cancelled event exclusion
    op.create_index(
        'idx_curated_events_status',
        'curated_events',
        ['status'],
        if_not_exists=True,
    )

    # 3. Composite index for common event list queries
    op.create_index(
        'idx_curated_events_family_active_start',
        'curated_events',
        ['family_id', 'is_active', 'normalized_start'],
        if_not_exists=True,
    )

    # 4. Update comments for extended target_type values
    op.execute(
        "COMMENT ON COLUMN event_associations.target_type IS "
        "'person, memory, place, task, date, gift (favor records), history (past events)'"
    )

    op.execute(
        "COMMENT ON COLUMN event_associations.association_type IS "
        "'location, temporal, person, semantic, memory, favor, history'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_curated_events_source_types_gin")
    op.drop_index('idx_curated_events_status', table_name='curated_events')
    op.drop_index('idx_curated_events_family_active_start', table_name='curated_events')
