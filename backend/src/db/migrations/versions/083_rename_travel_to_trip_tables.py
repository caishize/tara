"""Rename travel_* tables to trip-based names.

Matches the module rename: modules/travel → modules/trip.

Table renames:
- travel_plans → trips
- travel_itineraries → trip_itineraries
- travel_expenses → trip_expenses
- travel_memories → trip_memories

Index renames (travel_plans only; other tables' indexes had no travel_ prefix):
- idx_travel_plan_family → idx_trip_family
- idx_travel_plan_category → idx_trip_category
- idx_travel_plan_dates → idx_trip_dates
- idx_travel_plan_status → idx_trip_status

Revision ID: 083
Revises: 082
"""
from alembic import op

revision = "083"
down_revision = "082"


def upgrade():
    # 1. Rename travel_plans → trips
    op.rename_table("travel_plans", "trips")
    op.execute("ALTER INDEX IF EXISTS idx_travel_plan_family RENAME TO idx_trip_family")
    op.execute("ALTER INDEX IF EXISTS idx_travel_plan_category RENAME TO idx_trip_category")
    op.execute("ALTER INDEX IF EXISTS idx_travel_plan_dates RENAME TO idx_trip_dates")
    op.execute("ALTER INDEX IF EXISTS idx_travel_plan_status RENAME TO idx_trip_status")

    # 2. Rename travel_itineraries → trip_itineraries
    op.rename_table("travel_itineraries", "trip_itineraries")

    # 3. Rename travel_expenses → trip_expenses
    op.rename_table("travel_expenses", "trip_expenses")

    # 4. Rename travel_memories → trip_memories
    op.rename_table("travel_memories", "trip_memories")


def downgrade():
    # 4. Revert trip_memories → travel_memories
    op.rename_table("trip_memories", "travel_memories")

    # 3. Revert trip_expenses → travel_expenses
    op.rename_table("trip_expenses", "travel_expenses")

    # 2. Revert trip_itineraries → travel_itineraries
    op.rename_table("trip_itineraries", "travel_itineraries")

    # 1. Revert trips → travel_plans
    op.execute("ALTER INDEX IF EXISTS idx_trip_family RENAME TO idx_travel_plan_family")
    op.execute("ALTER INDEX IF EXISTS idx_trip_category RENAME TO idx_travel_plan_category")
    op.execute("ALTER INDEX IF EXISTS idx_trip_dates RENAME TO idx_travel_plan_dates")
    op.execute("ALTER INDEX IF EXISTS idx_trip_status RENAME TO idx_travel_plan_status")
    op.rename_table("trips", "travel_plans")
