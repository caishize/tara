"""Add travel planning tables

Revision ID: 009_add_travel_planning_tables
Revises: feffd9a27204
Create Date: 2025-11-24 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '009_add_travel_planning_tables'
down_revision: Union[str, None] = 'feffd9a27204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create travel_plans table
    op.create_table(
        'travel_plans',
        sa.Column('trip_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('trip_name', sa.String(200), nullable=True),
        sa.Column('destination', sa.String(500), nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('trip_type', sa.String(50), nullable=True, server_default='leisure'),
        sa.Column('budget', sa.Numeric(12, 2), nullable=True),
        sa.Column('actual_expense', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('participants', ARRAY(UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(50), nullable=False, server_default='planning'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('recommendation_context', JSONB, nullable=True),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('end_date >= start_date', name='check_travel_dates'),
        sa.CheckConstraint('budget >= 0', name='check_budget_positive'),
        sa.CheckConstraint('actual_expense >= 0', name='check_expense_positive'),
        sa.CheckConstraint(
            "status IN ('planning', 'confirmed', 'in_progress', 'completed', 'cancelled')",
            name='check_status_valid'
        ),
        sa.CheckConstraint(
            "trip_type IN ('leisure', 'family', 'business', 'visit', 'other')",
            name='check_trip_type_valid'
        ),
    )
    op.create_index('idx_travel_plan_family', 'travel_plans', ['family_id', 'status'])
    op.create_index('idx_travel_plan_dates', 'travel_plans', ['start_date', 'end_date'])
    op.create_index('idx_travel_plan_status', 'travel_plans', ['status'])

    # Create travel_itineraries table
    op.create_table(
        'travel_itineraries',
        sa.Column('itinerary_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trip_id', UUID(as_uuid=True), nullable=False),
        sa.Column('day_number', sa.Integer, nullable=False),
        sa.Column('schedule', JSONB, nullable=False, server_default='[]'),
        sa.Column('packing_notes', JSONB, nullable=True),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['trip_id'], ['travel_plans.trip_id'], ondelete='CASCADE'),
        sa.CheckConstraint('day_number > 0', name='check_day_number_positive'),
    )
    op.create_index('idx_itinerary_trip', 'travel_itineraries', ['trip_id', 'day_number'], unique=True)

    # Create travel_expenses table
    op.create_table(
        'travel_expenses',
        sa.Column('expense_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trip_id', UUID(as_uuid=True), nullable=False),
        sa.Column('expense_date', sa.Date, nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('payment_method', sa.String(100), nullable=True),
        sa.Column('receipt_url', sa.String(500), nullable=True),
        sa.Column('itinerary_item_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['trip_id'], ['travel_plans.trip_id'], ondelete='CASCADE'),
        sa.CheckConstraint('amount >= 0', name='check_amount_positive'),
        sa.CheckConstraint(
            "category IN ('transportation', 'accommodation', 'tickets', 'food', 'shopping', 'other')",
            name='check_category_valid'
        ),
    )
    op.create_index('idx_expense_trip', 'travel_expenses', ['trip_id', 'expense_date'])
    op.create_index('idx_expense_category', 'travel_expenses', ['trip_id', 'category'])

    # Create travel_memories table
    op.create_table(
        'travel_memories',
        sa.Column('memory_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trip_id', UUID(as_uuid=True), nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('content_urls', ARRAY(sa.String(500)), nullable=True, server_default='{}'),
        sa.Column('caption', sa.Text, nullable=True),
        sa.Column('ai_caption', sa.Text, nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('latitude', sa.String(50), nullable=True),
        sa.Column('longitude', sa.String(50), nullable=True),
        sa.Column('memory_date', TIMESTAMP, nullable=True),
        sa.Column('rating', sa.Integer, nullable=True),
        sa.Column('itinerary_item_id', UUID(as_uuid=True), nullable=True),
        sa.Column('tags', ARRAY(sa.String(50)), nullable=True, server_default='{}'),
        sa.Column('created_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['trip_id'], ['travel_plans.trip_id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "content_type IN ('photo', 'video', 'note')",
            name='check_content_type_valid'
        ),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name='check_rating_range'
        ),
    )
    op.create_index('idx_memory_trip', 'travel_memories', ['trip_id', 'memory_date'])
    op.create_index('idx_memory_type', 'travel_memories', ['trip_id', 'content_type'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_memory_type', 'travel_memories')
    op.drop_index('idx_memory_trip', 'travel_memories')
    op.drop_table('travel_memories')

    op.drop_index('idx_expense_category', 'travel_expenses')
    op.drop_index('idx_expense_trip', 'travel_expenses')
    op.drop_table('travel_expenses')

    op.drop_index('idx_itinerary_trip', 'travel_itineraries')
    op.drop_table('travel_itineraries')

    op.drop_index('idx_travel_plan_status', 'travel_plans')
    op.drop_index('idx_travel_plan_dates', 'travel_plans')
    op.drop_index('idx_travel_plan_family', 'travel_plans')
    op.drop_table('travel_plans')
