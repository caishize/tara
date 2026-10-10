"""Drop deprecated insight promotion/cascade columns.

Removes EA columns (promoted_at, promoted_insight_id, dismiss_cascaded_at)
and MemoryInsight.promoted_insight_id that pointed to the old user_insights
table.  These are replaced by the unified insight_entities association table.

Revision ID: 123
Revises: 122
Create Date: 2026-03-11
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "123"
down_revision = "122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- EventAssociation: drop deprecated columns ---
    # Drop FK constraint first, then the column
    op.drop_constraint(
        "event_associations_promoted_insight_id_fkey",
        "event_associations",
        type_="foreignkey",
    )
    op.drop_column("event_associations", "promoted_insight_id")
    op.drop_column("event_associations", "promoted_at")
    op.drop_column("event_associations", "dismiss_cascaded_at")

    # --- MemoryInsight: drop deprecated FK to user_insights ---
    op.drop_constraint(
        "memory_insights_promoted_insight_id_fkey",
        "memory_insights",
        type_="foreignkey",
    )
    op.drop_column("memory_insights", "promoted_insight_id")


def downgrade() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    # --- MemoryInsight: restore promoted_insight_id ---
    op.add_column(
        "memory_insights",
        sa.Column("promoted_insight_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "memory_insights_promoted_insight_id_fkey",
        "memory_insights",
        "user_insights",
        ["promoted_insight_id"],
        ["id"],
    )

    # --- EventAssociation: restore deprecated columns ---
    op.add_column(
        "event_associations",
        sa.Column("dismiss_cascaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "event_associations",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "event_associations",
        sa.Column("promoted_insight_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "event_associations_promoted_insight_id_fkey",
        "event_associations",
        "user_insights",
        ["promoted_insight_id"],
        ["id"],
    )
