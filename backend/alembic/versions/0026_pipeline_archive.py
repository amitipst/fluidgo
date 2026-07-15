"""Soft-delete (archive) for pipeline deals. Root cause of "dummy data from
deactivated users shows in Pipeline/Opportunities for super_admin/ceo/coo":
resolve_visible_user_ids returns None for scope="all", so list_deals/
list_opportunities applied NO owner filter at all, and there was no delete
endpoint anywhere. Deals still never hard-delete (they feed revenue/
win-loss/FGA history) — archived just excludes them from every list by
default, recoverable via include_archived=true.

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pipeline', sa.Column(
        'archived', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('pipeline', sa.Column(
        'archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pipeline', sa.Column(
        'archived_by', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade():
    op.drop_column('pipeline', 'archived_by')
    op.drop_column('pipeline', 'archived_at')
    op.drop_column('pipeline', 'archived')
