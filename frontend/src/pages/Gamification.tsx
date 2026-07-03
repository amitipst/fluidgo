import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import api from '@/hooks/useApi'
import { format } from 'date-fns'

// ── Helpers ───────────────────────────────────────────────────────────────────
const today = new Date()
const currentPeriod = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`

const METRIC_LABELS: Record<string,string> = {
  calls: '📞 Total Calls', visits: '🏢 Customer Visits',
  new_leads: '🎯 New Leads', proposals: '📄 Proposals Sent',
  followups: '🔄 Follow-Ups', rigor_avg: '⚡ Avg Rigor Score',
  bant_meetings: '🧠 BANT-Qualified Meetings', closed_won_value: '💰 Closed Won Value (₹)',
}
const REWARD_LABELS: Record<string,string> = {
  cash: '💵 Cash Bonus', points: '🏅 Points', badge: '🎖 Badge', recognition: '🌟 Recognition',
}

// ── Progress bar ──────────────────────────────────────────────────────────────
function ProgressBar({ pct, achieved }: { pct: number; achieved: boolean }) {
  return (
    <div className="h-2 bg-wep-border rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-700"
        style={{
          width: `${Math.min(pct, 100)}%`,
          background: achieved
            ? 'linear-gradient(90deg, #059669, #0D9488)'
            : pct >= 75
              ? 'linear-gradient(90deg, #D97706, #F59E0B)'
              : 'linear-gradient(90deg, #1E6FD9, #0EA5E9)'
        }} />
    </div>
  )
}

// ── Scheme card ───────────────────────────────────────────────────────────────
function SchemeCard({ scheme, onPause, canManage }: {
  scheme: any; onPause?: (id:string) => void; canManage?: boolean
}) {
  return (
    <div className={`card group hover:border-wep-border-strong transition-all ${
      scheme.status === 'closed' ? 'opacity-50' : ''}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="font-bold text-wep-navy text-sm">{scheme.name}</div>
          {scheme.description && (
            <div className="text-xs text-wep-muted mt-0.5 leading-relaxed">{scheme.description}</div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
            scheme.status === 'active'
              ? 'bg-emerald-50 text-emerald-700'
              : scheme.status === 'paused'
                ? 'bg-amber-50 text-amber-700'
                : 'bg-gray-100 text-gray-500'
          }`}>{scheme.status.toUpperCase()}</span>
          {canManage && scheme.status === 'active' && onPause && (
            <button onClick={() => onPause(scheme.id)}
              className="text-[10px] text-wep-muted hover:text-wep-orange transition-colors">
              Pause
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs mb-3">
        <div>
          <div className="text-wep-muted mb-0.5">Target</div>
          <div className="font-semibold text-wep-navy">
            {METRIC_LABELS[scheme.metric] ?? scheme.metric}
            {' ≥ '}
            {scheme.metric === 'closed_won_value'
              ? `₹${Number(scheme.target_value).toLocaleString('en-IN')}`
              : scheme.target_value}
          </div>
        </div>
        <div>
          <div className="text-wep-muted mb-0.5">Reward</div>
          <div className="font-semibold text-wep-navy">
            {REWARD_LABELS[scheme.reward_type] ?? scheme.reward_type}
            {scheme.reward_value ? ` · ${scheme.reward_type === 'cash' ? '₹' : ''}${scheme.reward_value}` : ''}
            {scheme.reward_badge ? ` · ${scheme.reward_badge}` : ''}
          </div>
        </div>
      </div>

      {/* Progress if available (from my-progress) */}
      {scheme.current_value !== undefined && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-wep-muted">Progress</span>
            <span className={`font-bold ${scheme.achieved ? 'text-wep-teal' : 'text-wep-accent'}`}>
              {scheme.achieved ? '🏆 Achieved!' : `${scheme.progress_pct?.toFixed(0)}%`}
            </span>
          </div>
          <ProgressBar pct={scheme.progress_pct} achieved={scheme.achieved} />
          <div className="text-xs text-wep-muted mt-1">
            {scheme.metric === 'closed_won_value'
              ? `₹${Number(scheme.current_value).toLocaleString('en-IN')} of ₹${Number(scheme.target_value).toLocaleString('en-IN')}`
              : `${scheme.current_value?.toFixed(scheme.metric.includes('avg') ? 1 : 0)} of ${scheme.target_value}`}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Create scheme form ────────────────────────────────────────────────────────
function CreateSchemeForm({ period, onCreated }: { period: string; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: '', description: '', period, scope: 'bu',
    metric: 'calls', target_value: 0,
    reward_type: 'points', reward_value: '', reward_badge: ''
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      await api.post('/incentives/schemes', {
        ...form, period,
        target_value: Number(form.target_value),
        reward_value: form.reward_value ? Number(form.reward_value) : undefined,
        reward_badge: form.reward_badge || undefined,
      })
      onCreated()
      setForm({ name:'', description:'', period, scope:'bu',
                metric:'calls', target_value:0, reward_type:'points',
                reward_value:'', reward_badge:'' })
    } catch (e: any) {
      setErr(e?.response?.data?.detail ?? 'Failed to create scheme')
    } finally { setLoading(false) }
  }

  return (
    <form onSubmit={submit} className="card space-y-4">
      <div className="font-bold text-wep-navy text-sm">➕ New Incentive Scheme</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <label className="form-label block mb-1">Scheme Name *</label>
          <input className="form-input" placeholder="e.g. July Calls Blitz 🔥" required
            value={form.name} onChange={e => setForm(f=>({...f,name:e.target.value}))} />
        </div>
        <div className="md:col-span-2">
          <label className="form-label block mb-1">Description</label>
          <textarea rows={2} className="form-input resize-none"
            placeholder="What does the rep need to do?"
            value={form.description} onChange={e => setForm(f=>({...f,description:e.target.value}))} />
        </div>
        <div>
          <label className="form-label block mb-1">Metric to Measure *</label>
          <select className="form-input" value={form.metric}
            onChange={e => setForm(f=>({...f,metric:e.target.value}))}>
            {Object.entries(METRIC_LABELS).map(([k,v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label block mb-1">Target Value *</label>
          <input type="number" className="form-input" min="0" step="any" required
            value={form.target_value} onChange={e => setForm(f=>({...f,target_value:+e.target.value}))} />
        </div>
        <div>
          <label className="form-label block mb-1">Reward Type *</label>
          <select className="form-input" value={form.reward_type}
            onChange={e => setForm(f=>({...f,reward_type:e.target.value}))}>
            {Object.entries(REWARD_LABELS).map(([k,v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label block mb-1">
            {form.reward_type === 'badge' ? 'Badge Key' : form.reward_type === 'cash' ? '₹ Amount' : 'Points'}
          </label>
          {form.reward_type === 'badge' ? (
            <select className="form-input" value={form.reward_badge}
              onChange={e => setForm(f=>({...f,reward_badge:e.target.value}))}>
              <option value="">Select badge</option>
              {['hat_trick','first_deal','streak_5','streak_10','lead_machine',
                'bant_master','consistent','deal_king','rigor_champ','top_caller'].map(b => (
                <option key={b} value={b}>{b.replace('_',' ')}</option>
              ))}
            </select>
          ) : (
            <input type="number" className="form-input" min="0"
              placeholder={form.reward_type === 'cash' ? '5000' : '100'}
              value={form.reward_value} onChange={e => setForm(f=>({...f,reward_value:e.target.value}))} />
          )}
        </div>
        <div>
          <label className="form-label block mb-1">Scope</label>
          <select className="form-input" value={form.scope}
            onChange={e => setForm(f=>({...f,scope:e.target.value}))}>
            <option value="bu">Whole BU</option>
            <option value="team">My Team Only</option>
          </select>
        </div>
      </div>
      {err && <p className="text-xs text-red-500">{err}</p>}
      <button type="submit" disabled={loading} className="btn-primary">
        {loading ? '⏳ Creating…' : '✅ Create Scheme'}
      </button>
    </form>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Gamification() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [period, setPeriod] = useState(currentPeriod)
  const [showCreate, setShowCreate] = useState(false)

  const isManager = ['manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const isRep = !isManager

  const { data: schemes = [] } = useQuery({
    queryKey: ['schemes', period],
    queryFn: () => api.get(`/incentives/schemes?period=${period}`).then(r => r.data),
  })

  const { data: progress } = useQuery({
    queryKey: ['my-progress', period],
    queryFn: () => api.get(`/incentives/my-progress?period=${period}`).then(r => r.data),
    enabled: isRep,
  })

  const { data: leaderboard = [] } = useQuery({
    queryKey: ['leaderboard', period],
    queryFn: () => api.get(`/incentives/leaderboard?period=${period}`).then(r => r.data),
  })

  const pauseScheme = useMutation({
    mutationFn: (id: string) => api.patch(`/incentives/schemes/${id}`, { status: 'paused' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schemes'] }),
  })

  const managerSchemes = isManager ? schemes : progress?.schemes ?? []

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="page-header">
        <div>
          <div className="page-title">🎮 Incentives & Gamification</div>
          <div className="page-sub">Special schemes · Points · Badges · Leaderboard</div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input type="month" className="form-input py-2 text-sm w-40"
            value={period} onChange={e => setPeriod(e.target.value)} />
          {isManager && (
            <button onClick={() => setShowCreate(v=>!v)} className="btn-primary">
              {showCreate ? '✕ Cancel' : '➕ New Scheme'}
            </button>
          )}
        </div>
      </div>

      {/* Create form */}
      {showCreate && isManager && (
        <div className="mb-6">
          <CreateSchemeForm period={period} onCreated={() => {
            setShowCreate(false)
            qc.invalidateQueries({ queryKey: ['schemes'] })
          }} />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* Left: Schemes / My Progress */}
        <div className="md:col-span-2 space-y-4">
          <div className="font-bold text-wep-navy text-sm">
            {isRep ? '🎯 My Progress' : '📋 Active Schemes'} — {period}
          </div>

          {isRep && progress && (
            <>
              {/* Rep points summary */}
              <div className="card flex items-center gap-4"
                style={{ background: 'linear-gradient(135deg, #0B1F3A, #1E4D8C)' }}>
                <div className="text-center">
                  <div className="font-display font-black text-3xl text-white">{progress.points}</div>
                  <div className="text-xs text-white/50 mt-0.5">Total Points</div>
                </div>
                <div className="w-px h-10 bg-white/20" />
                <div className="flex flex-wrap gap-1.5">
                  {progress.badges?.length ? progress.badges.map((b:any) => (
                    <span key={b.key} className="text-xs font-bold px-2 py-1 rounded-full"
                      style={{ background: 'rgba(255,255,255,0.12)', color: '#F5921E' }}>
                      {b.name}
                    </span>
                  )) : <span className="text-xs text-white/40">No badges yet — keep going!</span>}
                </div>
              </div>

              {/* Scheme progress */}
              {progress.schemes?.map((s: any) => (
                <SchemeCard key={s.id} scheme={s} />
              ))}
              {!progress.schemes?.length && (
                <div className="card text-center py-10 text-wep-muted text-sm">
                  No active schemes for {period}.
                </div>
              )}
            </>
          )}

          {isManager && (
            <>
              {managerSchemes.map((s: any) => (
                <SchemeCard key={s.id} scheme={s} canManage
                  onPause={id => pauseScheme.mutate(id)} />
              ))}
              {!managerSchemes.length && (
                <div className="card text-center py-10">
                  <div className="text-4xl mb-3">🎯</div>
                  <p className="text-wep-muted text-sm mb-4">No schemes for {period} yet.</p>
                  <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
                    Create First Scheme
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Right: Leaderboard */}
        <div>
          <div className="font-bold text-wep-navy text-sm mb-3">🏆 Leaderboard</div>
          <div className="card p-0 overflow-hidden">
            {leaderboard.length === 0 ? (
              <div className="p-6 text-center text-wep-muted text-sm">
                No points earned yet in {period}.
              </div>
            ) : leaderboard.map((entry: any, idx: number) => {
              const rankColors = ['#E8632A','#6B7A99','#8B6914']
              const rankEmoji  = ['🥇','🥈','🥉']
              return (
                <div key={entry.user_id}
                  className={`flex items-center gap-3 px-4 py-3 border-b border-wep-border/50 last:border-0
                    ${user?.id === entry.user_id ? 'bg-wep-orange-lt' : 'hover:bg-wep-surface'} transition-colors`}>
                  <div className="w-7 text-center font-bold text-sm"
                    style={{ color: idx < 3 ? rankColors[idx] : '#8FA3BF' }}>
                    {idx < 3 ? rankEmoji[idx] : idx + 1}
                  </div>
                  <div className="w-8 h-8 rounded-xl flex items-center justify-center text-[11px] font-bold text-white shrink-0"
                    style={{ background: idx === 0 ? '#E8632A' : 'linear-gradient(135deg,#1E6FD9,#0EA5E9)' }}>
                    {entry.name.split(' ').map((n:string)=>n[0]).join('').slice(0,2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-semibold truncate ${
                      user?.id === entry.user_id ? 'text-wep-orange' : 'text-wep-navy'}`}>
                      {entry.name} {user?.id === entry.user_id && '(you)'}
                    </div>
                    {entry.badges?.length > 0 && (
                      <div className="text-xs text-wep-muted truncate">
                        {entry.badges.map((b:any)=>b.name).join(' · ')}
                      </div>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-display font-bold text-sm text-wep-navy">{entry.points}</div>
                    <div className="text-[10px] text-wep-muted">pts</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
