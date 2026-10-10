"""Add action_options JSON column to user_insights table.

Revision ID: 114
Revises: 113

Adds a nullable JSON column to store List[ActionSpec] for typed action
dispatch on insight cards (PLAN-003, ROOT-003).
"""

from alembic import op
import sqlalchemy as sa


revision = "114"
down_revision = "113"


def upgrade() -> None:
    op.add_column(
        "user_insights",
        sa.Column(
            "action_options",
            sa.JSON(),
            nullable=True,
            comment="List[ActionSpec] as JSON for typed action dispatch",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_insights", "action_options")
