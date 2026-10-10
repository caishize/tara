"""Add briefing_schedule_hour and insights_schedule_hour to user_insight_settings

Support per-user scheduling preferences for the unified Redis Sorted Set
dispatcher. Users can choose what hour their daily briefing and insights
are generated.

Revision ID: 073
Revises: 072
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_insight_settings",
        sa.Column(
            "briefing_schedule_hour",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
    )
    op.add_column(
        "user_insight_settings",
        sa.Column(
            "insights_schedule_hour",
            sa.Integer(),
            nullable=False,
            server_default="6",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_insight_settings", "insights_schedule_hour")
    op.drop_column("user_insight_settings", "briefing_schedule_hour")
