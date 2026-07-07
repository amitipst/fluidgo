"""Add status/error_detail to ai_insights, for background-generated dashboard AI

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('ai_insights', sa.Column('status', sa.String(20),
                   server_default='ready', nullable=False))
    op.add_column('ai_insights', sa.Column('error_detail', sa.Text, nullable=True))
    # content was NOT NULL before; a 'pending' row is written before content
    # exists, so it must now be nullable.
    op.alter_column('ai_insights', 'content', nullable=True)

def downgrade():
    op.alter_column('ai_insights', 'content', nullable=False)
    op.drop_column('ai_insights', 'error_detail')
    op.drop_column('ai_insights', 'status')
