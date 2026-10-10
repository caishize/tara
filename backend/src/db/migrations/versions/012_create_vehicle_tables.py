"""Create vehicle management tables

Revision ID: 012_vehicle_tables
Revises: 011_create_dining_nutrition_tables
Create Date: 2025-11-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '012_vehicle_tables'
down_revision: Union[str, None] = '011_dining_nutrition'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create vehicles table
    op.create_table(
        'vehicles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False),
        sa.Column('brand', sa.String(100), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('plate_number', sa.Text, nullable=False),
        sa.Column('vin', sa.Text, nullable=True),
        sa.Column('purchase_date', sa.Date, nullable=True),
        sa.Column('current_mileage', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('fuel_type', sa.String(50), nullable=False, server_default='gasoline'),
        sa.Column('color', sa.String(50), nullable=True),
        sa.Column('engine_displacement', sa.String(50), nullable=True),
        sa.Column('maintenance_cycle_km', sa.Integer, nullable=False, server_default='10000'),
        sa.Column('maintenance_cycle_months', sa.Integer, nullable=False, server_default='12'),
        sa.Column('next_maintenance_km', sa.Float, nullable=True),
        sa.Column('next_maintenance_date', sa.Date, nullable=True),
        sa.Column('last_maintenance_date', sa.Date, nullable=True),
        sa.Column('last_maintenance_km', sa.Float, nullable=True),
        sa.Column('insurance_company', sa.String(100), nullable=True),
        sa.Column('insurance_expiry_date', sa.Date, nullable=True),
        sa.Column('last_insurance_premium', sa.Float, nullable=True),
        sa.Column('annual_inspection_date', sa.Date, nullable=True),
        sa.Column('purchase_price', sa.Float, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('vehicle_photo_url', sa.String(500), nullable=True),
        sa.Column('tags', JSONB, nullable=True),
        sa.Column('is_primary', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Integer, nullable=False, server_default='0'),
        sa.CheckConstraint('current_mileage >= 0', name='check_mileage_positive'),
        sa.CheckConstraint('maintenance_cycle_km > 0', name='check_maintenance_cycle_km'),
        sa.CheckConstraint('maintenance_cycle_months > 0', name='check_maintenance_cycle_months'),
    )
    op.create_index('idx_vehicle_family', 'vehicles', ['family_id', 'is_deleted'])
    op.create_index('idx_vehicle_owner', 'vehicles', ['owner_id', 'is_deleted'])

    # Create maintenance_records table
    op.create_table(
        'maintenance_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('vehicle_id', UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('maintenance_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('mileage_at_service', sa.Float, nullable=True),
        sa.Column('service_date', sa.Date, nullable=False),
        sa.Column('service_provider', sa.String(200), nullable=True),
        sa.Column('cost', sa.Float, nullable=True),
        sa.Column('parts_replaced', JSONB, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('next_service_km', sa.Float, nullable=True),
        sa.Column('next_service_date', sa.Date, nullable=True),
        sa.Column('receipt_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_index('idx_maintenance_vehicle', 'maintenance_records', ['vehicle_id', 'is_deleted'])
    op.create_index('idx_maintenance_date', 'maintenance_records', ['service_date'])

    # Create fuel_records table
    op.create_table(
        'fuel_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('vehicle_id', UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('fuel_date', sa.Date, nullable=False),
        sa.Column('fuel_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('price_per_unit', sa.Float, nullable=False),
        sa.Column('total_cost', sa.Float, nullable=False),
        sa.Column('mileage_at_fill', sa.Float, nullable=True),
        sa.Column('is_full_tank', sa.Integer, nullable=False, server_default='1'),
        sa.Column('station_name', sa.String(200), nullable=True),
        sa.Column('station_location', sa.String(500), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_index('idx_fuel_vehicle', 'fuel_records', ['vehicle_id', 'is_deleted'])
    op.create_index('idx_fuel_date', 'fuel_records', ['fuel_date'])

    # Create violation_records table
    op.create_table(
        'violation_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('vehicle_id', UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('violation_date', sa.Date, nullable=False),
        sa.Column('violation_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('fine_amount', sa.Float, nullable=True),
        sa.Column('points_deducted', sa.Integer, nullable=True),
        sa.Column('is_paid', sa.Integer, nullable=False, server_default='0'),
        sa.Column('payment_date', sa.Date, nullable=True),
        sa.Column('appeal_status', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_index('idx_violation_vehicle', 'violation_records', ['vehicle_id', 'is_deleted'])

    # Create insurance_policies table
    op.create_table(
        'insurance_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('vehicle_id', UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('policy_type', sa.String(100), nullable=False),
        sa.Column('insurance_company', sa.String(200), nullable=False),
        sa.Column('policy_number', sa.String(100), nullable=True),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('end_date', sa.Date, nullable=False),
        sa.Column('premium', sa.Float, nullable=True),
        sa.Column('coverage_amount', sa.Float, nullable=True),
        sa.Column('deductible', sa.Float, nullable=True),
        sa.Column('coverage_details', JSONB, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('document_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_index('idx_insurance_vehicle', 'insurance_policies', ['vehicle_id', 'is_deleted'])
    op.create_index('idx_insurance_expiry', 'insurance_policies', ['end_date'])

    # Create vehicle_expenses table
    op.create_table(
        'vehicle_expenses',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('vehicle_id', UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('expense_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('expense_date', sa.Date, nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('receipt_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_index('idx_expense_vehicle', 'vehicle_expenses', ['vehicle_id', 'is_deleted'])
    op.create_index('idx_expense_date', 'vehicle_expenses', ['expense_date'])


def downgrade() -> None:
    op.drop_table('vehicle_expenses')
    op.drop_table('insurance_policies')
    op.drop_table('violation_records')
    op.drop_table('fuel_records')
    op.drop_table('maintenance_records')
    op.drop_table('vehicles')
