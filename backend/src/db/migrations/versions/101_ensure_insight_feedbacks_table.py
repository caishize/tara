"""Ensure insight_feedbacks table exists.

Revision ID: 101
Revises: 100

Migration 046 may have been skipped during initial setup.
This migration re-creates the table if it doesn't exist.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "101"
down_revision = "100"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename = :t)"
        ),
        {"t": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    connection = op.get_bind()
    if _table_exists(connection, "insight_feedbacks"):
        return

    op.create_table(
        "insight_feedbacks",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("insight_id", UUID(as_uuid=True), nullable=False),
        sa.Column("feedback_type", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("source_memory_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["insight_id"], ["memory_insights.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_memory_id"],
            ["conversation_memories.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_insight_feedback_user", "insight_feedbacks", ["user_id"]
    )
    op.create_index(
        "ix_insight_feedback_insight", "insight_feedbacks", ["insight_id"]
    )
    op.create_index(
        "ix_insight_feedback_type", "insight_feedbacks", ["feedback_type"]
    )


def downgrade() -> None:
    connection = op.get_bind()
    if _table_exists(connection, "insight_feedbacks"):
        op.drop_table("insight_feedbacks")
