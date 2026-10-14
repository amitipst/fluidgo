"""Companies-first Contacts (v1.4.0): account descriptive fields + contact left/move continuity.

Additive and nullable only — safe to run on a live DB, no backfill needed.
Revision ID: 0035
Revises: 0034
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('accounts', sa.Column('industry', sa.String(100), nullable=True))
    op.add_column('accounts', sa.Column('website', sa.String(255), nullable=True))
    op.add_column('accounts', sa.Column('address_line1', sa.String(200), nullable=True))
    op.add_column('accounts', sa.Column('address_line2', sa.String(200), nullable=True))
    op.add_column('accounts', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('accounts', sa.Column('state', sa.String(100), nullable=True))
    op.add_column('accounts', sa.Column('country', sa.String(2), nullable=True))
    op.add_column('accounts', sa.Column('postal_code', sa.String(20), nullable=True))
    op.add_column('accounts', sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('contacts', sa.Column('left_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('contacts', sa.Column('previous_contact_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_contacts_previous', 'contacts', ['previous_contact_id'])
    # people already marked left before this release get a best-effort date
    op.execute("UPDATE contacts SET left_at = updated_at WHERE status = 'left' AND left_at IS NULL")


def downgrade():
    op.drop_index('ix_contacts_previous', table_name='contacts')
    op.drop_column('contacts', 'previous_contact_id')
    op.drop_column('contacts', 'left_at')
    op.drop_column('accounts', 'created_by')
    for col in ('postal_code', 'country', 'state', 'city', 'address_line2', 'address_line1'):
        op.drop_column('accounts', col)
    op.drop_column('accounts', 'website')
    op.drop_column('accounts', 'industry')
