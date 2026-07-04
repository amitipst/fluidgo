import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// ── Helpers ───────────────────────────────────────────────────────────────────
const inr = (n: number) =>
  n >= 10000000 ? `₹${(n/10000000).toFixed(1)}Cr`
  : n >= 100000 ? `₹${(n/100000).toFixed(1)}L`
  : `₹${Number(n||0).toLocaleString('en-IN')}`

const rigorBg  = (s: number) =>
  s >= 75 ? 'bg-emerald-50 text-emerald-700' :
  s >= 60 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-600'

const rankMedal = (r: number) =>
  r === 1 ? '🥇' : r === 2 ? '🥈' : r === 3 ? '🥉' : `#${r}`

const REGION_FLAGS: Record<string, string> = {
  'India - North':   '🏛️',
  'India - South':   '🌴',
  'India - West':    '🌊',
  'India - East':    '⛩️',
  'India - Central': '🌾',
}

// ── KPI Chip ──────────────────────────────────────────────────────────────────
function KpiChip({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="text-center">
      <div className="font-display font-bold text-lg text-wep-text leading-tight">{value}</div>
      <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted">{label}</div>
      {sub && <div className="text-[10px] text-wep-light">{sub}</div>}
    </div>
  )
}

// ── Region Card ───────────────────────────────────────────────────────────────
function RegionCard({ r, selected, onClick }: { r: any; selected: boolean; onClick: () => void }) {
  return (
    <div onClick={onClick} className={`card cursor-pointer transition-all hover:border-brand-pink/50 ${
      selected ? 'border-brand-pink ring-2 ring-brand-pink/20' : ''}`}>

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{REGION_FLAGS[r.region] ?? '📍'}</span>
          <div>
            <div className="font-bold text-wep-text text-sm">{r.region}</div>
            <div className="text-[11px] text-wep-muted">{r.team_size} members</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xl">{rankMedal(r.rank)}</span>
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${rigorBg(r.avg_rigor)}`}>
            {r.avg_rigor?.toFixed(0) ?? 0} rigor
          </span>
        </div>
      </div>

      {/* Progress bar — rigor vs 100 */}
      <div className="h-1.5 bg-wep-border rounded-full mb-3 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${Math.min(r.avg_rigor || 0, 100)}%`,
            background: r.avg_rigor >= 75 ? '#059669' : r.avg_rigor >= 60 ? '#D97706' : '#F0115E'
          }} />
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-1 divide-x divide-wep-border/60">
        <KpiChip label="Calls"     value={r.total_calls}    />
        <KpiChip label="Visits"    value={r.total_visits}   />
        <KpiChip label="Leads"     value={r.total_leads}    />
        <KpiChip label="DSR %"     value={`${r.dsr_compliance_pct}%`} />
      </div>

      {/* Proposals */}
      {r.total_proposals > 0 && (
        <div className="mt-2 text-xs text-wep-muted text-right">
          📄 {r.total_proposals} proposals · 🔄 {r.total_followups} follow-ups
        </div>
      )}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function RegionalPerformance() {
  const { user } = useAuthStore()
  const today = new Date()
  const [period, setPeriod] = useState(
    `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`
  )
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['regional', period],
    queryFn: () => api.get(`/analytics/regional?period=${period}`).then(r => r.data),
  })

  const regions: any[] = data?.regions ?? []
  const selected = selectedRegion ? regions.find(r => r.region === selectedRegion) : null

  // BU summary totals
  const totals = regions.reduce((acc, r) => ({
    calls:     acc.calls    + r.total_calls,
    visits:    acc.visits   + r.total_visits,
    leads:     acc.leads    + r.total_leads,
    followups: acc.followups + r.total_followups,
    proposals: acc.proposals + r.total_proposals,
    members:   acc.members  + r.team_size,
  }), { calls:0, visits:0, leads:0, followups:0, proposals:0, members:0 })

  const avgRigor = regions.length
    ? (regions.reduce((s, r) => s + (r.avg_rigor||0), 0) / regions.length).toFixed(1)
    : '—'

  const bestRegion  = regions[0]
  const worstRegion = regions[regions.length - 1]

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">🗺️ Regional Performance</h1>
          <p className="page-sub">
            fluidPro · {data?.total_regions ?? 0} regions · {period}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedRegion && (
            <button onClick={() => setSelectedRegion(null)} className="btn-outline text-sm py-2">
              ✕ Clear filter
            </button>
          )}
          <input type="month" className="form-input py-2 text-sm w-40"
            value={period} onChange={e => setPeriod(e.target.value)} />
        </div>
      </div>

      {/* Business Summary Bar */}
      {!isLoading && regions.length > 0 && (
        <div className="card mb-5"
          style={{ background: 'linear-gradient(135deg, #1A0B2E 0%, #3D1A6E 100%)' }}>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-widest text-white/40 mb-1">
                fluidPro · All India · {period}
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {bestRegion && (
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full"
                    style={{ background: 'rgba(5,150,105,0.25)', color: '#6EE7B7' }}>
                    🥇 Best: {bestRegion.region} ({bestRegion.avg_rigor?.toFixed(0)} rigor)
                  </span>
                )}
                {worstRegion && worstRegion !== bestRegion && (
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full"
                    style={{ background: 'rgba(220,38,38,0.20)', color: '#FCA5A5' }}>
                    Needs focus: {worstRegion.region} ({worstRegion.avg_rigor?.toFixed(0)} rigor)
                  </span>
                )}
              </div>
            </div>
            <div className="grid grid-cols-4 gap-6">
              {[
                { label:'Total Calls',    value: totals.calls    },
                { label:'New Leads',      value: totals.leads    },
                { label:'Avg Rigor',      value: `${avgRigor}/100` },
                { label:'Team Size',      value: totals.members  },
              ].map(s => (
                <div key={s.label} className="text-center">
                  <div className="font-display font-black text-2xl text-white">{s.value}</div>
                  <div className="text-[10px] text-white/40 uppercase tracking-wide">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Regions Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2,3,4,5].map(i => <div key={i} className="skeleton h-40 rounded-2xl" />)}
        </div>
      ) : regions.length === 0 ? (
        <div className="card text-center py-16">
          <div className="text-5xl mb-4">🗺️</div>
          <p className="font-semibold text-wep-text mb-1">No regional data for {period}</p>
          <p className="text-wep-muted text-sm">DSR entries with region mapping will appear here.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {regions.map(r => (
              <RegionCard
                key={r.region}
                r={r}
                selected={selectedRegion === r.region}
                onClick={() => setSelectedRegion(
                  selectedRegion === r.region ? null : r.region
                )}
              />
            ))}
          </div>

          {/* Detail drill-down */}
          {selected && (
            <div className="card mt-5 border-brand-pink">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{REGION_FLAGS[selected.region] ?? '📍'}</span>
                <div>
                  <h3 className="font-display font-bold text-lg text-wep-text">
                    {selected.region} — Detailed View
                  </h3>
                  <p className="text-wep-muted text-sm">
                    {selected.team_size} team members · {selected.dsr_days} DSR days logged
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Total Calls',    value: selected.total_calls,    icon: '📞', color: '#1E6FD9' },
                  { label: 'Customer Visits',value: selected.total_visits,   icon: '🏢', color: '#7B2D8B' },
                  { label: 'Follow-Ups',     value: selected.total_followups, icon: '🔄', color: '#D97706' },
                  { label: 'New Leads',      value: selected.total_leads,    icon: '🎯', color: '#059669' },
                  { label: 'Proposals',      value: selected.total_proposals, icon: '📄', color: '#F0115E' },
                  { label: 'Avg Rigor',      value: `${selected.avg_rigor?.toFixed(1)}/100`, icon: '⚡', color: rigorBg(selected.avg_rigor).includes('emerald') ? '#059669' : '#D97706' },
                  { label: 'DSR Compliance', value: `${selected.dsr_compliance_pct}%`, icon: '✅', color: '#0D9488' },
                  { label: 'Working Days',   value: selected.working_days,   icon: '📅', color: '#6B7280' },
                ].map(stat => (
                  <div key={stat.label} className="stat-card">
                    <div className="stat-card-accent" style={{ background: stat.color }} />
                    <div className="text-2xl mb-1">{stat.icon}</div>
                    <div className="font-display font-black text-2xl" style={{ color: stat.color }}>
                      {stat.value}
                    </div>
                    <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted mt-1">
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
