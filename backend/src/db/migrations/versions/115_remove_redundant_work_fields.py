"""Remove redundant work fields from members table.

Revision ID: 115
Revises: 114

Drops occupation, workplace, current_company, current_position from members.
work_histories is now the single source of truth for current work info.

Before dropping, backfills work_histories for members that have data in the
old columns but no is_current=True work_history record.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "115"
down_revision = "114"


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Backfill — insert work_histories for members with old column data
    # but no current work_history record
    conn.execute(sa.text("""
        INSERT INTO work_histories (id, family_id, member_id, company_name, position, is_current, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            m.family_id,
            m.id,
            COALESCE(NULLIF(m.current_company, ''), NULLIF(m.workplace, ''), NULLIF(m.current_position, ''), NULLIF(m.occupation, ''), '-'),
            COALESCE(NULLIF(m.current_position, ''), NULLIF(m.occupation, '')),
            TRUE,
            NOW(),
            NOW()
        FROM members m
        WHERE (m.current_company IS NOT NULL OR m.workplace IS NOT NULL
               OR m.current_position IS NOT NULL OR m.occupation IS NOT NULL)
          AND NOT EXISTS (
              SELECT 1 FROM work_histories wh
              WHERE wh.member_id = m.id AND wh.is_current = TRUE
          )
    """))

    # Step 2: Supplement — fill position on existing work_histories that are missing it
    conn.execute(sa.text("""
        UPDATE work_histories wh
        SET position = m.occupation
        FROM members m
        WHERE wh.member_id = m.id
          AND wh.is_current = TRUE
          AND wh.position IS NULL
          AND m.occupation IS NOT NULL
    """))

    # Step 3: Drop columns
    op.drop_column("members", "occupation")
    op.drop_column("members", "workplace")
    op.drop_column("members", "current_company")
    op.drop_column("members", "current_position")


def downgrade() -> None:
    # Step 1: Re-add columns
    op.add_column("members", sa.Column("occupation", sa.String(100), nullable=True))
    op.add_column("members", sa.Column("workplace", sa.String(200), nullable=True))
    op.add_column("members", sa.Column("current_company", sa.String(200), nullable=True))
    op.add_column("members", sa.Column("current_position", sa.String(100), nullable=True))

    # Step 2: Backfill from work_histories
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE members m
        SET current_company = wh.company_name,
            current_position = wh.position,
            workplace = wh.company_name,
            occupation = wh.position
        FROM work_histories wh
        WHERE wh.member_id = m.id
          AND wh.is_current = TRUE
    """))
