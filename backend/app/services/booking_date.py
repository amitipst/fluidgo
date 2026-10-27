"""The date a deal counts as WON for revenue, targets, FGA and incentives (v1.6.1).

Leading CRMs (Salesforce, HubSpot) report closed-won by the date the deal was
actually closed, not by the date the rep once forecast. fluidGo records that as
won_at: the day the customer's email / LOI / PO / agreement arrived (required to
enter Won since v1.5.0). Before this, revenue, targets, FGA "Business Generation",
Scheme Winners and the Executive Digest all keyed on closure_eta, the *expected*
close date, which stays wherever the rep last set it.

Older won deals have no won_at. They fall back to closure_eta, exactly as before,
so no historical figure moves; only wins recorded from now on are dated by won_at.
(Tax invoicing is out of scope: Finance invoices in the ERP.)
"""
from __future__ import annotations

from sqlalchemy import func

from app.models import PipelineDeal


def won_date_col():
    """SQL expression: order-booking date, else expected-closure date for older deals."""
    return func.coalesce(PipelineDeal.won_at, PipelineDeal.closure_eta)


def won_date_of(deal):
    """Python twin of won_date_col()."""
    return getattr(deal, "won_at", None) or deal.closure_eta
