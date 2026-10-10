"""Create curation tables for AI secretary service.

Tables for:
- curated_events: AI-processed and deduplicated events
- event_associations: AI-discovered event-to-entity relationships
- curation_jobs: Curation job tracking

Revision ID: 053_create_curation_tables
Revises: 052_enhance_shopping
Create Date: 2025-01-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '053_create_curation_tables'
down_revision = '052_enhance_shopping'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create curated_events table
    op.create_table(
        'curated_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

        # Source tracking
        sa.Column('original_event_ids', JSONB, nullable=False,
                  comment='Array of original event IDs that were merged'),
        sa.Column('source_types', JSONB, nullable=False,
                  comment='Array of source types: travel_plan, calendar, extracted_schedule'),

        # Normalized event data
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('normalized_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('normalized_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=True,
                  comment='business_trip, travel, meeting, appointment, reminder'),

        # Timeline items for multi-day events
        sa.Column('timeline_items', JSONB, nullable=True,
                  server_default='[]',
                  comment='Array of timeline items: [{time, item, confirmed, note}]'),

        # AI processing metadata
        sa.Column('dedup_reason', sa.Text, nullable=True,
                  comment='AI explanation of why events were merged'),
        sa.Column('enrichments', JSONB, nullable=True,
                  comment='AI-added context and enrichments'),
        sa.Column('confidence', sa.Float, nullable=False, server_default='0.8'),

        # Status
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Indexes for curated_events
    op.create_index(
        'idx_curated_events_family',
        'curated_events',
        ['family_id']
    )
    op.create_index(
        'idx_curated_events_date_range',
        'curated_events',
        ['family_id', 'normalized_start', 'normalized_end']
    )
    op.create_index(
        'idx_curated_events_active',
        'curated_events',
        ['family_id', 'is_active'],
        postgresql_where=sa.text('is_active = true')
    )

    # Create event_associations table
    op.create_table(
        'event_associations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

        # Association links
        sa.Column('source_event_id', UUID(as_uuid=True), sa.ForeignKey('curated_events.id', ondelete='CASCADE'), nullable=False,
                  comment='ID of the curated event'),
        sa.Column('target_id', sa.String(100), nullable=False,
                  comment='ID of the associated entity'),
        sa.Column('target_type', sa.String(50), nullable=False,
                  comment='person, memory, place, task, date'),

        # Association details
        sa.Column('association_type', sa.String(50), nullable=False,
                  comment='location, temporal, person, semantic, memory'),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('reason', sa.Text, nullable=False,
                  comment='AI-generated explanation of the association'),

        # Priority and confidence
        sa.Column('priority', sa.String(50), nullable=False,
                  server_default='convenient',
                  comment='strongly_recommend, convenient, optional'),
        sa.Column('confidence', sa.Float, nullable=False, server_default='0.8'),

        # User actions
        sa.Column('is_dismissed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_confirmed', sa.Boolean, nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Indexes for event_associations
    op.create_index(
        'idx_event_associations_source',
        'event_associations',
        ['source_event_id']
    )
    op.create_index(
        'idx_event_associations_family',
        'event_associations',
        ['family_id']
    )
    op.create_index(
        'idx_event_associations_active',
        'event_associations',
        ['source_event_id', 'is_dismissed'],
        postgresql_where=sa.text('is_dismissed = false')
    )

    # Create curation_jobs table
    op.create_table(
        'curation_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False, index=True),

        # Job configuration
        sa.Column('trigger_type', sa.String(50), nullable=False,
                  comment='scheduled, event, manual'),
        sa.Column('status', sa.String(50), nullable=False,
                  server_default='pending',
                  comment='pending, running, completed, failed'),

        # Processing scope
        sa.Column('date_range_start', sa.Date, nullable=True),
        sa.Column('date_range_end', sa.Date, nullable=True),

        # Results
        sa.Column('events_processed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('events_curated', sa.Integer, nullable=False, server_default='0'),
        sa.Column('associations_created', sa.Integer, nullable=False, server_default='0'),

        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # Error handling
        sa.Column('error_message', sa.Text, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Indexes for curation_jobs
    op.create_index(
        'idx_curation_jobs_family',
        'curation_jobs',
        ['family_id']
    )
    op.create_index(
        'idx_curation_jobs_status',
        'curation_jobs',
        ['family_id', 'status']
    )

    # Add check constraints
    op.create_check_constraint(
        'check_curated_event_type',
        'curated_events',
        "event_type IS NULL OR event_type IN ('business_trip', 'travel', 'meeting', 'appointment', 'reminder', 'birthday', 'anniversary', 'holiday', 'other')"
    )
    op.create_check_constraint(
        'check_association_type',
        'event_associations',
        "association_type IN ('location', 'temporal', 'person', 'semantic', 'memory', 'task')"
    )
    op.create_check_constraint(
        'check_association_priority',
        'event_associations',
        "priority IN ('strongly_recommend', 'convenient', 'optional')"
    )
    op.create_check_constraint(
        'check_target_type',
        'event_associations',
        "target_type IN ('person', 'memory', 'place', 'task', 'date', 'gift')"
    )
    op.create_check_constraint(
        'check_job_status',
        'curation_jobs',
        "status IN ('pending', 'running', 'completed', 'failed')"
    )
    op.create_check_constraint(
        'check_job_trigger',
        'curation_jobs',
        "trigger_type IN ('scheduled', 'event', 'manual')"
    )


def downgrade() -> None:
    # Drop check constraints
    op.drop_constraint('check_job_trigger', 'curation_jobs', type_='check')
    op.drop_constraint('check_job_status', 'curation_jobs', type_='check')
    op.drop_constraint('check_target_type', 'event_associations', type_='check')
    op.drop_constraint('check_association_priority', 'event_associations', type_='check')
    op.drop_constraint('check_association_type', 'event_associations', type_='check')
    op.drop_constraint('check_curated_event_type', 'curated_events', type_='check')

    # Drop indexes
    op.drop_index('idx_curation_jobs_status', table_name='curation_jobs')
    op.drop_index('idx_curation_jobs_family', table_name='curation_jobs')
    op.drop_index('idx_event_associations_active', table_name='event_associations')
    op.drop_index('idx_event_associations_family', table_name='event_associations')
    op.drop_index('idx_event_associations_source', table_name='event_associations')
    op.drop_index('idx_curated_events_active', table_name='curated_events')
    op.drop_index('idx_curated_events_date_range', table_name='curated_events')
    op.drop_index('idx_curated_events_family', table_name='curated_events')

    # Drop tables
    op.drop_table('curation_jobs')
    op.drop_table('event_associations')
    op.drop_table('curated_events')
