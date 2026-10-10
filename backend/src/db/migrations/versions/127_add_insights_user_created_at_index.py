"""Add composite index (user_id, created_at) on insights table.

Revision ID: 127
Revises: 126

Required by PLAN-007: timeline date filter needs this index to avoid
full-table scans on the insights table when filtering by created_at range.
"""

from alembic import op


revision = "127"
down_revision = "126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_insights_user_id_created_at",
        "insights",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_insights_user_id_created_at", table_name="insights")
