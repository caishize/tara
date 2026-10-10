"""Add related_important_date_id to user_insights.

Revision ID: 106
Revises: 105

Adds a first-class anchor for ImportantDate references in briefing insights.
This keeps curated-event links and important-date links separate and explicit.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "106"
down_revision = "105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {c["name"] for c in inspector.get_columns("user_insights")}
    if "related_important_date_id" not in existing_columns:
        op.add_column(
            "user_insights",
            sa.Column("related_important_date_id", UUID(as_uuid=True), nullable=True),
        )

    has_important_dates = inspector.has_table("important_dates")
    existing_fks = inspector.get_foreign_keys("user_insights")
    has_fk = any(
        fk.get("constrained_columns") == ["related_important_date_id"]
        for fk in existing_fks
    )
    if has_important_dates and not has_fk:
        op.create_foreign_key(
            "user_insights_related_important_date_id_fkey",
            source_table="user_insights",
            referent_table="important_dates",
            local_cols=["related_important_date_id"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("user_insights")}
    if "ix_user_insights_related_important_date_id" not in existing_indexes:
        op.create_index(
            "ix_user_insights_related_important_date_id",
            "user_insights",
            ["related_important_date_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("user_insights")}
    if "ix_user_insights_related_important_date_id" in existing_indexes:
        op.drop_index(
            "ix_user_insights_related_important_date_id",
            table_name="user_insights",
        )

    existing_fks = inspector.get_foreign_keys("user_insights")
    fk_name = None
    for fk in existing_fks:
        if fk.get("constrained_columns") == ["related_important_date_id"]:
            fk_name = fk.get("name")
            break
    if fk_name:
        op.drop_constraint(fk_name, "user_insights", type_="foreignkey")

    existing_columns = {c["name"] for c in inspector.get_columns("user_insights")}
    if "related_important_date_id" in existing_columns:
        op.drop_column("user_insights", "related_important_date_id")
