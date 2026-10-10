"""Add GIN index on memory_insights.related_trip_ids for insight lifecycle GC.

Revision ID: 110
Revises: 109

Adds:
  - GIN index ix_memory_insights_trip_ids on memory_insights.related_trip_ids
    for efficient array-containment queries used in trip-correlated insight lookup.
"""

from alembic import op


revision = "110"
down_revision = "109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_memory_insights_trip_ids",
        "memory_insights",
        ["related_trip_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_memory_insights_trip_ids",
        table_name="memory_insights",
    )
