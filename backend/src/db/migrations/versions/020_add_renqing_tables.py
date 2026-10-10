"""Add renqing (人情世故) enhanced tables

Revision ID: 020_add_renqing_tables
Revises: 015_knowledge
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '020_add_renqing_tables'
down_revision = '015_knowledge'


def upgrade():
    # Create social_events_v2 table (enhanced version)
    op.create_table('social_events_v2',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('location', sa.String(300), nullable=True),
        sa.Column('budget', sa.Numeric(10, 2), nullable=True),
        sa.Column('actual_cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('total_received', sa.Numeric(10, 2), server_default='0'),
        sa.Column('total_given', sa.Numeric(10, 2), server_default='0'),
        sa.Column('guest_count', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(20), server_default='upcoming'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_event_v2_family_date', 'social_events_v2', ['family_id', 'event_date'])
    op.create_index('idx_event_v2_status', 'social_events_v2', ['family_id', 'status'])

    # Create favor_records_v2 table (enhanced version)
    op.create_table('favor_records_v2',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('contact_id', UUID(as_uuid=True), nullable=True),
        sa.Column('contact_name', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_id', UUID(as_uuid=True), sa.ForeignKey('social_events_v2.id'), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('gift_type', sa.String(20), server_default='cash'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('recorded_at', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('is_private', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_favor_v2_family_contact', 'favor_records_v2', ['family_id', 'contact_id'])
    op.create_index('idx_favor_v2_family_date', 'favor_records_v2', ['family_id', 'recorded_at'])
    op.create_index('idx_favor_v2_status', 'favor_records_v2', ['family_id', 'status'])
    op.create_index('idx_favor_v2_event', 'favor_records_v2', ['event_id'])

    # Create gift_records table
    op.create_table('gift_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('contact_id', UUID(as_uuid=True), nullable=False),
        sa.Column('occasion', sa.String(50), nullable=False),
        sa.Column('gift_name', sa.String(200), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('gift_year', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_gift_family_year', 'gift_records', ['family_id', 'gift_year'])
    op.create_index('idx_gift_contact', 'gift_records', ['contact_id'])
    op.create_unique_constraint('uq_gift_unique', 'gift_records', ['family_id', 'contact_id', 'occasion', 'gift_year'])

    # Create favor_reminders table
    op.create_table('favor_reminders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('reminder_type', sa.String(50), nullable=False),
        sa.Column('trigger_date', sa.Date(), nullable=True),
        sa.Column('trigger_days_before', sa.Integer(), nullable=True),
        sa.Column('contact_id', UUID(as_uuid=True), nullable=True),
        sa.Column('event_id', UUID(as_uuid=True), sa.ForeignKey('social_events_v2.id'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('is_dismissed', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_reminder_family_type', 'favor_reminders', ['family_id', 'reminder_type'])
    op.create_index('idx_reminder_trigger_date', 'favor_reminders', ['family_id', 'trigger_date'])
    op.create_index('idx_reminder_unread', 'favor_reminders', ['family_id', 'is_read', 'is_dismissed'])



def downgrade():
    # Drop tables
    op.drop_table('favor_reminders')
    op.drop_table('gift_records')
    op.drop_table('favor_records_v2')
    op.drop_table('social_events_v2')
