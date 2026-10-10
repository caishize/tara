"""Create user_insight_settings table for configurable insight cycles.

Revision ID: 051_create_user_insight_settings
Revises: 050_add_trip_category
Create Date: 2025-01-25

This migration:
1. Creates user_insight_settings table with configurable cycle parameters
2. Adds indexes for user_id and family_id lookups
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '051_create_user_insight_settings'
down_revision = '050_add_trip_category'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_insight_settings table
    op.create_table(
        'user_insight_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),

        # Cycle configuration (in days)
        sa.Column('emotion_pattern_window_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('relationship_reminder_threshold_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('insight_expiry_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('old_plan_followup_threshold_days', sa.Integer(), nullable=False, server_default='14'),
        sa.Column('upcoming_trip_check_days', sa.Integer(), nullable=False, server_default='7'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create unique index on user_id (one settings record per user)
    op.create_index(
        'ix_user_insight_settings_user_id',
        'user_insight_settings',
        ['user_id'],
        unique=True
    )

    # Create index on family_id for family-level queries
    op.create_index(
        'ix_insight_settings_family',
        'user_insight_settings',
        ['family_id']
    )

    # Add check constraints for valid ranges
    op.create_check_constraint(
        'check_emotion_pattern_window_range',
        'user_insight_settings',
        'emotion_pattern_window_days >= 1 AND emotion_pattern_window_days <= 30'
    )
    op.create_check_constraint(
        'check_relationship_reminder_threshold_range',
        'user_insight_settings',
        'relationship_reminder_threshold_days >= 7 AND relationship_reminder_threshold_days <= 365'
    )
    op.create_check_constraint(
        'check_insight_expiry_range',
        'user_insight_settings',
        'insight_expiry_days >= 1 AND insight_expiry_days <= 30'
    )
    op.create_check_constraint(
        'check_old_plan_followup_range',
        'user_insight_settings',
        'old_plan_followup_threshold_days >= 1 AND old_plan_followup_threshold_days <= 60'
    )
    op.create_check_constraint(
        'check_upcoming_trip_check_range',
        'user_insight_settings',
        'upcoming_trip_check_days >= 1 AND upcoming_trip_check_days <= 30'
    )


def downgrade() -> None:
    # Drop check constraints
    op.drop_constraint('check_upcoming_trip_check_range', 'user_insight_settings', type_='check')
    op.drop_constraint('check_old_plan_followup_range', 'user_insight_settings', type_='check')
    op.drop_constraint('check_insight_expiry_range', 'user_insight_settings', type_='check')
    op.drop_constraint('check_relationship_reminder_threshold_range', 'user_insight_settings', type_='check')
    op.drop_constraint('check_emotion_pattern_window_range', 'user_insight_settings', type_='check')

    # Drop indexes
    op.drop_index('ix_insight_settings_family', table_name='user_insight_settings')
    op.drop_index('ix_user_insight_settings_user_id', table_name='user_insight_settings')

    # Drop table
    op.drop_table('user_insight_settings')
