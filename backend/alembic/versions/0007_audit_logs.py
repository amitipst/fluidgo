"""Add audit_logs table

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('audit_logs',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',     UUID(as_uuid=True), nullable=False),
        sa.Column('user_email',  sa.String(255), nullable=False),
        sa.Column('user_role',   sa.String(30), nullable=False),
        sa.Column('user_bu',     sa.String(50), nullable=True),
        sa.Column('action',      sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id',   sa.String(36), nullable=True),
        sa.Column('summary',     sa.String(500), nullable=True),
        sa.Column('diff',        JSONB, nullable=True),
        sa.Column('ip_address',  sa.String(45), nullable=True),
        sa.Column('user_agent',  sa.String(500), nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_audit_user_id',    'audit_logs', ['user_id'])
    op.create_index('ix_audit_entity',     'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_action',     'audit_logs', ['action'])
    op.create_index('ix_audit_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_bu',         'audit_logs', ['user_bu'])

def downgrade():
    op.drop_index('ix_audit_bu',         'audit_logs')
    op.drop_index('ix_audit_created_at', 'audit_logs')
    op.drop_index('ix_audit_action',     'audit_logs')
    op.drop_index('ix_audit_entity',     'audit_logs')
    op.drop_index('ix_audit_user_id',    'audit_logs')
    op.drop_table('audit_logs')
