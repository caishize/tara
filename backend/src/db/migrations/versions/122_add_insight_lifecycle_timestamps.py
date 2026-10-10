"""Add lifecycle timestamps to unified insights table.

Adds activated_at, acknowledged_at, acted_at, dismissed_at columns
to record when each status transition occurred — useful for analytics
and debugging.

Revision ID: 122
Revises: 121
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "122"
down_revision = "121"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "insights",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "insights",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "insights",
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "insights",
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("insights", "dismissed_at")
    op.drop_column("insights", "acted_at")
    op.drop_column("insights", "acknowledged_at")
    op.drop_column("insights", "activated_at")
