import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api, { getErrorMessage } from '@/hooks/useApi'
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
  target:         { label:'Revenue Target', icon:'🎯', fmt: inr             },
  order_booking_target: { label:'Order Bk. Target', icon:'📦', fmt: inr     },
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
  // edits keyed by `${user_id}:${type}`
  const [editing, setEditing] = useState<Record<string, string>>({})
  const [saving,  setSaving]  = useState<string | null>(null)
  const [saved,   setSaved]   = useState<Record<string, boolean>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['team-targets', period],
    queryFn: () => api.get(`/analytics/revenue/team-targets?period=${period}`).then(r => r.data),
  })

  const setTarget = useMutation({
    mutationFn: ({ user_id, amount, target_type }: { user_id: string; amount: number; target_type: string }) =>
      api.post('/analytics/revenue/targets', {
        user_id, period, target_amount: amount, target_type
      }),
    onSuccess: (_r, vars) => {
      const key = `${vars.user_id}:${vars.target_type}`
      setSaved(s => ({ ...s, [key]: true }))
      setSaving(null)
      setTimeout(() => setSaved(s => ({ ...s, [key]: false })), 2000)
      qc.invalidateQueries({ queryKey: ['team-targets'] })
      qc.invalidateQueries({ queryKey: ['revenue-analytics'] })
      qc.invalidateQueries({ queryKey: ['performance'] })
    },
    onError: (e: any) => { setSaving(null); alert(getErrorMessage(e, 'Could not save target')) },
  })

  if (isLoading) return <div className="skeleton h-32 rounded-2xl" />

  const members: any[] = data?.members ?? []
  const regionGroups = members.reduce((acc: any, m: any) => {
    const r = m.region || 'Unknown'
    if (!acc[r]) acc[r] = []
    acc[r].push(m)
    return acc
  }, {})

  // One editable target input (revenue or order_booking) for a member
  function TargetInput({ m, type, current }: { m: any; type: 'revenue' | 'order_booking'; current: number }) {
    const key = `${m.user_id}:${type}`
    const val = editing[key] ?? String(current || '')
    const isDirty = val !== String(current || '')
    return (
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-wep-muted">₹</span>
        <input
          type="number" min="0" step="50000"
          className="form-input py-1.5 text-sm w-28 text-right"
          value={val}
          onChange={e => setEditing(s => ({ ...s, [key]: e.target.value }))}
          placeholder="0"
        />
        {isDirty ? (
          <>
            <button
              disabled={saving === key}
              onClick={() => {
                setSaving(key)
                setTarget.mutate({ user_id: m.user_id, amount: parseFloat(val) || 0, target_type: type })
              }}
              className="text-xs font-bold px-2.5 py-1.5 rounded-lg text-white"
              style={{ background: type === 'revenue' ? '#F0115E' : '#0D9488' }}>
              {saving === key ? '…' : 'Set'}
            </button>
            <button
              onClick={() => setEditing(s => { const n = { ...s }; delete n[key]; return n })}
              className="text-xs font-semibold px-2 py-1.5 rounded-lg text-wep-muted hover:bg-wep-border/40"
              title="Discard change">
              ✕
            </button>
          </>
        ) : saved[key] ? (
          <span className="text-xs text-emerald-600 font-bold">✅</span>
        ) : (
          <span className="text-[11px] text-wep-muted w-14 text-right">{current > 0 ? inr(current) : '—'}</span>
        )}
      </div>
    )
  }

  return (
    <div className="card mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-wep-text">
          🎯 Targets — {period.includes('-Q') ? `${period.split('-Q')[0]} Q${period.split('-Q')[1]} (quarterly)`
            : /^\d{4}$/.test(period) ? `${period} (full year)`
            : `${period} (monthly)`}
        </h3>
        <span className="text-xs text-wep-muted">{members.length} team members</span>
      </div>
      <p className="text-xs text-wep-muted mb-4">
        Set <span className="font-semibold" style={{ color: '#F0115E' }}>Revenue</span> and{' '}
        <span className="font-semibold" style={{ color: '#0D9488' }}>Order Booking</span> targets separately for each member.
        <br/>
        <span className="text-[11px]">
          💡 Switch the <strong>Weekly / Monthly / Quarterly / Yearly</strong> tab above before editing to set targets for that period.
        </span>
      </p>

      {Object.entries(regionGroups).map(([region, reps]: [string, any]) => (
        <div key={region} className="mb-5 last:mb-0">
          <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2 px-1">
            🗺️ {region}
          </div>
          <div className="space-y-2">
            {reps.map((m: any) => (
              <div key={m.user_id}
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-wep-border bg-wep-surface/50 flex-wrap">
                <div className="flex-1 min-w-[140px]">
                  <div className="text-sm font-semibold text-wep-text truncate">{m.name}</div>
                  <div className="text-[10px] text-wep-muted">{m.role} · {m.email}</div>
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  <div className="flex items-center gap-2 justify-end">
                    <span className="text-[10px] font-bold uppercase tracking-wide w-16 text-right" style={{ color: '#F0115E' }}>Revenue</span>
                    <TargetInput m={m} type="revenue" current={m.revenue} />
                  </div>
                  <div className="flex items-center gap-2 justify-end">
                    <span className="text-[10px] font-bold uppercase tracking-wide w-16 text-right" style={{ color: '#0D9488' }}>Order Bk.</span>
                    <TargetInput m={m} type="order_booking" current={m.order_booking} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Quarterly / Yearly grid editor ─────────────────────────────────────────────
// One screen: Q1-Q4 per member, FY total auto-computed, "Save All" bulk-writes
// the underlying monthly rows in one call — never a separate quarterly/yearly
// literal period key, so this can never drift from what Analytics shows.
function QuarterlyTargetEditor({ fyYear, activeQuarter }: { fyYear: number; activeQuarter?: number }) {
  const qc = useQueryClient()
  const [targetType, setTargetType] = useState<'revenue' | 'order_booking'>('revenue')
  const [edits, setEdits] = useState<Record<string, { q1: string; q2: string; q3: string; q4: string }>>({})
  const [growthPct, setGrowthPct] = useState(15)
  const [saved, setSaved] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['team-targets-fy', fyYear],
    queryFn: () => api.get('/analytics/revenue/team-targets', {
      params: { mode: 'yearly', fy: fyYear }
    }).then(r => r.data),
  })

  const rollover = useMutation({
    mutationFn: () => api.get('/analytics/revenue/targets/rollover-preview', {
      params: { fy: fyYear, growth_pct: growthPct, target_type: targetType }
    }).then(r => r.data),
    onSuccess: (preview: any) => {
      const next: typeof edits = {}
      preview.members.forEach((m: any) => {
        next[m.user_id] = { q1: String(m.q1), q2: String(m.q2), q3: String(m.q3), q4: String(m.q4) }
      })
      setEdits(e => ({ ...e, ...next }))
    },
    onError: (e: any) => alert(getErrorMessage(e, 'Could not load last FY targets')),
  })

  const saveAll = useMutation({
    mutationFn: () => {
      const rows = Object.entries(edits).map(([user_id, v]) => ({
        user_id,
        q1: parseFloat(v.q1) || 0, q2: parseFloat(v.q2) || 0,
        q3: parseFloat(v.q3) || 0, q4: parseFloat(v.q4) || 0,
      }))
      return api.post('/analytics/revenue/targets/quarterly', { fy: fyYear, target_type: targetType, rows })
    },
    onSuccess: () => {
      setSaved(true); setEdits({})
      setTimeout(() => setSaved(false), 2500)
      qc.invalidateQueries({ queryKey: ['team-targets-fy'] })
      qc.invalidateQueries({ queryKey: ['revenue-analytics'] })
      qc.invalidateQueries({ queryKey: ['performance'] })
    },
    onError: (e: any) => alert(getErrorMessage(e, 'Could not save targets')),
  })

  if (isLoading) return <div className="skeleton h-40 rounded-2xl" />
  const members: any[] = data?.members ?? []
  const dirtyCount = Object.keys(edits).length

  const cellValue = (m: any, q: 'q1'|'q2'|'q3'|'q4') =>
    edits[m.user_id]?.[q] ?? String(m[targetType]?.[q] ?? 0)

  const setCell = (m: any, q: 'q1'|'q2'|'q3'|'q4', val: string) =>
    setEdits(prev => {
      const base = prev[m.user_id] ?? {
        q1: String(m[targetType]?.q1 ?? 0), q2: String(m[targetType]?.q2 ?? 0),
        q3: String(m[targetType]?.q3 ?? 0), q4: String(m[targetType]?.q4 ?? 0),
      }
      return { ...prev, [m.user_id]: { ...base, [q]: val } }
    })

  const rowFyTotal = (m: any) => (['q1','q2','q3','q4'] as const)
    .reduce((s, q) => s + (parseFloat(cellValue(m, q)) || 0), 0)
  const grandFyTotal = members.reduce((s, m) => s + rowFyTotal(m), 0)

  return (
    <div className="card mt-6">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="font-bold text-wep-text">🎯 {data?.fy_label} — Quarterly Targets</h3>
        <div className="flex rounded-lg overflow-hidden border border-wep-border text-xs">
          {(['revenue','order_booking'] as const).map(t => (
            <button key={t} onClick={() => setTargetType(t)}
              className={`px-3 py-1.5 font-semibold ${targetType===t ? 'text-white' : 'bg-white text-wep-muted'}`}
              style={targetType===t ? { background: t==='revenue' ? '#F0115E' : '#0D9488' } : {}}>
              {t === 'revenue' ? 'Revenue' : 'Order Booking'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap text-xs">
        <span className="text-wep-muted">🔄 Pre-fill from FY {fyYear-1}-{String(fyYear).slice(2)} with growth</span>
        <input type="number" className="form-input py-1 w-16 text-center"
          value={growthPct} onChange={e => setGrowthPct(Number(e.target.value))} />
        <span className="text-wep-muted">%</span>
        <button onClick={() => rollover.mutate()} disabled={rollover.isPending} className="btn-outline py-1 px-2.5 text-xs">
          {rollover.isPending ? 'Loading…' : 'Pre-fill'}
        </button>
        {dirtyCount > 0 && (
          <span className="text-[11px] font-semibold" style={{ color: '#D97706' }}>
            {dirtyCount} member(s) edited — not yet saved
          </span>
        )}
      </div>

      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-wep-muted">
              <th className="text-left px-1 pb-2">Member</th>
              <th className="text-right px-1 pb-2">Q1 (Apr–Jun)</th>
              <th className="text-right px-1 pb-2">Q2 (Jul–Sep)</th>
              <th className="text-right px-1 pb-2">Q3 (Oct–Dec)</th>
              <th className="text-right px-1 pb-2">Q4 (Jan–Mar)</th>
              <th className="text-right px-1 pb-2">FY Total</th>
            </tr>
          </thead>
          <tbody>
            {members.map(m => (
              <tr key={m.user_id} className="border-t border-wep-border/60">
                <td className="px-1 py-2">
                  <div className="font-semibold text-wep-text truncate max-w-[140px]">{m.name}</div>
                  <div className="text-[10px] text-wep-muted">{m.region}</div>
                </td>
                {(['q1','q2','q3','q4'] as const).map((q, i) => (
                  <td key={q} className="px-1 py-2">
                    <input type="number" min="0" step="10000"
                      className="form-input py-1 text-sm text-right w-24"
                      style={activeQuarter === i+1 ? { borderColor: '#F0115E', borderWidth: 2 } : {}}
                      value={cellValue(m, q)}
                      onChange={e => setCell(m, q, e.target.value)} />
                  </td>
                ))}
                <td className="px-1 py-2 text-right font-bold text-wep-text">{inr(rowFyTotal(m))}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-wep-border">
              <td className="px-1 py-2 font-bold text-wep-text">FY Total (all members)</td>
              <td colSpan={4}></td>
              <td className="px-1 py-2 text-right font-black" style={{ color: targetType==='revenue' ? '#F0115E' : '#0D9488' }}>
                {inr(grandFyTotal)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="flex justify-end mt-4">
        <button disabled={dirtyCount===0 || saveAll.isPending}
          onClick={() => saveAll.mutate()}
          className="text-sm font-bold px-4 py-2 rounded-xl text-white disabled:opacity-40"
          style={{ background: 'linear-gradient(135deg,#F0115E,#C2005A)' }}>
          {saveAll.isPending ? 'Saving…' : saved ? '✅ Saved' : `Save All${dirtyCount ? ` (${dirtyCount})` : ''}`}
        </button>
      </div>
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

  const canEditTargets = ['business_head','coo','ceo','super_admin'].includes(user?.role ?? '')

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
        mode === 'monthly'
          ? <TargetEditor period={period} />
          : <QuarterlyTargetEditor fyYear={fyYear} activeQuarter={mode === 'quarterly' ? qtr : undefined} />
      )}
    </div>
  )
}
