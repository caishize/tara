"""Insight engine v2: new columns, enums, tracked_threads table, delivery waves.

Revision ID: 125
Revises: 124

Adds:
  - insights.context_hint (TEXT)
  - insights.best_action_window (VARCHAR(100))
  - insights.information_tier (VARCHAR(20), default 'L2_FORMAL')
  - insights.generation_level (VARCHAR(10), default 'L2')
  - user_insight_settings.delivery_waves (JSONB)
  - tracked_threads table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "125"
down_revision = "124"
branch_labels = None
depends_on = None


DEFAULT_DELIVERY_WAVES = (
    '{"morning":{"enabled":true,"hour":7,"max_items":3},'
    '"noon":{"enabled":true,"hour":12,"max_items":2},'
    '"evening":{"enabled":true,"hour":17,"max_items":2},'
    '"night":{"enabled":true,"hour":21,"max_items":3}}'
)


def upgrade() -> None:
    # --- insights table: new columns ---
    op.add_column("insights", sa.Column(
        "context_hint", sa.Text(), nullable=True,
        comment="WHY this insight matters, e.g. '因为妈妈生日还有12天'",
    ))
    op.add_column("insights", sa.Column(
        "best_action_window", sa.String(100), nullable=True,
        comment="Optimal action timing, e.g. '本周末前'",
    ))
    op.add_column("insights", sa.Column(
        "information_tier", sa.String(20), nullable=False,
        server_default="L2_FORMAL",
        comment="L0_AUTO, L1_PASSIVE, L2_FORMAL",
    ))
    op.add_column("insights", sa.Column(
        "generation_level", sa.String(10), nullable=False,
        server_default="L2",
        comment="L1 (rule), L2 (Haiku), L3 (Sonnet)",
    ))

    # Index for filtering by tier in query service
    op.create_index(
        "ix_insights_tier",
        "insights",
        ["user_id", "information_tier"],
        postgresql_where=sa.text("status IN ('pending', 'active')"),
    )

    # --- user_insight_settings: delivery waves ---
    op.add_column("user_insight_settings", sa.Column(
        "delivery_waves",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.literal_column(f"'{DEFAULT_DELIVERY_WAVES}'::jsonb"),
        comment="Four-wave delivery config: morning/noon/evening/night",
    ))

    # --- tracked_threads table ---
    op.create_table(
        "tracked_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("thread_type", sa.String(30), nullable=False,
                  comment="project, relationship, commitment, preparation"),
        sa.Column("status", sa.String(20), nullable=False, server_default="monitoring",
                  comment="monitoring, approaching, active, resolved"),
        sa.Column("entity_refs", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'[]'::jsonb"),
                  comment="List[EntitySpec] as JSON"),
        sa.Column("checkpoints", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'[]'::jsonb"),
                  comment="Ordered checkpoint list"),
        sa.Column("context_log", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'[]'::jsonb"),
                  comment="Chronological context entries"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_tracked_threads_user_status",
                     "tracked_threads", ["user_id", "status"])
    op.create_index("ix_tracked_threads_family",
                     "tracked_threads", ["family_id", "status"])
    op.create_index("ix_tracked_threads_entity_refs",
                     "tracked_threads", ["entity_refs"],
                     postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("tracked_threads")

    op.drop_column("user_insight_settings", "delivery_waves")

    op.drop_index("ix_insights_tier", table_name="insights")
    op.drop_column("insights", "generation_level")
    op.drop_column("insights", "information_tier")
    op.drop_column("insights", "best_action_window")
    op.drop_column("insights", "context_hint")
