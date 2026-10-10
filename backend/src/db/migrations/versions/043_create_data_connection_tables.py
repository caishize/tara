"""Create data connection tables

Revision ID: 043_data_connection
Revises: 042_notebook_tables
Create Date: 2026-01-20

Creates the data connection hub tables:
- data_connections: External data source connections (OAuth tokens, sync config)
- synced_data: Raw synced data from external sources
- parsed_orders: Orders extracted from email parsing
- parsed_travel_bookings: Travel bookings extracted from email parsing
- data_usage_logs: Tracks how synced data is used by services
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = '043_data_connection'
down_revision = '042_create_notebook_tables'
branch_labels = None
depends_on = None


def table_exists(connection, table_name):
    """Check if a table exists in the database."""
    result = connection.execute(sa.text(
        f"SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = '{table_name}')"
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # =========================================================================
    # Data Connections table - stores OAuth tokens and connection configuration
    # =========================================================================
    if not table_exists(connection, 'data_connections'):
        op.create_table(
            'data_connections',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),

            # Connector identification
            sa.Column('connector_id', sa.String(50), nullable=False),  # e.g., 'google_calendar', 'gmail'
            sa.Column('connector_name', sa.String(100), nullable=False),  # Display name

            # Connection status
            sa.Column('status', sa.String(20), nullable=False, server_default='disconnected'),
            # Status: disconnected, connecting, connected, syncing, error, expired
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('error_code', sa.String(50), nullable=True),

            # Encrypted credentials (AES-256-GCM)
            sa.Column('encrypted_access_token', sa.Text, nullable=True),
            sa.Column('encrypted_refresh_token', sa.Text, nullable=True),
            sa.Column('encrypted_api_key', sa.Text, nullable=True),
            sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('extra_credentials', JSONB, server_default='{}'),  # Additional encrypted data

            # Authorization scope
            sa.Column('requested_scopes', ARRAY(sa.String), server_default='{}'),
            sa.Column('granted_scopes', ARRAY(sa.String), server_default='{}'),

            # Sync configuration
            sa.Column('sync_frequency', sa.String(20), nullable=False, server_default='daily'),
            # Frequency: realtime, hourly, daily, weekly, manual
            sa.Column('sync_enabled', sa.Boolean, nullable=False, server_default='true'),
            sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_sync_cursor', sa.String(500), nullable=True),  # For incremental sync
            sa.Column('next_sync_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('sync_error_count', sa.Integer, nullable=False, server_default='0'),

            # Data usage permissions (user-configurable)
            sa.Column('usage_permissions', JSONB, server_default='{}'),
            # e.g., {"daily_briefing": true, "smart_suggestion": true, "memory_extraction": false}

            # Webhook configuration
            sa.Column('webhook_id', sa.String(200), nullable=True),  # External webhook registration ID
            sa.Column('webhook_url', sa.String(500), nullable=True),
            sa.Column('webhook_secret', sa.Text, nullable=True),  # Encrypted

            # Connection timestamps
            sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

        # Create indexes
        op.create_index('ix_data_conn_user_id', 'data_connections', ['user_id'])
        op.create_index('ix_data_conn_family_id', 'data_connections', ['family_id'])
        op.create_index('ix_data_conn_connector_id', 'data_connections', ['connector_id'])
        op.create_index('ix_data_conn_status', 'data_connections', ['status'])
        op.create_index('ix_data_conn_user_connector', 'data_connections', ['user_id', 'connector_id'])
        op.create_index('ix_data_conn_family_connector', 'data_connections', ['family_id', 'connector_id'])
        op.create_index('ix_data_conn_next_sync', 'data_connections', ['next_sync_at'])

        # Unique constraint: one connection per user per connector type
        op.create_unique_constraint(
            'uq_data_conn_user_connector',
            'data_connections',
            ['user_id', 'connector_id']
        )

    # =========================================================================
    # Synced Data table - stores raw synced data from external sources
    # =========================================================================
    if not table_exists(connection, 'synced_data'):
        op.create_table(
            'synced_data',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('connection_id', UUID(as_uuid=True), nullable=False),

            # Source identification
            sa.Column('source_id', sa.String(500), nullable=False),  # External system's ID
            sa.Column('data_type', sa.String(50), nullable=False),
            # Types: calendar_event, email, email_thread, contact, order, etc.

            # Raw and processed content
            sa.Column('raw_content', JSONB, nullable=False),  # Complete original data
            sa.Column('normalized_content', JSONB, server_default='{}'),  # Standardized format
            sa.Column('extracted_entities', JSONB, server_default='{}'),
            # Extracted: {person: [], location: [], time: [], amount: []}

            # Content metadata
            sa.Column('title', sa.String(500), nullable=True),  # For display
            sa.Column('preview', sa.Text, nullable=True),  # Short preview text
            sa.Column('content_hash', sa.String(64), nullable=True),  # For deduplication

            # Source timestamps
            sa.Column('source_created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_updated_at', sa.DateTime(timezone=True), nullable=True),

            # Sync metadata
            sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('sync_version', sa.Integer, nullable=False, server_default='1'),

            # Processing status
            sa.Column('is_processed', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('processing_error', sa.Text, nullable=True),

            # Lifecycle
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),

            # Foreign keys
            sa.ForeignKeyConstraint(['connection_id'], ['data_connections.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('ix_synced_data_connection_id', 'synced_data', ['connection_id'])
        op.create_index('ix_synced_data_source_id', 'synced_data', ['source_id'])
        op.create_index('ix_synced_data_type', 'synced_data', ['data_type'])
        op.create_index('ix_synced_data_conn_type', 'synced_data', ['connection_id', 'data_type'])
        op.create_index('ix_synced_data_synced_at', 'synced_data', ['synced_at'])
        op.create_index('ix_synced_data_source_created', 'synced_data', ['source_created_at'])
        op.create_index('ix_synced_data_is_processed', 'synced_data', ['is_processed'])
        op.create_index('ix_synced_data_content_hash', 'synced_data', ['content_hash'])
        op.create_index('ix_synced_data_entities', 'synced_data', ['extracted_entities'], postgresql_using='gin')

        # Unique constraint: prevent duplicate syncs of same source item
        op.create_unique_constraint(
            'uq_synced_data_source',
            'synced_data',
            ['connection_id', 'source_id', 'data_type']
        )

    # =========================================================================
    # Parsed Orders table - orders extracted from email parsing
    # =========================================================================
    if not table_exists(connection, 'parsed_orders'):
        op.create_table(
            'parsed_orders',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('synced_data_id', UUID(as_uuid=True), nullable=True),  # Link to source email
            sa.Column('connection_id', UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),

            # Platform identification
            sa.Column('platform', sa.String(50), nullable=False),  # taobao, jd, pdd, amazon, etc.
            sa.Column('order_id', sa.String(100), nullable=False),  # Platform's order ID
            sa.Column('order_url', sa.String(500), nullable=True),

            # Order status
            sa.Column('order_status', sa.String(30), nullable=False, server_default='pending'),
            # Status: pending, paid, shipped, delivered, completed, cancelled, refunded

            # Order items
            sa.Column('items', JSONB, nullable=False, server_default='[]'),
            # [{name, quantity, price, image_url, product_url}]
            sa.Column('total_amount', sa.Numeric(12, 2), nullable=True),
            sa.Column('currency', sa.String(10), nullable=False, server_default='CNY'),

            # Shipping info
            sa.Column('shipping_address', sa.Text, nullable=True),
            sa.Column('tracking_number', sa.String(100), nullable=True),
            sa.Column('carrier', sa.String(50), nullable=True),  # 顺丰, 中通, etc.
            sa.Column('estimated_delivery', sa.DateTime(timezone=True), nullable=True),
            sa.Column('actual_delivery', sa.DateTime(timezone=True), nullable=True),

            # Timestamps
            sa.Column('order_placed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

            # Parsing metadata
            sa.Column('parse_confidence', sa.Float, nullable=False, server_default='0.8'),
            sa.Column('raw_email_subject', sa.String(500), nullable=True),

            # Reminder tracking
            sa.Column('reminder_created', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('reminder_id', UUID(as_uuid=True), nullable=True),

            # Foreign keys
            sa.ForeignKeyConstraint(['synced_data_id'], ['synced_data.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['connection_id'], ['data_connections.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('ix_parsed_orders_user_id', 'parsed_orders', ['user_id'])
        op.create_index('ix_parsed_orders_family_id', 'parsed_orders', ['family_id'])
        op.create_index('ix_parsed_orders_platform', 'parsed_orders', ['platform'])
        op.create_index('ix_parsed_orders_status', 'parsed_orders', ['order_status'])
        op.create_index('ix_parsed_orders_user_status', 'parsed_orders', ['user_id', 'order_status'])
        op.create_index('ix_parsed_orders_order_id', 'parsed_orders', ['order_id'])
        op.create_index('ix_parsed_orders_tracking', 'parsed_orders', ['tracking_number'])
        op.create_index('ix_parsed_orders_delivery', 'parsed_orders', ['estimated_delivery'])

        # Unique constraint: prevent duplicate orders
        op.create_unique_constraint(
            'uq_parsed_orders_platform_order',
            'parsed_orders',
            ['user_id', 'platform', 'order_id']
        )

    # =========================================================================
    # Parsed Travel Bookings table - travel bookings extracted from email
    # =========================================================================
    if not table_exists(connection, 'parsed_travel_bookings'):
        op.create_table(
            'parsed_travel_bookings',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('synced_data_id', UUID(as_uuid=True), nullable=True),
            sa.Column('connection_id', UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),
            sa.Column('family_id', UUID(as_uuid=True), nullable=False),

            # Booking type
            sa.Column('booking_type', sa.String(30), nullable=False),
            # Types: flight, hotel, train, car_rental, cruise, activity

            # Platform and booking reference
            sa.Column('platform', sa.String(50), nullable=False),  # ctrip, qunar, feizhu, airline
            sa.Column('booking_id', sa.String(100), nullable=False),
            sa.Column('booking_url', sa.String(500), nullable=True),
            sa.Column('booking_status', sa.String(30), nullable=False, server_default='confirmed'),

            # Flight specific
            sa.Column('flight_number', sa.String(20), nullable=True),
            sa.Column('airline', sa.String(100), nullable=True),
            sa.Column('departure_city', sa.String(100), nullable=True),
            sa.Column('arrival_city', sa.String(100), nullable=True),
            sa.Column('departure_airport', sa.String(100), nullable=True),
            sa.Column('arrival_airport', sa.String(100), nullable=True),
            sa.Column('departure_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('arrival_time', sa.DateTime(timezone=True), nullable=True),

            # Hotel specific
            sa.Column('hotel_name', sa.String(200), nullable=True),
            sa.Column('hotel_address', sa.Text, nullable=True),
            sa.Column('check_in_date', sa.Date, nullable=True),
            sa.Column('check_out_date', sa.Date, nullable=True),
            sa.Column('room_type', sa.String(100), nullable=True),

            # Train specific
            sa.Column('train_number', sa.String(20), nullable=True),

            # Common fields
            sa.Column('passengers', JSONB, server_default='[]'),  # [{name, id_type, id_number}]
            sa.Column('total_amount', sa.Numeric(12, 2), nullable=True),
            sa.Column('currency', sa.String(10), nullable=False, server_default='CNY'),

            # Timestamps
            sa.Column('booked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

            # Parsing metadata
            sa.Column('parse_confidence', sa.Float, nullable=False, server_default='0.8'),
            sa.Column('raw_email_subject', sa.String(500), nullable=True),

            # Integration with travel module
            sa.Column('linked_travel_plan_id', UUID(as_uuid=True), nullable=True),
            sa.Column('auto_created_travel_plan', sa.Boolean, nullable=False, server_default='false'),

            # Foreign keys
            sa.ForeignKeyConstraint(['synced_data_id'], ['synced_data.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['connection_id'], ['data_connections.id'], ondelete='CASCADE'),
        )

        # Create indexes
        op.create_index('ix_parsed_travel_user_id', 'parsed_travel_bookings', ['user_id'])
        op.create_index('ix_parsed_travel_family_id', 'parsed_travel_bookings', ['family_id'])
        op.create_index('ix_parsed_travel_type', 'parsed_travel_bookings', ['booking_type'])
        op.create_index('ix_parsed_travel_status', 'parsed_travel_bookings', ['booking_status'])
        op.create_index('ix_parsed_travel_departure', 'parsed_travel_bookings', ['departure_time'])
        op.create_index('ix_parsed_travel_checkin', 'parsed_travel_bookings', ['check_in_date'])
        op.create_index('ix_parsed_travel_flight', 'parsed_travel_bookings', ['flight_number'])
        op.create_index('ix_parsed_travel_booking_id', 'parsed_travel_bookings', ['booking_id'])

        # Unique constraint
        op.create_unique_constraint(
            'uq_parsed_travel_booking',
            'parsed_travel_bookings',
            ['user_id', 'platform', 'booking_id']
        )

    # =========================================================================
    # Data Usage Logs table - tracks how synced data is consumed
    # =========================================================================
    if not table_exists(connection, 'data_usage_logs'):
        op.create_table(
            'data_usage_logs',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('connection_id', UUID(as_uuid=True), nullable=False),
            sa.Column('synced_data_id', UUID(as_uuid=True), nullable=True),
            sa.Column('user_id', UUID(as_uuid=True), nullable=False),

            # Usage details
            sa.Column('usage_type', sa.String(50), nullable=False),
            # Types: daily_briefing, smart_suggestion, memory_extraction, schedule_aggregation
            sa.Column('consumer_service', sa.String(100), nullable=False),
            # Service: DailyBriefingService, SmartSuggestionService, etc.

            # What was accessed
            sa.Column('data_type', sa.String(50), nullable=True),
            sa.Column('fields_accessed', ARRAY(sa.String), server_default='{}'),

            # Audit timestamp
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

            # Foreign keys
            sa.ForeignKeyConstraint(['connection_id'], ['data_connections.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['synced_data_id'], ['synced_data.id'], ondelete='SET NULL'),
        )

        # Create indexes
        op.create_index('ix_data_usage_connection_id', 'data_usage_logs', ['connection_id'])
        op.create_index('ix_data_usage_user_id', 'data_usage_logs', ['user_id'])
        op.create_index('ix_data_usage_type', 'data_usage_logs', ['usage_type'])
        op.create_index('ix_data_usage_service', 'data_usage_logs', ['consumer_service'])
        op.create_index('ix_data_usage_used_at', 'data_usage_logs', ['used_at'])
        op.create_index('ix_data_usage_conn_type', 'data_usage_logs', ['connection_id', 'usage_type'])


def downgrade():
    op.drop_table('data_usage_logs')
    op.drop_table('parsed_travel_bookings')
    op.drop_table('parsed_orders')
    op.drop_table('synced_data')
    op.drop_table('data_connections')
