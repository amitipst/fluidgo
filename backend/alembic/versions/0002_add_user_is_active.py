"""Add is_active to users — soft-disable accounts without losing historical data

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('is_active', sa.Boolean, server_default=sa.text('true'), nullable=False))

def downgrade():
    op.drop_column('users', 'is_active')
