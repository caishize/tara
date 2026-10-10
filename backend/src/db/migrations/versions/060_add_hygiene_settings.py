"""Add event hygiene settings to user_insight_settings.

Revision ID: 060_add_hygiene_settings
Revises: 059_add_curation_interval
Create Date: 2026-01-31

Adds:
1. hygiene_enabled - per-family opt-out for daily cleanup (default: true)
2. inactive_retention_days - days to keep is_active=False events (1-90, default: 7)
3. cancelled_retention_days - days to keep cancelled events (1-365, default: 30)
"""
from alembic import op
import sqlalchemy as sa


revision = '060_add_hygiene_settings'
down_revision = '059_add_curation_interval'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user_insight_settings',
        sa.Column(
            'hygiene_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='true',
        ),
    )
    op.add_column(
        'user_insight_settings',
        sa.Column(
            'inactive_retention_days',
            sa.Integer(),
            nullable=False,
            server_default='7',
        ),
    )
    op.add_column(
        'user_insight_settings',
        sa.Column(
            'cancelled_retention_days',
            sa.Integer(),
            nullable=False,
            server_default='30',
        ),
    )

    op.create_check_constraint(
        'ck_inactive_retention_range',
        'user_insight_settings',
        'inactive_retention_days >= 1 AND inactive_retention_days <= 90',
    )
    op.create_check_constraint(
        'ck_cancelled_retention_range',
        'user_insight_settings',
        'cancelled_retention_days >= 1 AND cancelled_retention_days <= 365',
    )


def downgrade() -> None:
    op.drop_constraint('ck_cancelled_retention_range', 'user_insight_settings', type_='check')
    op.drop_constraint('ck_inactive_retention_range', 'user_insight_settings', type_='check')
    op.drop_column('user_insight_settings', 'cancelled_retention_days')
    op.drop_column('user_insight_settings', 'inactive_retention_days')
    op.drop_column('user_insight_settings', 'hygiene_enabled')
