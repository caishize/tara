"""create social_intents table

Revision ID: 070
Revises: 069
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_intents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        # Intent content
        sa.Column("intent_type", sa.String(50), nullable=False),
        sa.Column("target_person_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_person_name", sa.String(200), nullable=True),
        sa.Column("action_description", sa.Text(), nullable=False),
        # Trigger conditions
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_location", sa.String(200), nullable=True, index=True),
        sa.Column("trigger_date", sa.Date(), nullable=True, index=True),
        sa.Column("trigger_event_type", sa.String(50), nullable=True),
        # Metadata
        sa.Column(
            "source_memory_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversation_memories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_social_intents_family_status",
        "social_intents",
        ["family_id", "status"],
    )
    op.create_index(
        "ix_social_intents_trigger_location_status",
        "social_intents",
        ["trigger_location", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_social_intents_trigger_location_status", table_name="social_intents")
    op.drop_index("ix_social_intents_family_status", table_name="social_intents")
    op.drop_table("social_intents")
