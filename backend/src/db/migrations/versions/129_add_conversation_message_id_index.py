"""Add composite index on (session_id, sequence_number DESC) for pagination.

Revision ID: 129
Revises: 128

The existing ix_assistant_chat_messages_session covers (session_id, created_at)
but cursor-based pagination by sequence_number requires a separate index.
"""

from alembic import op


revision = "129"
down_revision = "128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_messages_session_seq_desc"
        " ON assistant_chat_messages (session_id, sequence_number DESC)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_chat_messages_session_seq_desc"
    )
