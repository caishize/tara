"""Add dismiss_reason column to event_associations.

Revision ID: 074
Revises: 073
"""

from alembic import op
import sqlalchemy as sa

revision = "074"
down_revision = "073"


def upgrade() -> None:
    op.add_column(
        "event_associations",
        sa.Column(
            "dismiss_reason",
            sa.Text(),
            nullable=True,
            comment="User correction when dismissing (e.g. '外婆不在澳门')",
        ),
    )


def downgrade() -> None:
    op.drop_column("event_associations", "dismiss_reason")
