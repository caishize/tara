"""Clean up historical duplicate memory insights.

Deduplicates near-identical rows in `memory_insights` for active items
(`pending` / `shown`) using a normalized semantic key:
- user_id + family_id + insight_type
- normalized person/location from action_data
- normalized title
- normalized content prefix (first 80 chars)

Within each duplicate cluster, keeps the best row:
1) higher priority
2) newer created_at
3) deterministic id fallback

All other rows in the cluster are soft-dismissed (status -> dismissed).

Revision ID: 078
Revises: 077
"""

from alembic import op
import sqlalchemy as sa


revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            WITH normalized AS (
                SELECT
                    mi.id,
                    mi.user_id,
                    mi.family_id,
                    mi.insight_type,
                    COALESCE(mi.priority, 0) AS priority,
                    mi.created_at,
                    -- Normalize title/content and strip noisy person prefixes.
                    regexp_replace(
                        lower(
                            replace(
                                replace(
                                    replace(
                                        replace(COALESCE(mi.title, ''), '用户', ''),
                                        '我的', ''
                                    ),
                                    '咱们的', ''
                                ),
                                '我们的', ''
                            )
                        ),
                        '\\s+',
                        '',
                        'g'
                    ) AS title_norm,
                    left(
                        regexp_replace(
                            lower(
                                replace(
                                    replace(
                                        replace(
                                            replace(COALESCE(mi.content, ''), '用户', ''),
                                            '我的', ''
                                        ),
                                        '咱们的', ''
                                    ),
                                    '我们的', ''
                                )
                            ),
                            '\\s+',
                            '',
                            'g'
                        ),
                        80
                    ) AS content_prefix_norm,
                    regexp_replace(
                        lower(
                            replace(
                                replace(
                                    replace(
                                        replace(COALESCE(mi.action_data ->> 'person', ''), '用户', ''),
                                        '我的', ''
                                    ),
                                    '咱们的', ''
                                ),
                                '我们的', ''
                            )
                        ),
                        '\\s+',
                        '',
                        'g'
                    ) AS person_norm,
                    regexp_replace(
                        lower(
                            replace(
                                replace(
                                    replace(
                                        replace(
                                            COALESCE(
                                                COALESCE(mi.action_data ->> 'location', mi.action_data ->> 'destination'),
                                                ''
                                            ),
                                            '用户',
                                            ''
                                        ),
                                        '我的',
                                        ''
                                    ),
                                    '咱们的',
                                    ''
                                ),
                                '我们的',
                                ''
                            )
                        ),
                        '\\s+',
                        '',
                        'g'
                    ) AS location_norm
                FROM memory_insights mi
                WHERE mi.status IN ('pending', 'shown')
            ),
            ranked AS (
                SELECT
                    n.id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            n.user_id,
                            n.family_id,
                            n.insight_type,
                            COALESCE(NULLIF(n.person_norm, ''), '__empty_person__'),
                            COALESCE(NULLIF(n.location_norm, ''), '__empty_location__'),
                            COALESCE(NULLIF(n.title_norm, ''), n.id::text),
                            COALESCE(NULLIF(n.content_prefix_norm, ''), '__empty_content__')
                        ORDER BY
                            n.priority DESC,
                            n.created_at DESC,
                            n.id DESC
                    ) AS rn
                FROM normalized n
            ),
            dup_ids AS (
                SELECT id
                FROM ranked
                WHERE rn > 1
            )
            UPDATE memory_insights mi
            SET
                status = 'dismissed',
                dismissed_at = COALESCE(mi.dismissed_at, NOW())
            WHERE mi.id IN (SELECT id FROM dup_ids)
              AND mi.status IN ('pending', 'shown')
            """
        )
    )


def downgrade() -> None:
    # Irreversible data cleanup migration.
    pass

