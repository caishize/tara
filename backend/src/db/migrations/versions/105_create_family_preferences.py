"""Create family_preferences table.

Revision ID: 105
Revises: 104

Stores per-family personalization weights learned from user feedback.
Used by HybridPriorityEngine, SecretaryOrchestrator, RecommendationEngine,
and DensityController at curation time.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "105"
down_revision = "104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_families_table = inspector.has_table("families")

    op.create_table(
        "family_preferences",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "family_id",
            UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        # Priority dimension weights
        sa.Column(
            "priority_weights",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Event type severity overrides
        sa.Column(
            "event_type_severity",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Buffer time preferences
        sa.Column(
            "buffer_minutes",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Recommendation type weights
        sa.Column(
            "recommendation_weights",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Suppressed recommendation types
        sa.Column(
            "suppressed_types",
            JSONB(),
            nullable=False,
            server_default="[]",
        ),
        # Association type effectiveness
        sa.Column(
            "association_weights",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Info density preferences
        sa.Column(
            "density_preferences",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Secretary annotation preferences
        sa.Column(
            "annotation_preferences",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        # Learning metadata
        sa.Column("last_learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "learning_events_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Legacy databases may not have a `families` table.
    # Keep migration forward-compatible by adding FK only when possible.
    if has_families_table:
        op.create_foreign_key(
            "fk_family_preferences_family_id_families",
            source_table="family_preferences",
            referent_table="families",
            local_cols=["family_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )

    op.create_index(
        "ix_family_preferences_family_id",
        "family_preferences",
        ["family_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_family_preferences_family_id", table_name="family_preferences"
    )
    op.drop_table("family_preferences")
