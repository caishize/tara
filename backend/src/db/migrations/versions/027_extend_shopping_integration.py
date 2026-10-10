"""Extend shopping items with additional integration fields

Revision ID: 027_shopping_integration
Revises: 026_recommendation_cache
Create Date: 2024-12-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '027_shopping_integration'
down_revision = '026_recommendation_cache'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add additional integration fields to shopping_items."""
    # Add purchase_url for external purchase links
    op.add_column('shopping_items', sa.Column('purchase_url', sa.Text(), nullable=True))

    # Add event_id and event_type for tracking source events
    op.add_column('shopping_items', sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shopping_items', sa.Column('event_type', sa.String(20), nullable=True))

    # Create index for event lookup
    op.create_index('idx_shopping_items_event', 'shopping_items', ['event_id', 'event_type'])

    # Add linked_shopping_item_id to gift_recommendations for bidirectional reference
    # Note: shopping_item_id was added in 024, this adds explicit bidirectional link
    op.add_column('gift_recommendations', sa.Column('linked_shopping_item_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('idx_gift_recommendations_linked_shopping', 'gift_recommendations', ['linked_shopping_item_id'])


def downgrade() -> None:
    """Remove additional integration fields."""
    op.drop_index('idx_gift_recommendations_linked_shopping', 'gift_recommendations')
    op.drop_column('gift_recommendations', 'linked_shopping_item_id')

    op.drop_index('idx_shopping_items_event', 'shopping_items')
    op.drop_column('shopping_items', 'event_type')
    op.drop_column('shopping_items', 'event_id')
    op.drop_column('shopping_items', 'purchase_url')
