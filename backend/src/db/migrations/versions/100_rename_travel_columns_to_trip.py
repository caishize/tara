"""Rename remaining travel-era column and constraint names to trip.

Revision ID: 100
Revises: 099

Renames:
- memory_insights.related_travel_ids -> related_trip_ids
- user_insight_settings.auto_curate_on_travel_create -> auto_curate_on_trip_create
- trips.check_travel_dates constraint -> check_trip_dates
"""

from alembic import op


revision = "100"
down_revision = "099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename column: memory_insights.related_travel_ids -> related_trip_ids
    op.alter_column(
        "memory_insights",
        "related_travel_ids",
        new_column_name="related_trip_ids",
    )

    # Rename column: user_insight_settings.auto_curate_on_travel_create -> auto_curate_on_trip_create
    op.alter_column(
        "user_insight_settings",
        "auto_curate_on_travel_create",
        new_column_name="auto_curate_on_trip_create",
    )

    # Rename constraint: trips.check_travel_dates -> check_trip_dates
    op.drop_constraint("check_travel_dates", "trips", type_="check")
    op.create_check_constraint(
        "check_trip_dates",
        "trips",
        "end_date >= start_date",
    )


def downgrade() -> None:
    op.drop_constraint("check_trip_dates", "trips", type_="check")
    op.create_check_constraint(
        "check_travel_dates",
        "trips",
        "end_date >= start_date",
    )

    op.alter_column(
        "user_insight_settings",
        "auto_curate_on_trip_create",
        new_column_name="auto_curate_on_travel_create",
    )

    op.alter_column(
        "memory_insights",
        "related_trip_ids",
        new_column_name="related_travel_ids",
    )
