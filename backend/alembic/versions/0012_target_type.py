"""Add target_type to revenue_targets (revenue vs order_booking).
Also update the uniqueness so a user can hold both a revenue AND an
order_booking target for the same period.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('revenue_targets', sa.Column('target_type', sa.String(20),
                   server_default='revenue', nullable=False))

def downgrade():
    op.drop_column('revenue_targets', 'target_type')
