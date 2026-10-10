"""Create user_briefing_settings table for per-period briefing preferences.

Revision ID: 081_create_user_briefing_settings
Revises: 080_create_preparation_items_table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "081"
down_revision = "080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_briefing_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("morning_hour", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("afternoon_hour", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("evening_hour", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("timezone", sa.String(50), nullable=True),
        sa.Column(
            "enabled_modules",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{today_events,preparation,weather,favor}",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_user_briefing_settings_user_id",
        "user_briefing_settings",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_briefing_settings_user_id", table_name="user_briefing_settings")
    op.drop_table("user_briefing_settings")
