"""Add edit-request/grant fields to dsr_daily, for the 24h self-edit window
with manager-granted exceptions after that.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('dsr_daily', sa.Column('edit_request_reason', sa.String(500), nullable=True))
    op.add_column('dsr_daily', sa.Column('edit_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('dsr_daily', sa.Column('edit_granted_until', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('dsr_daily', 'edit_granted_until')
    op.drop_column('dsr_daily', 'edit_requested_at')
    op.drop_column('dsr_daily', 'edit_request_reason')
