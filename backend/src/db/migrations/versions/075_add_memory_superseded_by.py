"""Add superseded_by column to conversation_memories.

Supports memory correction: when a newer memory corrects an older one,
the old memory's status is set to SUPERSEDED and superseded_by points
to the correcting memory's ID.

Revision ID: 075
Revises: 074
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "075"
down_revision = "074"


def upgrade() -> None:
    op.add_column(
        "conversation_memories",
        sa.Column(
            "superseded_by",
            UUID(as_uuid=True),
            nullable=True,
            comment="Points to the correcting memory when status=SUPERSEDED",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversation_memories", "superseded_by")
