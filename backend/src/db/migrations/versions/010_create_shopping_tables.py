"""Create shopping management tables

Revision ID: 010_create_shopping_tables
Revises: 009_add_travel_planning_tables
Create Date: 2025-01-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '010_create_shopping_tables'
down_revision = '009_add_travel_planning_tables'


def upgrade() -> None:
    # Create enums for shopping module
    op.execute("CREATE TYPE list_type_enum AS ENUM ('regular', 'replenishment', 'seasonal', 'bulk', 'urgent')")
    op.execute("CREATE TYPE list_status_enum AS ENUM ('active', 'in_progress', 'completed', 'archived')")
    op.execute("CREATE TYPE appliance_status_enum AS ENUM ('normal', 'degraded', 'failing', 'broken')")

    # shopping_lists table
    op.create_table(
        'shopping_lists',
        sa.Column('list_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('list_name', sa.String(200), nullable=False),
        sa.Column('list_type', sa.String(20), nullable=False, server_default='regular'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.TIMESTAMP, nullable=True),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
    )
    op.create_index('idx_shopping_list_family', 'shopping_lists', ['family_id', 'status', 'is_deleted'])
    op.create_index('idx_shopping_list_created_by', 'shopping_lists', ['created_by'])
    op.create_index('idx_shopping_list_due_date', 'shopping_lists', ['due_date'], postgresql_where=sa.text('due_date IS NOT NULL'))

    # shopping_items table
    op.create_table(
        'shopping_items',
        sa.Column('item_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('list_id', UUID(as_uuid=True), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('quantity', sa.Float, nullable=False, default=1.0),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('priority', sa.Integer, nullable=False, default=3),
        sa.Column('estimated_price', sa.Float, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_purchased', sa.Boolean, nullable=False, default=False),
        sa.Column('purchased_by', UUID(as_uuid=True), nullable=True),
        sa.Column('purchased_at', sa.TIMESTAMP, nullable=True),
        sa.Column('actual_price', sa.Float, nullable=True),
        sa.Column('merchant', sa.String(200), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
        sa.ForeignKeyConstraint(['list_id'], ['shopping_lists.list_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_shopping_item_list', 'shopping_items', ['list_id', 'is_purchased'])
    op.create_index('idx_shopping_item_category', 'shopping_items', ['category'])
    op.create_index('idx_shopping_item_priority', 'shopping_items', ['priority'])

    # household_inventory table
    op.create_table(
        'household_inventory',
        sa.Column('inventory_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('current_quantity', sa.Float, nullable=False, default=0.0),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('min_threshold', sa.Float, nullable=False, default=1.0),
        sa.Column('storage_location', sa.String(100), nullable=True),
        sa.Column('expiry_date', sa.Date, nullable=True),
        sa.Column('last_purchase_date', sa.Date, nullable=True),
        sa.Column('purchase_frequency_days', sa.Integer, nullable=True),
        sa.Column('daily_consumption_rate', sa.Float, nullable=True),
        sa.Column('predicted_depletion_date', sa.Date, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
    )
    op.create_index('idx_household_inventory_family', 'household_inventory', ['family_id', 'is_deleted'])
    op.create_index('idx_household_inventory_product', 'household_inventory', ['product_name', 'family_id'])
    op.create_index('idx_household_inventory_category', 'household_inventory', ['category'])
    op.create_index('idx_household_inventory_low_stock', 'household_inventory', ['current_quantity', 'min_threshold'])
    op.create_index('idx_household_inventory_depletion', 'household_inventory', ['predicted_depletion_date'], postgresql_where=sa.text('predicted_depletion_date IS NOT NULL'))

    # purchase_history table
    op.create_table(
        'purchase_history',
        sa.Column('purchase_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('purchased_by', UUID(as_uuid=True), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('quantity', sa.Float, nullable=False, default=1.0),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('unit_price', sa.Float, nullable=False),
        sa.Column('total_price', sa.Float, nullable=False),
        sa.Column('merchant', sa.String(200), nullable=True),
        sa.Column('platform', sa.String(100), nullable=True),
        sa.Column('purchase_date', sa.Date, nullable=False),
        sa.Column('product_url', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
    )
    op.create_index('idx_purchase_history_family', 'purchase_history', ['family_id', 'purchase_date'])
    op.create_index('idx_purchase_history_product', 'purchase_history', ['product_name', 'family_id'])
    op.create_index('idx_purchase_history_member', 'purchase_history', ['purchased_by'])
    op.create_index('idx_purchase_history_category', 'purchase_history', ['category', 'purchase_date'])
    op.create_index('idx_purchase_history_date', 'purchase_history', ['purchase_date'])

    # price_watches table
    op.create_table(
        'price_watches',
        sa.Column('watch_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('product_url', sa.Text, nullable=False),
        sa.Column('platform', sa.String(100), nullable=True),
        sa.Column('baseline_price', sa.Float, nullable=False),
        sa.Column('current_price', sa.Float, nullable=False),
        sa.Column('target_price', sa.Float, nullable=True),
        sa.Column('lowest_price', sa.Float, nullable=True),
        sa.Column('watch_start_date', sa.Date, nullable=False),
        sa.Column('last_check_date', sa.Date, nullable=True),
        sa.Column('price_history', JSONB, nullable=True),
        sa.Column('alert_on_drop_percentage', sa.Float, nullable=False, default=5.0),
        sa.Column('alert_on_historical_low', sa.Boolean, nullable=False, default=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
    )
    op.create_index('idx_price_watch_family', 'price_watches', ['family_id', 'is_active'])
    op.create_index('idx_price_watch_product', 'price_watches', ['product_name', 'family_id'])
    op.create_index('idx_price_watch_active', 'price_watches', ['is_active', 'last_check_date'])

    # appliances table
    op.create_table(
        'appliances',
        sa.Column('appliance_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('purchase_date', sa.Date, nullable=False),
        sa.Column('purchase_price', sa.Float, nullable=True),
        sa.Column('merchant', sa.String(200), nullable=True),
        sa.Column('expected_lifespan_years', sa.Integer, nullable=False, default=10),
        sa.Column('warranty_end_date', sa.Date, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('replacement_due_date', sa.Date, nullable=True),
        sa.Column('replacement_notified', sa.Boolean, nullable=False, default=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
    )
    op.create_index('idx_appliance_family', 'appliances', ['family_id', 'status'])
    op.create_index('idx_appliance_category', 'appliances', ['category'])
    op.create_index('idx_appliance_replacement', 'appliances', ['replacement_due_date'], postgresql_where=sa.text('replacement_due_date IS NOT NULL'))

    # member_size_preferences table
    op.create_table(
        'member_size_preferences',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('member_id', UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('clothing_size', sa.String(20), nullable=True),
        sa.Column('shoe_size', sa.String(20), nullable=True),
        sa.Column('pants_size', sa.String(20), nullable=True),
        sa.Column('height', sa.Float, nullable=True),
        sa.Column('weight', sa.Float, nullable=True),
        sa.Column('chest', sa.Float, nullable=True),
        sa.Column('waist', sa.Float, nullable=True),
        sa.Column('preferred_brands', sa.String(500), nullable=True),
        sa.Column('preferred_styles', sa.String(500), nullable=True),
        sa.Column('last_update_date', sa.Date, nullable=True),
        sa.Column('last_purchase_date', sa.Date, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, default=False),
    )
    op.create_index('idx_member_size_family', 'member_size_preferences', ['family_id'])
    op.create_index('idx_member_size_member', 'member_size_preferences', ['member_id', 'is_deleted'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('member_size_preferences')
    op.drop_table('appliances')
    op.drop_table('price_watches')
    op.drop_table('purchase_history')
    op.drop_table('household_inventory')
    op.drop_table('shopping_items')
    op.drop_table('shopping_lists')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS appliance_status_enum')
    op.execute('DROP TYPE IF EXISTS list_status_enum')
    op.execute('DROP TYPE IF EXISTS list_type_enum')
