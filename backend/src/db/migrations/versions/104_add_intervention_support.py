"""Add full-duplex intervention support columns and audit log table.

Revision ID: 104
Revises: 103

Adds columns to assistant_chat_messages (generation_id, is_partial,
signal_type, continues_from) and assistant_chat_sessions (sdk_session_id,
generation_count). Creates intervention_audit_log table for tracking
intervention classifications and actions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "104"
down_revision = "103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- assistant_chat_messages: full-duplex columns ---
    op.add_column(
        "assistant_chat_messages",
        sa.Column("generation_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "assistant_chat_messages",
        sa.Column(
            "is_partial",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "assistant_chat_messages",
        sa.Column("signal_type", sa.String(30), nullable=True),
    )
    op.add_column(
        "assistant_chat_messages",
        sa.Column("continues_from", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_chat_messages_generation",
        "assistant_chat_messages",
        ["generation_id"],
    )

    # --- assistant_chat_sessions: full-duplex columns ---
    op.add_column(
        "assistant_chat_sessions",
        sa.Column("sdk_session_id", sa.String(200), nullable=True),
    )
    op.add_column(
        "assistant_chat_sessions",
        sa.Column(
            "generation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # --- intervention_audit_log ---
    op.create_table(
        "intervention_audit_log",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assistant_chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_id", UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(30), nullable=False),
        sa.Column("job_id", sa.String(100), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("generation_state", sa.String(20), nullable=False),
        sa.Column("action_taken", sa.String(30), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_intervention_audit_session",
        "intervention_audit_log",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_intervention_audit_type",
        "intervention_audit_log",
        ["signal_type"],
    )


def downgrade() -> None:
    # --- intervention_audit_log ---
    op.drop_index(
        "ix_intervention_audit_type", table_name="intervention_audit_log"
    )
    op.drop_index(
        "ix_intervention_audit_session", table_name="intervention_audit_log"
    )
    op.drop_table("intervention_audit_log")

    # --- assistant_chat_sessions: remove columns ---
    op.drop_column("assistant_chat_sessions", "generation_count")
    op.drop_column("assistant_chat_sessions", "sdk_session_id")

    # --- assistant_chat_messages: remove columns ---
    op.drop_index(
        "ix_chat_messages_generation", table_name="assistant_chat_messages"
    )
    op.drop_column("assistant_chat_messages", "continues_from")
    op.drop_column("assistant_chat_messages", "signal_type")
    op.drop_column("assistant_chat_messages", "is_partial")
    op.drop_column("assistant_chat_messages", "generation_id")
