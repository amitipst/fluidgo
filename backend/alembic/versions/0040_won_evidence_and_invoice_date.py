"""won_evidence_and_invoice_date — when a deal is WON vs when revenue is recognised

v1.5.0 (2026-10-26). Amit: "won should be when we get a customer email / LOI /
PO / agreement, but for revenue we report when the tax invoice is raised."

  pipeline.won_at       date the customer's commitment was received
  pipeline.won_basis    email | loi | po | agreement
  pipeline.won_ref      PO / LOI / agreement number or mail reference (free text)
  pipeline.invoiced_at  date the tax invoice was raised (revenue recognition)
  pipeline.invoice_ref  tax invoice number

Purely additive and nullable; nothing is backfilled and existing revenue / FGA
reports are not changed by this migration.

Revision ID: 0040
Revises: 0039
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline", sa.Column("won_at", sa.Date(), nullable=True))
    op.add_column("pipeline", sa.Column("won_basis", sa.String(20), nullable=True))
    op.add_column("pipeline", sa.Column("won_ref", sa.String(120), nullable=True))
    op.add_column("pipeline", sa.Column("invoiced_at", sa.Date(), nullable=True))
    op.add_column("pipeline", sa.Column("invoice_ref", sa.String(60), nullable=True))


def downgrade() -> None:
    for c in ("invoice_ref", "invoiced_at", "won_ref", "won_basis", "won_at"):
        op.drop_column("pipeline", c)
