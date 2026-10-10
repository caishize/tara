"""Unified insight lifecycle: source traceability, promotion tracking, consolidation.

Revision ID: 117
Revises: 116

Adds source traceability columns to user_insights (source_type, source_id, promoted_at)
with a unique partial index for active dedup. Adds promotion tracking to
event_associations and memory_insights. Adds consolidation timestamps to
user_insight_settings. Backfills missing expires_at on memory_insights and marks
already-expired rows as dismissed.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "117"
down_revision = "116"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1.1  user_insights — source traceability
    # ------------------------------------------------------------------
    op.add_column(
        "user_insights",
        sa.Column(
            "source_type",
            sa.String(30),
            nullable=True,
            server_default="briefing",
            comment="Origin: briefing | trip | association | memory",
        ),
    )
    op.add_column(
        "user_insights",
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "user_insights",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Unique partial index: one active insight per (user, dedup_key)
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_user_insights_active_dedup
        ON user_insights (user_id, semantic_dedup_key)
        WHERE semantic_dedup_key IS NOT NULL
          AND status NOT IN ('dismissed', 'actioned')
    """))

    # ------------------------------------------------------------------
    # 1.2  event_associations — promotion tracking
    # ------------------------------------------------------------------
    op.add_column(
        "event_associations",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "event_associations",
        sa.Column(
            "promoted_insight_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user_insights.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "event_associations",
        sa.Column("dismiss_cascaded_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # 1.3  memory_insights — promotion tracking
    # ------------------------------------------------------------------
    op.add_column(
        "memory_insights",
        sa.Column(
            "is_promoted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "memory_insights",
        sa.Column(
            "promoted_insight_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user_insights.id"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 1.4  user_insight_settings — consolidation timestamps
    # ------------------------------------------------------------------
    op.add_column(
        "user_insight_settings",
        sa.Column("last_consolidation_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_insight_settings",
        sa.Column(
            "last_association_promotion_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 1.5  Data cleanup
    # ------------------------------------------------------------------
    conn = op.get_bind()

    # Backfill source_type for existing user_insights rows (server_default only applies to INSERTs)
    conn.execute(sa.text("""
        UPDATE user_insights SET source_type = 'briefing'
        WHERE source_type IS NULL
    """))

    # Backfill NULL expires_at on memory_insights
    conn.execute(sa.text("""
        UPDATE memory_insights
        SET expires_at = created_at + INTERVAL '14 days'
        WHERE expires_at IS NULL
          AND status IN ('pending', 'shown')
    """))

    # Mark already-expired rows as dismissed
    conn.execute(sa.text("""
        UPDATE memory_insights
        SET status = 'dismissed'
        WHERE expires_at IS NOT NULL
          AND expires_at < NOW()
          AND status IN ('pending', 'shown')
    """))


def downgrade() -> None:
    # 1.5  Data cleanup — not reversible (no-op)

    # 1.4  user_insight_settings
    op.drop_column("user_insight_settings", "last_association_promotion_at")
    op.drop_column("user_insight_settings", "last_consolidation_at")

    # 1.3  memory_insights
    op.drop_column("memory_insights", "promoted_insight_id")
    op.drop_column("memory_insights", "is_promoted")

    # 1.2  event_associations
    op.drop_column("event_associations", "dismiss_cascaded_at")
    op.drop_column("event_associations", "promoted_insight_id")
    op.drop_column("event_associations", "promoted_at")

    # 1.1  user_insights
    op.drop_index(
        "uq_user_insights_active_dedup",
        table_name="user_insights",
    )
    op.drop_column("user_insights", "promoted_at")
    op.drop_column("user_insights", "source_id")
    op.drop_column("user_insights", "source_type")
