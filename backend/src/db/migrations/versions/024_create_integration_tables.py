"""Create integration module tables and extend existing tables

Revision ID: 024_integration
Revises: 023
Create Date: 2025-12-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '024_integration'
down_revision = '023_gift_memory'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create cross_module_links table
    op.create_table(
        'cross_module_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_module', sa.String(50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_module', sa.String(50), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('link_type', sa.String(50), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False, server_default='bidirectional'),
        sa.Column('context', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_cross_module_links_source', 'cross_module_links', ['source_module', 'source_id'])
    op.create_index('idx_cross_module_links_target', 'cross_module_links', ['target_module', 'target_id'])
    op.create_index('idx_cross_module_links_family', 'cross_module_links', ['family_id'])
    op.create_index('idx_cross_module_links_type', 'cross_module_links', ['link_type'])
    op.create_index(
        'idx_cross_module_links_unique', 'cross_module_links',
        ['source_module', 'source_id', 'target_module', 'target_id', 'link_type'],
        unique=True
    )

    # 2. Create integration_events table
    op.create_table(
        'integration_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('source_module', sa.String(50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_integration_events_status', 'integration_events', ['status', 'created_at'])
    op.create_index('idx_integration_events_type', 'integration_events', ['event_type'])
    op.create_index('idx_integration_events_source', 'integration_events', ['source_module', 'source_id'])

    # 3. Create travel_shopping_recommendations table
    op.create_table(
        'travel_shopping_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('travel_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('travel_plans.trip_id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('inventory_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('current_stock', sa.Integer, nullable=True),
        sa.Column('recommended_quantity', sa.Integer, nullable=False, server_default='1'),
        sa.Column('priority', sa.String(20), nullable=False, server_default='recommended'),
        sa.Column('shopping_item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shopping_items.item_id'), nullable=True),
        sa.Column('is_added_to_list', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_travel_shopping_rec_travel', 'travel_shopping_recommendations', ['travel_plan_id'])
    op.create_index('idx_travel_shopping_rec_status', 'travel_shopping_recommendations', ['inventory_status'])
    op.create_index('idx_travel_shopping_rec_priority', 'travel_shopping_recommendations', ['priority'])

    # 4. Extend gift_recommendations table
    op.add_column('gift_recommendations', sa.Column('gift_type', sa.String(20), server_default='product'))
    op.add_column('gift_recommendations', sa.Column('integration_status', sa.String(20), server_default='pending'))
    op.add_column('gift_recommendations', sa.Column('shopping_item_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('gift_recommendations', sa.Column('travel_plan_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('gift_recommendations', sa.Column('purchase_status', sa.String(20), nullable=True))
    op.add_column('gift_recommendations', sa.Column('purchase_date', sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_index('idx_gift_rec_gift_type', 'gift_recommendations', ['gift_type'])
    op.create_index('idx_gift_rec_integration_status', 'gift_recommendations', ['integration_status'])

    # 5. Extend shopping_items table
    op.add_column('shopping_items', sa.Column('gift_recommendation_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shopping_items', sa.Column('gift_recipient_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shopping_items', sa.Column('gift_context', sa.String(200), nullable=True))
    op.add_column('shopping_items', sa.Column('travel_plan_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shopping_items', sa.Column('is_souvenir', sa.Boolean, server_default='false'))
    op.add_column('shopping_items', sa.Column('source_type', sa.String(20), server_default='manual'))
    op.create_index('idx_shopping_items_gift', 'shopping_items', ['gift_recommendation_id'])
    op.create_index('idx_shopping_items_travel', 'shopping_items', ['travel_plan_id'])

    # 6. Extend travel_plans table
    op.add_column('travel_plans', sa.Column('is_gift', sa.Boolean, server_default='false'))
    op.add_column('travel_plans', sa.Column('gift_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('travel_plans', sa.Column('original_giver_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('travel_plans', sa.Column('shopping_list_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('travel_plans', sa.Column('has_shopping_prepared', sa.Boolean, server_default='false'))

    # 7. Extend travel_expenses table
    op.add_column('travel_expenses', sa.Column('is_gift', sa.Boolean, server_default='false'))
    op.add_column('travel_expenses', sa.Column('gift_recipient_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('travel_expenses', sa.Column('gift_history_id', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade():
    # Remove travel_expenses extensions
    op.drop_column('travel_expenses', 'gift_history_id')
    op.drop_column('travel_expenses', 'gift_recipient_id')
    op.drop_column('travel_expenses', 'is_gift')

    # Remove travel_plans extensions
    op.drop_column('travel_plans', 'has_shopping_prepared')
    op.drop_column('travel_plans', 'shopping_list_id')
    op.drop_column('travel_plans', 'original_giver_id')
    op.drop_column('travel_plans', 'gift_id')
    op.drop_column('travel_plans', 'is_gift')

    # Remove shopping_items extensions
    op.drop_index('idx_shopping_items_travel', 'shopping_items')
    op.drop_index('idx_shopping_items_gift', 'shopping_items')
    op.drop_column('shopping_items', 'source_type')
    op.drop_column('shopping_items', 'is_souvenir')
    op.drop_column('shopping_items', 'travel_plan_id')
    op.drop_column('shopping_items', 'gift_context')
    op.drop_column('shopping_items', 'gift_recipient_id')
    op.drop_column('shopping_items', 'gift_recommendation_id')

    # Remove gift_recommendations extensions
    op.drop_index('idx_gift_rec_integration_status', 'gift_recommendations')
    op.drop_index('idx_gift_rec_gift_type', 'gift_recommendations')
    op.drop_column('gift_recommendations', 'purchase_date')
    op.drop_column('gift_recommendations', 'purchase_status')
    op.drop_column('gift_recommendations', 'travel_plan_id')
    op.drop_column('gift_recommendations', 'shopping_item_id')
    op.drop_column('gift_recommendations', 'integration_status')
    op.drop_column('gift_recommendations', 'gift_type')

    # Drop new tables
    op.drop_table('travel_shopping_recommendations')
    op.drop_table('integration_events')
    op.drop_table('cross_module_links')
