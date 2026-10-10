"""Add preparation_items to curated_events and timezone to user_insight_settings.

preparation_items: JSONB column for event preparation checklists.
timezone: VARCHAR(50) for per-user timezone configuration.

Revision ID: 076
Revises: 075
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "076"
down_revision = "075"


def upgrade() -> None:
    op.add_column(
        "curated_events",
        sa.Column(
            "preparation_items",
            JSONB,
            nullable=True,
            server_default="[]",
            comment="Preparation checklist: [{item, source, done}]",
        ),
    )

    op.add_column(
        "user_insight_settings",
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=True,
            server_default="Asia/Shanghai",
            comment="User timezone for schedule calculations (IANA tz name)",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_insight_settings", "timezone")
    op.drop_column("curated_events", "preparation_items")
