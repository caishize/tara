"""Consolidate trips table into travel_plans.

Revision ID: 057_consolidate_trip_tables
Revises: 056_create_pending_actions
Create Date: 2026-01-30

This migration:
1. Adds priority, description, extra_data columns to travel_plans
2. Migrates data from trips → travel_plans (with status mapping)
3. Updates curated_events FK from trips.id → travel_plans.trip_id
4. Drops the trips table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '057_consolidate_trip_tables'
down_revision = '056_create_pending_actions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1. Add missing columns to travel_plans
    # ============================================
    op.add_column('travel_plans', sa.Column(
        'priority', sa.String(10), nullable=False, server_default='normal'
    ))
    op.add_column('travel_plans', sa.Column(
        'description', sa.Text, nullable=True
    ))
    op.add_column('travel_plans', sa.Column(
        'extra_data', JSONB, nullable=True, server_default='{}'
    ))

    # Add check constraint for priority
    op.create_check_constraint(
        'check_priority_valid',
        'travel_plans',
        "priority IN ('low', 'normal', 'high', 'critical')"
    )

    # ============================================
    # 2. Migrate data from trips → travel_plans
    # ============================================
    # Map trips rows into travel_plans with field and status mapping:
    #   trips.user_id     → travel_plans.created_by
    #   trips.title       → travel_plans.trip_name
    #   trips.location    → travel_plans.destination
    #   trips.status: upcoming→planning, ongoing→in_progress
    op.execute("""
        INSERT INTO travel_plans (
            trip_id, family_id, created_by,
            trip_name, destination, start_date, end_date,
            category, status, priority, description, extra_data,
            created_at, updated_at
        )
        SELECT
            t.id,
            COALESCE(t.family_id, t.user_id),
            t.user_id,
            t.title,
            COALESCE(t.location, t.title),
            t.start_date,
            t.end_date,
            'personal',
            CASE t.status
                WHEN 'upcoming' THEN 'planning'
                WHEN 'ongoing' THEN 'in_progress'
                ELSE t.status
            END,
            t.priority,
            t.description,
            COALESCE(t.extra_data, '{}'),
            t.created_at,
            t.updated_at
        FROM trips t
        WHERE NOT EXISTS (
            SELECT 1 FROM travel_plans tp WHERE tp.trip_id = t.id
        )
    """)

    # ============================================
    # 3. Update curated_events FK: trips → travel_plans
    # ============================================
    # Drop old FK constraint (named fk_curated_events_trip in migration 055)
    op.drop_constraint(
        'fk_curated_events_trip',
        'curated_events',
        type_='foreignkey'
    )

    # Create new FK pointing to travel_plans
    op.create_foreign_key(
        'fk_curated_events_trip',
        'curated_events', 'travel_plans',
        ['trip_id'], ['trip_id'],
        ondelete='SET NULL'
    )

    # ============================================
    # 4. Drop FKs from user_insights and event_reminders that reference trips
    # ============================================
    op.drop_constraint(
        'user_insights_related_trip_id_fkey',
        'user_insights',
        type_='foreignkey'
    )
    op.drop_constraint(
        'event_reminders_trip_id_fkey',
        'event_reminders',
        type_='foreignkey'
    )

    # ============================================
    # 5. Drop trips table
    # ============================================
    op.drop_table('trips')


def downgrade() -> None:
    # ============================================
    # 1. Recreate trips table
    # ============================================
    op.create_table(
        'trips',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='upcoming'),
        sa.Column('priority', sa.String(10), nullable=False, server_default='normal'),
        sa.Column('extra_data', JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('upcoming', 'ongoing', 'completed', 'cancelled')",
            name='trips_status_check'
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')",
            name='trips_priority_check'
        ),
    )
    op.create_index('idx_trips_user_id', 'trips', ['user_id'])
    op.create_index('idx_trips_family_id', 'trips', ['family_id'])
    op.create_index('idx_trips_status', 'trips', ['status'])

    # ============================================
    # 2. Revert curated_events FK back to trips
    # ============================================
    op.drop_constraint(
        'fk_curated_events_trip',
        'curated_events',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'fk_curated_events_trip',
        'curated_events', 'trips',
        ['trip_id'], ['id'],
        ondelete='SET NULL'
    )

    # ============================================
    # 3. Recreate FKs from user_insights and event_reminders to trips
    # ============================================
    op.create_foreign_key(
        'user_insights_related_trip_id_fkey',
        'user_insights', 'trips',
        ['related_trip_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'event_reminders_trip_id_fkey',
        'event_reminders', 'trips',
        ['trip_id'], ['id'],
        ondelete='SET NULL'
    )

    # ============================================
    # 4. Remove added columns from travel_plans
    # ============================================
    op.drop_constraint('check_priority_valid', 'travel_plans', type_='check')
    op.drop_column('travel_plans', 'extra_data')
    op.drop_column('travel_plans', 'description')
    op.drop_column('travel_plans', 'priority')
