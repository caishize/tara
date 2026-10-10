"""Add curation interval and event change trigger settings.

Revision ID: 059_add_curation_interval
Revises: 058_add_user_event_support
Create Date: 2026-01-31

Adds:
1. curation_interval_minutes - minimum interval between curation runs (15-1440 min)
2. auto_curate_on_event_change - whether to auto-curate on event CRUD
"""
from alembic import op
import sqlalchemy as sa


revision = '059_add_curation_interval'
down_revision = '058_add_user_event_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user_insight_settings',
        sa.Column(
            'curation_interval_minutes',
            sa.Integer(),
            nullable=False,
            server_default='60',
        ),
    )
    op.add_column(
        'user_insight_settings',
        sa.Column(
            'auto_curate_on_event_change',
            sa.Boolean(),
            nullable=False,
            server_default='true',
        ),
    )

    # Check constraint: interval between 15 and 1440 minutes
    op.create_check_constraint(
        'ck_curation_interval_range',
        'user_insight_settings',
        'curation_interval_minutes >= 15 AND curation_interval_minutes <= 1440',
    )


def downgrade() -> None:
    op.drop_constraint('ck_curation_interval_range', 'user_insight_settings', type_='check')
    op.drop_column('user_insight_settings', 'auto_curate_on_event_change')
    op.drop_column('user_insight_settings', 'curation_interval_minutes')
