"""deal_title — a short name per deal so parallel deals on one company are distinguishable

v1.6.0 (2026-10-26). Amit: 2-3 deals run in parallel on one customer; the
duplicate guard warns (and allows) rather than blocks, and needs a name to tell
them apart (Salesforce "Opportunity Name"). Additive, nullable; existing rows
show their company + requirement as before.

Revision ID: 0041
Revises: 0040
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline", sa.Column("title", sa.String(150), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline", "title")
