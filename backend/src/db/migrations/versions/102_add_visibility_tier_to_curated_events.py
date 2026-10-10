"""Add visibility_tier column to curated_events.

Revision ID: 102
Revises: 101

Adds a visibility_tier column (focus | standard | detail) to curated_events
for display prioritization on the timeline.
"""

from alembic import op
import sqlalchemy as sa


revision = "102"
down_revision = "101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "curated_events",
        sa.Column(
            "visibility_tier",
            sa.String(20),
            nullable=False,
            server_default="standard",
            comment="focus | standard | detail",
        ),
    )
    op.create_index(
        "ix_curated_events_visibility_tier",
        "curated_events",
        ["visibility_tier"],
    )


def downgrade() -> None:
    op.drop_index("ix_curated_events_visibility_tier", table_name="curated_events")
    op.drop_column("curated_events", "visibility_tier")
