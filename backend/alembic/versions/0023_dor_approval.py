"""Simple manager approve/reject for DOR entries (Service Delivery). Unlike
DSR, deliberately no edit-lock/window: the SDM can always resubmit, and
approval_status resets to "submitted" on any save - a rejected entry stays
editable and reappears for review once resaved. Purely additive.

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dor_daily', sa.Column(
        'approval_status', sa.String(20), server_default='submitted', nullable=False))
    op.add_column('dor_daily', sa.Column(
        'approved_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('dor_daily', sa.Column(
        'approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('dor_daily', sa.Column(
        'manager_comment', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('dor_daily', 'manager_comment')
    op.drop_column('dor_daily', 'approved_at')
    op.drop_column('dor_daily', 'approved_by')
    op.drop_column('dor_daily', 'approval_status')
