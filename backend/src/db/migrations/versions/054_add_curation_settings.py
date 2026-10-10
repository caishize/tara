"""Add curation settings to user_insight_settings

Revision ID: 054_add_curation_settings
Revises: 053_create_curation_tables
Create Date: 2025-01-26

Adds curation cycle configuration fields to user_insight_settings:
- curation_schedule_hour: Hour of day to run curation (0-23)
- curation_days_ahead: Days ahead to curate (1-30)
- auto_curate_on_travel_create: Auto-trigger on travel creation
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '054_add_curation_settings'
down_revision = '053_create_curation_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add curation settings columns to user_insight_settings table
    op.add_column(
        'user_insight_settings',
        sa.Column('curation_schedule_hour', sa.Integer(), nullable=False, server_default='2')
    )
    op.add_column(
        'user_insight_settings',
        sa.Column('curation_days_ahead', sa.Integer(), nullable=False, server_default='14')
    )
    op.add_column(
        'user_insight_settings',
        sa.Column('auto_curate_on_travel_create', sa.Boolean(), nullable=False, server_default='true')
    )


def downgrade() -> None:
    # Remove curation settings columns
    op.drop_column('user_insight_settings', 'auto_curate_on_travel_create')
    op.drop_column('user_insight_settings', 'curation_days_ahead')
    op.drop_column('user_insight_settings', 'curation_schedule_hour')
