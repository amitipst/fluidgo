"""AI deal-momentum check (on-demand): given the pipeline_updates sequence
for a deal, judge whether it's moving forward, stalled, or going in
circles. Adds two nullable columns to cache the last verdict on the deal
itself, mirroring outcome_ai_analysis's pattern - so reopening a deal card
doesn't require re-running Ollama every time. Purely additive.

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pipeline', sa.Column(
        'ai_momentum_summary', sa.Text(), nullable=True))
    op.add_column('pipeline', sa.Column(
        'ai_momentum_generated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('pipeline', 'ai_momentum_generated_at')
    op.drop_column('pipeline', 'ai_momentum_summary')
