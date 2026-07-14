"""Password security: force-change-on-first-login + force-change-after-
admin-reset. Adds must_change_password (drives a hard client+server gate
until the user sets their own password) and password_changed_at (basic
audit trail, foundation for a future "password age" policy if ever needed).

Existing users are backfilled to must_change_password=true rather than
false - nobody gets silently grandfathered out of the new policy just
because their account predates this migration. Business Head/Admin can
walk through Team page and reset each real account's password once to
clear it (which is itself now the properly-audited admin-reset flow).

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column(
        'must_change_password', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column(
        'password_changed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'must_change_password')
