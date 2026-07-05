import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// ── Helpers ───────────────────────────────────────────────────────────────────
const inr = (n: number) =>
  n >= 10000000 ? `₹${(n/10000000).toFixed(2)}Cr`
  : n >= 100000 ? `₹${(n/100000).toFixed(1)}L`
  : `₹${Number(n||0).toLocaleString('en-IN')}`

const trendIcon = (t?: string) =>
  t === 'up' ? '↑' : t === 'down' ? '↓' : t === 'flat' ? '→' : '—'
const trendColor = (t?: string, k?: string) => {
  const positive = ['calls','visits','followups','leads','proposals','revenue','deals_won','achievement_pct']
  const isPositive = positive.includes(k ?? '')
  if (!t || t === 'new' || t === 'flat') return 'text-wep-muted'
  if (t === 'up')   return isPositive ? 'text-emerald-600' : 'text-red-500'
  if (t === 'down') return isPositive ? 'text-red-500' : 'text-emerald-600'
  return 'text-wep-muted'
}

type Mode = 'monthly' | 'quarterly' | 'yearly' | 'weekly'
const MODES: { key: Mode; label: string }[] = [
  { key: 'weekly',    label: 'Weekly'    },
  { key: 'monthly',   label: 'Monthly'   },
  { key: 'quarterly', label: 'Quarterly' },
  { key: 'yearly',    label: 'Yearly'    },
]
const QUARTERS = ['Q1 (Apr–Jun)', 'Q2 (Jul–Sep)', 'Q3 (Oct–Dec)', 'Q4 (Jan–Mar)']
const KPI_META: Record<string, { label: string; icon: string; fmt: (v:number)=>string }> = {
  calls:          { label:'Calls',         icon:'📞', fmt: v => v.toString() },
  visits:         { label:'Visits',        icon:'🏢', fmt: v => v.toString() },
  followups:      { label:'Follow-Ups',    icon:'🔄', fmt: v => v.toString() },
  leads:          { label:'Leads',         icon:'🎯', fmt: v => v.toString() },
  proposals:      { label:'Proposals',     icon:'📄', fmt: v => v.toString() },
  avg_rigor:      { label:'Avg Rigor',     icon:'⚡', fmt: v => `${v}/100`  },
  revenue:        { label:'Revenue',       icon:'💰', fmt: inr              },
  target:         { label:'Target',        icon:'🎯', fmt: inr              },
  achievement_pct:{ label:'Achievement',   icon:'%',  fmt: v => `${v}%`    },
  deals_won:      { label:'Deals Won',     icon:'🏆', fmt: v => v.toString() },
}

// ── KPI comparison card ───────────────────────────────────────────────────────
function KpiCard({ k, data, mode }: { k: string; data: any; mode: Mode }) {
  const meta  = KPI_META[k]
  const curr  = data?.kpis?.[k]
  const yoy   = curr?.yoy
  const mom   = curr?.mom
  const isFuture = data?.is_future
  if (!meta || !curr) return null

  const valueText = meta.fmt(curr.current)
  // Shrink font for long currency strings so they never clip the card
  const valueSize = valueText.length > 7 ? 'text-lg' : valueText.length > 5 ? 'text-xl' : 'text-2xl'

  return (
    <div className="card">
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-base">{meta.icon}</span>
        <span className="text-[11px] font-bold uppercase tracking-wider text-wep-muted">{meta.label}</span>
      </div>
      <div className={`font-display font-black text-wep-text mb-2 truncate ${valueSize}`} title={valueText}>
        {valueText}
      </div>
      <div className="space-y-1">
        {isFuture ? (
          <div className="text-xs text-wep-muted italic">Period hasn't started yet</div>
        ) : (
          <>
            {yoy && yoy.change !== null && (
              <div className={`text-xs font-semibold flex items-center gap-1 ${trendColor(yoy.trend, k)}`}>
                <span>{trendIcon(yoy.trend)}</span>
                <span>{Math.abs(yoy.change)}% vs {data.prev_period}</span>
              </div>
            )}
            {yoy && yoy.trend === 'new' && (
              <div className="text-xs text-wep-muted">No data for {data.prev_period}</div>
            )}
            {mode === 'monthly' && mom && mom.change !== null && (
              <div className={`text-xs flex items-center gap-1 ${trendColor(mom.trend, k)}`}>
                <span>{trendIcon(mom.trend)}</span>
                <span>{Math.abs(mom.change)}% vs {data.mom_period}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Target editor ─────────────────────────────────────────────────────────────
function TargetEditor({ period }: { period: string }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [saving,  setSaving]  = useState<string | null>(null)
  const [saved,   setSaved]   = useState<Record<string, boolean>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['team-targets', period],
    queryFn: () => api.get(`/analytics/revenue/team-targets?period=${period}`).then(r => r.data),
  })

  const setTarget = useMutation({
    mutationFn: ({ user_id, amount }: { user_id: string; amount: number }) =>
      api.post('/analytics/revenue/targets', {
        user_id, period, target_amount: amount
      }),
    onSuccess: (_r, vars) => {
      setSaved(s => ({ ...s, [vars.user_id]: true }))
      setSaving(null)
      setTimeout(() => setSaved(s => ({ ...s, [vars.user_id]: false })), 2000)
      qc.invalidateQueries({ queryKey: ['team-targets'] })
      qc.invalidateQueries({ queryKey: ['revenue-analytics'] })
      qc.invalidateQueries({ queryKey: ['performance'] })
    },
    onError: () => setSaving(null),
  })

  if (isLoading) return <div className="skeleton h-32 rounded-2xl" />

  const members: any[] = data?.members ?? []
  const regionGroups = members.reduce((acc: any, m: any) => {
    const r = m.region || 'Unknown'
    if (!acc[r]) acc[r] = []
    acc[r].push(m)
    return acc
  }, {})

  return (
    <div className="card mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-wep-text">🎯 Revenue Targets — {period}</h3>
        <span className="text-xs text-wep-muted">{members.length} team members</span>
      </div>

      {Object.entries(regionGroups).map(([region, reps]: [string, any]) => (
        <div key={region} className="mb-5 last:mb-0">
          <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2 px-1">
            🗺️ {region}
          </div>
          <div className="space-y-2">
            {reps.map((m: any) => {
              const val = editing[m.user_id] ?? String(m.target || '')
              const isDirty = val !== String(m.target || '')
              return (
                <div key={m.user_id}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-wep-border bg-wep-surface/50">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-wep-text truncate">{m.name}</div>
                    <div className="text-[10px] text-wep-muted">{m.role} · {m.email}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-wep-muted">₹</span>
                    <input
                      type="number" min="0" step="50000"
                      className="form-input py-1.5 text-sm w-28 text-right"
                      value={val}
                      onChange={e => setEditing(s => ({ ...s, [m.user_id]: e.target.value }))}
                      placeholder="0"
                    />
                    {isDirty && (
                      <button
                        disabled={saving === m.user_id}
                        onClick={() => {
                          setSaving(m.user_id)
                          setTarget.mutate({ user_id: m.user_id, amount: parseFloat(val) || 0 })
                        }}
                        className="text-xs font-bold px-2.5 py-1.5 rounded-lg text-white"
                        style={{ background: '#F0115E' }}>
                        {saving === m.user_id ? '…' : 'Set'}
                      </button>
                    )}
                    {saved[m.user_id] && (
                      <span className="text-xs text-emerald-600 font-bold">✅</span>
                    )}
                    {!isDirty && m.target > 0 && (
                      <span className="text-xs text-wep-muted">{inr(m.target)}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function RevenueIntelligence() {
  const { user } = useAuthStore()
  const now = new Date()
  const [mode, setMode] = useState<Mode>('monthly')
  const [period, setPeriod] = useState(`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`)
  const [qtr, setQtr] = useState(1)
  const [fyYear, setFyYear] = useState(now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear()-1)
  const [showTargets, setShowTargets] = useState(false)

  const canEditTargets = ['manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')

  // Build period string per mode
  const periodParam = () => {
    if (mode === 'quarterly') return `${fyYear}-Q${qtr}`
    if (mode === 'yearly')    return `${fyYear}`
    if (mode === 'weekly')    return undefined  // current week auto
    return period  // monthly
  }

  const { data: perfData, isLoading: perfLoading } = useQuery({
    queryKey: ['performance', mode, periodParam()],
    queryFn: () => api.get('/analytics/performance', {
      params: { mode, period: periodParam() }
    }).then(r => r.data),
  })

  // Also fetch revenue summary (existing endpoint for the stat cards)
  const { data: revData, isLoading: revLoading } = useQuery({
    queryKey: ['revenue-analytics', period],
    queryFn: () => api.get('/analytics/revenue', { params: { period } }).then(r => r.data),
    enabled: mode === 'monthly',
  })

  const isLoading = perfLoading || revLoading

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">💰 Revenue Intelligence</h1>
          <p className="page-sub">
            {perfData?.period ?? '—'} vs {perfData?.prev_period ?? '—'}
            {perfData?.team_size ? ` · ${perfData.team_size} members` : ''}
          </p>
        </div>
        {canEditTargets && (
          <button onClick={() => setShowTargets(v => !v)} className="btn-outline text-sm">
            {showTargets ? '✕ Close Targets' : '🎯 Edit Targets'}
          </button>
        )}
      </div>

      {/* Period controls */}
      <div className="flex items-center gap-2 mb-5 flex-wrap">
        {/* Mode toggle */}
        <div className="flex rounded-xl overflow-hidden border border-wep-border">
          {MODES.map(m => (
            <button key={m.key} onClick={() => setMode(m.key)}
              className={`px-3 py-2 text-sm font-medium transition-colors
                ${mode === m.key ? 'text-white' : 'text-wep-muted bg-white hover:text-wep-text'}`}
              style={mode === m.key
                ? { background: 'linear-gradient(135deg,#F0115E,#C2005A)' } : {}}>
              {m.label}
            </button>
          ))}
        </div>

        {/* Period selector */}
        {mode === 'monthly' && (
          <input type="month" className="form-input py-2 text-sm w-40"
            value={period} onChange={e => setPeriod(e.target.value)} />
        )}
        {mode === 'quarterly' && (
          <>
            <select className="form-input py-2 text-sm w-44"
              value={qtr} onChange={e => setQtr(Number(e.target.value))}>
              {QUARTERS.map((q, i) => <option key={i+1} value={i+1}>{q}</option>)}
            </select>
            <select className="form-input py-2 text-sm w-32"
              value={fyYear} onChange={e => setFyYear(Number(e.target.value))}>
              {[fyYear-1, fyYear, fyYear+1].map(y => (
                <option key={y} value={y}>FY {y}-{String(y+1).slice(2)}</option>
              ))}
            </select>
          </>
        )}
        {mode === 'yearly' && (
          <select className="form-input py-2 text-sm w-36"
            value={fyYear} onChange={e => setFyYear(Number(e.target.value))}>
            {[fyYear-2, fyYear-1, fyYear, fyYear+1].map(y => (
              <option key={y} value={y}>FY {y}-{String(y+1).slice(2)}</option>
            ))}
          </select>
        )}
        {mode === 'weekly' && (
          <span className="text-sm text-wep-muted">Current week vs same week last year</span>
        )}
      </div>

      {/* Comparison legend */}
      {!isLoading && perfData && (
        <div className="flex items-center gap-4 mb-4 px-1 text-xs flex-wrap">
          <div className="flex items-center gap-1.5 text-emerald-600 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
            ↑ = Better than {perfData.prev_period}
          </div>
          <div className="flex items-center gap-1.5 text-red-500 font-medium">
            <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
            ↓ = Worse than {perfData.prev_period}
          </div>
          {mode === 'monthly' && perfData.mom_period && (
            <div className="text-wep-muted">· MoM = vs {perfData.mom_period}</div>
          )}
        </div>
      )}

      {/* KPI Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[1,2,3,4,5,6,7,8,9,10].map(i=><div key={i} className="skeleton h-24 rounded-2xl"/>)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {Object.keys(KPI_META).map(k => (
            <KpiCard key={k} k={k} data={perfData} mode={mode} />
          ))}
        </div>
      )}

      {/* Revenue summary bar (monthly only) */}
      {mode === 'monthly' && revData && revData.target > 0 && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-wep-muted uppercase tracking-wide">Achievement Progress</span>
            <span className="text-sm font-bold"
              style={{ color: revData.target_achievement_pct >= 100 ? '#059669' :
                              revData.target_achievement_pct >= 75  ? '#D97706' : '#F0115E' }}>
              {revData.target_achievement_pct}% of {inr(revData.target)}
            </span>
          </div>
          <div className="h-3 bg-wep-border rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.min(revData.target_achievement_pct, 100)}%`,
                background: revData.target_achievement_pct >= 100 ? '#059669'
                          : revData.target_achievement_pct >= 75  ? '#D97706' : '#F0115E'
              }} />
          </div>
          <div className="flex justify-between text-xs text-wep-muted mt-1.5">
            <span>{inr(revData.revenue)} achieved</span>
            <span>{inr(revData.gap > 0 ? revData.gap : 0)} gap remaining</span>
          </div>
        </div>
      )}

      {/* Target editor */}
      {showTargets && canEditTargets && (
        <TargetEditor period={
          mode === 'quarterly' ? `${fyYear}-Q${qtr}`
          : mode === 'yearly'  ? `${fyYear}`
          : period
        } />
      )}
    </div>
  )
}
