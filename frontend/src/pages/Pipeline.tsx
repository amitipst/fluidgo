import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { format } from 'date-fns'
import api from '@/hooks/useApi'
import CloseDealModal from '@/components/CloseDealModal'

const STAGES = ['All', 'cold', 'warm', 'hot', 'closed_won', 'closed_lost', 'dropped']
const PRACTICES = ['All practices', 'Cloud & Security', 'Microsoft', 'Managed Services',
                   'Network', 'End User Computing', 'Cybersecurity', 'Azure']
const today = format(new Date(), 'yyyy-MM-dd')

const stageCfg: Record<string, { label: string; color: string; dot: string }> = {
  cold:        { label: 'Cold',        color: 'text-sky-600 bg-sky-50',      dot: '#0EA5E9' },
  warm:        { label: 'Warm',        color: 'text-amber-600 bg-amber-50',  dot: '#D97706' },
  hot:         { label: '🔥 Hot',      color: 'text-red-600 bg-red-50',      dot: '#DC2626' },
  closed_won:  { label: '✅ Won',       color: 'text-green-700 bg-green-50',  dot: '#059669' },
  closed_lost: { label: '❌ Lost',     color: 'text-gray-500 bg-gray-100',   dot: '#9CA3AF' },
  on_hold:     { label: '⏸ On Hold',   color: 'text-amber-600 bg-amber-50',  dot: '#D97706' },
  dropped:     { label: '🚫 Dropped',  color: 'text-gray-400 bg-gray-50',    dot: '#D1D5DB' },
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
  const [form, setForm] = useState({
    company: '', stage: 'cold', deal_value: '',
    closure_eta: '', todays_update: '', next_step: '',
  })
  const [addErr, setAddErr] = useState('')
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({
    company: '', stage: 'cold', deal_value: '', closure_eta: '', todays_update: '', next_step: '',
  })
  const [closingDeal, setClosingDeal] = useState<any | null>(null)

  const { data: deals = [], isLoading } = useQuery({
    queryKey: ['pipeline'],
    queryFn: () => api.get('/pipeline').then(r => r.data)
  })

  const addDeal = useMutation({
    mutationFn: () => api.post('/pipeline', {
      ...form,
      deal_value: form.deal_value ? parseFloat(form.deal_value) : undefined,
      closure_eta: form.closure_eta || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipeline'] })
      setForm({ company:'', stage:'cold', deal_value:'', closure_eta:'', todays_update:'', next_step:'' })
      setShowAdd(false); setAddErr('')
    },
    onError: (e: any) => setAddErr(e?.response?.data?.detail ?? 'Failed to save deal')
  })

  const updateDeal = useMutation({
    mutationFn: (id: string) => api.patch(`/pipeline/${id}`, {
      company: editForm.company,
      stage: editForm.stage,
      deal_value: editForm.deal_value ? parseFloat(editForm.deal_value) : undefined,
      closure_eta: editForm.closure_eta || undefined,
      todays_update: editForm.todays_update || undefined,
      next_step: editForm.next_step || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipeline'] })
      setEditId(null)
    },
    onError: (e: any) => alert(e?.response?.data?.detail ?? 'Failed to update deal')
  })

  function startEdit(d: any) {
    setEditId(d.id)
    setEditForm({
      company: d.company ?? '',
      stage: d.stage ?? 'cold',
      deal_value: d.deal_value ? String(parseFloat(d.deal_value)) : '',
      closure_eta: d.closure_eta ?? '',
      todays_update: d.todays_update ?? '',
      next_step: d.next_step ?? '',
    })
  }

  // Filtered
  const filtered = (deals as any[]).filter(d => {
    const matchSearch = !search ||
      d.company?.toLowerCase().includes(search.toLowerCase()) ||
      d.todays_update?.toLowerCase().includes(search.toLowerCase())
    const matchStage = stageFilter === 'All' || d.stage === stageFilter
    const matchPractice = practiceFilter === 'All practices' ||
      d.todays_update?.toLowerCase().includes(practiceFilter.toLowerCase())
    return matchSearch && matchStage && matchPractice
  })

  // Summary stats
  const active   = (deals as any[]).filter(d => !['closed_won','closed_lost','dropped'].includes(d.stage))
  const won      = (deals as any[]).filter(d => d.stage === 'closed_won')
  const totalVal = won.reduce((s: number, d: any) => s + parseFloat(d.deal_value || 0), 0)
  const pipelineVal = active.reduce((s: number, d: any) => s + parseFloat(d.deal_value || 0), 0)

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-text">📋 Pipeline</h1>
          <p className="text-wep-muted text-sm">
            {filtered.length} of {(deals as any[]).length} deals
          </p>
        </div>
        <button onClick={() => {
          if (showAdd) {
            setForm({ company:'', stage:'cold', deal_value:'', closure_eta:'', todays_update:'', next_step:'' })
            setAddErr('')
          }
          setShowAdd(v => !v)
        }} className="btn-primary">
          {showAdd ? '✕ Cancel' : '➕ Add Deal'}
        </button>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3 mb-5">
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

      {/* Add Deal Form */}
      {showAdd && (
        <div className="card mb-5 border-brand-pink/30">
          <h3 className="font-bold text-sm text-wep-text mb-4">📋 New Pipeline Deal</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="form-label block mb-1">Company Name *</label>
              <input className="form-input" placeholder="e.g. Infosys BPM" required
                value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Stage</label>
              <select className="form-input" value={form.stage}
                onChange={e => setForm(f => ({ ...f, stage: e.target.value }))}>
                {STAGES.filter(s => s !== 'All').map(s => (
                  <option key={s} value={s}>{stageCfg[s]?.label ?? s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label block mb-1">Deal Value (₹)</label>
              <input type="number" className="form-input" placeholder="e.g. 500000"
                value={form.deal_value} onChange={e => setForm(f => ({ ...f, deal_value: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Expected Closure</label>
              <input type="date" className="form-input"
                value={form.closure_eta} onChange={e => setForm(f => ({ ...f, closure_eta: e.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="form-label block mb-1">Today's Update</label>
              <input className="form-input" placeholder="Brief update on the opportunity"
                value={form.todays_update} onChange={e => setForm(f => ({ ...f, todays_update: e.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="form-label block mb-1">Next Step</label>
              <input className="form-input" placeholder="e.g. Send proposal, arrange demo..."
                value={form.next_step} onChange={e => setForm(f => ({ ...f, next_step: e.target.value }))} />
            </div>
          </div>
          {addErr && <p className="text-red-500 text-xs mt-2">{addErr}</p>}
          <div className="flex gap-2 mt-4">
            <button onClick={() => addDeal.mutate()} disabled={!form.company || addDeal.isPending}
              className="btn-primary">
              {addDeal.isPending ? '⏳ Saving…' : '✅ Save Deal'}
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input type="search" className="form-input py-2 text-sm flex-1 min-w-[180px]"
          placeholder="🔍 Search company or update…"
          value={search} onChange={e => setSearch(e.target.value)} />
        <select className="form-input py-2 text-sm w-32"
          value={stageFilter} onChange={e => setStageFilter(e.target.value)}>
          {STAGES.map(s => <option key={s} value={s}>{s === 'All' ? '📊 All Stages' : (stageCfg[s]?.label ?? s)}</option>)}
        </select>
        <select className="form-input py-2 text-sm w-44"
          value={practiceFilter} onChange={e => setPracticeFilter(e.target.value)}>
          {PRACTICES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        {(search || stageFilter !== 'All' || practiceFilter !== 'All practices') && (
          <button onClick={() => { setSearch(''); setStageFilter('All'); setPracticeFilter('All practices') }}
            className="btn-outline text-sm py-2">✕ Clear</button>
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
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="form-label block mb-1">Company</label>
                      <input className="form-input" value={editForm.company}
                        onChange={e => setEditForm(f => ({ ...f, company: e.target.value }))} />
                    </div>
                    <div>
                      <label className="form-label block mb-1">Stage</label>
                      <select className="form-input" value={editForm.stage}
                        onChange={e => setEditForm(f => ({ ...f, stage: e.target.value }))}>
                        {STAGES.filter(s => s !== 'All').map(s => (
                          <option key={s} value={s}>{stageCfg[s]?.label ?? s}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="form-label block mb-1">Deal Value (₹)</label>
                      <input type="number" className="form-input" value={editForm.deal_value}
                        onChange={e => setEditForm(f => ({ ...f, deal_value: e.target.value }))} />
                    </div>
                    <div>
                      <label className="form-label block mb-1">Expected Closure</label>
                      <input type="date" className="form-input" value={editForm.closure_eta}
                        onChange={e => setEditForm(f => ({ ...f, closure_eta: e.target.value }))} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="form-label block mb-1">Today's Update</label>
                      <input className="form-input" value={editForm.todays_update}
                        onChange={e => setEditForm(f => ({ ...f, todays_update: e.target.value }))} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="form-label block mb-1">Next Step</label>
                      <input className="form-input" value={editForm.next_step}
                        onChange={e => setEditForm(f => ({ ...f, next_step: e.target.value }))} />
                    </div>
                    <div className="md:col-span-2 flex gap-2">
                      <button onClick={() => updateDeal.mutate(d.id)} disabled={updateDeal.isPending}
                        className="btn-primary text-sm py-1.5">
                        {updateDeal.isPending ? '⏳ Saving…' : '✅ Save'}
                      </button>
                      <button onClick={() => setEditId(null)} className="btn-outline text-sm py-1.5">Cancel</button>
                    </div>
                  </div>
                ) : (
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <div className="font-semibold text-wep-text">{d.company}</div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cfg.color}`}>
                        {cfg.label}
                      </span>
                      {d.roadblock && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-50 text-red-500">
                          ⚠️ Roadblock
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-wep-muted">
                      {d.closure_eta && `ETA: ${d.closure_eta} · `}
                      {d.deal_value && <strong className="text-wep-text">{fmt(parseFloat(d.deal_value))}</strong>}
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
                  <div className="flex items-center gap-3 shrink-0">
                    {d.ai_closure_pct != null && (
                      <div className="text-right">
                        <div className="font-display font-bold text-lg"
                          style={{ color: d.ai_closure_pct >= 70 ? '#059669' : d.ai_closure_pct >= 40 ? '#D97706' : '#9CA3AF' }}>
                          {d.ai_closure_pct}%
                        </div>
                        <div className="text-[10px] text-wep-muted">closure prob.</div>
                      </div>
                    )}
                    <button onClick={() => startEdit(d)}
                      className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-wep-surface text-wep-navy hover:bg-wep-border/60">
                      ✏️ Edit
                    </button>
                    {!['closed_won','closed_lost','on_hold','dropped'].includes(d.stage) && (
                      <button onClick={() => setClosingDeal(d)}
                        className="text-xs font-semibold px-3 py-1.5 rounded-lg text-white hover:opacity-90"
                        style={{ background: 'linear-gradient(135deg,#92278E,#5B1A6E)' }}>
                        🏁 Close
                      </button>
                    )}
                  </div>
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
    </div>
  )
}
