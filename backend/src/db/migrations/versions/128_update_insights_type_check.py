"""Update ck_insights_insight_type to include engine v2 types.

Revision ID: 128
Revises: 127

The original CHECK constraint (migration 120) only allowed 7 types:
time, relationship, favor, health, memory, efficiency, finance.
Engine v2 (migration 125) added columns but did not update the constraint,
causing INSERT failures for trend_alert, social_obligation, etc.
"""

from alembic import op


revision = "128"
down_revision = "127"
branch_labels = None
depends_on = None

_OLD_TYPES = (
    "time", "relationship", "favor", "health", "memory", "efficiency", "finance"
)

_NEW_TYPES = _OLD_TYPES + (
    "social_obligation", "positive_affirmation", "trend_alert",
    "prep_chain", "life_admin", "weather_care", "family_climate",
    "habit_tracking",
)


def upgrade() -> None:
    op.drop_constraint("ck_insights_insight_type", "insights", type_="check")
    op.create_check_constraint(
        "ck_insights_insight_type",
        "insights",
        f"insight_type IN ({', '.join(repr(t) for t in _NEW_TYPES)})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_insights_insight_type", "insights", type_="check")
    op.create_check_constraint(
        "ck_insights_insight_type",
        "insights",
        f"insight_type IN ({', '.join(repr(t) for t in _OLD_TYPES)})",
    )
