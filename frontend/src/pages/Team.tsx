import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { format } from 'date-fns'

const rigorColor = (s: number) =>
  s >= 80 ? 'text-wep-teal' : s >= 60 ? 'text-wep-amber' : s > 0 ? 'text-red-500' : 'text-wep-muted'

// v3 role definitions — matches backend ROLE_HIERARCHY
const V3_ROLES = [
  { key: 'rep',           label: '💼 Salesperson (Rep)',       level: 10 },
  { key: 'inside_sales',  label: '📞 Inside Sales',           level: 10 },
  { key: 'pre_sales',     label: '🔧 Pre-Sales',              level: 10 },
  { key: 'manager',       label: '👔 Manager',                level: 20 },
  { key: 'bu_head',       label: '🏢 BU Head',                level: 30 },
  { key: 'business_head', label: '🏭 Business Head',          level: 40 },
  { key: 'hr',            label: '👥 HR',                     level: 25 },
  { key: 'finance',       label: '💰 Finance',                level: 25 },
  { key: 'ceo',           label: '👑 CEO',                    level: 50 },
  { key: 'super_admin',   label: '⚙️ Super Admin',            level: 99 },
]

const BUSINESSES = [
  { key: 'fluidpro',   label: 'fluidPro (IT Infra)' },
  { key: 'fluidprint', label: 'fluidPrint (Managed Print)' },
  { key: 'floxtax',    label: 'floxtax (GST/ASP)' },
  { key: 'hooks',      label: 'Hooks (POS/Channel)' },
]

const REGIONS = [
  { key: 'India - North',   label: '🗺️ India — North   (Delhi, NCR, Chandigarh)' },
  { key: 'India - South',   label: '🗺️ India — South   (Bangalore, Chennai, Hyderabad)' },
  { key: 'India - West',    label: '🗺️ India — West    (Mumbai, Pune, Ahmedabad)' },
  { key: 'India - East',    label: '🗺️ India — East    (Kolkata, Bhubaneswar)' },
  { key: 'India - Central', label: '🗺️ India — Central (Nagpur, Bhopal, Indore)' },
]

const emptyForm = {
  name: '', email: '', password: '', role: 'rep',
  region: 'India - West', business: 'fluidpro'
}

export default function Team() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const today = format(new Date(), 'yyyy-MM-dd')
  const [aiContent, setAiContent] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const canManageUsers = ['manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const [showManage, setShowManage] = useState(false)
  const [showExited, setShowExited] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [formError, setFormError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ role: '', region: '', business: '', manager_id: '' })
  const [editError, setEditError] = useState('')

  const { data: teamData = [], isLoading } = useQuery({
    queryKey: ['team-analytics', showExited],
    queryFn: () => api.get(`/analytics/team${showExited ? '?include_inactive=true' : ''}`).then(r => r.data)
  })

  const { data: todayDSRs = [] } = useQuery({
    queryKey: ['team-dsr-today', today],
    queryFn: () => api.get(`/dsr/team?date=${today}`).then(r => r.data)
  })

  const { data: allUsers = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/users').then(r => r.data),
    enabled: canManageUsers && showManage
  })

  // Get roles assignable by current actor
  const { data: assignableRoles = [] } = useQuery({
    queryKey: ['assignable-roles'],
    queryFn: () => api.get('/users/roles').then(r => r.data),
    enabled: canManageUsers
  })

  const createUser = useMutation({
    mutationFn: () => api.post('/users', form),
    onSuccess: () => {
      setForm(emptyForm); setFormError('')
      qc.invalidateQueries({ queryKey: ['users'] })
      qc.invalidateQueries({ queryKey: ['team-analytics'] })
    },
    onError: (err: any) => setFormError(err?.response?.data?.detail ?? 'Could not create user')
  })

  const setStatus = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch(`/users/${id}/status`, { is_active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      qc.invalidateQueries({ queryKey: ['team-analytics'] })
    }
  })

  const updateUser = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => api.patch(`/users/${id}`, body),
    onSuccess: () => {
      setEditingId(null); setEditError('')
      qc.invalidateQueries({ queryKey: ['users'] })
      qc.invalidateQueries({ queryKey: ['team-analytics'] })
    },
    onError: (err: any) => setEditError(err?.response?.data?.detail ?? 'Could not update member')
  })

  function startEdit(u: any) {
    setEditingId(u.id)
    setEditError('')
    setEditForm({
      role: u.role,
      region: u.region || 'India - West',
      business: u.business || 'fluidpro',
      manager_id: u.manager_id || ''
    })
  }

  function saveEdit(id: string) {
    updateUser.mutate({
      id,
      body: {
        role: editForm.role,
        region: editForm.region,
        business: editForm.business,
        manager_id: editForm.manager_id || null
      }
    })
  }

  // Anyone with role_level >= 20 (manager and above) can be assigned as a manager
  const potentialManagers = allUsers.filter((u: any) => u.role_level >= 20)

  const submittedToday = new Set(todayDSRs.map((d: any) => d.user_id))

  async function runTeamAI() {
    setAiLoading(true); setAiContent('')
    const context = `West BU Team Performance:\n${teamData.map((m: any) =>
      `${m.name} (${m.role}): Rigor=${m.avg_rigor}, Calls=${m.total_calls}, Visits=${m.total_visits}, Leads=${m.total_leads}, Proposals=${m.total_proposals}, Days=${m.working_days}`
    ).join('\n')}\n\nSubmitted DSR today: ${todayDSRs.length}/${teamData.length} reps.\n\nProvide team performance summary, top/bottom performers, coaching priorities, and BU-level action items.`
    try {
      const res = await api.post('/ai/analyse', { entity_type: 'team', context })
      setAiContent(res.data.content)
    } catch {
      setAiContent('⚠️ AI analysis unavailable. Ensure Ollama is running.')
    } finally {
      setAiLoading(false)
    }
  }

  const viewTitle = user?.role === 'bu_head'
    ? `🏢 BU Head — ${user?.bu} BU`
    : user?.role === 'inside_sales'
      ? '📞 Inside Sales View'
      : user?.role === 'manager'
        ? `👥 Manager Dashboard — ${user?.bu} BU`
        : '👥 Team Dashboard'

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">{viewTitle}</h1>
          <p className="text-wep-muted text-sm">West BU · {today} · {todayDSRs.length}/{teamData.length} DSRs submitted today</p>
        </div>
        <div className="flex gap-2">
          {canManageUsers && (
            <button onClick={() => setShowManage(v => !v)} className="btn-outline">
              {showManage ? 'Close' : '👤 Manage Team'}
            </button>
          )}
          <button onClick={runTeamAI} disabled={aiLoading} className="btn-primary">
            {aiLoading ? '⏳ Analysing...' : '✨ AI Team Analysis'}
          </button>
        </div>
      </div>

      {canManageUsers && showManage && (
        <div className="card mb-6">
          <div className="font-bold text-sm text-wep-navy mb-4">👤 Onboard a New Team Member</div>
          <form
            onSubmit={e => { e.preventDefault(); createUser.mutate() }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-3"
          >
            <div>
              <label className="form-label block mb-1">Full Name *</label>
              <input className="form-input" placeholder="e.g. Rahul Sharma" required
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Work Email *</label>
              <input className="form-input" type="email" placeholder="rahul@fluidpro.in" required
                value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Temp Password (min 8 chars) *</label>
              <input className="form-input" type="text" placeholder="Temp@2026!" required
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            </div>
            <div>
              <label className="form-label block mb-1">Role *</label>
              <select className="form-input" value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                {/* Dynamic from backend — shows only roles below current actor's level */}
                {(assignableRoles.length ? assignableRoles : V3_ROLES).map((r: any) => (
                  <option key={r.key} value={r.key}>{r.label}</option>
                ))}
              </select>
              <p className="text-[10px] text-wep-muted mt-0.5">Only roles below your level shown</p>
            </div>
            <div>
              <label className="form-label block mb-1">Business *</label>
              <select className="form-input" value={form.business}
                onChange={e => setForm(f => ({ ...f, business: e.target.value }))}>
                {BUSINESSES.map(b => (
                  <option key={b.key} value={b.key}>{b.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label block mb-1">Region *</label>
              <select className="form-input" value={form.region}
                onChange={e => setForm(f => ({ ...f, region: e.target.value }))}>
                {REGIONS.map(r => (
                  <option key={r.key} value={r.key}>{r.label}</option>
                ))}
              </select>
              <p className="text-[10px] text-wep-muted mt-0.5">Which India region is this person based in?</p>
            </div>
            <div className="md:col-span-2 lg:col-span-3 flex items-center gap-3">
              <button type="submit" disabled={createUser.isPending} className="btn-primary">
                {createUser.isPending ? '⏳ Adding...' : '➕ Add Member'}
              </button>
              {formError && <p className="text-red-500 text-sm">{formError}</p>}
            </div>
          </form>

          <label className="flex items-center gap-2 text-xs text-wep-muted mb-3">
            <input type="checkbox" checked={showExited} onChange={e => setShowExited(e.target.checked)} />
            Show exited members in the performance table below
          </label>

          <div className="space-y-2">
            {allUsers.map((u: any) => (
              <div key={u.id} className="border-b border-wep-border/50 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <span className={`font-medium ${u.is_active ? 'text-wep-navy' : 'text-wep-muted line-through'}`}>{u.name}</span>
                    <span className="text-wep-muted ml-2 text-xs">
                      {u.email} · {u.role.replace('_',' ')} · {u.region || u.bu}
                      {u.manager_id && (() => {
                        const mgr = allUsers.find((m: any) => m.id === u.manager_id)
                        return mgr ? ` · reports to ${mgr.name}` : ''
                      })()}
                    </span>
                    {!u.is_active && <span className="ml-2 text-[10px] font-bold uppercase text-red-500">Exited</span>}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {u.is_active && (
                      <button
                        onClick={() => editingId === u.id ? setEditingId(null) : startEdit(u)}
                        className="text-xs font-semibold px-3 py-1 rounded-lg bg-wep-surface text-wep-navy hover:bg-wep-border/60"
                      >
                        {editingId === u.id ? 'Cancel' : '✏️ Edit'}
                      </button>
                    )}
                    <button
                      disabled={setStatus.isPending || u.id === user?.id}
                      onClick={() => setStatus.mutate({ id: u.id, is_active: !u.is_active })}
                      className={`text-xs font-semibold px-3 py-1 rounded-lg ${
                        u.is_active ? 'bg-red-50 text-red-500 hover:bg-red-100' : 'bg-teal-50 text-teal-600 hover:bg-teal-100'
                      } disabled:opacity-40`}
                      title={u.id === user?.id ? "You can't deactivate your own account" : undefined}
                    >
                      {u.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </div>
                </div>

                {editingId === u.id && (
                  <div className="mt-3 mb-1 bg-wep-surface rounded-xl p-3 grid grid-cols-1 md:grid-cols-4 gap-3">
                    <div>
                      <label className="form-label block mb-1 text-[10px]">Role</label>
                      <select className="form-input" value={editForm.role}
                        onChange={e => setEditForm(f => ({ ...f, role: e.target.value }))}>
                        <option value={u.role}>{u.role.replace('_',' ')} (current)</option>
                        {(assignableRoles.length ? assignableRoles : V3_ROLES)
                          .filter((r: any) => r.key !== u.role)
                          .map((r: any) => (<option key={r.key} value={r.key}>{r.label}</option>))}
                      </select>
                    </div>
                    <div>
                      <label className="form-label block mb-1 text-[10px]">Region / BU</label>
                      <select className="form-input" value={editForm.region}
                        onChange={e => setEditForm(f => ({ ...f, region: e.target.value }))}>
                        {REGIONS.map(r => (<option key={r.key} value={r.key}>{r.label}</option>))}
                      </select>
                    </div>
                    <div>
                      <label className="form-label block mb-1 text-[10px]">Reports to (Manager)</label>
                      <select className="form-input" value={editForm.manager_id}
                        onChange={e => setEditForm(f => ({ ...f, manager_id: e.target.value }))}>
                        <option value="">— No manager —</option>
                        {potentialManagers.filter((m: any) => m.id !== u.id).map((m: any) => (
                          <option key={m.id} value={m.id}>{m.name} ({m.role.replace('_',' ')})</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="form-label block mb-1 text-[10px]">Business</label>
                      <select className="form-input" value={editForm.business}
                        onChange={e => setEditForm(f => ({ ...f, business: e.target.value }))}>
                        {BUSINESSES.map(b => (<option key={b.key} value={b.key}>{b.label}</option>))}
                      </select>
                    </div>
                    <div className="md:col-span-4 flex items-center gap-3">
                      <button
                        onClick={() => saveEdit(u.id)}
                        disabled={updateUser.isPending}
                        className="btn-primary text-xs"
                      >
                        {updateUser.isPending ? '⏳ Saving...' : '💾 Save Changes'}
                      </button>
                      <button onClick={() => setEditingId(null)} className="btn-outline text-xs">Cancel</button>
                      {editError && <p className="text-red-500 text-xs">{editError}</p>}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Today's submission status */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card text-center">
          <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Team Size</div>
          <div className="font-display font-bold text-2xl text-wep-navy">{teamData.length}</div>
        </div>
        <div className="card text-center">
          <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">DSRs Today</div>
          <div className={`font-display font-bold text-2xl ${todayDSRs.length === teamData.length ? 'text-wep-teal' : 'text-wep-amber'}`}>
            {todayDSRs.length}/{teamData.length}
          </div>
        </div>
        <div className="card text-center">
          <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Avg Rigor</div>
          <div className="font-display font-bold text-2xl text-wep-accent">
            {teamData.length ? Math.round(teamData.reduce((a: number, d: any) => a + d.avg_rigor, 0) / teamData.length) : '—'}
          </div>
        </div>
        <div className="card text-center">
          <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Total Leads</div>
          <div className="font-display font-bold text-2xl text-wep-electric">
            {teamData.reduce((a: number, d: any) => a + d.total_leads, 0)}
          </div>
        </div>
      </div>

      {/* AI panel */}
      {(aiContent || aiLoading) && (
        <div className="ai-panel mb-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 bg-wep-electric/20 border border-wep-electric/30 text-wep-electric text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-wep-electric animate-pulse inline-block"/>AI Team Intelligence
            </span>
          </div>
          {aiLoading ? (
            <div className="flex items-center gap-2 text-white/60 text-sm">
              <span className="flex gap-1">{[0,1,2].map(i=>(
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-wep-electric animate-bounce" style={{animationDelay:`${i*0.15}s`}}/>
              ))}</span>
              Querying local LLM...
            </div>
          ) : (
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-white/85 leading-relaxed whitespace-pre-wrap"
              dangerouslySetInnerHTML={{__html: aiContent.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br/>')}}/>
          )}
        </div>
      )}

      {/* Team table */}
      <div className="card overflow-x-auto">
        <div className="font-semibold text-sm text-wep-navy mb-4">Team Performance Matrix</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-wep-border">
              {['Rep','DSR Today','Calls','Visits','Follow-Ups','Leads','Avg Rigor'].map(h => (
                <th key={h} className="text-left text-[10px] font-bold uppercase tracking-wide text-wep-muted py-2 pr-4 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={7} className="py-8 text-center text-wep-muted">Loading...</td></tr>
            ) : teamData.map((m: any) => {
              const didSubmit = submittedToday.has(m.user_id)
              return (
                <tr key={m.user_id} className={`border-b border-wep-border/50 hover:bg-wep-surface transition-colors ${m.is_active === false ? 'opacity-50' : ''}`}>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-wep-accent to-wep-electric flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                        {m.name.split(' ').map((n: string) => n[0]).join('').slice(0,2)}
                      </div>
                      <div>
                        <div className="font-medium text-wep-navy">{m.name}</div>
                        <div className="text-[10px] text-wep-muted capitalize">{m.role.replace('_',' ')}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    {m.is_active === false ? (
                      <span className="text-xs font-bold px-2 py-1 rounded-lg bg-gray-100 text-gray-500">🚪 Exited</span>
                    ) : (
                      <span className={`text-xs font-bold px-2 py-1 rounded-lg ${didSubmit ? 'bg-teal-50 text-teal-600' : 'bg-red-50 text-red-500'}`}>
                        {didSubmit ? '✅ Done' : '🔴 Pending'}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-4 font-medium">{m.total_calls}</td>
                  <td className="py-3 pr-4 font-medium">{m.total_visits}</td>
                  <td className="py-3 pr-4 font-medium">{m.total_followups}</td>
                  <td className="py-3 pr-4 font-medium">{m.total_leads}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-wep-border rounded-full max-w-[60px]">
                        <div className="h-full rounded-full bg-wep-accent" style={{ width: `${m.avg_rigor}%` }}/>
                      </div>
                      <span className={`text-xs font-bold ${rigorColor(m.avg_rigor)}`}>{m.avg_rigor}</span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
