"""Add GIN index on memory_insights.related_member_ids.

Revision ID: 113
Revises: 112

Supports efficient containment queries (`@>`) for fetching insights
related to a specific family member.
"""

from alembic import op


revision = "113"
down_revision = "112"


def upgrade() -> None:
    op.create_index(
        "ix_memory_insights_member_ids",
        "memory_insights",
        ["related_member_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_memory_insights_member_ids", table_name="memory_insights")
