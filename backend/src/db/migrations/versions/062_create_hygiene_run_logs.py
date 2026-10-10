"""create hygiene_run_logs table

Revision ID: 062_create_hygiene_run_logs
Revises: 061_create_users_table
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "062_create_hygiene_run_logs"
down_revision = "061_create_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hygiene_run_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("inactive_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancelled_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dismissed_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_purged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("hygiene_run_logs")
