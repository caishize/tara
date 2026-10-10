"""Add content_hash column to conversation_memories for idempotent writes.

Adds an indexed String(64) column that stores the MD5 hash of
(content + memory_type + sorted_entities_json). Used to prevent
duplicate memory insertions.

Includes a backfill step that computes md5(content || memory_type)
for existing rows (entities excluded from backfill for simplicity).

Revision ID: 092
Revises: 091
"""

from alembic import op
import sqlalchemy as sa


revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_memories",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_conv_memories_content_hash",
        "conversation_memories",
        ["content_hash"],
    )
    # Backfill existing rows with a hash of content + memory_type
    op.execute(
        "UPDATE conversation_memories "
        "SET content_hash = md5(content || '|' || memory_type) "
        "WHERE content_hash IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_conv_memories_content_hash", table_name="conversation_memories")
    op.drop_column("conversation_memories", "content_hash")
