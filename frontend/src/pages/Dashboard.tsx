import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import LeadershipPanel from '@/components/LeadershipPanel'
import PlatformPanel from '@/components/PlatformPanel'
import api from '@/hooks/useApi'
import { format } from 'date-fns'
import { Link, Navigate } from 'react-router-dom'
import { getQuoteOfDay } from '@/lib/quotes'

// Compact Indian-format currency (₹2.5Cr / ₹1.5L / ₹5,000)
function inrShort(n: number): string {
  if (!n) return '₹0'
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`
  return `₹${Math.round(n).toLocaleString('en-IN')}`
}

// ── Motivational background motif — ascending bars / momentum, on-brand,
// rendered translucent so it reads as texture, not content. Pure SVG (no
// external image), so there's nothing that can 404 or need hosting.
// IMPORTANT: no `absolute` positioning here — this must render as a normal,
// self-contained block that fills whatever fixed-size wrapper places it,
// never reaching past its own box regardless of ancestor size. ──
function MomentumMotif() {
  return (
    <svg viewBox="0 0 400 160" className="w-full h-full pointer-events-none select-none"
      style={{ opacity: 0.14 }} preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
      <rect x="20"  y="100" width="28" height="60" rx="6" fill="#92278E" />
      <rect x="60"  y="75"  width="28" height="85" rx="6" fill="#92278E" />
      <rect x="100" y="55"  width="28" height="105" rx="6" fill="#F0115E" />
      <rect x="140" y="30"  width="28" height="130" rx="6" fill="#F0115E" />
      <rect x="180" y="5"   width="28" height="155" rx="6" fill="#F0115E" />
      <path d="M20 95 L60 70 L100 50 L140 25 L180 0" stroke="#0D9488" strokeWidth="5"
        fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="180" cy="0" r="9" fill="#0D9488" />
    </svg>
  )
}

// ── KPI Stat Card ─────────────────────────────────────────────────────────────
function KPICard({ label, value, sub, accentColor, icon, loading }: {
  label: string; value: string | number; sub?: string;
  accentColor: string; icon: string; loading?: boolean
}) {
  return (
    <div className="stat-card">
      <div className="stat-card-accent" style={{ background: accentColor }} />
      <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-3">{label}</div>
      {loading ? (
        <div className="skeleton h-9 w-20 mb-1" />
      ) : (
        <div className={`font-display font-black text-wep-navy leading-none mb-1 ${
          String(value).length > 5 ? 'text-[1.4rem]' : 'text-[2rem]'
        }`}>{value}</div>
      )}
      {sub && <div className="text-xs text-wep-muted mt-1">{sub}</div>}
      <div className="absolute right-4 top-1/2 -translate-y-1/2 text-4xl opacity-[0.06] select-none pointer-events-none">
        {icon}
      </div>
    </div>
  )
}

// ── Performance Intelligence (v1.6.1) ─────────────────────────────────────────
// Rule-based and instant: every line is a deterministic rule over the person's own
// DSRs, deals and leads (GET /performance-insights). No model call, nothing to wait
// for, and each line says what was measured and what to do. Severity is shown as
// text as well as colour so it never relies on colour alone.
const SEV: Record<string, { label: string; dot: string }> = {
  high: { label: 'Act now', dot: '#F87171' }, medium: { label: 'Improve', dot: '#FBBF24' },
  low: { label: 'Note', dot: '#94A3B8' }, good: { label: 'On track', dot: '#34D399' },
}

function PerformancePanel() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['performance-insights'],
    queryFn: () => api.get('/performance-insights').then(r => r.data),
    staleTime: 60_000,
  })
  const items: any[] = data?.items ?? []

  return (
    <div className="ai-panel mb-6" style={{ background: 'linear-gradient(135deg, #1A0B2E 0%, #3D1A6E 100%)' }}>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
            style={{ background: 'rgba(14,165,233,0.20)', color: '#38BDF8', border: '1px solid rgba(14,165,233,0.25)' }}>
            Rules-based · explainable
          </span>
          <span className="font-display font-bold text-white text-sm">Performance Intelligence</span>
          {data?.headline && <span className="text-[11px]" style={{ color: 'rgba(255,255,255,0.55)' }}>· {data.headline}</span>}
        </div>
        <button onClick={() => refetch()} disabled={isFetching}
          className="text-xs font-semibold disabled:opacity-40 min-h-[44px] px-2" style={{ color: '#F5921E' }}>
          {isFetching ? 'Refreshing…' : '🔄 Refresh'}
        </button>
      </div>

      {isLoading && <p className="text-sm" style={{ color: 'rgba(255,255,255,0.55)' }}>Reading your activity…</p>}
      {isError && <p className="text-sm" style={{ color: 'rgba(255,150,150,0.8)' }}>Could not load insights. Try Refresh.</p>}
      {!isLoading && !isError && (
        <ul className="space-y-2">
          {items.map((i: any) => {
            const sev = SEV[i.severity] ?? SEV.low
            return (
              <li key={i.key} className="rounded-xl p-3 text-sm"
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', color: 'rgba(255,255,255,0.88)' }}>
                <div className="flex items-start gap-2">
                  <span className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: sev.dot }} aria-hidden="true" />
                  <div className="min-w-0">
                    <div className="font-semibold text-white">
                      <span className="text-[10px] uppercase tracking-wider mr-2" style={{ color: sev.dot }}>{sev.label}</span>{i.title}
                    </div>
                    {i.detail && <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.6)' }}>{i.detail}</div>}
                    <div className="text-xs mt-1" style={{ color: '#F5C27A' }}>→ {i.action}</div>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
      {data?.basis && <p className="text-[10px] mt-3" style={{ color: 'rgba(255,255,255,0.35)' }}>{data.basis}</p>}
    </div>
  )
}


// ── HR: BU-wise FGA overview ──────────────────────────────────────────────────
// HR doesn't work sales pipeline concepts and never submits a DSR — their
// dashboard is a company-wide FGA governance snapshot instead: team size,
// submission coverage and average score per Business, across ALL businesses
// (not just their own region), since HR's scope is org-wide by design.
const BIZ_LABELS: Record<string, string> = {
  fluidpro: 'fluidPro (IT Infra)', fluidprint: 'fluidPrint (Managed Print)',
  floxtax: 'floxtax (GST/ASP)', hooks: 'Hooks (POS/Channel)',
}

function HRDashboard({ selectedMonth }: { selectedMonth: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['hr-bu-overview', selectedMonth],
    queryFn: () => api.get(`/fga-approval/bu-overview?period=${selectedMonth}`).then(r => r.data),
  })
  const businesses = data?.businesses ?? []
  const totals = data?.totals

  return (
    <div>
      {/* Company-wide totals */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KPICard label="Total Headcount" value={totals?.team_size ?? 0} icon="👥"
          sub={selectedMonth} accentColor="#1E6FD9" loading={isLoading} />
        <KPICard label="FGA Applicable" value={totals?.applicable ?? 0} icon="✅"
          sub={totals?.exempt ? `${totals.exempt} marked N/A` : undefined}
          accentColor="#0D9488" loading={isLoading} />
        <KPICard label="FGA Coverage" value={isLoading ? '…' : `${totals?.coverage_pct ?? 0}%`} icon="📊"
          sub={`${totals?.submitted ?? 0} / ${totals?.applicable ?? 0} submitted`}
          accentColor={totals?.coverage_pct >= 80 ? '#059669' : totals?.coverage_pct >= 50 ? '#D97706' : '#DC2626'}
          loading={isLoading} />
        <KPICard label="Avg FGA Score" value={isLoading ? '…' : (totals?.avg_score != null ? `${totals.avg_score}/100` : '—')} icon="⚡"
          accentColor="#92278E" loading={isLoading} />
      </div>

      {/* Per-business breakdown */}
      <div className="card mb-6">
        <div className="font-bold text-wep-navy text-sm mb-4">🏢 FGA Coverage by Business</div>
        {isLoading ? (
          <div className="skeleton h-24 w-full" />
        ) : businesses.length === 0 ? (
          <p className="text-sm text-wep-muted text-center py-6">No active Sales, Pre-Sales or Service Delivery headcount found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] font-bold uppercase tracking-wide text-wep-muted border-b border-wep-border">
                  <th className="py-2 pr-3">Business</th>
                  <th className="py-2 pr-3">Team Size</th>
                  <th className="py-2 pr-3">N/A</th>
                  <th className="py-2 pr-3">Submitted</th>
                  <th className="py-2 pr-3">Coverage</th>
                  <th className="py-2 pr-3">Avg Score</th>
                </tr>
              </thead>
              <tbody>
                {businesses.map((b: any) => (
                  <tr key={b.business} className="border-b border-wep-border/50">
                    <td className="py-2.5 pr-3 font-semibold text-wep-navy">{BIZ_LABELS[b.business] ?? b.business}</td>
                    <td className="py-2.5 pr-3">{b.team_size}</td>
                    <td className="py-2.5 pr-3 text-wep-muted">{b.exempt > 0 ? b.exempt : '—'}</td>
                    <td className="py-2.5 pr-3">{b.submitted} / {b.applicable}</td>
                    <td className="py-2.5 pr-3">
                      <span className="font-bold" style={{
                        color: b.coverage_pct >= 80 ? '#059669' : b.coverage_pct >= 50 ? '#D97706' : '#DC2626'
                      }}>{b.coverage_pct}%</span>
                    </td>
                    <td className="py-2.5 pr-3">{b.avg_score != null ? `${b.avg_score}/100` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <QuickTile to="/fga-approval"    icon="🏆" label="FGA Approval"   desc="Review pending scores across Sales, Pre-Sales & Service Delivery" />
        <QuickTile to="/scheme-winners"  icon="🎉" label="Scheme Winners" desc="Sign off cash-reward scheme payouts" />
        <QuickTile to="/activity-logs"   icon="🗂️" label="Activity Logs" desc="Rigor scores & submission logs (read-only)" />
      </div>
    </div>
  )
}

// ── Quick-link tile ───────────────────────────────────────────────────────────
function QuickTile({ to, icon, label, desc }: { to: string; icon: string; label: string; desc: string }) {
  return (
    <Link to={to}
      className="card group flex flex-col gap-2 hover:border-wep-orange transition-all duration-200 cursor-pointer"
      style={{ boxShadow: '0 1px 3px rgba(11,31,58,0.06)' }}>
      <div className="text-2xl">{icon}</div>
      <div className="font-bold text-sm text-wep-navy group-hover:text-wep-orange transition-colors">{label}</div>
      <div className="text-xs text-wep-muted leading-relaxed">{desc}</div>
    </Link>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { user } = useAuthStore()
  const today  = format(new Date(), 'yyyy-MM-dd')
  const hour   = new Date().getHours()
  const isBU   = ['manager','regional_manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const isField = ['rep','inside_sales','pre_sales','manager'].includes(user?.role ?? '')
  const isSDM = user?.role === 'service_delivery_manager'
  // HR doesn't submit DSR/DOR and doesn't work sales-pipeline concepts —
  // gets its own company-wide FGA governance dashboard instead (see
  // HRDashboard below), not the generic rep/BU-head layout.
  const isHR = user?.role === 'hr'
  // Validation-only — no KPIs/revenue of its own; redirected below, after
  // every hook has been called (never gate a hook call itself on this, or
  // conditionally-called hooks break the rules of hooks on next render).
  const isGovernance = user?.role === 'governance'
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const [selectedMonth, setSelectedMonth] = useState(format(new Date(), 'yyyy-MM'))
  const [quote] = useState(getQuoteOfDay)

  const { data: dash, isLoading } = useQuery({
    queryKey: ['dashboard', user?.id, selectedMonth],
    queryFn: () => api.get(`/analytics/dashboard?month=${selectedMonth}`).then(r => r.data),
    enabled: !!user?.id && !isSDM && !isHR && !isGovernance,
  })

  // Service Delivery: DOR history for the month, aggregated client-side —
  // avoids a bespoke backend endpoint for what's a small, already-fetched list.
  const { data: dorHistory = [], isLoading: dorLoading } = useQuery({
    queryKey: ['dor-history', selectedMonth],
    queryFn: () => api.get(`/dor/history?month=${selectedMonth}`).then(r => r.data),
    enabled: isSDM,
  })
  const todayDOR = dorHistory.find((d: any) => d.date === today)
  const dorMonthTotals = dorHistory.reduce((acc: any, d: any) => ({
    tickets_closed: acc.tickets_closed + (d.tickets_closed || 0),
    escalations_raised: acc.escalations_raised + (d.escalations_raised || 0),
    tickets_overdue: acc.tickets_overdue + (d.tickets_overdue || 0),
    client_meetings_held: acc.client_meetings_held + (d.client_meetings_held || 0),
  }), { tickets_closed: 0, escalations_raised: 0, tickets_overdue: 0, client_meetings_held: 0 })

  const { data: todayDSR } = useQuery({
    queryKey: ['dsr-today', today],
    queryFn: () => api.get(`/dsr?date=${today}`).then(r => r.data),
    enabled: !isSDM && !isHR && !isGovernance,
  })

  // Rep's own revenue target vs achievement (field roles that carry a number)
  const isRevenueRep = ['rep','inside_sales'].includes(user?.role ?? '')
  const { data: myRev } = useQuery({
    queryKey: ['my-revenue', selectedMonth],
    queryFn: () => api.get(`/analytics/my-revenue?period=${selectedMonth}`).then(r => r.data),
    enabled: isRevenueRep,
  })

  const rigor = dash?.avg_rigor ?? 0
  const rigorColor = rigor >= 80 ? '#059669' : rigor >= 60 ? '#D97706' : rigor > 0 ? '#DC2626' : '#DDE3EE'
  const rigorLabel = rigor >= 80 ? '🏆 Excellent' : rigor >= 60 ? '✅ Good' : rigor > 0 ? '⚠️ Needs focus' : undefined

  // Governance has no KPI/revenue landing of its own — send it straight to
  // its dedicated validation queue instead of building a bespoke empty
  // Dashboard variant (same idea as HRDashboard above, one level simpler
  // since governance doesn't even need a company-wide KPI view). Placed
  // after every hook above so hook order never depends on role.
  if (isGovernance) return <Navigate to="/governance" replace />

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="font-display font-black text-wep-navy text-2xl leading-tight">
            {greeting}, {user?.name?.split(' ')[0]} 👋
          </div>
          <div className="text-wep-muted text-sm mt-1 flex items-center gap-2 flex-wrap">
            <span>{format(new Date(), 'EEEE, d MMMM yyyy')}</span>
            <span className="text-wep-border-strong">·</span>
            <span>{user?.bu} BU · {user?.business ?? 'fluidPro'}</span>
            {isBU && dash?.pending_today > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold"
                style={{ background: '#FEF2F2', color: '#DC2626' }}>
                🔴 {dash.pending_today} DSR pending today
              </span>
            )}
          </div>
          <p className="text-xs italic text-wep-muted mt-2 max-w-md">
            "{quote.text}" <span className="not-italic font-semibold">— {quote.author}</span>
          </p>
        </div>
        {/* Motif + controls grouped together, in NORMAL flow (not absolute) —
            this cannot overlap the text block no matter how long the quote or
            greeting gets, because it's a separate flex sibling, not layered on top. */}
        <div className="flex items-start gap-4 shrink-0">
          <div className="hidden md:block w-28 h-14 opacity-90 pointer-events-none">
            <MomentumMotif />
          </div>
          <div className="flex items-center gap-2">
            {(isBU || isHR) && (
              <input type="month" className="form-input py-2 text-sm w-40"
                value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)} />
            )}
            {isField && (
              <Link to="/dsr" className="btn-primary">✏️ Submit DSR</Link>
            )}
            {isSDM && (
              <Link to="/dor" className="btn-primary">🛠️ Submit DOR</Link>
            )}
          </div>
        </div>
      </div>

      {/* ── HR: company-wide FGA governance view — replaces the rest of the
          page entirely, since sales KPIs/AI insight/DSR widgets don't apply. ── */}
      {isHR ? (
        <HRDashboard selectedMonth={selectedMonth} />
      ) : (
      <>
      {/* ── KPI Grid ── */}
      {isSDM ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <KPICard label="Tickets Closed" value={dorMonthTotals.tickets_closed} icon="🎫"
            sub={selectedMonth} accentColor="#0D9488" loading={dorLoading} />
          <KPICard label="Overdue (>3d)" value={dorMonthTotals.tickets_overdue} icon="⏰"
            accentColor={dorMonthTotals.tickets_overdue > 0 ? '#DC2626' : '#0D9488'} loading={dorLoading} />
          <KPICard label="Escalations" value={dorMonthTotals.escalations_raised} icon="⚠️"
            accentColor={dorMonthTotals.escalations_raised > 0 ? '#D97706' : '#0D9488'} loading={dorLoading} />
          <KPICard label="Client Meetings" value={dorMonthTotals.client_meetings_held} icon="🤝"
            accentColor="#1E6FD9" loading={dorLoading} />
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
          <KPICard label="Visits"      value={dash?.total_visits    ?? 0} icon="🏢"
            sub={isBU ? `BU · ${selectedMonth}` : selectedMonth}
            accentColor="#0D9488" loading={isLoading} />
          <KPICard label="Calls"       value={dash?.total_calls     ?? 0} icon="📞"
            accentColor="#1E6FD9" loading={isLoading} />
          <KPICard label="Follow-Ups"  value={dash?.total_followups ?? 0} icon="🔄"
            accentColor="#D97706" loading={isLoading} />
          <KPICard label="New Leads"   value={dash?.total_leads     ?? 0} icon="🎯"
            accentColor="#0EA5E9" loading={isLoading} />
          <KPICard label="Avg Rigor"
            value={isLoading ? '…' : rigor > 0 ? `${rigor}/100` : '—'}
            sub={rigorLabel} icon="⚡"
            accentColor={rigorColor} loading={isLoading} />
        </div>
      )}

      {/* ── AI Panel (sales-activity insight — not relevant for Service Delivery) ── */}
      {user?.id && ['business_head','practice_head','coo','ceo'].includes(user?.role ?? '') && <LeadershipPanel />}
      {user?.id && user?.role === 'super_admin' && <PlatformPanel />}
      {user?.id && !isSDM && <PerformancePanel />}

      {/* ── My Targets (rep visibility into own revenue) ── */}
      {isRevenueRep && myRev?.has_target && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="font-bold text-wep-navy text-sm">🎯 My Targets — {myRev.period}</div>
            <div className="text-xs text-wep-muted">
              {myRev.deals_won} {myRev.deals_won === 1 ? 'deal' : 'deals'} won
            </div>
          </div>

          {/* Revenue progress bar */}
          <div className="mb-3">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-wep-muted">Revenue</span>
              <span className="font-semibold text-wep-text">
                {inrShort(myRev.revenue_achieved)} <span className="text-wep-muted">/ {inrShort(myRev.revenue_target)}</span>
              </span>
            </div>
            <div className="h-2.5 rounded-full overflow-hidden" style={{ background: '#EDE9F5' }}>
              <div className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min(100, myRev.achievement_pct)}%`,
                  background: myRev.achievement_pct >= 100 ? '#059669'
                    : myRev.achievement_pct >= 60 ? 'linear-gradient(90deg,#F0115E,#92278E)' : '#F0115E',
                }} />
            </div>
            <div className="flex items-center justify-between text-[11px] mt-1">
              <span className="font-bold" style={{ color: myRev.achievement_pct >= 100 ? '#059669' : '#F0115E' }}>
                {myRev.achievement_pct}% achieved
              </span>
              {myRev.gap > 0 && (
                <span className="text-wep-muted">{inrShort(myRev.gap)} to target</span>
              )}
            </div>
          </div>

          {/* Order booking target (if set) */}
          {myRev.order_booking_target > 0 && (
            <div className="flex items-center justify-between text-xs pt-2 border-t border-wep-border">
              <span className="text-wep-muted">📦 Order Booking Target</span>
              <span className="font-semibold text-wep-text">{inrShort(myRev.order_booking_target)}</span>
            </div>
          )}
        </div>
      )}

      {/* ── Today's DSR (field roles) ── */}
      {!isBU && !isSDM && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="font-bold text-wep-navy text-sm">📋 Today's DSR</div>
            {!todayDSR && (
              <Link to="/dsr" className="text-xs font-semibold text-wep-orange hover:underline">
                Submit now →
              </Link>
            )}
          </div>
          {todayDSR ? (
            <div className="grid grid-cols-3 gap-4 text-center">
              {[
                { label: 'Calls',      val: todayDSR.calls,     color: '#1E6FD9' },
                { label: 'Follow-ups', val: todayDSR.followups, color: '#0D9488' },
                { label: 'Rigor',      val: `${todayDSR.rigor_score}/100`,
                  color: todayDSR.rigor_score >= 80 ? '#059669' : todayDSR.rigor_score >= 60 ? '#D97706' : '#DC2626' },
              ].map(({ label, val, color }) => (
                <div key={label}>
                  <div className="font-display font-black text-2xl" style={{ color }}>{val}</div>
                  <div className="text-wep-muted text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-wep-muted text-sm mb-4">No DSR submitted yet today.</p>
              <Link to="/dsr" className="btn-primary text-sm">Submit Today's DSR →</Link>
            </div>
          )}
        </div>
      )}

      {/* ── Today's DOR (Service Delivery Manager) ── */}
      {isSDM && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="font-bold text-wep-navy text-sm">🛠️ Today's Operations Report</div>
            {!todayDOR && (
              <Link to="/dor" className="text-xs font-semibold text-wep-orange hover:underline">
                Submit now →
              </Link>
            )}
          </div>
          {todayDOR ? (
            <div className="grid grid-cols-3 gap-4 text-center">
              {[
                { label: 'Tickets Closed', val: todayDOR.tickets_closed, color: '#0D9488' },
                { label: 'Escalations',    val: todayDOR.escalations_raised,
                  color: todayDOR.escalations_raised > 0 ? '#D97706' : '#0D9488' },
                { label: 'Status',
                  val: todayDOR.status === 'on_track' ? '🟢' : todayDOR.status === 'at_risk' ? '🟡' : '🔴',
                  color: '#1E6FD9' },
              ].map(({ label, val, color }) => (
                <div key={label}>
                  <div className="font-display font-black text-2xl" style={{ color }}>{val}</div>
                  <div className="text-wep-muted text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="text-4xl mb-3">🛠️</div>
              <p className="text-wep-muted text-sm mb-4">No Operations Report submitted yet today.</p>
              <Link to="/dor" className="btn-primary text-sm">Submit Today's DOR →</Link>
            </div>
          )}
        </div>
      )}

      {/* ── BU Head quick tiles ── */}
      {isBU && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <QuickTile to="/team"          icon="👥" label="Team"         desc="DSR compliance & rigor leaderboard" />
          <QuickTile to="/revenue"       icon="💰" label="Revenue"      desc="Target achievement & pipeline" />
          <QuickTile to="/deals?tab=weak" icon="🧭" label="Deals & weak areas" desc="Health, risk and what needs action" />
          <QuickTile to="/fga-approval"  icon="🏆" label="FGA Approval" desc="Score review & Finance export" />
        </div>
      )}
      </>
      )}
    </div>
  )
}
