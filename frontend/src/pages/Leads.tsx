import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import api from '@/hooks/useApi'

const SOURCES = ['All', 'Call', 'Visit', 'Referral', 'LinkedIn', 'Email']
const STATUSES = ['All', 'new', 'qualified', 'proposal', 'closed_won', 'closed_lost']
const REQUIREMENTS = ['MS 365 Migration', 'SD-WAN', 'Managed NOC', 'Cloud Backup',
                      'Endpoint Security', 'EUC Solution', 'Microsoft 365', 'Azure',
                      'Cybersecurity', 'Network Infrastructure', 'Other']

const sourceIcon: Record<string, string> = {
  Call: '📞', Visit: '🏢', Referral: '🤝', LinkedIn: '💼', Email: '📧'
}
const scoreColor = (s: number) =>
  s >= 80 ? 'text-green-600 bg-green-50' :
  s >= 60 ? 'text-amber-600 bg-amber-50' :
  s >= 40 ? 'text-blue-600 bg-blue-50' : 'text-gray-500 bg-gray-100'

const statusConfig: Record<string, { label: string; color: string }> = {
  new:          { label: 'New',        color: 'bg-sky-50 text-sky-600'     },
  qualified:    { label: 'Qualified',  color: 'bg-blue-50 text-blue-700'   },
  proposal:     { label: 'Proposal',   color: 'bg-purple-50 text-purple-700'},
  closed_won:   { label: '✅ Won',     color: 'bg-green-50 text-green-700'  },
  closed_lost:  { label: '❌ Lost',    color: 'bg-gray-100 text-gray-500'  },
  converted:    { label: '🎯 In Pipeline', color: 'bg-teal-50 text-teal-700' },
}

const today = format(new Date(), 'yyyy-MM-dd')

export default function Leads() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({
    date: today, company: '', contact_name: '', requirement: '',
    source: 'Call', next_action: '', next_action_date: ''
  })
  const [addErr, setAddErr] = useState('')

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: () => api.get('/leads').then(r => r.data)
  })

  const addLead = useMutation({
    mutationFn: () => api.post('/leads', {
      ...form,
      next_action_date: form.next_action_date || undefined
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['leads'] })
      setForm({ date: today, company: '', contact_name: '', requirement: '',
                source: 'Call', next_action: '', next_action_date: '' })
      setShowAdd(false); setAddErr('')
    },
    onError: (e: any) => setAddErr(e?.response?.data?.detail ?? 'Failed to save lead')
  })

  const convertToDeal = useMutation({
    mutationFn: (leadId: string) => api.post(`/leads/${leadId}/convert-to-deal`, {}),
    onSuccess: (res: any) => {
      qc.invalidateQueries({ queryKey: ['leads'] })
      qc.invalidateQueries({ queryKey: ['pipeline'] })
      if (window.confirm(`${res.data.message}\n\nGo to Pipeline to add deal value and next steps?`)) {
        navigate('/pipeline')
      }
    },
    onError: (e: any) => alert(e?.response?.data?.detail ?? 'Could not convert to deal'),
  })

  // Filtered view
  const filtered = (leads as any[]).filter(l => {
    const matchSearch = !search ||
      l.company?.toLowerCase().includes(search.toLowerCase()) ||
      l.contact_name?.toLowerCase().includes(search.toLowerCase()) ||
      l.requirement?.toLowerCase().includes(search.toLowerCase())
    const matchSource = sourceFilter === 'All' || l.source === sourceFilter
    const matchStatus = statusFilter === 'All' || l.status === statusFilter
    return matchSearch && matchSource && matchStatus
  })

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-text">🎯 Leads</h1>
          <p className="text-wep-muted text-sm">
            {filtered.length} of {(leads as any[]).length} leads
            {sourceFilter !== 'All' || statusFilter !== 'All' ? ' (filtered)' : ''}
          </p>
        </div>
        <button onClick={() => {
          if (showAdd) {
            // Closing the form → clear any half-filled fields so a reopen is fresh
            setForm({ date: today, company: '', contact_name: '', requirement: '',
                      source: 'Call', next_action: '', next_action_date: '' })
            setAddErr('')
          }
          setShowAdd(v => !v)
        }} className="btn-primary">
          {showAdd ? '✕ Cancel' : '➕ Add Lead'}
        </button>
      </div>

      {/* Add Lead Form */}
      {showAdd && (
        <div className="card mb-5 border-brand-pink/30">
          <h3 className="font-bold text-sm text-wep-text mb-4">🎯 New Lead</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="form-label block mb-1">Company Name *</label>
              <input className="form-input" placeholder="e.g. Infosys Pune" required
                value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Contact Name</label>
              <input className="form-input" placeholder="e.g. Mr. Anil Kumar"
                value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Requirement</label>
              <select className="form-input" value={form.requirement}
                onChange={e => setForm(f => ({ ...f, requirement: e.target.value }))}>
                <option value="">Select or type below</option>
                {REQUIREMENTS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="form-label block mb-1">Source *</label>
              <select className="form-input" value={form.source}
                onChange={e => setForm(f => ({ ...f, source: e.target.value }))}>
                {SOURCES.filter(s => s !== 'All').map(s => (
                  <option key={s} value={s}>{sourceIcon[s]} {s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label block mb-1">Next Action</label>
              <input className="form-input" placeholder="e.g. Send proposal by Friday"
                value={form.next_action} onChange={e => setForm(f => ({ ...f, next_action: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Follow-Up Date</label>
              <input type="date" className="form-input"
                value={form.next_action_date} onChange={e => setForm(f => ({ ...f, next_action_date: e.target.value }))} />
            </div>
          </div>
          {addErr && <p className="text-red-500 text-xs mt-2">{addErr}</p>}
          <div className="flex gap-2 mt-4">
            <button onClick={() => addLead.mutate()} disabled={!form.company || addLead.isPending}
              className="btn-primary">
              {addLead.isPending ? '⏳ Saving…' : '✅ Save Lead'}
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input type="search" className="form-input py-2 text-sm flex-1 min-w-[180px]"
          placeholder="🔍 Search company, contact, requirement…"
          value={search} onChange={e => setSearch(e.target.value)} />
        <select className="form-input py-2 text-sm w-32"
          value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
          {SOURCES.map(s => <option key={s} value={s}>{s === 'All' ? '📌 All Sources' : `${sourceIcon[s]} ${s}`}</option>)}
        </select>
        <select className="form-input py-2 text-sm w-36"
          value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          {STATUSES.map(s => <option key={s} value={s}>{s === 'All' ? '🔖 All Status' : (statusConfig[s]?.label ?? s)}</option>)}
        </select>
        {(search || sourceFilter !== 'All' || statusFilter !== 'All') && (
          <button onClick={() => { setSearch(''); setSourceFilter('All'); setStatusFilter('All') }}
            className="btn-outline text-sm py-2">✕ Clear</button>
        )}
      </div>

      {/* Leads List */}
      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-2xl" />)}</div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-4xl mb-3">🎯</div>
          <p className="text-wep-muted">
            {search || sourceFilter !== 'All' || statusFilter !== 'All'
              ? 'No leads match your filters.'
              : 'No leads yet — add your first lead above.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((l: any) => (
            <div key={l.id} className="card hover:border-wep-border-strong transition-all">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="font-semibold text-wep-text">{l.company}</div>
                    {l.status && statusConfig[l.status] && (
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusConfig[l.status].color}`}>
                        {statusConfig[l.status].label}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-wep-muted mt-0.5">
                    {l.contact_name && <span>{l.contact_name} · </span>}
                    Added {l.date}
                  </div>
                  {l.requirement && (
                    <div className="text-xs text-wep-muted mt-1 flex items-center gap-1">
                      <span>📋</span> {l.requirement}
                    </div>
                  )}
                  {l.next_action && (
                    <div className="text-xs mt-1">
                      <span className="text-brand-pink">→ {l.next_action}</span>
                      {l.next_action_date && (
                        <span className="text-wep-muted"> · by {l.next_action_date}</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs font-semibold px-2 py-1 rounded-lg"
                    style={{ background: 'rgba(255,255,255,0.8)', border: '1px solid #E8DFF5' }}>
                    {sourceIcon[l.source] ?? '📌'} {l.source}
                  </span>
                  {l.ai_lead_score != null && (
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${scoreColor(l.ai_lead_score)}`}>
                      {l.ai_lead_score} score
                    </span>
                  )}
                </div>
              </div>
              {/* Provenance + Convert to Deal — funnel step 2 */}
              <div className="mt-3 pt-3 border-t border-wep-border flex items-center justify-between gap-2 flex-wrap">
                <span className="text-[11px] text-wep-muted">
                  {l.source_meeting_id ? '🔗 From a meeting' : ''}
                  {l.converted_to_deal_id
                    ? ' · ✓ Promoted to Pipeline'
                    : l.source_meeting_id ? '' : 'Qualified? Promote this lead into a pipeline deal.'}
                </span>
                {!l.converted_to_deal_id && (
                  <button
                    onClick={() => convertToDeal.mutate(l.id)}
                    disabled={convertToDeal.isPending}
                    className="text-xs font-bold px-3 py-1.5 rounded-lg text-white disabled:opacity-40"
                    style={{ background: 'linear-gradient(135deg,#0D9488,#0F766E)' }}>
                    {convertToDeal.isPending ? '⏳ Converting…' : '→ Convert to Deal'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
