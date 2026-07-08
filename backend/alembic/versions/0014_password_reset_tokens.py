"""Add password_reset_tokens table (single-use, hashed, time-limited).

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('password_reset_tokens',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',    UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at',    sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_prt_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)

def downgrade():
    op.drop_index('ix_prt_token_hash', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
