"""company_first_and_sp_stage — link leads/deals to the Contacts master and
give deals an SP stage

v1.5.0 (2026-10-26). Purely additive and nullable: no existing row changes
meaning and nothing is backfilled here. Matching old free-text company names
to Accounts is a judgement call (is "Sunpack Systems" the same customer as
"Sunpack Group"?), so it lives in scripts/backfill_company_links.py — a
dry-run-by-default report Amit reviews — not in a migration that would decide
silently.

  leads.account_id / leads.contact_id   soft refs to accounts / contacts
  pipeline.contact_id                   soft ref to contacts
  pipeline.sp_stage                     SP1..SP7 key (deal_rules_service)

Indexed on the account columns because "all deals / leads for this customer"
is now a primary query (company page, trends by customer).

Revision ID: 0039
Revises: 0038
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("leads", sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("pipeline", sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("pipeline", sa.Column("sp_stage", sa.String(40), nullable=True))
    op.create_index("ix_leads_account_id", "leads", ["account_id"])
    op.create_index("ix_pipeline_account_id", "pipeline", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_account_id", table_name="pipeline")
    op.drop_index("ix_leads_account_id", table_name="leads")
    op.drop_column("pipeline", "sp_stage")
    op.drop_column("pipeline", "contact_id")
    op.drop_column("leads", "contact_id")
    op.drop_column("leads", "account_id")
