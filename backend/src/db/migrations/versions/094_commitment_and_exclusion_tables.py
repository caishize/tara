"""Create commitment_items and exclusion_rules tables.

Revision ID: 094
Revises: 093

commitment_items: Persists tracked commitments extracted from conversations,
    with social intent classification and follow-up scheduling.

exclusion_rules: Entity-level exclusion rules for the ContextAssembler
    pipeline, supporting cooldown-based expiration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "094"
down_revision = "093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- commitment_items --
    op.create_table(
        "commitment_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("commitment_type", sa.String(30), nullable=False),
        sa.Column("who", sa.String(200), nullable=False),
        sa.Column("what", sa.Text, nullable=False),
        sa.Column("to_whom", sa.String(200), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("social_intent", sa.String(30), nullable=True),
        sa.Column("tracking_score", sa.Float, server_default="0.5"),
        sa.Column("follow_up_count", sa.Integer, server_default="0"),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_commitment_items_user_id", "commitment_items", ["user_id"])
    op.create_index("ix_commitment_items_family_id", "commitment_items", ["family_id"])
    op.create_index("ix_commitment_items_status", "commitment_items", ["status"])
    op.create_index(
        "ix_commitment_items_next_follow_up",
        "commitment_items",
        ["next_follow_up_at"],
        postgresql_where=sa.text("next_follow_up_at IS NOT NULL"),
    )

    # -- exclusion_rules --
    op.create_table(
        "exclusion_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_exclusion_rules_user_id", "exclusion_rules", ["user_id"])
    op.create_index("ix_exclusion_rules_entity_id", "exclusion_rules", ["entity_id"])
    op.create_index(
        "ix_exclusion_rules_user_entity",
        "exclusion_rules",
        ["user_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_exclusion_rules_user_entity", table_name="exclusion_rules")
    op.drop_index("ix_exclusion_rules_entity_id", table_name="exclusion_rules")
    op.drop_index("ix_exclusion_rules_user_id", table_name="exclusion_rules")
    op.drop_table("exclusion_rules")

    op.drop_index("ix_commitment_items_next_follow_up", table_name="commitment_items")
    op.drop_index("ix_commitment_items_status", table_name="commitment_items")
    op.drop_index("ix_commitment_items_family_id", table_name="commitment_items")
    op.drop_index("ix_commitment_items_user_id", table_name="commitment_items")
    op.drop_table("commitment_items")
