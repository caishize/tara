"""create device_tokens table for FCM push notifications

Revision ID: 064_create_device_tokens
Revises: 063_fix_date_reminders_timezone
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "064_create_device_tokens"
down_revision = "063_fix_date_reminders_timezone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("fcm_token", sa.String(500), nullable=False, unique=True),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_device_tokens_user_active",
        "device_tokens",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_tokens_user_active", table_name="device_tokens")
    op.drop_table("device_tokens")
