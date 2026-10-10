"""Add GIN index on assistant_chat_messages.message_metadata->job_id for poll fallback.

Revision ID: 103
Revises: 102

The /chat/poll/{job_id} endpoint filters by message_metadata->>'job_id'.
A GIN index on this JSONB path makes the query efficient.
"""

from alembic import op


revision = "103"
down_revision = "102"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_chat_messages_metadata_job_id"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
        "ON assistant_chat_messages USING GIN ((message_metadata->'job_id'))"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
