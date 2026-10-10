"""add city column to curated_events

Revision ID: 067
Revises: 066_add_association_unique_constraint
Create Date: 2026-02-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "067"
down_revision = "066_assoc_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "curated_events",
        sa.Column(
            "city",
            sa.String(100),
            nullable=True,
            comment="City-level location for trip grouping (LLM normalized)",
        ),
    )
    op.create_index("ix_curated_events_city", "curated_events", ["city"])


def downgrade() -> None:
    op.drop_index("ix_curated_events_city", table_name="curated_events")
    op.drop_column("curated_events", "city")
