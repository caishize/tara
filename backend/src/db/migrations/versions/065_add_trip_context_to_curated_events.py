"""add trip_name and trip_day_label to curated_events

Revision ID: 065_add_trip_context
Revises: 064_create_device_tokens
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa

revision = "065_add_trip_context"
down_revision = "064_create_device_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "curated_events",
        sa.Column("trip_name", sa.String(200), nullable=True),
    )
    op.add_column(
        "curated_events",
        sa.Column("trip_day_label", sa.String(100), nullable=True),
    )

    # Backfill existing events that have a trip_id
    op.execute("""
        UPDATE curated_events ce
        SET trip_name = tp.trip_name
        FROM travel_plans tp
        WHERE ce.trip_id = tp.trip_id
          AND ce.trip_name IS NULL
          AND ce.trip_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("curated_events", "trip_day_label")
    op.drop_column("curated_events", "trip_name")
