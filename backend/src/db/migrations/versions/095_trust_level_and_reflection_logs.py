"""Add trust_level to members and create reflection_logs table.

Revision ID: 095
Revises: 094

Adds trust_level (L0-L3) and trust_updated_at columns to the members table,
and creates the reflection_logs table for tracking trust transitions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "095"
down_revision = "094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Add trust columns to members --
    op.add_column(
        "members",
        sa.Column("trust_level", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "members",
        sa.Column("trust_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- Create reflection_logs table --
    op.create_table(
        "reflection_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("trust_before", sa.Integer, nullable=False),
        sa.Column("trust_after", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_reflection_logs_user_id", "reflection_logs", ["user_id"])
    op.create_index(
        "ix_reflection_logs_user_event",
        "reflection_logs",
        ["user_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_reflection_logs_user_event", table_name="reflection_logs")
    op.drop_index("ix_reflection_logs_user_id", table_name="reflection_logs")
    op.drop_table("reflection_logs")

    op.drop_column("members", "trust_updated_at")
    op.drop_column("members", "trust_level")
