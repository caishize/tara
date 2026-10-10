"""Enhance shopping item fields for prototype implementation.

Add fields for:
- Item tags (多标签支持)
- Assigned buyer (指定购买人)
- Item status tracking (商品状态追踪)
- Delivery tracking (物流追踪)

Revision ID: 052_enhance_shopping
Revises: 051_create_user_insight_settings
Create Date: 2025-01-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '052_enhance_shopping'
down_revision = '051_create_user_insight_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tags field (多标签支持)
    op.add_column('shopping_items', sa.Column(
        'tags',
        JSONB,
        nullable=True,
        server_default='[]',
        comment='Item tags: daily, business_trip, gift, urgent'
    ))

    # Add assigned_to field (指定购买人)
    op.add_column('shopping_items', sa.Column(
        'assigned_to',
        UUID(as_uuid=True),
        nullable=True,
        comment='Member ID who should purchase this item'
    ))

    # Add item_status field (商品状态)
    op.add_column('shopping_items', sa.Column(
        'item_status',
        sa.String(20),
        nullable=False,
        server_default='pending',
        comment='Item status: pending, ordered, in_transit, delivered, cancelled'
    ))

    # Add order_date field (下单时间)
    op.add_column('shopping_items', sa.Column(
        'order_date',
        sa.TIMESTAMP,
        nullable=True,
        comment='When the item was ordered'
    ))

    # Add expected_delivery_date field (预计送达日期)
    op.add_column('shopping_items', sa.Column(
        'expected_delivery_date',
        sa.Date,
        nullable=True,
        comment='Expected delivery date'
    ))

    # Add tracking_number field (运单号)
    op.add_column('shopping_items', sa.Column(
        'tracking_number',
        sa.String(100),
        nullable=True,
        comment='Shipping tracking number'
    ))

    # Add tracking_updates field (物流更新)
    op.add_column('shopping_items', sa.Column(
        'tracking_updates',
        JSONB,
        nullable=True,
        server_default='[]',
        comment='Array of tracking updates: [{timestamp, status, location, description}]'
    ))

    # Create indexes for new fields
    op.create_index(
        'idx_shopping_item_assigned',
        'shopping_items',
        ['assigned_to'],
        postgresql_where=sa.text('assigned_to IS NOT NULL')
    )

    op.create_index(
        'idx_shopping_item_status',
        'shopping_items',
        ['item_status']
    )

    op.create_index(
        'idx_shopping_item_delivery',
        'shopping_items',
        ['expected_delivery_date'],
        postgresql_where=sa.text('expected_delivery_date IS NOT NULL')
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_shopping_item_delivery', table_name='shopping_items')
    op.drop_index('idx_shopping_item_status', table_name='shopping_items')
    op.drop_index('idx_shopping_item_assigned', table_name='shopping_items')

    # Drop columns
    op.drop_column('shopping_items', 'tracking_updates')
    op.drop_column('shopping_items', 'tracking_number')
    op.drop_column('shopping_items', 'expected_delivery_date')
    op.drop_column('shopping_items', 'order_date')
    op.drop_column('shopping_items', 'item_status')
    op.drop_column('shopping_items', 'assigned_to')
    op.drop_column('shopping_items', 'tags')
