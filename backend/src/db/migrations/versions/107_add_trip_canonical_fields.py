"""Add canonical/superseded fields to trips.

Revision ID: 107
Revises: 106

Introduces semantic dedup linkage for trips:
- canonical_trip_id: points to the canonical trip when this row is superseded
- is_active: controls whether the trip is visible in default queries
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "107"
down_revision = "106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {c["name"] for c in inspector.get_columns("trips")}

    if "canonical_trip_id" not in existing_columns:
        op.add_column(
            "trips",
            sa.Column("canonical_trip_id", UUID(as_uuid=True), nullable=True),
        )

    if "is_active" not in existing_columns:
        op.add_column(
            "trips",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )

    existing_fks = inspector.get_foreign_keys("trips")
    has_canonical_fk = any(
        fk.get("constrained_columns") == ["canonical_trip_id"] for fk in existing_fks
    )
    if not has_canonical_fk:
        op.create_foreign_key(
            "trips_canonical_trip_id_fkey",
            source_table="trips",
            referent_table="trips",
            local_cols=["canonical_trip_id"],
            remote_cols=["trip_id"],
            ondelete="SET NULL",
        )

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("trips")}
    if "ix_trips_canonical_trip_id" not in existing_indexes:
        op.create_index("ix_trips_canonical_trip_id", "trips", ["canonical_trip_id"])
    if "idx_trip_family_active" not in existing_indexes:
        op.create_index("idx_trip_family_active", "trips", ["family_id", "is_active"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("trips")}
    if "idx_trip_family_active" in existing_indexes:
        op.drop_index("idx_trip_family_active", table_name="trips")
    if "ix_trips_canonical_trip_id" in existing_indexes:
        op.drop_index("ix_trips_canonical_trip_id", table_name="trips")

    existing_fks = inspector.get_foreign_keys("trips")
    fk_name = None
    for fk in existing_fks:
        if fk.get("constrained_columns") == ["canonical_trip_id"]:
            fk_name = fk.get("name")
            break
    if fk_name:
        op.drop_constraint(fk_name, "trips", type_="foreignkey")

    existing_columns = {c["name"] for c in inspector.get_columns("trips")}
    if "is_active" in existing_columns:
        op.drop_column("trips", "is_active")
    if "canonical_trip_id" in existing_columns:
        op.drop_column("trips", "canonical_trip_id")
