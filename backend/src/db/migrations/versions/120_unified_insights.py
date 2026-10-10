"""Unified insights — single table replacing scattered insight sources.

Revision ID: 120
Revises: 119

Adds:
  - insights: unified insight table with delivery tracking, dedup, lifecycle fields
  - insight_entities: many-to-many linking insights to domain entities with roles
  - pending_actions.source_entity_id: optional link to the insight entity that spawned the action
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "120"
down_revision = "119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 1. Create insights table
    # ------------------------------------------------------------------
    if "insights" not in existing_tables:
        op.create_table(
            "insights",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("family_id", UUID(as_uuid=True), nullable=False),
            sa.Column("insight_type", sa.String(30), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "importance",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("50"),
            ),
            sa.Column(
                "urgency",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("50"),
            ),
            sa.Column(
                "source",
                sa.String(30),
                nullable=False,
                server_default=sa.text("'scheduled'"),
            ),
            sa.Column(
                "source_context",
                JSONB,
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("feedback", sa.String(20), nullable=True),
            sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "feedback_source",
                sa.String(30),
                nullable=False,
                server_default=sa.text("'user'"),
            ),
            sa.Column("suggested_action", sa.Text(), nullable=True),
            sa.Column("action_options", JSONB, nullable=True),
            sa.Column("dedup_key", sa.String(255), nullable=True),
            sa.Column("shown_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "delivered_via_briefing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "delivered_via_sidekick",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "delivered_via_kanban",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "delivered_via_push",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("regen_suppressed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            # CHECK constraints
            sa.CheckConstraint(
                "insight_type IN ('time', 'relationship', 'favor', 'health', 'memory', 'efficiency', 'finance')",
                name="ck_insights_insight_type",
            ),
            sa.CheckConstraint(
                "source IN ('scheduled', 'trip_event', 'reflection', 'manual')",
                name="ck_insights_source",
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'active', 'acknowledged', 'acted', 'dismissed', 'expired')",
                name="ck_insights_status",
            ),
            sa.CheckConstraint(
                "importance >= 0 AND importance <= 100",
                name="ck_insights_importance_range",
            ),
            sa.CheckConstraint(
                "urgency >= 0 AND urgency <= 100",
                name="ck_insights_urgency_range",
            ),
        )

        # Kanban board query: active insights sorted by importance/urgency
        op.create_index(
            "ix_insights_kanban",
            "insights",
            ["user_id", sa.text("importance DESC"), sa.text("urgency DESC"), sa.text("created_at DESC")],
            postgresql_where=sa.text("status IN ('pending', 'active')"),
        )

        # Briefing query: high-importance pending insights
        op.create_index(
            "ix_insights_briefing",
            "insights",
            ["user_id", sa.text("importance DESC")],
            postgresql_where=sa.text("status = 'pending' AND importance >= 60"),
        )

        # Dedup: unique active dedup_key per user
        op.create_index(
            "ix_insights_dedup",
            "insights",
            ["user_id", "dedup_key"],
            unique=True,
            postgresql_where=sa.text("dedup_key IS NOT NULL AND status NOT IN ('dismissed', 'acted', 'expired')"),
        )

        # Family-level queries
        op.create_index(
            "ix_insights_family",
            "insights",
            ["family_id", "status"],
        )

        # Lifecycle management (expiry, snooze, regen suppression)
        op.create_index(
            "ix_insights_lifecycle",
            "insights",
            ["expires_at", "snoozed_until", "regen_suppressed_until"],
            postgresql_where=sa.text("status IN ('pending', 'active', 'dismissed')"),
        )

    # ------------------------------------------------------------------
    # 2. Create insight_entities table
    # ------------------------------------------------------------------
    if "insight_entities" not in existing_tables:
        op.create_table(
            "insight_entities",
            sa.Column(
                "insight_id",
                UUID(as_uuid=True),
                sa.ForeignKey("insights.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("entity_type", sa.String(30), nullable=False),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "role",
                sa.String(20),
                nullable=False,
                server_default=sa.text("'related'"),
            ),
            sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("insight_id", "entity_type", "entity_id"),
            sa.CheckConstraint(
                "entity_type IN ('person', 'trip', 'event', 'important_date', 'event_association', 'favor', 'commitment', 'memory')",
                name="ck_ie_entity_type",
            ),
            sa.CheckConstraint(
                "role IN ('primary', 'related', 'mentioned', 'source')",
                name="ck_ie_role",
            ),
            sa.CheckConstraint(
                "adopted_at IS NULL OR role IN ('primary', 'related')",
                name="ck_ie_adopted_role",
            ),
            sa.CheckConstraint(
                "done_at IS NULL OR adopted_at IS NOT NULL",
                name="ck_ie_done_requires_adopted",
            ),
        )

        # Entity lookup
        op.create_index(
            "ix_ie_entity",
            "insight_entities",
            ["entity_type", "entity_id"],
        )

        # Source entity lookup
        op.create_index(
            "ix_ie_source",
            "insight_entities",
            ["entity_type", "entity_id"],
            postgresql_where=sa.text("role = 'source'"),
        )

    # ------------------------------------------------------------------
    # 3. Add source_entity_id to pending_actions
    # ------------------------------------------------------------------
    existing_pa_columns = {c["name"] for c in inspector.get_columns("pending_actions")}

    if "source_entity_id" not in existing_pa_columns:
        op.add_column(
            "pending_actions",
            sa.Column("source_entity_id", UUID(as_uuid=True), nullable=True),
        )

    existing_pa_indexes = {idx["name"] for idx in inspector.get_indexes("pending_actions")}
    if "ix_pending_actions_source_entity_id" not in existing_pa_indexes:
        op.create_index(
            "ix_pending_actions_source_entity_id",
            "pending_actions",
            ["source_entity_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------
    # 3. Reverse: remove source_entity_id from pending_actions
    # ------------------------------------------------------------------
    existing_pa_indexes = {idx["name"] for idx in inspector.get_indexes("pending_actions")}
    if "ix_pending_actions_source_entity_id" in existing_pa_indexes:
        op.drop_index("ix_pending_actions_source_entity_id", table_name="pending_actions")

    existing_pa_columns = {c["name"] for c in inspector.get_columns("pending_actions")}
    if "source_entity_id" in existing_pa_columns:
        op.drop_column("pending_actions", "source_entity_id")

    # ------------------------------------------------------------------
    # 2. Reverse: drop insight_entities table
    # ------------------------------------------------------------------
    existing_tables = inspector.get_table_names()
    if "insight_entities" in existing_tables:
        op.drop_table("insight_entities")

    # ------------------------------------------------------------------
    # 1. Reverse: drop insights table
    # ------------------------------------------------------------------
    if "insights" in existing_tables:
        op.drop_table("insights")
