"""Allow NULL for event_associations.title and event_associations.reason.

Revision ID: 126
Revises: 125

Rule-engine generated associations have no LLM-produced title/reason.
The presentation layer already has fallback logic (present_association_copy)
to generate display text when these fields are NULL.
"""

from alembic import op
import sqlalchemy as sa


revision = "126"
down_revision = "125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "event_associations", "title",
        existing_type=sa.String(200),
        nullable=True,
    )
    op.alter_column(
        "event_associations", "reason",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE event_associations SET title = '' WHERE title IS NULL")
    op.execute("UPDATE event_associations SET reason = '' WHERE reason IS NULL")
    op.alter_column(
        "event_associations", "title",
        existing_type=sa.String(200),
        nullable=False,
    )
    op.alter_column(
        "event_associations", "reason",
        existing_type=sa.Text(),
        nullable=False,
    )
