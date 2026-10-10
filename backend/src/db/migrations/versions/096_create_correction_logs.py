"""Create correction_logs table for trust repair tracking.

Revision ID: 096
Revises: 095

Stores user corrections so the assistant can proactively reference
past mistakes, building trust via the repair cycle.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "096"
down_revision = "095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "correction_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("original_text", sa.Text, nullable=False),
        sa.Column("corrected_text", sa.Text, nullable=False),
        sa.Column("context", sa.Text, nullable=True),
        sa.Column("is_surfaced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("surfaced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_correction_logs_user_id", "correction_logs", ["user_id"])
    op.create_index(
        "ix_correction_logs_user_unsurfaced",
        "correction_logs",
        ["user_id", "is_surfaced"],
        postgresql_where=sa.text("is_surfaced = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_correction_logs_user_unsurfaced", table_name="correction_logs")
    op.drop_index("ix_correction_logs_user_id", table_name="correction_logs")
    op.drop_table("correction_logs")
