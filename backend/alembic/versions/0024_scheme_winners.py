"""Scheme winner validation. Previously an "achieved" scheme was just a
number computed on the fly in Gamification.tsx's progress view - nothing
was ever persisted, and PointsLedger was never actually written to by
anything despite the model existing. This adds a real winner record with
an HR sign-off gate before cash rewards are treated as payable; points/
badge/recognition stay low-stakes and auto-approve on detection (and are
now actually credited for the first time). Purely additive.

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheme_winners',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scheme_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period', sa.String(7), nullable=False),
        sa.Column('achieved_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('target_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('reward_type', sa.String(20), nullable=False),
        sa.Column('reward_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('reward_badge', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending_hr', nullable=False),
        sa.Column('hr_reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('hr_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hr_comment', sa.String(500), nullable=True),
        sa.Column('paid', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_scheme_winners_scheme_user_period',
        'scheme_winners', ['scheme_id', 'user_id', 'period'], unique=True,
    )


def downgrade():
    op.drop_index('ix_scheme_winners_scheme_user_period', table_name='scheme_winners')
    op.drop_table('scheme_winners')
