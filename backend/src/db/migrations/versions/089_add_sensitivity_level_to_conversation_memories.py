"""Add sensitivity_level column to conversation_memories table.

Revision ID: 089
Revises: 088
"""

from alembic import op
import sqlalchemy as sa


revision = "089"
down_revision = "088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_memories",
        sa.Column(
            "sensitivity_level",
            sa.String(20),
            nullable=False,
            server_default="public",
        ),
    )
    op.create_index(
        "ix_conv_memories_user_sensitivity",
        "conversation_memories",
        ["user_id", "sensitivity_level"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conv_memories_user_sensitivity",
        table_name="conversation_memories",
    )
    op.drop_column("conversation_memories", "sensitivity_level")
