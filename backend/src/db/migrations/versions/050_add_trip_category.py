"""Add trip category field for two-level classification.

Revision ID: 050_add_trip_category
Revises: 049_add_memory_summary_tables
Create Date: 2025-01-24

This migration:
1. Adds 'category' column to travel_plans table (personal/business)
2. Migrates existing 'business' trip_type to category='business', trip_type='business_trip'
3. Updates trip_type constraint to include new sub-types
4. Adds category constraint and index
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '050_add_trip_category'
down_revision = '049_memory_summary_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add category column with default 'personal'
    op.add_column(
        'travel_plans',
        sa.Column('category', sa.String(50), nullable=False, server_default='personal')
    )

    # 2. Migrate existing data: trip_type='business' → category='business', trip_type='business_trip'
    op.execute("""
        UPDATE travel_plans
        SET category = 'business', trip_type = 'business_trip'
        WHERE trip_type = 'business'
    """)

    # 3. Drop old trip_type constraint
    op.drop_constraint('check_trip_type_valid', 'travel_plans', type_='check')

    # 4. Create new trip_type constraint with updated values
    op.create_check_constraint(
        'check_trip_type_valid',
        'travel_plans',
        "trip_type IN ('leisure', 'family', 'visit', 'business_trip', 'conference', 'client_visit', 'other')"
    )

    # 5. Add category constraint
    op.create_check_constraint(
        'check_category_valid',
        'travel_plans',
        "category IN ('personal', 'business')"
    )

    # 6. Add index for category filtering
    op.create_index(
        'idx_travel_plan_category',
        'travel_plans',
        ['family_id', 'category']
    )


def downgrade() -> None:
    # 1. Drop index
    op.drop_index('idx_travel_plan_category', table_name='travel_plans')

    # 2. Drop category constraint
    op.drop_constraint('check_category_valid', 'travel_plans', type_='check')

    # 3. Drop new trip_type constraint
    op.drop_constraint('check_trip_type_valid', 'travel_plans', type_='check')

    # 4. Restore original trip_type constraint
    op.create_check_constraint(
        'check_trip_type_valid',
        'travel_plans',
        "trip_type IN ('leisure', 'family', 'business', 'visit', 'other')"
    )

    # 5. Migrate data back: category='business' → trip_type='business'
    op.execute("""
        UPDATE travel_plans
        SET trip_type = 'business'
        WHERE category = 'business' AND trip_type = 'business_trip'
    """)

    # 6. Drop category column
    op.drop_column('travel_plans', 'category')
