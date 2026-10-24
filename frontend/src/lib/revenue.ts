// Mirrors backend/app/services/pipeline_sheet_service.py's amounts() exactly.
// Added 2026-10-23: Opportunities.tsx and Pipeline.tsx (Cards view) were each
// summing raw `deal_value` only for their headline numbers (Open Pipeline,
// Weighted Forecast, Won, per-card value) — the same class of bug fixed
// server-side in v1.4.3 (Revenue Intelligence, FGA, incentives, funnel, the
// Win-Loss widget). Those were fixed by reusing pipeline_sheet_service's
// amounts() on the backend; these two screens compute their totals
// client-side from the raw deal rows the API already returns, so they need
// the same fallback logic ported here rather than a second parallel
// implementation. Any deal using the newer ARR/One-time fields (Pipeline
// Sheet) was silently showing ₹0 toward these totals before this fix.
export function dealRevenue(d: { recurring_revenue?: number | string | null; one_time_revenue?: number | string | null; deal_value?: number | string | null }): number {
  const arr = d.recurring_revenue != null ? Number(d.recurring_revenue) : null
  const once = d.one_time_revenue != null ? Number(d.one_time_revenue) : null
  if (arr === null && once === null) return Number(d.deal_value || 0)
  return (arr || 0) + (once || 0)
}
