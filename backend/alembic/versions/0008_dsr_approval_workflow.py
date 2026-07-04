"""Add DSR approval workflow + data persistence verification

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

def upgrade():
    # ── DSR approval fields ───────────────────────────────────────────────────
    # approval_status: draft → submitted → approved | rejected
    op.add_column('dsr_daily', sa.Column(
        'approval_status',
        sa.String(20),
        nullable=False,
        server_default='submitted'   # all existing DSRs count as submitted
    ))
    op.add_column('dsr_daily', sa.Column(
        'approved_by',
        sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True
    ))
    op.add_column('dsr_daily', sa.Column(
        'approved_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))
    op.add_column('dsr_daily', sa.Column(
        'manager_comment',
        sa.String(500),
        nullable=True
    ))

    # Index for fast approval queue queries
    op.create_index('ix_dsr_approval_status', 'dsr_daily', ['approval_status'])
    op.create_index('ix_dsr_user_date', 'dsr_daily', ['user_id', 'date'])

def downgrade():
    op.drop_index('ix_dsr_user_date', 'dsr_daily')
    op.drop_index('ix_dsr_approval_status', 'dsr_daily')
    for col in ['approval_status', 'approved_by', 'approved_at', 'manager_comment']:
        op.drop_column('dsr_daily', col)
