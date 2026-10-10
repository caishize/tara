"""create housing and housekeeping tables

Revision ID: 013_create_housing_tables
Revises: 011_create_dining_nutrition_tables
Create Date: 2025-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '013_create_housing_tables'
down_revision: Union[str, None] = '011_dining_nutrition'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums
    op.execute("""
        CREATE TYPE property_fee_cycle_enum AS ENUM ('monthly', 'quarterly', 'semi_annual', 'annual')
    """)

    op.execute("""
        CREATE TYPE payment_status_enum AS ENUM ('pending', 'completed', 'overdue', 'cancelled')
    """)

    op.execute("""
        CREATE TYPE appliance_type_enum AS ENUM (
            'air_conditioner', 'washing_machine', 'refrigerator', 'range_hood',
            'water_heater', 'water_purifier', 'dishwasher', 'dryer', 'other'
        )
    """)

    op.execute("""
        CREATE TYPE housing_appliance_status_enum AS ENUM ('active', 'maintenance', 'retired', 'broken')
    """)

    op.execute("""
        CREATE TYPE service_type_enum AS ENUM (
            'cleaning', 'deep_cleaning', 'repair', 'moving',
            'nanny', 'babysitter', 'elderly_care', 'other'
        )
    """)

    # Create properties table
    op.create_table(
        'properties',
        sa.Column('property_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('family_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('area_sqm', sa.Numeric(10, 2), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),

        # Mortgage info
        sa.Column('mortgage_bank', sa.String(200), nullable=True),
        sa.Column('mortgage_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('mortgage_day', sa.Integer(), nullable=True),
        sa.Column('mortgage_account', sa.String(100), nullable=True),

        # Property fee info
        sa.Column('property_fee_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('property_fee_cycle', postgresql.ENUM(
            'monthly', 'quarterly', 'semi_annual', 'annual',
            name='property_fee_cycle_enum', create_type=False
        ), nullable=True),
        sa.Column('property_fee_day', sa.Integer(), nullable=True),
        sa.Column('last_property_fee_date', sa.Date(), nullable=True),

        # Metadata
        sa.Column('notes', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('property_id'),
        sa.CheckConstraint('mortgage_day >= 1 AND mortgage_day <= 31', name='check_mortgage_day'),
        sa.CheckConstraint('property_fee_day >= 1 AND property_fee_day <= 31', name='check_property_fee_day'),
    )

    op.create_index('ix_properties_family_id', 'properties', ['family_id'])
    op.create_index('ix_properties_owner_id', 'properties', ['owner_id'])

    # Create mortgage_payments table
    op.create_table(
        'mortgage_payments',
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_method', sa.String(100), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'pending', 'completed', 'overdue', 'cancelled',
            name='payment_status_enum', create_type=False
        ), nullable=False),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('payment_id'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.property_id'], ondelete='CASCADE'),
    )

    op.create_index('ix_mortgage_payments_property_id', 'mortgage_payments', ['property_id'])
    op.create_index('ix_mortgage_payments_payment_date', 'mortgage_payments', ['payment_date'])
    op.create_index('ix_mortgage_payments_status', 'mortgage_payments', ['status'])

    # Create property_fee_payments table
    op.create_table(
        'property_fee_payments',
        sa.Column('fee_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('period', sa.String(100), nullable=True),
        sa.Column('payment_method', sa.String(100), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'pending', 'completed', 'overdue', 'cancelled',
            name='payment_status_enum', create_type=False
        ), nullable=False),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('fee_id'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.property_id'], ondelete='CASCADE'),
    )

    op.create_index('ix_property_fee_payments_property_id', 'property_fee_payments', ['property_id'])
    op.create_index('ix_property_fee_payments_payment_date', 'property_fee_payments', ['payment_date'])
    op.create_index('ix_property_fee_payments_status', 'property_fee_payments', ['status'])

    # Create property_appliances table
    op.create_table(
        'property_appliances',
        sa.Column('appliance_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', postgresql.ENUM(
            'air_conditioner', 'washing_machine', 'refrigerator', 'range_hood',
            'water_heater', 'water_purifier', 'dishwasher', 'dryer', 'other',
            name='appliance_type_enum', create_type=False
        ), nullable=False),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('maintenance_cycle_months', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('last_maintenance_date', sa.Date(), nullable=True),
        sa.Column('next_maintenance_date', sa.Date(), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'active', 'maintenance', 'retired', 'broken',
            name='housing_appliance_status_enum', create_type=False
        ), nullable=False),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('appliance_id'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.property_id'], ondelete='CASCADE'),
        sa.CheckConstraint('maintenance_cycle_months >= 1 AND maintenance_cycle_months <= 60', name='check_maintenance_cycle'),
    )

    op.create_index('ix_property_appliances_property_id', 'property_appliances', ['property_id'])
    op.create_index('ix_property_appliances_status', 'property_appliances', ['status'])
    op.create_index('ix_property_appliances_next_maintenance_date', 'property_appliances', ['next_maintenance_date'])

    # Create appliance_maintenance table
    op.create_table(
        'appliance_maintenance',
        sa.Column('maintenance_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('appliance_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('maintenance_date', sa.Date(), nullable=False),
        sa.Column('content', sa.String(1000), nullable=True),
        sa.Column('cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('service_provider', sa.String(200), nullable=True),
        sa.Column('technician_name', sa.String(100), nullable=True),
        sa.Column('technician_phone', sa.String(20), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('maintenance_id'),
        sa.ForeignKeyConstraint(['appliance_id'], ['property_appliances.appliance_id'], ondelete='CASCADE'),
    )

    op.create_index('ix_appliance_maintenance_appliance_id', 'appliance_maintenance', ['appliance_id'])
    op.create_index('ix_appliance_maintenance_maintenance_date', 'appliance_maintenance', ['maintenance_date'])

    # Create housekeeping_services table
    op.create_table(
        'housekeeping_services',
        sa.Column('service_id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_date', sa.Date(), nullable=False),
        sa.Column('service_type', postgresql.ENUM(
            'cleaning', 'deep_cleaning', 'repair', 'moving',
            'nanny', 'babysitter', 'elderly_care', 'other',
            name='service_type_enum', create_type=False
        ), nullable=False),
        sa.Column('provider', sa.String(200), nullable=True),
        sa.Column('service_person_name', sa.String(100), nullable=True),
        sa.Column('service_person_phone', sa.String(20), nullable=True),
        sa.Column('cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('frequency_days', sa.Integer(), nullable=True),
        sa.Column('next_booking_reminder', sa.Date(), nullable=True),
        sa.Column('notes', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('service_id'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.property_id'], ondelete='CASCADE'),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating'),
        sa.CheckConstraint('frequency_days >= 1', name='check_frequency'),
    )

    op.create_index('ix_housekeeping_services_property_id', 'housekeeping_services', ['property_id'])
    op.create_index('ix_housekeeping_services_service_date', 'housekeeping_services', ['service_date'])
    op.create_index('ix_housekeeping_services_next_booking_reminder', 'housekeeping_services', ['next_booking_reminder'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('housekeeping_services')
    op.drop_table('appliance_maintenance')
    op.drop_table('property_appliances')
    op.drop_table('property_fee_payments')
    op.drop_table('mortgage_payments')
    op.drop_table('properties')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS service_type_enum')
    op.execute('DROP TYPE IF EXISTS housing_appliance_status_enum')
    op.execute('DROP TYPE IF EXISTS appliance_type_enum')
    op.execute('DROP TYPE IF EXISTS payment_status_enum')
    op.execute('DROP TYPE IF EXISTS property_fee_cycle_enum')
