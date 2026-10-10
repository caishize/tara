"""Add member locations and vehicle primary driver

Revision ID: 030
Revises: 029
Create Date: 2025-12-23

Adds:
- Member: locations (JSONB) for storing home/work/custom locations
- Member: default_location_type for default location preference
- Vehicle: primary_driver_id for tracking who drives daily

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '030_member_loc_vehicle_drv'
down_revision = '029_intelligent_secretary'
branch_labels = None
depends_on = None


def column_exists(connection, table_name, column_name):
    """Check if a column exists in the table."""
    result = connection.execute(sa.text(
        f"""SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = '{table_name}'
            AND column_name = '{column_name}'
        )"""
    ))
    return result.scalar()


def upgrade():
    connection = op.get_bind()

    # Add locations field to members table
    if not column_exists(connection, 'members', 'locations'):
        op.add_column('members', sa.Column('locations', JSONB, nullable=True, server_default='{}'))

    # Add default_location_type field to members table
    if not column_exists(connection, 'members', 'default_location_type'):
        op.add_column('members', sa.Column('default_location_type', sa.String(50), nullable=True, server_default='home'))

    # Add primary_driver_id field to vehicles table
    if not column_exists(connection, 'vehicles', 'primary_driver_id'):
        op.add_column('vehicles', sa.Column('primary_driver_id', UUID(as_uuid=True), nullable=True))
        # Create index for primary_driver_id
        op.create_index('idx_vehicle_primary_driver', 'vehicles', ['primary_driver_id', 'is_deleted'])


def downgrade():
    connection = op.get_bind()

    # Remove index and primary_driver_id from vehicles
    if column_exists(connection, 'vehicles', 'primary_driver_id'):
        op.drop_index('idx_vehicle_primary_driver', table_name='vehicles')
        op.drop_column('vehicles', 'primary_driver_id')

    # Remove default_location_type from members
    if column_exists(connection, 'members', 'default_location_type'):
        op.drop_column('members', 'default_location_type')

    # Remove locations from members
    if column_exists(connection, 'members', 'locations'):
        op.drop_column('members', 'locations')
