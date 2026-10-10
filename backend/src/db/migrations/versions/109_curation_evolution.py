"""Curation evolution: preference signals, preference rules, fatigue state, preparation lead days.

Revision ID: 109
Revises: 108

Adds:
  - preference_signals: collects user preference signals (defer, never, dismiss) for batch extraction
  - user_preference_rules: LLM-extracted conditional suppression rules from preference signals
  - family_preferences.fatigue_state: JSONB for active-load-reduction fatigue tracking
  - important_dates.preparation_lead_days: per-date preparation lead days override
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import inspect as sa_inspect


revision = "109"
down_revision = "108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 1. Create preference_signals table (E2 - Preference Extraction)
    # ------------------------------------------------------------------
    if "preference_signals" not in existing_tables:
        op.create_table(
            "preference_signals",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("family_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "signal_type",
                sa.String(32),
                nullable=False,
                comment="defer, never, dismiss, too_frequent, not_relevant",
            ),
            sa.Column(
                "source_type",
                sa.String(32),
                nullable=False,
                comment="insight, suggestion, association, curation",
            ),
            sa.Column("source_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "source_context",
                JSONB,
                nullable=False,
                server_default="{}",
                comment="Snapshot of source metadata at signal time",
            ),
            sa.Column("user_reason", sa.Text(), nullable=True),
            sa.Column(
                "category_key",
                sa.String(128),
                nullable=False,
                comment="Normalized category for batch grouping",
            ),
            sa.Column(
                "processed",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE",
            ),
        )
        op.create_index(
            "ix_preference_signals_user_category",
            "preference_signals",
            ["user_id", "category_key", "processed"],
        )

    # ------------------------------------------------------------------
    # 2. Create user_preference_rules table (E2 - Preference Extraction)
    # ------------------------------------------------------------------
    if "user_preference_rules" not in existing_tables:
        op.create_table(
            "user_preference_rules",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("family_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "condition_event_type",
                sa.String(64),
                nullable=True,
                comment="Matches curated_event.event_type",
            ),
            sa.Column(
                "condition_suggestion_type",
                sa.String(64),
                nullable=True,
                comment="Matches insight_type or suggestion category",
            ),
            sa.Column(
                "condition_person_id",
                UUID(as_uuid=True),
                nullable=True,
                comment="Matches target member_id",
            ),
            sa.Column(
                "condition_location",
                sa.String(128),
                nullable=True,
                comment="Matches event location",
            ),
            sa.Column(
                "action",
                sa.String(32),
                nullable=False,
                comment="suppress, reduce_frequency, deprioritize",
            ),
            sa.Column(
                "confidence",
                sa.Float(),
                nullable=False,
                comment="Extraction confidence from LLM",
            ),
            sa.Column(
                "explanation",
                sa.Text(),
                nullable=False,
                comment="LLM-generated human-readable explanation",
            ),
            sa.Column(
                "scope",
                sa.String(32),
                nullable=False,
                comment="user, family",
            ),
            sa.Column(
                "source_signal_count",
                sa.Integer(),
                nullable=False,
                server_default="3",
                comment="Number of signals that produced this rule",
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE",
            ),
        )
        op.create_index(
            "ix_preference_rules_user_active",
            "user_preference_rules",
            ["user_id", "is_active"],
        )

    # ------------------------------------------------------------------
    # 3. Add fatigue_state JSONB column to family_preferences (E5)
    # ------------------------------------------------------------------
    if "family_preferences" in existing_tables:
        existing_fp_columns = {
            c["name"] for c in inspector.get_columns("family_preferences")
        }
        if "fatigue_state" not in existing_fp_columns:
            op.add_column(
                "family_preferences",
                sa.Column(
                    "fatigue_state",
                    JSONB,
                    nullable=True,
                    server_default="{}",
                    comment="Active-load-reduction fatigue tracking state",
                ),
            )

    # ------------------------------------------------------------------
    # 4. Add preparation_lead_days to important_dates (E7)
    # ------------------------------------------------------------------
    if "important_dates" in existing_tables:
        existing_id_columns = {
            c["name"] for c in inspector.get_columns("important_dates")
        }
        if "preparation_lead_days" not in existing_id_columns:
            op.add_column(
                "important_dates",
                sa.Column(
                    "preparation_lead_days",
                    sa.Integer(),
                    nullable=True,
                    server_default="7",
                    comment="Per-date preparation lead days override",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 4. Reverse: remove preparation_lead_days from important_dates
    # ------------------------------------------------------------------
    if "important_dates" in existing_tables:
        existing_id_columns = {
            c["name"] for c in inspector.get_columns("important_dates")
        }
        if "preparation_lead_days" in existing_id_columns:
            op.drop_column("important_dates", "preparation_lead_days")

    # ------------------------------------------------------------------
    # 3. Reverse: remove fatigue_state from family_preferences
    # ------------------------------------------------------------------
    if "family_preferences" in existing_tables:
        existing_fp_columns = {
            c["name"] for c in inspector.get_columns("family_preferences")
        }
        if "fatigue_state" in existing_fp_columns:
            op.drop_column("family_preferences", "fatigue_state")

    # ------------------------------------------------------------------
    # 2. Reverse: drop user_preference_rules table
    # ------------------------------------------------------------------
    if "user_preference_rules" in existing_tables:
        op.drop_table("user_preference_rules")

    # ------------------------------------------------------------------
    # 1. Reverse: drop preference_signals table
    # ------------------------------------------------------------------
    if "preference_signals" in existing_tables:
        op.drop_table("preference_signals")
