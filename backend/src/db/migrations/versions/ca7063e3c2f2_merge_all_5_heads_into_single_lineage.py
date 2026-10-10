"""Merge all 5 heads into single lineage

Revision ID: ca7063e3c2f2
Revises: 083, 004_create_child_growth_tables, 008, 012_vehicle_tables, f5619f3a2a5f
Create Date: 2026-02-12 23:38:59.970600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca7063e3c2f2'
down_revision: Union[str, None] = ('083', '004_create_child_growth_tables', '008', '012_vehicle_tables', 'f5619f3a2a5f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
