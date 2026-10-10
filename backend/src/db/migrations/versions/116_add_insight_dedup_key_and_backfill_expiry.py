"""Add semantic_dedup_key to user_insights and backfill expires_at.

Revision ID: 116
Revises: 115

Adds semantic_dedup_key VARCHAR(255) column (nullable, indexed) for entity-level
deduplication. Backfills expires_at = NOW() + 14 days for existing rows where
expires_at IS NULL, excluding rows created in the last hour (race condition protection).
"""

from alembic import op
import sqlalchemy as sa


revision = "116"
down_revision = "115"


def upgrade() -> None:
    # Step 1: Add semantic_dedup_key column
    op.add_column(
        "user_insights",
        sa.Column(
            "semantic_dedup_key",
            sa.String(255),
            nullable=True,
            comment="Entity dedup key: {insight_type}:{entity_type}:{entity_id}",
        ),
    )
    op.create_index(
        "ix_user_insights_semantic_dedup_key",
        "user_insights",
        ["semantic_dedup_key"],
    )

    # Step 2: Backfill expires_at for existing rows missing it.
    # Exclude rows created in the last hour to avoid race conditions with
    # concurrent insight generation.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE user_insights
        SET expires_at = NOW() + INTERVAL '14 days'
        WHERE expires_at IS NULL
          AND created_at < NOW() - INTERVAL '1 hour'
    """))


def downgrade() -> None:
    op.drop_index("ix_user_insights_semantic_dedup_key", table_name="user_insights")
    op.drop_column("user_insights", "semantic_dedup_key")
