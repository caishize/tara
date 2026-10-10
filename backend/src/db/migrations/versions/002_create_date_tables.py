"""create date tables

Revision ID: 002_create_date_tables
Revises: 001_create_member_tables
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_create_date_tables'
down_revision: Union[str, None] = '001_create_member_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create important_dates table
    op.create_table(
        'important_dates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('date_type', sa.String(50), nullable=False),
        sa.Column('solar_date', sa.Date(), nullable=False),
        sa.Column('is_lunar', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('lunar_year', sa.Integer(), nullable=True),
        sa.Column('lunar_month', sa.Integer(), nullable=True),
        sa.Column('lunar_day', sa.Integer(), nullable=True),
        sa.Column('lunar_leap', sa.Boolean(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('recurrence_rule', postgresql.JSONB(), nullable=True),
        sa.Column('reminder_offsets', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('reminder_time', sa.String(5), nullable=True),
        sa.Column('reminder_channels', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('importance_level', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('health_related', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('attachments', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_date_family_solar', 'important_dates', ['family_id', 'solar_date'])
    op.create_index('idx_date_member', 'important_dates', ['member_id'])
    op.create_index('idx_date_type', 'important_dates', ['date_type'])

    # Create date_occurrences table
    op.create_table(
        'date_occurrences',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('parent_date_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('occurrence_date', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('user_response', sa.String(50), nullable=True),
        sa.Column('response_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_date_id'], ['important_dates.id'], ondelete='CASCADE')
    )

    op.create_index('idx_occurrence_parent', 'date_occurrences', ['parent_date_id'])
    op.create_index('idx_occurrence_date', 'date_occurrences', ['occurrence_date'])
    op.create_index('idx_occurrence_status', 'date_occurrences', ['status'])

    # Create date_reminders table
    op.create_table(
        'date_reminders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('date_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('occurrence_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reminder_time', sa.DateTime(), nullable=False),
        sa.Column('actual_sent_time', sa.DateTime(), nullable=True),
        sa.Column('reminder_offset', sa.Integer(), nullable=False),
        sa.Column('reminder_content', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('user_clicked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('clicked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['date_id'], ['important_dates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['occurrence_id'], ['date_occurrences.id'], ondelete='CASCADE')
    )

    op.create_index('idx_reminder_date', 'date_reminders', ['date_id'])
    op.create_index('idx_reminder_time', 'date_reminders', ['reminder_time'])
    op.create_index('idx_reminder_status', 'date_reminders', ['status'])
    op.create_index('idx_reminder_pending', 'date_reminders', ['status', 'reminder_time'],
                    postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_table('date_reminders')
    op.drop_table('date_occurrences')
    op.drop_table('important_dates')
