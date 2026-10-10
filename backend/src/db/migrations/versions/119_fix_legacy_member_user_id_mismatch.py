"""Fix legacy member-user ID mismatch.

Legacy users may have member.id != user.id, linked via
MemberRelation(relation_type='self'). This migration:
1. Finds all such legacy pairs
2. Updates all FK references from old_member_id → user_id
3. Merges the member record (updates member.id or merges data)
4. Deletes the self-relation MemberRelation records

After this migration, all users have member.id == user.id.

Revision ID: 119
Revises: 118
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "119"
down_revision = "118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Find legacy (old_member_id, user_id) pairs via self-relations.
    #
    # In the self-relation, from_member_id is the user's member (which may
    # or may not equal user.id), and to_member_id is the "self" target.
    # We need to determine which side is user.id by joining with users.
    legacy_pairs = conn.execute(
        sa.text("""
            SELECT
                mr.id AS relation_id,
                mr.from_member_id,
                mr.to_member_id,
                mr.family_id,
                CASE
                    WHEN u_from.id IS NOT NULL THEN mr.from_member_id
                    ELSE mr.to_member_id
                END AS user_id,
                CASE
                    WHEN u_from.id IS NOT NULL THEN mr.to_member_id
                    ELSE mr.from_member_id
                END AS old_member_id
            FROM member_relations mr
            LEFT JOIN users u_from ON u_from.id = mr.from_member_id
            LEFT JOIN users u_to ON u_to.id = mr.to_member_id
            WHERE mr.relation_type = 'self'
              AND (u_from.id IS NOT NULL OR u_to.id IS NOT NULL)
        """)
    ).fetchall()

    if not legacy_pairs:
        # No legacy data to fix
        return

    for row in legacy_pairs:
        relation_id = row.relation_id
        user_id = row.user_id
        old_member_id = row.old_member_id

        if user_id == old_member_id:
            # IDs already match, just clean up the self-relation
            conn.execute(
                sa.text("DELETE FROM member_relations WHERE id = :rid"),
                {"rid": relation_id},
            )
            continue

        # Check if a member with id=user_id already exists (new-style)
        existing_new = conn.execute(
            sa.text("SELECT id FROM members WHERE id = :uid"),
            {"uid": user_id},
        ).fetchone()

        if existing_new:
            # Both old and new member records exist — merge old into new.
            # The new-style record (id=user_id) is the keeper.
            # Transfer any data from old that new doesn't have.
            conn.execute(
                sa.text("""
                    UPDATE members SET
                        name = COALESCE(
                            (SELECT name FROM members WHERE id = :new_id),
                            (SELECT name FROM members WHERE id = :old_id)
                        ),
                        locations = COALESCE(
                            (SELECT locations FROM members WHERE id = :new_id),
                            (SELECT locations FROM members WHERE id = :old_id)
                        ),
                        phone = COALESCE(
                            (SELECT phone FROM members WHERE id = :new_id),
                            (SELECT phone FROM members WHERE id = :old_id)
                        ),
                        email = COALESCE(
                            (SELECT email FROM members WHERE id = :new_id),
                            (SELECT email FROM members WHERE id = :old_id)
                        )
                    WHERE id = :new_id
                """),
                {"new_id": user_id, "old_id": old_member_id},
            )
        else:
            # No new-style member exists — we need to update the old
            # member's ID to user_id. First update all FK references.
            pass

        # Step 2: Update all FK references from old_member_id → user_id
        # across all tables that reference members.id

        fk_updates = [
            # (table, column)
            ("member_profiles", "member_id"),
            ("member_relations", "from_member_id"),
            ("member_relations", "to_member_id"),
            ("person_profiles", "member_id"),
            ("professional_relations", "from_member_id"),
            ("professional_relations", "to_member_id"),
            ("work_histories", "member_id"),
            ("important_dates", "member_id"),
            ("gift_recommendations", "recipient_member_id"),
            ("gift_preferences", "member_id"),
            ("gift_wishlists", "member_id"),
            ("gift_budgets", "recipient_member_id"),
            ("gift_occasions", "member_id"),
            ("gift_recipient_profiles", "member_id"),
            ("memory_summaries", "member_id"),
            ("preparation_plans", "member_id"),
            ("user_insights", "related_person_id"),
        ]

        for table, column in fk_updates:
            # Check if table exists before updating
            table_exists = conn.execute(
                sa.text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = :tbl
                    )
                """),
                {"tbl": table},
            ).scalar()

            if not table_exists:
                continue

            conn.execute(
                sa.text(f"""
                    UPDATE {table}
                    SET {column} = :new_id
                    WHERE {column} = :old_id
                """),
                {"new_id": user_id, "old_id": old_member_id},
            )

        # Also update event_associations.target_id (TEXT column storing UUID)
        conn.execute(
            sa.text("""
                UPDATE event_associations
                SET target_id = :new_id_str
                WHERE target_id = :old_id_str
            """),
            {"new_id_str": str(user_id), "old_id_str": str(old_member_id)},
        )

        # Step 3: Delete the self-relation first (before member deletion)
        conn.execute(
            sa.text("DELETE FROM member_relations WHERE id = :rid"),
            {"rid": relation_id},
        )

        # Also delete any other relations involving old_member_id that
        # would violate the check_no_self_relation constraint after merge
        conn.execute(
            sa.text("""
                DELETE FROM member_relations
                WHERE (from_member_id = :old_id OR to_member_id = :old_id)
            """),
            {"old_id": old_member_id},
        )

        if existing_new:
            # Merge complete — delete the old member record
            conn.execute(
                sa.text("""
                    DELETE FROM members WHERE id = :old_id AND id != :new_id
                """),
                {"old_id": old_member_id, "new_id": user_id},
            )
        else:
            # Rename old member's ID to user_id
            # Temporarily disable the FK constraint check
            conn.execute(
                sa.text("""
                    UPDATE members SET id = :new_id WHERE id = :old_id
                """),
                {"new_id": user_id, "old_id": old_member_id},
            )


def downgrade() -> None:
    # This migration is not reversible — data has been merged
    pass
