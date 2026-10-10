"""Add life_type and valid_until columns to secretary_notes table.

Revision ID: 088
Revises: 087
"""

from alembic import op
import sqlalchemy as sa


revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "secretary_notes",
        sa.Column(
            "life_type",
            sa.String(20),
            nullable=False,
            server_default="permanent",
        ),
    )
    op.add_column(
        "secretary_notes",
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("secretary_notes", "valid_until")
    op.drop_column("secretary_notes", "life_type")
