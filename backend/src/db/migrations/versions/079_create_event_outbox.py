"""Create event_outbox table for transactional outbox pattern.

Stores domain events atomically with business operations.
A relay task polls unpublished rows and publishes to Redis Streams.

Revision ID: 079
Revises: 078
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "079"
down_revision = "078"


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial index for efficient relay queries (only unpublished rows)
    op.create_index(
        "idx_outbox_unpublished",
        "event_outbox",
        ["created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_outbox_unpublished", table_name="event_outbox")
    op.drop_table("event_outbox")
