"""Curation optimization - trip completeness checks, meal window inference, association-driven actions.

Revision ID: 108
Revises: 107

Adds:
  - trip_completeness_checks: caches LLM completeness check results per trip input hash
  - family_preferences.inferred_meal_windows: learned meal-time windows per family
  - family_preferences.meal_windows_inferred_at: timestamp of last meal window inference
  - pending_actions.association_id: links a pending action back to the EventAssociation that triggered it
  - pending_actions.draft_content: stores AI-drafted message/content for the action
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "108"
down_revision = "107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 1. Create trip_completeness_checks table
    # ------------------------------------------------------------------
    if "trip_completeness_checks" not in existing_tables:
        op.create_table(
            "trip_completeness_checks",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "trip_id",
                UUID(as_uuid=True),
                sa.ForeignKey("trips.trip_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("family_id", UUID(as_uuid=True), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("result", JSONB, nullable=False),
            sa.Column(
                "checked_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.UniqueConstraint("trip_id", "input_hash", name="uq_trip_completeness_trip_hash"),
        )
        op.create_index(
            "ix_trip_completeness_checks_trip_id",
            "trip_completeness_checks",
            ["trip_id"],
        )
        op.create_index(
            "ix_trip_completeness_checks_family_id",
            "trip_completeness_checks",
            ["family_id"],
        )

    # ------------------------------------------------------------------
    # 2. Add inferred meal-window columns to family_preferences
    # ------------------------------------------------------------------
    existing_fp_columns = {c["name"] for c in inspector.get_columns("family_preferences")}

    if "inferred_meal_windows" not in existing_fp_columns:
        op.add_column(
            "family_preferences",
            sa.Column("inferred_meal_windows", JSONB, nullable=True),
        )

    if "meal_windows_inferred_at" not in existing_fp_columns:
        op.add_column(
            "family_preferences",
            sa.Column("meal_windows_inferred_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ------------------------------------------------------------------
    # 3. Add association_id and draft_content columns to pending_actions
    # ------------------------------------------------------------------
    existing_pa_columns = {c["name"] for c in inspector.get_columns("pending_actions")}

    if "association_id" not in existing_pa_columns:
        op.add_column(
            "pending_actions",
            sa.Column(
                "association_id",
                UUID(as_uuid=True),
                sa.ForeignKey("event_associations.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if "draft_content" not in existing_pa_columns:
        op.add_column(
            "pending_actions",
            sa.Column("draft_content", sa.Text(), nullable=True),
        )

    # Create index on association_id if it doesn't exist yet
    existing_pa_indexes = {idx["name"] for idx in inspector.get_indexes("pending_actions")}
    if "ix_pending_actions_association_id" not in existing_pa_indexes:
        op.create_index(
            "ix_pending_actions_association_id",
            "pending_actions",
            ["association_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------
    # 3. Reverse: remove index and columns from pending_actions
    # ------------------------------------------------------------------
    existing_pa_indexes = {idx["name"] for idx in inspector.get_indexes("pending_actions")}
    if "ix_pending_actions_association_id" in existing_pa_indexes:
        op.drop_index("ix_pending_actions_association_id", table_name="pending_actions")

    existing_pa_columns = {c["name"] for c in inspector.get_columns("pending_actions")}
    if "draft_content" in existing_pa_columns:
        op.drop_column("pending_actions", "draft_content")
    if "association_id" in existing_pa_columns:
        op.drop_column("pending_actions", "association_id")

    # ------------------------------------------------------------------
    # 2. Reverse: remove columns from family_preferences
    # ------------------------------------------------------------------
    existing_fp_columns = {c["name"] for c in inspector.get_columns("family_preferences")}
    if "meal_windows_inferred_at" in existing_fp_columns:
        op.drop_column("family_preferences", "meal_windows_inferred_at")
    if "inferred_meal_windows" in existing_fp_columns:
        op.drop_column("family_preferences", "inferred_meal_windows")

    # ------------------------------------------------------------------
    # 1. Reverse: drop trip_completeness_checks table
    # ------------------------------------------------------------------
    existing_tables = inspector.get_table_names()
    if "trip_completeness_checks" in existing_tables:
        op.drop_table("trip_completeness_checks")
