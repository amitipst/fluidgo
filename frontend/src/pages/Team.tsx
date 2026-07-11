import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api, { getErrorMessage } from '@/hooks/useApi'
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
  { key: 'service_delivery_manager', label: '🛠️ Service Delivery Manager', level: 20 },
  { key: 'regional_manager', label: '🗺️ Regional Manager',     level: 30 },
  { key: 'business_head', label: '🏭 Business Head',          level: 40 },
  { key: 'coo',           label: '🎯 COO',                     level: 45 },
  { key: 'hr',            label: '👥 HR',                     level: 25 },
  { key: 'finance',       label: '💰 Finance',                level: 25 },
  { key: 'ceo',           label: '👑 CEO',                    level: 50 },
  { key: 'super_admin',   label: '⚙️ Super Admin',            level: 99 },
]

// Team visibility tracks — each shows only its own roster + relevant metrics,
// instead of one flat list mixing Sales DSR numbers with Service Delivery
// ops numbers. Leadership/admin roles (regional_manager and up) sit outside
// all three tracks and always show in their own section.
interface Track { key: 'sales' | 'presales' | 'operations'; label: string; roles: string[] }
const TRACKS: Track[] = [
  { key: 'sales',      label: '💼 Sales',       roles: ['rep', 'inside_sales', 'manager'] },
  { key: 'presales',   label: '🔧 Pre-Sales',   roles: ['pre_sales'] },
  { key: 'operations', label: '🛠️ Operations',  roles: ['service_delivery_manager'] },
]
const LEADERSHIP_ROLES = ['regional_manager', 'bu_head', 'business_head', 'coo', 'hr', 'finance', 'ceo', 'super_admin']

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

// Single member row in the "Manage Team" list — shared between the
// Leadership section and whichever track's roster is active, so the two
// sections can't drift out of sync with each other.
function MemberRow({ u, allUsers, currentUserId, editingId, setEditingId, startEdit,
                      canManageTarget, setStatus, editForm, setEditForm,
                      assignableRoles, potentialManagers, updateUser, editError, saveEdit }: any) {
  return (
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
          {u.has_direct_reports && u.role !== 'manager' && (
            <span className="ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded-full"
              style={{ background: '#FDE8F0', color: '#F0115E' }}
              title={`Also personally manages ${u.direct_report_count} ${u.direct_report_count === 1 ? 'person' : 'people'} (dual role)`}>
              🎖️ Dual role · manages {u.direct_report_count}
            </span>
          )}
          {!u.is_active && <span className="ml-2 text-[10px] font-bold uppercase text-red-500">Exited</span>}
        </div>
        <div className="flex gap-2 shrink-0">
          {u.is_active && canManageTarget(u) && (
            <button
              onClick={() => editingId === u.id ? setEditingId(null) : startEdit(u)}
              className="text-xs font-semibold px-3 py-1 rounded-lg bg-wep-surface text-wep-navy hover:bg-wep-border/60"
            >
              {editingId === u.id ? 'Cancel' : '✏️ Edit'}
            </button>
          )}
          {canManageTarget(u) ? (
            <button
              disabled={setStatus.isPending || u.id === currentUserId}
              onClick={() => setStatus.mutate({ id: u.id, is_active: !u.is_active })}
              className={`text-xs font-semibold px-3 py-1 rounded-lg ${
                u.is_active ? 'bg-red-50 text-red-500 hover:bg-red-100' : 'bg-teal-50 text-teal-600 hover:bg-teal-100'
              } disabled:opacity-40`}
              title={u.id === currentUserId ? "You can't deactivate your own account" : undefined}
            >
              {u.is_active ? 'Deactivate' : 'Reactivate'}
            </button>
          ) : (
            <span className="text-[10px] text-wep-muted italic px-2 py-1" title="This account is at or above your role level">
              🔒 protected
            </span>
          )}
        </div>
      </div>

      {editingId === u.id && (
        <div className="mt-3 mb-1 bg-wep-surface rounded-xl p-3 grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="form-label block mb-1 text-[10px]">Role</label>
            <select className="form-input" value={editForm.role}
              onChange={(e: any) => setEditForm((f: any) => ({ ...f, role: e.target.value }))}>
              <option value={u.role}>{u.role.replace('_',' ')} (current)</option>
              {(assignableRoles.length ? assignableRoles : V3_ROLES)
                .filter((r: any) => r.key !== u.role)
                .map((r: any) => (<option key={r.key} value={r.key}>{r.label}</option>))}
            </select>
          </div>
          <div>
            <label className="form-label block mb-1 text-[10px]">Region / BU</label>
            <select className="form-input" value={editForm.region}
              onChange={(e: any) => setEditForm((f: any) => ({ ...f, region: e.target.value }))}>
              {REGIONS.map(r => (<option key={r.key} value={r.key}>{r.label}</option>))}
            </select>
          </div>
          <div>
            <label className="form-label block mb-1 text-[10px]">Reports to (Manager)</label>
            <select className="form-input" value={editForm.manager_id}
              onChange={(e: any) => setEditForm((f: any) => ({ ...f, manager_id: e.target.value }))}>
              <option value="">— No manager —</option>
              {potentialManagers.filter((m: any) => m.id !== u.id).map((m: any) => (
                <option key={m.id} value={m.id}>{m.name} ({m.role.replace('_',' ')})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label block mb-1 text-[10px]">Business</label>
            <select className="form-input" value={editForm.business}
              onChange={(e: any) => setEditForm((f: any) => ({ ...f, business: e.target.value }))}>
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
  )
}

export default function Team() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const today = format(new Date(), 'yyyy-MM-dd')
  const currentMonth = format(new Date(), 'yyyy-MM')
  const canManageUsers = ['manager','regional_manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const [activeTrack, setActiveTrack] = useState<typeof TRACKS[number]['key']>('sales')
  const [showManage, setShowManage] = useState(false)
  const [showExited, setShowExited] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [formError, setFormError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<{ role: string; region: string; business: string; manager_id: string }>({
    role: '', region: '', business: '', manager_id: ''
  })
  const [editError, setEditError] = useState('')

  const { data: teamData = [], isLoading } = useQuery({
    queryKey: ['team-analytics', showExited],
    queryFn: () => api.get(`/analytics/team${showExited ? '?include_inactive=true' : ''}`).then(r => r.data)
  })

  const { data: todayDSRs = [] } = useQuery({
    queryKey: ['team-dsr-today', today],
    queryFn: () => api.get(`/dsr/team?date=${today}`).then(r => r.data)
  })

  // Operations track — DOR month history, aggregated client-side per member.
  // Fetched whenever the actor can manage the team (not just on the
  // Operations tab), so switching tabs is instant, not a fresh loading spinner.
  const { data: dorTeamMonth = [] } = useQuery({
    queryKey: ['dor-team', currentMonth],
    queryFn: () => api.get(`/dor/team?month=${currentMonth}`).then(r => r.data),
    enabled: canManageUsers,
  })

  const { data: allUsers = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/users').then(r => r.data),
    enabled: canManageUsers && showManage
  })

  // Team AI insight — background + poll, same reliable pattern as the dashboard
  const { data: teamAI } = useQuery({
    queryKey: ['team-ai', user?.id],
    queryFn: () => api.get(`/ai/team/${user?.id}`).then(r => r.data),
    enabled: !!user?.id,
    refetchInterval: (q) => (q.state.data?.status === 'pending' ? 4000 : false),
  })
  const regenerateTeamAI = useMutation({
    mutationFn: () => api.post(`/ai/team/${user?.id}/regenerate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['team-ai', user?.id] }),
  })
  const aiStatus = teamAI?.status
  const aiPending = aiStatus === 'pending' || regenerateTeamAI.isPending

  // Get roles assignable by current actor
  const { data: assignableRoles = [] } = useQuery({
    queryKey: ['assignable-roles'],
    queryFn: () => api.get('/users/roles').then(r => r.data),
    enabled: canManageUsers
  })

  const createUser = useMutation({
    mutationFn: () => api.post('/users', form),
    onSuccess: () => {
      setForm(f => ({ ...emptyForm, role: f.role })); setFormError('')
      qc.invalidateQueries({ queryKey: ['users'] })
      qc.invalidateQueries({ queryKey: ['team-analytics'] })
    },
    onError: (err: any) => setFormError(getErrorMessage(err, 'Could not create user'))
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
    onError: (err: any) => setEditError(getErrorMessage(err, 'Could not update member'))
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

  function switchTrack(key: typeof TRACKS[number]['key']) {
    setActiveTrack(key)
    // Default the onboard form's role to this track's primary role, so
    // "Add Member" while on the Operations tab doesn't default to "Rep".
    const track = TRACKS.find(t => t.key === key)
    if (track) setForm(f => ({ ...f, role: track.roles[0] }))
  }

  // Anyone with role_level >= 20 (manager and above) can be assigned as a manager
  const potentialManagers = allUsers.filter((u: any) => u.role_level >= 20)

  // Own level, used to hide (not just block) Edit/Deactivate for equal-or-higher accounts —
  // matches the backend rule in update_user / set_user_status exactly.
  const myLevel = V3_ROLES.find(r => r.key === user?.role)?.level ?? 0
  const canManageTarget = (u: any) => u.id === user?.id || u.role_level < myLevel

  const submittedToday = new Set(todayDSRs.map((d: any) => d.user_id))
  const todayDORs = new Set(dorTeamMonth.filter((d: any) => d.date === today).map((d: any) => d.user_id))

  const track = TRACKS.find(t => t.key === activeTrack)!
  const isOpsTrack = activeTrack === 'operations'

  // Sales/PreSales matrix rows — straight filter of the DSR-based team data.
  const trackTeamData = teamData.filter((m: any) => track.roles.includes(m.role))

  // Operations matrix rows — DSR-based teamData still gives the ROSTER (so a
  // Service Delivery Manager who hasn't submitted a DOR yet still shows, at
  // zero), enriched with DOR-aggregated numbers instead of Sales metrics.
  const dorAgg: Record<string, any> = {}
  dorTeamMonth.forEach((d: any) => {
    if (!dorAgg[d.user_id]) {
      dorAgg[d.user_id] = { tickets_closed: 0, escalations_raised: 0, tickets_overdue: 0, client_meetings_held: 0 }
    }
    dorAgg[d.user_id].tickets_closed += d.tickets_closed || 0
    dorAgg[d.user_id].escalations_raised += d.escalations_raised || 0
    dorAgg[d.user_id].tickets_overdue += d.tickets_overdue || 0
    dorAgg[d.user_id].client_meetings_held += d.client_meetings_held || 0
  })
  const opsMatrixData = teamData
    .filter((m: any) => m.role === 'service_delivery_manager')
    .map((m: any) => ({
      ...m,
      ...(dorAgg[m.user_id] || { tickets_closed: 0, escalations_raised: 0, tickets_overdue: 0, client_meetings_held: 0 }),
    }))

  // Member-management list: leadership always visible (regardless of tab),
  // track roster filtered by the active tab.
  const leadershipUsers = allUsers.filter((u: any) => LEADERSHIP_ROLES.includes(u.role))
  const trackUsers = allUsers.filter((u: any) => track.roles.includes(u.role))

  const viewTitle = (user?.role === 'regional_manager' || user?.role === 'bu_head')
    ? `🗺️ Regional Manager — ${user?.region || user?.bu}`
    : user?.role === 'inside_sales'
      ? '📞 Inside Sales View'
      : user?.role === 'manager'
        ? `👥 Manager Dashboard — ${user?.region || user?.bu}`
        : '👥 Team Dashboard'

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">{viewTitle}</h1>
          <p className="text-wep-muted text-sm">
            {isOpsTrack
              ? `${today} · ${todayDORs.size}/${opsMatrixData.length} DORs submitted today`
              : `${today} · ${todayDSRs.filter((d: any) => trackTeamData.some((m: any) => m.user_id === d.user_id)).length}/${trackTeamData.length} DSRs submitted today`}
          </p>
        </div>
        <div className="flex gap-2">
          {canManageUsers && (
            <button onClick={() => setShowManage(v => !v)} className="btn-outline">
              {showManage ? 'Close' : '👤 Manage Team'}
            </button>
          )}
          <button onClick={() => regenerateTeamAI.mutate()} disabled={aiPending} className="btn-primary">
            {aiPending ? '⏳ Analysing...' : aiStatus === 'ready' ? '🔄 Regenerate Analysis' : '✨ AI Team Analysis'}
          </button>
        </div>
      </div>

      {/* Track tabs — Sales / Pre-Sales / Operations, each its own roster + metrics */}
      <div className="flex gap-2 mb-6">
        {TRACKS.map(t => (
          <button key={t.key} onClick={() => switchTrack(t.key)}
            className={`text-sm font-semibold px-4 py-2 rounded-xl border transition-colors ${
              activeTrack === t.key
                ? 'border-wep-accent bg-wep-accent/10 text-wep-accent'
                : 'border-wep-border text-wep-muted hover:bg-wep-surface'
            }`}>
            {t.label}
          </button>
        ))}
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
              <p className="text-[10px] text-wep-muted mt-0.5">Defaults to the {track.label} tab — change anytime</p>
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

          <div className="mb-4">
            <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted mb-1">Leadership &amp; Admin</div>
            <div className="space-y-2">
              {leadershipUsers.map((u: any) => (
                <MemberRow key={u.id} u={u} allUsers={allUsers} currentUserId={user?.id}
                  editingId={editingId} setEditingId={setEditingId} startEdit={startEdit}
                  canManageTarget={canManageTarget} setStatus={setStatus}
                  editForm={editForm} setEditForm={setEditForm}
                  assignableRoles={assignableRoles} potentialManagers={potentialManagers}
                  updateUser={updateUser} editError={editError} saveEdit={saveEdit} />
              ))}
            </div>
          </div>

          <div>
            <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted mb-1">{track.label}</div>
            <div className="space-y-2">
              {trackUsers.length === 0 ? (
                <p className="text-wep-muted text-sm py-3">No members in {track.label} yet.</p>
              ) : trackUsers.map((u: any) => (
                <MemberRow key={u.id} u={u} allUsers={allUsers} currentUserId={user?.id}
                  editingId={editingId} setEditingId={setEditingId} startEdit={startEdit}
                  canManageTarget={canManageTarget} setStatus={setStatus}
                  editForm={editForm} setEditForm={setEditForm}
                  assignableRoles={assignableRoles} potentialManagers={potentialManagers}
                  updateUser={updateUser} editError={editError} saveEdit={saveEdit} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Today's submission status — track-aware */}
      {isOpsTrack ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Team Size</div>
            <div className="font-display font-bold text-2xl text-wep-navy">{opsMatrixData.length}</div>
          </div>
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">DORs Today</div>
            <div className={`font-display font-bold text-2xl ${todayDORs.size === opsMatrixData.length ? 'text-wep-teal' : 'text-wep-amber'}`}>
              {todayDORs.size}/{opsMatrixData.length}
            </div>
          </div>
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Tickets Closed</div>
            <div className="font-display font-bold text-2xl text-wep-accent">
              {opsMatrixData.reduce((a: number, d: any) => a + d.tickets_closed, 0)}
            </div>
          </div>
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Escalations</div>
            <div className="font-display font-bold text-2xl text-wep-electric">
              {opsMatrixData.reduce((a: number, d: any) => a + d.escalations_raised, 0)}
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Team Size</div>
            <div className="font-display font-bold text-2xl text-wep-navy">{trackTeamData.length}</div>
          </div>
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">DSRs Today</div>
            <div className={`font-display font-bold text-2xl ${submittedToday.size === trackTeamData.length ? 'text-wep-teal' : 'text-wep-amber'}`}>
              {trackTeamData.filter((m: any) => submittedToday.has(m.user_id)).length}/{trackTeamData.length}
            </div>
          </div>
          <div className="card text-center">
            <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Avg Rigor</div>
            <div className="font-display font-bold text-2xl text-wep-accent">
              {trackTeamData.length ? Math.round(trackTeamData.reduce((a: number, d: any) => a + d.avg_rigor, 0) / trackTeamData.length) : '—'}
            </div>
          </div>
          {activeTrack === 'presales' ? (
            <div className="card text-center">
              <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Demos + POCs</div>
              <div className="font-display font-bold text-2xl text-wep-electric">
                {trackTeamData.reduce((a: number, d: any) => a + d.total_demos + d.total_pocs, 0)}
              </div>
            </div>
          ) : (
            <div className="card text-center">
              <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Total Leads</div>
              <div className="font-display font-bold text-2xl text-wep-electric">
                {trackTeamData.reduce((a: number, d: any) => a + d.total_leads, 0)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI panel — analyses the whole team across all tracks, not scoped to
          the active tab yet (a track-aware version is a natural next step) */}
      {(aiStatus || aiPending) && (
        <div className="ai-panel mb-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 bg-wep-electric/20 border border-wep-electric/30 text-wep-electric text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-wep-electric animate-pulse inline-block"/>AI Team Intelligence
            </span>
            {aiStatus === 'ready' && teamAI?.generated_at && (
              <span className="text-[11px] text-white/35">
                · Generated {Math.max(1, Math.round((Date.now() - new Date(teamAI.generated_at).getTime())/60000))}m ago
              </span>
            )}
          </div>
          {aiPending ? (
            <div className="flex items-center gap-2 text-white/60 text-sm">
              <span className="flex gap-1">{[0,1,2].map(i=>(
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-wep-electric animate-bounce" style={{animationDelay:`${i*0.15}s`}}/>
              ))}</span>
              Generating team analysis on the local model — takes about 2-3 minutes.
              It saves automatically and appears here when ready; no need to wait.
            </div>
          ) : aiStatus === 'failed' ? (
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-red-300">
              ⚠️ Last attempt didn't complete. Click "Regenerate Analysis" to try again.
            </div>
          ) : aiStatus === 'ready' && teamAI?.content ? (
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-white/85 leading-relaxed whitespace-pre-wrap"
              dangerouslySetInnerHTML={{__html: teamAI.content.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br/>')}}/>
          ) : null}
        </div>
      )}

      {/* Team matrix — Sales/PreSales (DSR-based) or Operations (DOR-based) */}
      {isOpsTrack ? (
        <div className="card overflow-x-auto">
          <div className="font-semibold text-sm text-wep-navy mb-4">Operations Performance Matrix — {currentMonth}</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-wep-border">
                {['Member','DOR Today','Tickets Closed','Overdue (>3d)','Escalations','Client Meetings'].map(h => (
                  <th key={h} className="text-left text-[10px] font-bold uppercase tracking-wide text-wep-muted py-2 pr-4 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={6} className="py-8 text-center text-wep-muted">Loading...</td></tr>
              ) : opsMatrixData.length === 0 ? (
                <tr><td colSpan={6} className="py-8 text-center text-wep-muted">No Service Delivery Managers in scope yet.</td></tr>
              ) : opsMatrixData.map((m: any) => {
                const didSubmit = todayDORs.has(m.user_id)
                return (
                  <tr key={m.user_id} className={`border-b border-wep-border/50 hover:bg-wep-surface transition-colors ${m.is_active === false ? 'opacity-50' : ''}`}>
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-wep-accent to-wep-electric flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                          {m.name.split(' ').map((n: string) => n[0]).join('').slice(0,2)}
                        </div>
                        <div className="font-medium text-wep-navy">{m.name}</div>
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
                    <td className="py-3 pr-4 font-medium">{m.tickets_closed}</td>
                    <td className="py-3 pr-4 font-medium" style={{ color: m.tickets_overdue > 0 ? '#DC2626' : undefined }}>{m.tickets_overdue}</td>
                    <td className="py-3 pr-4 font-medium" style={{ color: m.escalations_raised > 0 ? '#D97706' : undefined }}>{m.escalations_raised}</td>
                    <td className="py-3 pr-4 font-medium">{m.client_meetings_held}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
      <div className="card overflow-x-auto">
        <div className="font-semibold text-sm text-wep-navy mb-4">{track.label} Performance Matrix</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-wep-border">
              {(activeTrack === 'presales'
                ? ['Rep','DSR Today','Demos','POCs','Proposals/Solutions','Tech Discussions','Avg Rigor']
                : ['Rep','DSR Today','Calls','Visits','Follow-Ups','Leads','Avg Rigor']
              ).map(h => (
                <th key={h} className="text-left text-[10px] font-bold uppercase tracking-wide text-wep-muted py-2 pr-4 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={7} className="py-8 text-center text-wep-muted">Loading...</td></tr>
            ) : trackTeamData.length === 0 ? (
              <tr><td colSpan={7} className="py-8 text-center text-wep-muted">No members in {track.label} yet.</td></tr>
            ) : trackTeamData.map((m: any) => {
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
                  {activeTrack === 'presales' ? (
                    <>
                      <td className="py-3 pr-4 font-medium">{m.total_demos}</td>
                      <td className="py-3 pr-4 font-medium">{m.total_pocs}</td>
                      <td className="py-3 pr-4 font-medium">{m.total_proposals_supported}</td>
                      <td className="py-3 pr-4 font-medium">{m.total_tech_discussions}</td>
                    </>
                  ) : (
                    <>
                      <td className="py-3 pr-4 font-medium">{m.total_calls}</td>
                      <td className="py-3 pr-4 font-medium">{m.total_visits}</td>
                      <td className="py-3 pr-4 font-medium">{m.total_followups}</td>
                      <td className="py-3 pr-4 font-medium">{m.total_leads}</td>
                    </>
                  )}
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
      )}
    </div>
  )
}
