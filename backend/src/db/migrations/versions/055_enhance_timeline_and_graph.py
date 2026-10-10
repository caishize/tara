"""Enhance timeline and event graph for intelligent secretary system.

Revision ID: 055_enhance_timeline_and_graph
Revises: 054_add_curation_settings
Create Date: 2025-01-27

This migration adds:
1. trips table - Container for multi-day journeys
2. Enhanced curated_events with trip_id, status, priority
3. user_insights table - AI-generated insights
4. event_reminders table - Event reminders

Based on: docs/ARCH_Secretary_Intelligence_System.md
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '055_enhance_timeline_and_graph'
down_revision = '054_add_curation_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1. Create trips table
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

    op.create_index('idx_trips_user_date', 'trips', ['user_id', 'start_date', 'end_date'])
    op.create_index('idx_trips_status', 'trips', ['user_id', 'status'])
    op.create_index('idx_trips_family', 'trips', ['family_id'])

    # ============================================
    # 2. Enhance curated_events table
    # ============================================
    # Add trip_id column
    op.add_column('curated_events', sa.Column(
        'trip_id', UUID(as_uuid=True), nullable=True
    ))
    op.create_foreign_key(
        'fk_curated_events_trip',
        'curated_events', 'trips',
        ['trip_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add user_id column (for user-level queries)
    op.add_column('curated_events', sa.Column(
        'user_id', UUID(as_uuid=True), nullable=True
    ))

    # Add status column
    op.add_column('curated_events', sa.Column(
        'status', sa.String(20), nullable=False, server_default='pending'
    ))

    # Add priority column
    op.add_column('curated_events', sa.Column(
        'priority', sa.String(10), nullable=False, server_default='normal'
    ))

    # Add notes column (secretary notes)
    op.add_column('curated_events', sa.Column(
        'notes', sa.Text, nullable=True
    ))

    # Add tags column
    op.add_column('curated_events', sa.Column(
        'tags', JSONB, nullable=True, server_default='[]'
    ))

    # Add check constraints for new columns
    op.execute("""
        ALTER TABLE curated_events
        ADD CONSTRAINT curated_events_status_check
        CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled'))
    """)

    op.execute("""
        ALTER TABLE curated_events
        ADD CONSTRAINT curated_events_priority_check
        CHECK (priority IN ('low', 'normal', 'high', 'critical'))
    """)

    # Create indexes for new columns
    op.create_index('idx_curated_events_trip', 'curated_events', ['trip_id'])
    op.create_index('idx_curated_events_user', 'curated_events', ['user_id'])
    op.create_index('idx_curated_events_status', 'curated_events', ['user_id', 'status', 'normalized_start'])

    # ============================================
    # 3. Create user_insights table
    # ============================================
    op.create_table(
        'user_insights',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=True),

        # Insight content
        sa.Column('insight_type', sa.String(30), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text, nullable=False),

        # Scoring
        sa.Column('importance_score', sa.Integer, nullable=False, server_default='50'),
        sa.Column('urgency_score', sa.Integer, nullable=False, server_default='50'),

        # Related entities
        sa.Column('related_event_id', UUID(as_uuid=True), nullable=True),
        sa.Column('related_trip_id', UUID(as_uuid=True), nullable=True),
        sa.Column('related_person_id', UUID(as_uuid=True), nullable=True),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('push_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_time', sa.DateTime(timezone=True), nullable=True),

        # Feedback
        sa.Column('feedback', sa.String(20), nullable=True),
        sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True),

        # Action
        sa.Column('suggested_action', sa.Text, nullable=True),
        sa.Column('action_taken', sa.Boolean, nullable=False, server_default='false'),

        # Metadata
        sa.Column('extra_data', JSONB, nullable=True, server_default='{}'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        # Check constraints
        sa.CheckConstraint(
            "insight_type IN ('time', 'relationship', 'favor', 'efficiency', 'health', 'finance', 'memory')",
            name='user_insights_type_check'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'pushed', 'read', 'actioned', 'dismissed')",
            name='user_insights_status_check'
        ),
        sa.CheckConstraint(
            "feedback IS NULL OR feedback IN ('useful', 'ignored', 'never_again')",
            name='user_insights_feedback_check'
        ),
        sa.CheckConstraint(
            "importance_score >= 0 AND importance_score <= 100",
            name='user_insights_importance_range'
        ),
        sa.CheckConstraint(
            "urgency_score >= 0 AND urgency_score <= 100",
            name='user_insights_urgency_range'
        ),

        # Foreign keys
        sa.ForeignKeyConstraint(['related_event_id'], ['curated_events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_trip_id'], ['trips.id'], ondelete='SET NULL'),
    )

    op.create_index('idx_user_insights_user', 'user_insights', ['user_id', 'created_at'])
    op.create_index('idx_user_insights_status', 'user_insights', ['user_id', 'status'])
    op.create_index('idx_user_insights_score', 'user_insights', ['user_id', 'importance_score'])
    op.create_index('idx_user_insights_type', 'user_insights', ['user_id', 'insight_type'])

    # ============================================
    # 4. Create event_reminders table
    # ============================================
    op.create_table(
        'event_reminders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_id', UUID(as_uuid=True), nullable=True),
        sa.Column('trip_id', UUID(as_uuid=True), nullable=True),

        # Reminder content
        sa.Column('reminder_type', sa.String(30), nullable=False),
        sa.Column('content', sa.Text, nullable=False),

        # Trigger time
        sa.Column('trigger_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('triggered', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=True),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('snooze_until', sa.DateTime(timezone=True), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        # Check constraints
        sa.CheckConstraint(
            "reminder_type IN ('preparation', 'action', 'weather', 'item', 'followup')",
            name='event_reminders_type_check'
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'triggered', 'acknowledged', 'snoozed', 'cancelled')",
            name='event_reminders_status_check'
        ),

        # Foreign keys
        sa.ForeignKeyConstraint(['event_id'], ['curated_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
    )

    op.create_index('idx_event_reminders_trigger', 'event_reminders', ['trigger_time', 'triggered'])
    op.create_index('idx_event_reminders_user', 'event_reminders', ['user_id', 'trigger_time'])
    op.create_index('idx_event_reminders_event', 'event_reminders', ['event_id'])


def downgrade() -> None:
    # Drop event_reminders
    op.drop_index('idx_event_reminders_event')
    op.drop_index('idx_event_reminders_user')
    op.drop_index('idx_event_reminders_trigger')
    op.drop_table('event_reminders')

    # Drop user_insights
    op.drop_index('idx_user_insights_type')
    op.drop_index('idx_user_insights_score')
    op.drop_index('idx_user_insights_status')
    op.drop_index('idx_user_insights_user')
    op.drop_table('user_insights')

    # Remove curated_events enhancements
    op.drop_index('idx_curated_events_status')
    op.drop_index('idx_curated_events_user')
    op.drop_index('idx_curated_events_trip')
    op.execute("ALTER TABLE curated_events DROP CONSTRAINT IF EXISTS curated_events_priority_check")
    op.execute("ALTER TABLE curated_events DROP CONSTRAINT IF EXISTS curated_events_status_check")
    op.drop_constraint('fk_curated_events_trip', 'curated_events', type_='foreignkey')
    op.drop_column('curated_events', 'tags')
    op.drop_column('curated_events', 'notes')
    op.drop_column('curated_events', 'priority')
    op.drop_column('curated_events', 'status')
    op.drop_column('curated_events', 'user_id')
    op.drop_column('curated_events', 'trip_id')

    # Drop trips
    op.drop_index('idx_trips_family')
    op.drop_index('idx_trips_status')
    op.drop_index('idx_trips_user_date')
    op.drop_table('trips')
