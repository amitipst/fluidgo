import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// ── Helpers ──────────────────────────────────────────────────────────────────
const today = new Date()
// Default to PREVIOUS month — current month scores can't be frozen yet
const defaultPeriod = (() => {
  const d = new Date(today.getFullYear(), today.getMonth() - 1, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2,'0')}`
})()

const STATUS_CFG: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  pending_manager: { label: 'Awaiting Manager', dot: '#D97706', bg: '#FFFBEB', text: '#92400E' },
  pending_hr:      { label: 'Awaiting HR',      dot: '#1E6FD9', bg: '#EFF6FF', text: '#1E40AF' },
  pending_vp:      { label: 'Awaiting VP',      dot: '#7C3AED', bg: '#F5F3FF', text: '#4C1D95' },
  approved:        { label: 'Approved',          dot: '#059669', bg: '#ECFDF5', text: '#064E3B' },
  disputed:        { label: 'Disputed',          dot: '#DC2626', bg: '#FEF2F2', text: '#7F1D1D' },
}

// Which endpoint does the current user hit?
function getReviewEndpoint(resultId: string, status: string): string {
  if (status === 'pending_manager') return `/fga/${resultId}/manager-review`
  if (status === 'pending_hr')      return `/fga/${resultId}/hr-review`
  if (status === 'pending_vp')      return `/fga/${resultId}/vp-approve`
  return ''
}

// What actions can this status accept?
function getActionOptions(status: string) {
  if (status === 'pending_hr') {
    return [
      { val: 'approve',  label: '✅ Approve & forward to VP' },
      { val: 'override', label: '✏️ Override score (HR adjustment)' },
      { val: 'dispute',  label: '🔴 Dispute — send back' },
    ]
  }
  if (status === 'pending_vp') {
    return [
      { val: 'approve',  label: '✅ Final Approval' },
      { val: 'dispute',  label: '🔴 Reject — send back' },
    ]
  }
  // pending_manager (default)
  return [
    { val: 'approve',  label: '✅ Approve & forward to HR' },
    { val: 'dispute',  label: '🔴 Dispute — flag for review' },
  ]
}

// ── Score bar ─────────────────────────────────────────────────────────────────
function ScoreBar({ score, max = 100, size = 'md' }: { score: number; max?: number; size?: 'sm'|'md'|'lg' }) {
  const pct = Math.min((score / max) * 100, 100)
  const color = score >= 80 ? '#059669' : score >= 60 ? '#D97706' : score >= 40 ? '#1E6FD9' : '#DC2626'
  const h = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3' : 'h-2'
  return (
    <div className="flex items-center gap-3">
      <div className={`flex-1 ${h} rounded-full overflow-hidden`} style={{ background: '#E2EAF4' }}>
        <div className={`${h} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-sm font-bold w-10 text-right tabular-nums" style={{ color }}>
        {score.toFixed(1)}
      </span>
    </div>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CFG[status] ?? { label: status, dot: '#8FA3BF', bg: '#F0F4F8', text: '#5A6880' }
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-full border"
      style={{ background: cfg.bg, color: cfg.text, borderColor: cfg.dot + '40' }}>
      <span className="w-1.5 h-1.5 rounded-full inline-block shrink-0" style={{ background: cfg.dot }} />
      {cfg.label}
    </span>
  )
}

// ── Breakdown rows ────────────────────────────────────────────────────────────
function Breakdown({ breakdown }: { breakdown: any[] }) {
  if (!breakdown?.length) return <p className="text-xs text-wep-muted italic">No breakdown available</p>
  return (
    <div className="space-y-2 mt-3">
      {breakdown.map((b: any) => (
        <div key={b.name} className="flex items-center gap-3 text-xs">
          <span className="text-wep-muted flex-1 truncate">{b.name}</span>
          <span className="text-wep-muted tabular-nums shrink-0">
            {b.weight_pct}% × <span className="text-wep-text font-medium">{b.value?.toFixed(1)}</span>
          </span>
          <span className="font-bold text-wep-navy tabular-nums w-10 text-right shrink-0">
            {b.contribution?.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Review modal ──────────────────────────────────────────────────────────────
function ReviewModal({ result, onClose, onDone }: {
  result: any; onClose: () => void; onDone: () => void
}) {
  const [action, setAction] = useState<string>('approve')
  const [comment, setComment] = useState('')
  const [overrideScore, setOverrideScore] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const endpoint   = getReviewEndpoint(result.result_id, result.approval_status)
  const options    = getActionOptions(result.approval_status)
  const effectiveScore = result.override_score ?? result.score

  async function submit() {
    if (!endpoint) { setErr('This record cannot be actioned in its current state.'); return }
    if (action === 'dispute' && !comment.trim()) { setErr('A comment is required when disputing.'); return }
    setLoading(true); setErr('')
    try {
      await api.post(endpoint, {
        action,
        comment: comment.trim() || undefined,
        override_score: action === 'override' && overrideScore ? parseFloat(overrideScore) : undefined
      })
      onDone(); onClose()
    } catch (e: any) {
      setErr(e?.response?.data?.detail ?? 'Action failed. Please try again.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(11,31,58,0.55)', backdropFilter: 'blur(4px)' }}>
      <div className="bg-white rounded-3xl shadow-card-lg w-full max-w-md overflow-hidden">

        {/* Header */}
        <div className="px-6 py-5 flex items-start justify-between"
          style={{ background: 'linear-gradient(135deg, #0B1F3A 0%, #1E4D8C 100%)' }}>
          <div>
            <div className="font-display font-bold text-white text-lg leading-tight">{result.name}</div>
            <div className="text-sm mt-0.5 font-medium capitalize"
              style={{ color: 'rgba(255,255,255,0.55)' }}>
              {result.role?.replace('_',' ')} · {result.bu} · {result.period}
            </div>
            <div className="mt-2"><StatusBadge status={result.approval_status} /></div>
          </div>
          <button onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 transition-colors text-lg">
            ✕
          </button>
        </div>

        {/* Score section */}
        <div className="px-6 py-4 border-b border-wep-border">
          <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">FGA Score</div>
          <ScoreBar score={effectiveScore} size="lg" />
          {result.override_score != null && (
            <div className="text-xs text-amber-600 mt-1.5 font-medium">
              ✏️ Overridden from {result.score.toFixed(1)} → {result.override_score.toFixed(1)}
            </div>
          )}
          <Breakdown breakdown={result.breakdown} />
        </div>

        {/* Action section */}
        <div className="px-6 py-4 space-y-4">
          <div>
            <div className="form-label mb-2">Action</div>
            <div className="space-y-2">
              {options.map(o => (
                <label key={o.val}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all text-sm font-medium
                    ${action === o.val
                      ? 'border-wep-orange bg-wep-orange-lt text-wep-orange'
                      : 'border-wep-border text-wep-muted hover:border-wep-border-strong hover:text-wep-text'}`}>
                  <input type="radio" name="fga-action" value={o.val}
                    checked={action === o.val}
                    onChange={() => { setAction(o.val); setErr('') }}
                    className="hidden" />
                  <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-all
                    ${action === o.val ? 'border-wep-orange' : 'border-wep-border'}`}>
                    {action === o.val && (
                      <span className="w-2 h-2 rounded-full" style={{ background: '#E8632A' }} />
                    )}
                  </span>
                  {o.label}
                </label>
              ))}
            </div>
          </div>

          {action === 'override' && (
            <div>
              <label className="form-label block mb-1.5">Override Score (0–100)</label>
              <input type="number" min="0" max="100" step="0.1"
                className="form-input" placeholder="e.g. 68.5"
                value={overrideScore} onChange={e => setOverrideScore(e.target.value)} />
            </div>
          )}

          <div>
            <label className="form-label block mb-1.5">
              Comment {action === 'dispute' ? <span className="text-red-500 normal-case font-normal">(required)</span> : '(optional)'}
            </label>
            <textarea rows={3} className="form-input resize-none"
              placeholder={action === 'dispute' ? 'Explain the reason for dispute...' : 'Add context or notes...'}
              value={comment} onChange={e => { setComment(e.target.value); setErr('') }} />
          </div>

          {err && (
            <div className="text-sm px-3 py-2.5 rounded-xl font-medium"
              style={{ background: '#FEF2F2', color: '#DC2626', border: '1px solid rgba(220,38,38,0.20)' }}>
              ⚠️ {err}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-wep-border flex gap-3 justify-end">
          <button onClick={onClose} className="btn-outline">Cancel</button>
          <button onClick={submit}
            disabled={loading || !endpoint || (action === 'dispute' && !comment.trim())}
            className="btn-primary disabled:opacity-50">
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="flex gap-0.5">
                  {[0,1,2].map(i => (
                    <span key={i} className="w-1 h-1 rounded-full bg-white/70 animate-bounce"
                      style={{ animationDelay: `${i*0.12}s` }} />
                  ))}
                </span>
                Submitting...
              </span>
            ) : 'Submit Review'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Summary stat card ─────────────────────────────────────────────────────────
function SummaryCard({ count, status }: { count: number; status: string }) {
  const cfg = STATUS_CFG[status] ?? { label: status, dot: '#8FA3BF', bg: '#F0F4F8', text: '#5A6880' }
  return (
    <div className="card text-center">
      <div className="font-display font-black text-3xl mb-1" style={{ color: cfg.dot }}>{count}</div>
      <div className="text-[11px] font-semibold" style={{ color: cfg.text }}>{cfg.label}</div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function FGAApproval() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [period, setPeriod] = useState(defaultPeriod)
  const [selected, setSelected] = useState<any>(null)
  const [freezing, setFreezing] = useState(false)
  const [freezeMsg, setFreezeMsg] = useState('')

  // business_head == practice_head (whole business); regional_manager (formerly
  // mislabeled 'bu_head') is a distinct, region-scoped tier — see BU_LEVEL_ROLES
  // in the backend fga_approval.py router.
  const BU_LEVEL  = ['regional_manager','bu_head','business_head','practice_head','ceo','super_admin']
  const isBUHead  = BU_LEVEL.includes(user?.role ?? '')
  const isManager = ['manager', ...BU_LEVEL].includes(user?.role ?? '')

  const { data: pending = [], isLoading, refetch } = useQuery({
    queryKey: ['fga-pending', period],
    queryFn: () => api.get(`/fga/pending?period=${period}`).then(r => r.data),
    enabled: isManager,
  })

  // Group by status
  const byStatus = (status: string) => (pending as any[]).filter(r => r.approval_status === status)
  const actionable = (pending as any[]).filter(r =>
    ['pending_manager','pending_hr','pending_vp','disputed'].includes(r.approval_status)
  )

  async function freezePeriod() {
    setFreezing(true); setFreezeMsg('')
    try {
      const res = await api.post('/fga/freeze', { period })
      setFreezeMsg(`✅ ${res.data.frozen} scores frozen for ${period}`)
      refetch()
    } catch (e: any) {
      setFreezeMsg(`❌ ${e?.response?.data?.detail ?? 'Freeze failed'}`)
    } finally { setFreezing(false) }
  }

  async function downloadCSV() {
    try {
      const res = await api.get(`/fga/export?period=${period}`, { responseType: 'blob' })
      const url  = URL.createObjectURL(new Blob([res.data as any], { type: 'text/csv' }))
      const link = document.createElement('a')
      link.href = url; link.download = `fga_approved_${period}.csv`
      link.click(); URL.revokeObjectURL(url)
    } catch { alert('No approved scores to export for this period.') }
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <div className="page-title">🏆 FGA Approval Workflow</div>
          <div className="page-sub">
            Field Growth Assessment · Manager → HR → VP → Finance export
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input type="month" className="form-input py-2 text-sm w-40"
            value={period} onChange={e => { setPeriod(e.target.value); setFreezeMsg('') }} />
          {isBUHead && (
            <button onClick={freezePeriod} disabled={freezing} className="btn-outline">
              {freezing ? '⏳ Freezing…' : '❄️ Freeze Period'}
            </button>
          )}
          <button onClick={downloadCSV} className="btn-blue">⬇️ Export CSV</button>
        </div>
      </div>

      {freezeMsg && (
        <div className="mb-4 px-4 py-3 rounded-xl text-sm font-medium"
          style={{
            background: freezeMsg.startsWith('✅') ? '#ECFDF5' : '#FEF2F2',
            color: freezeMsg.startsWith('✅') ? '#064E3B' : '#7F1D1D',
            border: `1px solid ${freezeMsg.startsWith('✅') ? '#A7F3D0' : '#FECACA'}`,
          }}>
          {freezeMsg}
        </div>
      )}

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {Object.keys(STATUS_CFG).map(status => (
          <SummaryCard key={status} status={status} count={byStatus(status).length} />
        ))}
      </div>

      {/* ── Actionable queue ── */}
      {actionable.length > 0 && (
        <div className="card mb-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#E8632A' }} />
            <div className="font-bold text-wep-navy text-sm">Requires Your Action ({actionable.length})</div>
          </div>
          <div className="space-y-3">
            {actionable.map((r: any) => (
              <div key={r.result_id}
                className="flex items-center gap-4 p-4 rounded-xl border border-wep-border hover:border-wep-border-strong transition-all group">
                {/* Avatar */}
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold text-white shrink-0"
                  style={{ background: 'linear-gradient(135deg, #1E6FD9 0%, #0EA5E9 100%)' }}>
                  {r.name.split(' ').map((n:string) => n[0]).join('').slice(0,2)}
                </div>
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-wep-navy text-sm">{r.name}</div>
                  <div className="text-xs text-wep-muted capitalize">{r.role?.replace('_',' ')} · {r.bu}</div>
                </div>
                {/* Score */}
                <div className="w-32 hidden md:block">
                  <ScoreBar score={r.override_score ?? r.score} size="sm" />
                </div>
                {/* Status + action */}
                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={r.approval_status} />
                  <button onClick={() => setSelected(r)} className="btn-primary text-xs py-1.5 px-3">
                    Review
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Full table ── */}
      <div className="card overflow-x-auto">
        <div className="font-bold text-wep-navy text-sm mb-4">All Scores — {period}</div>

        {isLoading ? (
          <div className="space-y-2 py-4">
            {[1,2,3].map(i => <div key={i} className="skeleton h-10 w-full" />)}
          </div>
        ) : (pending as any[]).length === 0 ? (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">📊</div>
            <p className="font-semibold text-wep-navy mb-1">No scores for {period}</p>
            <p className="text-wep-muted text-sm mb-6">
              Freeze the period first to compute and lock FGA scores for all active reps.
            </p>
            {isBUHead && (
              <button onClick={freezePeriod} disabled={freezing} className="btn-primary">
                {freezing ? '⏳ Computing…' : '❄️ Freeze & Compute Scores'}
              </button>
            )}
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th><th>Role</th><th>FGA Score</th>
                <th className="hidden md:table-cell">Breakdown</th>
                <th>Status</th>
                <th className="hidden md:table-cell">Comments</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(pending as any[]).map((r: any) => (
                <tr key={r.result_id}>
                  <td>
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-xl flex items-center justify-center text-[11px] font-bold text-white shrink-0"
                        style={{ background: 'linear-gradient(135deg, #1E6FD9,#0EA5E9)' }}>
                        {r.name.split(' ').map((n:string) => n[0]).join('').slice(0,2)}
                      </div>
                      <div>
                        <div className="font-semibold text-wep-navy text-sm">{r.name}</div>
                        <div className="text-xs text-wep-muted">{r.bu}</div>
                      </div>
                    </div>
                  </td>
                  <td className="capitalize text-wep-muted text-xs">
                    {r.role?.replace('_',' ')}
                  </td>
                  <td className="w-36">
                    <ScoreBar score={r.override_score ?? r.score} size="sm" />
                    {r.override_score != null && (
                      <div className="text-[10px] text-amber-600 mt-0.5">
                        Override from {r.score.toFixed(1)}
                      </div>
                    )}
                  </td>
                  <td className="hidden md:table-cell text-xs text-wep-muted max-w-[200px]">
                    {r.breakdown?.map((b:any) => `${b.name}: ${b.contribution?.toFixed(1)}`).join(' · ')}
                  </td>
                  <td><StatusBadge status={r.approval_status} /></td>
                  <td className="hidden md:table-cell text-xs text-wep-muted max-w-[160px] truncate">
                    {[r.manager_comment, r.hr_comment, r.vp_comment].filter(Boolean).join(' · ') || '—'}
                  </td>
                  <td>
                    {['pending_manager','pending_hr','pending_vp','disputed'].includes(r.approval_status) && isManager ? (
                      <button onClick={() => setSelected(r)}
                        className="text-xs font-semibold text-wep-orange hover:underline">
                        Review →
                      </button>
                    ) : r.approval_status === 'approved' ? (
                      <span className="text-xs text-wep-teal font-semibold">✅ Done</span>
                    ) : (
                      <span className="text-xs text-wep-muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <ReviewModal
          result={selected}
          onClose={() => setSelected(null)}
          onDone={() => qc.invalidateQueries({ queryKey: ['fga-pending'] })}
        />
      )}
    </div>
  )
}
