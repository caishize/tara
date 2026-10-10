"""Expand curated_events event_type check constraint for solar-term date events.

Revision ID: 087
Revises: 086
"""

from alembic import op


revision = "087"
down_revision = "086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("check_curated_event_type", "curated_events", type_="check")
    op.create_check_constraint(
        "check_curated_event_type",
        "curated_events",
        "event_type IS NULL OR event_type IN ("
        "'business_trip', 'travel', 'meeting', 'appointment', 'reminder', "
        "'birthday', 'anniversary', 'holiday', 'holiday_solar_term', "
        "'solar_term', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint("check_curated_event_type", "curated_events", type_="check")
    op.create_check_constraint(
        "check_curated_event_type",
        "curated_events",
        "event_type IS NULL OR event_type IN ("
        "'business_trip', 'travel', 'meeting', 'appointment', 'reminder', "
        "'birthday', 'anniversary', 'holiday', 'other')",
    )
