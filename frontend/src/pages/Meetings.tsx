import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { format } from 'date-fns'
import api from '@/hooks/useApi'

const MEETING_TYPES = ['F2F', 'Virtual', 'Call']
const today = format(new Date(), 'yyyy-MM-dd')

const INTENT_CFG: Record<string, { label: string; cls: string }> = {
  hot:      { label: '🔥 Hot',     cls: 'bg-red-50 text-red-600'    },
  warm:     { label: '🌡 Warm',    cls: 'bg-amber-50 text-amber-700' },
  engaged:  { label: '💡 Engaged', cls: 'bg-teal-50 text-teal-700'  },
  cold:     { label: '❄️ Cold',    cls: 'bg-sky-50 text-sky-600'    },
}

const emptyForm = {
  date: today, company: '', contact_name: '', meeting_type: 'F2F',
  discussion: '', opportunity: false, support_needed: '',
  bant_budget: false, bant_authority: false, bant_need: false, bant_timeline: false,
}

function BANTBar({ m }: { m: any }) {
  const items = [
    { label: 'Budget',    val: m.bant_budget    },
    { label: 'Authority', val: m.bant_authority },
    { label: 'Need',      val: m.bant_need      },
    { label: 'Timeline',  val: m.bant_timeline  },
  ]
  const filled = items.filter(i => i.val).length
  return (
    <div className="mt-3 flex items-center gap-2">
      <span className="text-[10px] font-bold text-wep-muted uppercase tracking-wide">BANT</span>
      <div className="flex gap-1 flex-1">
        {items.map(item => (
          <div key={item.label}
            className={`flex-1 h-1.5 rounded-full transition-colors ${item.val ? 'bg-wep-teal' : 'bg-wep-border'}`}
            title={item.label} />
        ))}
      </div>
      <span className="text-[10px] text-wep-muted font-semibold">{filled}/4</span>
      {m.opportunity && <span className="text-[10px] font-bold text-brand-pink">• Opp</span>}
    </div>
  )
}

export default function Meetings() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [addErr, setAddErr] = useState('')

  const { data: meetings = [], isLoading } = useQuery({
    queryKey: ['meetings'],
    queryFn: () => api.get('/meetings').then(r => r.data),
  })

  const addMeeting = useMutation({
    mutationFn: () => api.post('/meetings', form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meetings'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      setForm(emptyForm); setShowAdd(false); setAddErr('')
    },
    onError: (e: any) => setAddErr(e?.response?.data?.detail ?? 'Failed to save meeting'),
  })

  const filtered = (meetings as any[]).filter(m => {
    const q = search.toLowerCase()
    const matchSearch = !search ||
      m.company?.toLowerCase().includes(q) ||
      m.discussion?.toLowerCase().includes(q) ||
      m.contact_name?.toLowerCase().includes(q)
    const matchType = typeFilter === 'All' || m.meeting_type === typeFilter
    return matchSearch && matchType
  })

  const hot   = (meetings as any[]).filter(m => m.ai_intent_score === 'hot').length
  const opp   = (meetings as any[]).filter(m => m.opportunity).length
  const total = (meetings as any[]).length

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">🤝 Meeting Intelligence</h1>
          <p className="page-sub">{total} meetings · {hot} hot · {opp} opportunities</p>
        </div>
        <button onClick={() => setShowAdd(v => !v)} className="btn-primary">
          {showAdd ? '✕ Cancel' : '➕ Log Meeting'}
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="card mb-5 border-brand-pink/30">
          <h3 className="font-bold text-sm text-wep-text mb-4">📝 Log a Meeting</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="form-label block mb-1">Company *</label>
              <input className="form-input" placeholder="e.g. Infosys Pune" required
                value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Contact Name</label>
              <input className="form-input" placeholder="e.g. Mr. Anil Kumar"
                value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Date</label>
              <input type="date" className="form-input" value={form.date}
                onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Type</label>
              <select className="form-input" value={form.meeting_type}
                onChange={e => setForm(f => ({ ...f, meeting_type: e.target.value }))}>
                {MEETING_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="form-label block mb-1">Discussion Summary *</label>
              <textarea rows={2} className="form-input resize-none"
                placeholder="What was discussed? Requirements, next steps, concerns..."
                value={form.discussion} onChange={e => setForm(f => ({ ...f, discussion: e.target.value }))} />
            </div>
          </div>

          {/* BANT checkboxes */}
          <div className="mt-3">
            <label className="form-label block mb-2">BANT Qualification</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { key: 'bant_budget', label: '💰 Budget confirmed' },
                { key: 'bant_authority', label: '👔 Decision maker met' },
                { key: 'bant_need', label: '✅ Need established' },
                { key: 'bant_timeline', label: '📅 Timeline agreed' },
              ].map(({ key, label }) => (
                <label key={key} className={`flex items-center gap-2 px-3 py-2 rounded-xl border cursor-pointer text-xs font-medium transition-all
                  ${(form as any)[key] ? 'border-wep-teal bg-teal-50 text-teal-700' : 'border-wep-border text-wep-muted'}`}>
                  <input type="checkbox" className="accent-wep-teal"
                    checked={(form as any)[key]}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.checked }))} />
                  {label}
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 mt-4 flex-wrap">
            <label className="flex items-center gap-2 text-sm cursor-pointer text-wep-muted">
              <input type="checkbox" className="accent-brand-pink"
                checked={form.opportunity}
                onChange={e => setForm(f => ({ ...f, opportunity: e.target.checked }))} />
              🧭 Mark as opportunity
            </label>
          </div>

          {addErr && <p className="text-red-500 text-xs mt-2">{addErr}</p>}
          <button onClick={() => addMeeting.mutate()}
            disabled={!form.company || !form.discussion || addMeeting.isPending}
            className="btn-primary mt-4">
            {addMeeting.isPending ? '⏳ Saving…' : '✅ Save Meeting'}
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input type="search" className="form-input py-2 text-sm flex-1 min-w-[180px]"
          placeholder="🔍 Search company, contact, discussion…"
          value={search} onChange={e => setSearch(e.target.value)} />
        <select className="form-input py-2 text-sm w-36"
          value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          {['All', ...MEETING_TYPES].map(t => (
            <option key={t} value={t}>{t === 'All' ? '📌 All Types' : t}</option>
          ))}
        </select>
        {(search || typeFilter !== 'All') && (
          <button onClick={() => { setSearch(''); setTypeFilter('All') }}
            className="btn-outline text-sm py-2">✕ Clear</button>
        )}
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i=><div key={i} className="skeleton h-24 rounded-2xl"/>)}</div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-4xl mb-3">🤝</div>
          <p className="text-wep-muted">
            {search || typeFilter !== 'All' ? 'No meetings match your filters.' : 'No meetings yet — log your first above.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((m: any) => {
            const intent = INTENT_CFG[m.ai_intent_score] ?? INTENT_CFG.cold
            return (
              <div key={m.id} className="card hover:border-wep-border-strong transition-all">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-wep-text">{m.company}</div>
                    <div className="text-xs text-wep-muted mt-0.5">
                      {m.date} · {m.meeting_type}
                      {m.contact_name && ` · ${m.contact_name}`}
                    </div>
                    {m.discussion && (
                      <p className="text-sm text-wep-muted mt-1.5 leading-relaxed line-clamp-2">
                        {m.discussion}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full ${intent.cls}`}>
                      {intent.label}
                    </span>
                    {m.ai_closure_pct != null && (
                      <span className="text-sm font-bold text-wep-accent">{m.ai_closure_pct}%</span>
                    )}
                  </div>
                </div>
                <BANTBar m={m} />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
