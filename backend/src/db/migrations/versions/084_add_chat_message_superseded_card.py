"""Add is_superseded and card_type columns to assistant_chat_messages.

These columns were added to the SQLAlchemy model but never migrated.

Revision ID: 084
Revises: ca7063e3c2f2
"""
import sqlalchemy as sa
from alembic import op

revision = "084"
down_revision = "ca7063e3c2f2"


def upgrade() -> None:
    op.add_column(
        "assistant_chat_messages",
        sa.Column(
            "is_superseded",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "assistant_chat_messages",
        sa.Column("card_type", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assistant_chat_messages", "card_type")
    op.drop_column("assistant_chat_messages", "is_superseded")
