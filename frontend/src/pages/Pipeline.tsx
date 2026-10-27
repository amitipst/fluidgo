import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { format } from 'date-fns'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import CloseDealModal from '@/components/CloseDealModal'
import PipelineHistory from '@/components/PipelineHistory'
import DealMomentum from '@/components/DealMomentum'
import PipelineSheet from '@/components/PipelineSheet'
import DealForm from '@/components/DealForm'
import { dealRevenue } from '@/lib/revenue'

// Must match every stage the backend can actually set (pipeline.py's DealIn
// Literal) — "qualification" (default landing stage when a lead is converted,
// see Leads.convert_lead_to_deal) and "on_hold" (a close_deal outcome) were
// missing here, so the Edit form's Stage dropdown had no option matching a
// deal actually sitting in either state: the <select> rendered with nothing
// selected, and a rep couldn't move it into a normal stage. Same underlying
// gap as the backend Literal fix in pipeline.py — fix both together or the
// bug just moves between them.
const STAGES = ['All', 'cold', 'warm', 'qualification', 'hot', 'on_hold', 'closed_won', 'closed_lost', 'dropped']
const PRACTICES = ['All practices', 'Cloud & Security', 'Microsoft', 'Managed Services',
                   'Network', 'End User Computing', 'Cybersecurity', 'Azure']
const today = format(new Date(), 'yyyy-MM-dd')

const stageCfg: Record<string, { label: string; color: string; dot: string }> = {
  cold:          { label: 'Cold',           color: 'text-sky-600 bg-sky-50',       dot: '#0EA5E9' },
  warm:          { label: 'Warm',           color: 'text-amber-600 bg-amber-50',   dot: '#D97706' },
  qualification: { label: 'Qualification',  color: 'text-purple-600 bg-purple-50', dot: '#92278E' },
  hot:           { label: '🔥 Hot',         color: 'text-red-600 bg-red-50',       dot: '#DC2626' },
  closed_won:    { label: '✅ Won',          color: 'text-green-700 bg-green-50',   dot: '#059669' },
  closed_lost:   { label: '❌ Lost',        color: 'text-gray-500 bg-gray-100',    dot: '#9CA3AF' },
  on_hold:       { label: '⏸ On Hold',      color: 'text-amber-600 bg-amber-50',   dot: '#D97706' },
  dropped:       { label: '🚫 Dropped',     color: 'text-gray-400 bg-gray-50',     dot: '#D1D5DB' },
}

function fmt(v: number) {
  if (v >= 10000000) return `₹${(v/10000000).toFixed(1)}Cr`
  if (v >= 100000)   return `₹${(v/100000).toFixed(1)}L`
  if (v >= 1000)     return `₹${(v/1000).toFixed(0)}K`
  return `₹${v}`
}

export default function Pipeline() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [stageFilter, setStageFilter] = useState('All')
  const [practiceFilter, setPracticeFilter] = useState('All practices')
  const [showAdd, setShowAdd] = useState(false)
    const [editId, setEditId] = useState<string | null>(null)
  const [closingDeal, setClosingDeal] = useState<any | null>(null)
  const [reassigningId, setReassigningId] = useState<string | null>(null)
  const [reassignTo, setReassignTo] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [view, setView] = useState<'cards' | 'sheet'>('cards')

  const { user } = useAuthStore()
  const canReassign = ['manager','regional_manager','bu_head','business_head','coo','ceo','super_admin'].includes(user?.role ?? '')

  const { data: teamUsers = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/users').then(r => r.data),
    enabled: canReassign,
  })
  const salesUsers = teamUsers.filter((u: any) =>
    ['rep','inside_sales','pre_sales','manager'].includes(u.role))

  const reassignDeal = useMutation({
    mutationFn: ({ id, new_owner_id }: { id: string; new_owner_id: string }) =>
      api.post(`/pipeline/${id}/reassign`, { new_owner_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipeline'] })
      setReassigningId(null); setReassignTo('')
    },
    onError: (e: any) => alert(getErrorMessage(e, 'Could not reassign deal')),
  })

  const { data: deals = [], isLoading } = useQuery({
    queryKey: ['pipeline', showArchived],
    queryFn: () => api.get(`/pipeline${showArchived ? '?include_archived=true' : ''}`).then(r => r.data)
  })

  const archiveDeal = useMutation({
    mutationFn: ({ id, archive }: { id: string; archive: boolean }) =>
      api.post(`/pipeline/${id}/${archive ? 'archive' : 'unarchive'}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pipeline'] }),
    onError: (e: any) => alert(getErrorMessage(e, 'Could not update deal')),
  })

  // Filtered
  const filtered = (deals as any[]).filter(d => {
    const matchSearch = !search ||
      d.company?.toLowerCase().includes(search.toLowerCase()) ||
      d.title?.toLowerCase().includes(search.toLowerCase()) ||
      d.todays_update?.toLowerCase().includes(search.toLowerCase())
    const matchStage = stageFilter === 'All' || d.stage === stageFilter
    const matchPractice = practiceFilter === 'All practices' ||
      d.todays_update?.toLowerCase().includes(practiceFilter.toLowerCase())
    return matchSearch && matchStage && matchPractice
  })

  // Summary stats
  // v1.6.1: same server-side definition of "open" as Health and the radar (excludes dropped and on-hold)
  const active   = (deals as any[]).filter(d => d.is_open ?? !['closed_won','closed_lost','dropped','on_hold'].includes(d.stage))
  const won      = (deals as any[]).filter(d => d.stage === 'closed_won')
  // dealRevenue() = ARR + One-time, falling back to legacy deal_value — see
  // lib/revenue.ts. Raw deal_value alone silently zeroed out any deal using
  // the newer Pipeline Sheet fields (same bug class fixed server-side in v1.4.3).
  const totalVal = won.reduce((s: number, d: any) => s + dealRevenue(d), 0)
  const pipelineVal = active.reduce((s: number, d: any) => s + (d.amount ?? dealRevenue(d)), 0)

  return (
    <div className={`p-4 md:p-6 mx-auto ${view === 'sheet' ? 'max-w-7xl' : 'max-w-5xl'}`}>

      {/* Header */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-text">📋 Deals</h1>
          <p className="text-wep-muted text-sm">
            {filtered.length} of {(deals as any[]).length} deals
          </p>
        </div>
        <div role="tablist" aria-label="Pipeline view" className="inline-flex rounded-xl border border-wep-border overflow-hidden">
          {([['cards', 'Cards'], ['sheet', 'Sheet by rep']] as const).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={view === k} onClick={() => setView(k)}
              className={`px-4 min-h-[44px] text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink ${view === k ? 'bg-brand-pink text-white' : 'text-wep-muted hover:bg-wep-surface'}`}>{label}</button>))}
        </div>
        {view === 'cards' && <button onClick={() => setShowAdd(v => !v)} className="btn-primary">
          {showAdd ? '✕ Cancel' : '➕ Add Deal'}
        </button>}
      </div>

      {view === 'sheet' ? <PipelineSheet /> : <>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-2 sm:gap-3 mb-5">
        {[
          { label: 'Active Deals',     value: active.length,     sub: 'in progress',  color: '#1E6FD9' },
          { label: 'Pipeline Value',   value: fmt(pipelineVal),  sub: 'active',        color: '#D97706' },
          { label: 'Won Revenue',      value: fmt(totalVal),     sub: `${won.length} deals closed`, color: '#059669' },
        ].map(s => (
          <div key={s.label} className="card text-center py-3">
            <div className="font-display font-bold text-xl" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted mt-1">{s.label}</div>
            <div className="text-[10px] text-wep-light">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Add Deal Form — company/contact first, ARR + One-time mandatory (v1.5.0) */}
      {showAdd && (
        <div className="card mb-5 border-brand-pink/30">
          <h3 className="font-bold text-sm text-wep-text mb-4">📋 New Pipeline Deal</h3>
          <DealForm onSaved={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input type="search" className="form-input py-2 text-sm flex-1 min-w-[180px]"
          placeholder="🔍 Search company, deal or update…"
          value={search} onChange={e => setSearch(e.target.value)} />
        <select className="form-input py-2 text-sm w-full sm:w-32"
          value={stageFilter} onChange={e => setStageFilter(e.target.value)}>
          {STAGES.map(s => <option key={s} value={s}>{s === 'All' ? '📊 All Stages' : (stageCfg[s]?.label ?? s)}</option>)}
        </select>
        <select className="form-input py-2 text-sm w-full sm:w-44"
          value={practiceFilter} onChange={e => setPracticeFilter(e.target.value)}>
          {PRACTICES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        {(search || stageFilter !== 'All' || practiceFilter !== 'All practices') && (
          <button onClick={() => { setSearch(''); setStageFilter('All'); setPracticeFilter('All practices') }}
            className="btn-outline text-sm py-2">✕ Clear</button>
        )}
        {canReassign && (
          <label className="flex items-center gap-1.5 text-xs text-wep-muted px-2">
            <input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)} />
            🗄️ Show archived
          </label>
        )}
      </div>

      {/* Deals list */}
      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-2xl" />)}</div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-4xl mb-3">📋</div>
          <p className="text-wep-muted">No deals match your filters.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((d: any) => {
            const cfg = stageCfg[d.stage] ?? { label: d.stage, color: 'text-gray-500 bg-gray-100', dot: '#9CA3AF' }
            const isEditing = editId === d.id
            return (
              <div key={d.id} className="card hover:border-wep-border-strong transition-all">
                {isEditing ? (
                  <div className="space-y-4">
                    <DealForm deal={d} onSaved={() => { qc.invalidateQueries({ queryKey: ['pipeline-history', d.id] }); setEditId(null) }} onCancel={() => setEditId(null)} />
                    <PipelineHistory dealId={d.id} />
                    <DealMomentum dealId={d.id} />
                  </div>
                ) : (
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                  <div className="flex-1 min-w-0 w-full">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <div className="font-semibold text-wep-text">{d.company}{d.title && <span className="font-normal text-wep-muted"> · {d.title}</span>}</div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cfg.color}`}>
                        {cfg.label}
                      </span>
                      {d.sp_stage_label && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">{d.sp_stage_label}</span>
                      )}
                      {d.forecast_category_label && d.stage !== 'closed_won' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-50 text-sky-700" title="Forecast category, from the SP stage">{d.forecast_category_label}</span>
                      )}
                      {['high', 'critical'].includes(d.risk_level) && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-50 text-red-600" title="Deal risk (see Health & risk)">⚠ {d.risk_level} risk</span>
                      )}
                      {d.needs_revenue_split && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700"
                          title="ARR and One-time are required — open Edit to add them">⚠️ Add ARR / One-time</span>
                      )}
                      {d.source === 'service_delivery' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-50 text-purple-600"
                          title="This deal came from a Service Delivery signal">
                          🛠️ From Service Delivery
                        </span>
                      )}
                      {d.deal_type === 'farming' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600">
                          🌱 Farming
                        </span>
                      )}
                      {d.roadblock && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-50 text-red-500">
                          ⚠️ Roadblock
                        </span>
                      )}
                      {d.is_stalled && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-orange-50 text-orange-600"
                          title={`No activity in ${d.days_since_activity} days`}>
                          🐌 Stalled ({d.days_since_activity}d)
                        </span>
                      )}
                      {d.archived && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                          🗄️ Archived
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-wep-muted">
                      {d.closure_eta && `ETA: ${d.closure_eta} · `}
                      {dealRevenue(d) > 0 && <strong className="text-wep-text">{fmt(dealRevenue(d))}</strong>}
                      {(d.recurring_revenue != null || d.one_time_revenue != null) &&
                        <span> (ARR {fmt(Number(d.recurring_revenue || 0))} + One-time {fmt(Number(d.one_time_revenue || 0))})</span>}
                    </div>
                    {d.todays_update && (
                      <div className="text-xs text-wep-muted mt-1 truncate">{d.todays_update}</div>
                    )}
                    {d.next_step && (
                      <div className="text-xs mt-1">
                        <span className="text-brand-pink">→ {d.next_step}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3 sm:justify-end sm:max-w-[46%]">
                    {d.forecast_probability != null && (
                      <div className="text-left sm:text-right mr-auto sm:mr-0 min-w-[64px]">
                        <div className="font-display font-bold text-lg"
                          style={{ color: d.forecast_probability >= 70 ? '#059669' : d.forecast_probability >= 40 ? '#D97706' : '#9CA3AF' }}>
                          {d.forecast_probability}%
                        </div>
                        <div className="text-[10px] text-wep-muted">win prob.</div>
                      </div>
                    )}
                    <button onClick={() => setEditId(d.id)}
                      className="text-xs font-semibold px-3 min-h-[40px] sm:min-h-0 sm:py-1.5 rounded-lg bg-wep-surface text-wep-navy hover:bg-wep-border/60">
                      ✏️ Edit
                    </button>
                    {canReassign && (
                      <button onClick={() => { setReassigningId(reassigningId === d.id ? null : d.id); setReassignTo('') }}
                        className="text-xs font-semibold px-3 min-h-[40px] sm:min-h-0 sm:py-1.5 rounded-lg bg-wep-surface text-wep-navy hover:bg-wep-border/60">
                        🔀 Reassign
                      </button>
                    )}
                    {!['closed_won','closed_lost','on_hold','dropped'].includes(d.stage) && (
                      <button onClick={() => setClosingDeal(d)}
                        className="text-xs font-semibold px-3 min-h-[40px] sm:min-h-0 sm:py-1.5 rounded-lg text-white hover:opacity-90"
                        style={{ background: 'linear-gradient(135deg,#92278E,#5B1A6E)' }}>
                        🏁 Close
                      </button>
                    )}
                    {canReassign && (
                      <button
                        disabled={archiveDeal.isPending}
                        onClick={() => {
                          const verb = d.archived ? 'Unarchive' : 'Archive'
                          if (!window.confirm(`${verb} the deal "${d.company}"? ${d.archived ? 'It will reappear in normal views.' : 'It will be hidden from Pipeline/Opportunities but never deleted — you can unarchive it any time.'}`)) return
                          archiveDeal.mutate({ id: d.id, archive: !d.archived })
                        }}
                        className="text-xs font-semibold px-3 min-h-[40px] sm:min-h-0 sm:py-1.5 rounded-lg bg-wep-surface text-wep-muted hover:bg-wep-border/60 disabled:opacity-40">
                        {d.archived ? '♻️ Unarchive' : '🗄️ Archive'}
                      </button>
                    )}
                  </div>
                </div>
                )}
                {reassigningId === d.id && (
                  <div className="mt-3 pt-3 border-t border-wep-border flex items-center gap-2 flex-wrap">
                    <select className="form-input py-1.5 text-sm w-56" value={reassignTo}
                      onChange={e => setReassignTo(e.target.value)}>
                      <option value="">Select a team member…</option>
                      {salesUsers.map((u: any) => (
                        <option key={u.id} value={u.id}>{u.name} ({u.role.replace('_',' ')})</option>
                      ))}
                    </select>
                    <button disabled={!reassignTo || reassignDeal.isPending}
                      onClick={() => reassignDeal.mutate({ id: d.id, new_owner_id: reassignTo })}
                      className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40">
                      {reassignDeal.isPending ? 'Assigning…' : 'Assign'}
                    </button>
                    <button onClick={() => setReassigningId(null)} className="btn-outline text-xs px-3 py-1.5">Cancel</button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {closingDeal && (
        <CloseDealModal
          deal={closingDeal}
          onClose={() => setClosingDeal(null)}
          onDone={() => {
            setClosingDeal(null)
            qc.invalidateQueries({ queryKey: ['pipeline'] })
            qc.invalidateQueries({ queryKey: ['opportunities'] })
            qc.invalidateQueries({ queryKey: ['loss-analysis'] })
            qc.invalidateQueries({ queryKey: ['win-back-alerts'] })
          }}
        />
      )}
      </>}
    </div>
  )
}
