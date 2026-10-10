"""Add confidence_score column to memory_summaries.

Revision ID: 099
Revises: 098

Stores a computed confidence score (0.0-1.0) for each memory summary,
based on source memory count, agreement, and recency.
"""

from alembic import op
import sqlalchemy as sa


revision = "099"
down_revision = "098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_summaries",
        sa.Column("confidence_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memory_summaries", "confidence_score")
