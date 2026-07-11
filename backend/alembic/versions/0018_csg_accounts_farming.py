"""CSG Phase 1: Account entity, hunting/farming distinction on pipeline,
Service Delivery -> Sales opportunity signal.

All additive - zero risk to existing rows. Existing deals default to
deal_type='hunting', source='sales' (accurate: they were all net-new
pipeline before this concept existed).

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('business', sa.String(50), server_default='fluidpro', nullable=False),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('primary_owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column('pipeline', sa.Column(
        'deal_type', sa.String(20), server_default='hunting', nullable=True))
    op.add_column('pipeline', sa.Column(
        'source', sa.String(20), server_default='sales', nullable=True))
    op.add_column('pipeline', sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True))

    op.add_column('dor_daily', sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade():
    op.drop_column('dor_daily', 'account_id')
    op.drop_column('pipeline', 'account_id')
    op.drop_column('pipeline', 'source')
    op.drop_column('pipeline', 'deal_type')
    op.drop_table('accounts')
