import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { format } from 'date-fns'

const rigorColor = (s: number) =>
  s >= 80 ? 'text-wep-teal' : s >= 60 ? 'text-wep-amber' : s > 0 ? 'text-wep-red' : 'text-wep-muted'

const rigorBg = (s: number) =>
  s >= 80 ? 'bg-teal-50 border-teal-200' : s >= 60 ? 'bg-amber-50 border-amber-200' : s > 0 ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'

const emptyForm = { name: '', email: '', password: '', role: 'rep', bu: 'West' }

export default function Team() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const today = format(new Date(), 'yyyy-MM-dd')
  const [aiContent, setAiContent] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const canManageUsers = user?.role === 'manager' || user?.role === 'bu_head'
  const [showManage, setShowManage] = useState(false)
  const [showExited, setShowExited] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [formError, setFormError] = useState('')

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

  const viewTitle = user?.role === 'bu_head' ? '🏢 BU Head Dashboard' : user?.role === 'inside_sales' ? '📞 Inside Sales View' : '👥 Manager Dashboard'

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
          <div className="font-semibold text-sm text-wep-navy mb-4">Onboard a new member</div>
          <form
            onSubmit={e => { e.preventDefault(); createUser.mutate() }}
            className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-2"
          >
            <input className="form-input" placeholder="Full name" required
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <input className="form-input" type="email" placeholder="Email" required
              value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            <input className="form-input" type="text" placeholder="Temp password (min 8 chars)" required
              value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            <select className="form-input" value={form.role}
              onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
              <option value="rep">Rep</option>
              <option value="inside_sales">Inside Sales</option>
              <option value="manager">Manager</option>
              <option value="bu_head">BU Head</option>
            </select>
            <button type="submit" disabled={createUser.isPending} className="btn-primary">
              {createUser.isPending ? 'Adding...' : '+ Add Member'}
            </button>
          </form>
          {formError && <p className="text-red-500 text-sm mb-3">{formError}</p>}

          <label className="flex items-center gap-2 text-xs text-wep-muted mb-3">
            <input type="checkbox" checked={showExited} onChange={e => setShowExited(e.target.checked)} />
            Show exited members in the performance table below
          </label>

          <div className="space-y-2">
            {allUsers.map((u: any) => (
              <div key={u.id} className="flex items-center justify-between border-b border-wep-border/50 py-2 text-sm">
                <div>
                  <span className={`font-medium ${u.is_active ? 'text-wep-navy' : 'text-wep-muted line-through'}`}>{u.name}</span>
                  <span className="text-wep-muted ml-2 text-xs">{u.email} · {u.role.replace('_',' ')}</span>
                  {!u.is_active && <span className="ml-2 text-[10px] font-bold uppercase text-red-500">Exited</span>}
                </div>
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
