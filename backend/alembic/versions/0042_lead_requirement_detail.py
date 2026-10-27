"""lead_requirement_detail - free-text description of what the customer actually needs

v1.6.1 (2026-10-27). The Requirement dropdown is a category only, so a lead logged
as "Other" lost the real need ("VDI instead of new workstations, quote for PA
system"). Salesforce keeps a Description on the Lead for exactly this; amount and
close date stay on the deal. Additive, nullable, no backfill.

Revision ID: 0042
Revises: 0041
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("requirement_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "requirement_detail")
