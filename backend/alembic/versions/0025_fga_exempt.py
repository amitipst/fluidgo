"""Per-user FGA exemption flag. When set, freeze_period skips this person
entirely (no ScoringResult ever gets created for them), and HR's BU-wise
overview reports them as "Not Applicable" instead of counting them as an
incomplete/missing submission. Purely additive.

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'fga_exempt', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('users', 'fga_exempt')
