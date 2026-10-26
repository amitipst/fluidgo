"""Tell Finance a deal is Won so they can raise the proforma / tax invoice (v1.6.0).

Amit (2026-10-26): "for incentive Order Booking is enough ... revenue
realisation once a PO is invoiced by wepsol as a tax invoice is not needed here
as we have a separate ERP for invoicing, but we can trigger an email or
notification for the finance team to invoice the POs completed with customer
sign-off or proforma invoice."

So fluidGo does not invoice. It records the order booking (Won) and tells
Finance. The email degrades to a server log when SMTP is not configured,
exactly like the digest and MOM emails. A later version can post to the ERP or
raise an in-app task instead.
"""
from __future__ import annotations

from html import escape

from app.services.deal_rules_service import WON_BASIS_LABELS


def _inr(v) -> str:
    try:
        return f"₹{float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


def build_won_notice(deal, owner_name: str) -> tuple[str, str, str]:
    """(subject, html, text) — pure, so it is unit-testable."""
    name = deal.title or deal.company
    basis = WON_BASIS_LABELS.get(deal.won_basis or "", "Customer commitment")
    rows = [
        ("Customer", deal.company),
        ("Deal", name),
        ("Sales owner", owner_name or "—"),
        ("ARR", _inr(deal.recurring_revenue)),
        ("One-time", _inr(deal.one_time_revenue)),
        ("Total", _inr(deal.deal_value)),
        ("Customer sign-off", f"{basis}" + (f" · {deal.won_ref}" if deal.won_ref else "")),
        ("Received on", deal.won_at.isoformat() if deal.won_at else "—"),
    ]
    subject = f"Order booked — please invoice: {deal.company} ({name})"
    text = "A deal has been marked Won in fluidGo and is ready for invoicing in the ERP.\n\n" + \
        "\n".join(f"{k}: {v}" for k, v in rows)
    html = ("<div style='font-family:Arial,sans-serif;font-size:14px;color:#1f2937'>"
            "<p>A deal has been marked <b>Won</b> in fluidGo and is ready for the proforma / tax invoice "
            "to be raised in the ERP.</p><table cellpadding='6' style='border-collapse:collapse'>"
            + "".join(f"<tr><td style='color:#6b7280'>{escape(k)}</td><td><b>{escape(str(v))}</b></td></tr>"
                      for k, v in rows)
            + "</table><p style='color:#6b7280'>Once invoiced, the invoice date can be added on the deal.</p></div>")
    return subject, html, text
