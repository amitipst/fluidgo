import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { format } from 'date-fns'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// ── Helpers ───────────────────────────────────────────────────────────────────
const STATUS_CFG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  submitted: { label: 'Submitted',  bg: '#EFF6FF', text: '#1E40AF', dot: '#3B82F6' },
  approved:  { label: '✅ Approved', bg: '#ECFDF5', text: '#065F46', dot: '#10B981' },
  draft:     { label: 'Draft',      bg: '#F9FAFB', text: '#6B7280', dot: '#9CA3AF' },
}
const rigorColor = (s: number) =>
  s >= 80 ? '#059669' : s >= 60 ? '#D97706' : s > 0 ? '#DC2626' : '#9CA3AF'

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CFG[status] ?? STATUS_CFG.submitted
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-full"
      style={{ background: cfg.bg, color: cfg.text }}>
      <span className="w-1.5 h-1.5 rounded-full inline-block shrink-0" style={{ background: cfg.dot }} />
      {cfg.label}
    </span>
  )
}

// ── DSR Row Card ──────────────────────────────────────────────────────────────
function DSRCard({ dsr, canApprove, onApprove }: {
  dsr: any; canApprove?: boolean; onApprove?: (id: string, action: string, comment?: string) => void
}) {
  const [showDetail, setShowDetail] = useState(false)
  const [comment, setComment] = useState('')
  const isLocked = dsr.approval_status === 'approved'

  return (
    <div className={`card border-l-4 transition-all ${
      isLocked ? 'border-l-emerald-400' :
      dsr.approval_status === 'submitted' ? 'border-l-blue-400' : 'border-l-gray-300'
    }`}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-bold text-wep-text">
              {format(new Date(dsr.date), 'EEE, d MMM yyyy')}
            </span>
            <StatusBadge status={dsr.approval_status} />
            {isLocked && (
              <span className="text-[10px] text-wep-muted">🔒 Locked</span>
            )}
          </div>
          {/* KPI summary */}
          <div className="flex items-center gap-4 text-sm text-wep-muted flex-wrap">
            {dsr.dsr_type === 'sales' ? (
              <>
                <span>📞 {dsr.calls} calls</span>
                <span>🏢 {dsr.visits} visits</span>
                <span>🔄 {dsr.followups} follow-ups</span>
                <span>🎯 {dsr.new_leads} leads</span>
                {dsr.proposals > 0 && <span>📄 {dsr.proposals} proposals</span>}
              </>
            ) : (
              <>
                <span>🖥️ {dsr.demos_conducted} demos</span>
                <span>🔬 {dsr.pocs_conducted} POCs</span>
                <span>📝 {dsr.proposals_supported} prop support</span>
                <span>💬 {dsr.tech_discussions} tech disc.</span>
              </>
            )}
          </div>
          {dsr.manager_comment && (
            <div className="mt-1.5 text-xs px-2.5 py-1.5 rounded-lg"
              style={{ background: isLocked ? '#ECFDF5' : '#FEF3C7',
                       color: isLocked ? '#065F46' : '#92400E' }}>
              💬 Manager: {dsr.manager_comment}
            </div>
          )}
        </div>

        {/* Rigor score */}
        <div className="text-right shrink-0">
          <div className="font-display font-black text-2xl leading-none"
            style={{ color: rigorColor(dsr.rigor_score) }}>
            {dsr.rigor_score > 0 ? dsr.rigor_score : '—'}
          </div>
          <div className="text-[10px] text-wep-muted mt-0.5">rigor</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-wep-border/50 flex-wrap">
        <button onClick={() => setShowDetail(v => !v)}
          className="text-xs text-wep-accent font-medium hover:underline">
          {showDetail ? 'Hide details ▲' : 'View details ▼'}
        </button>

        {/* Manager approval buttons */}
        {canApprove && dsr.approval_status === 'submitted' && onApprove && (
          <>
            <button onClick={() => onApprove(dsr.id, 'approve', comment || undefined)}
              className="text-xs font-bold px-3 py-1.5 rounded-lg text-white"
              style={{ background: '#059669' }}>
              ✅ Approve
            </button>
            <button onClick={() => onApprove(dsr.id, 'reject', comment || 'Please review and resubmit')}
              className="text-xs font-bold px-3 py-1.5 rounded-lg text-white"
              style={{ background: '#DC2626' }}>
              ↩ Reject
            </button>
            <input className="form-input py-1 text-xs flex-1 min-w-[150px]"
              placeholder="Comment (optional)"
              value={comment} onChange={e => setComment(e.target.value)} />
          </>
        )}
      </div>

      {/* Detail expansion */}
      {showDetail && (
        <div className="mt-3 pt-3 border-t border-wep-border/50 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          {dsr.dsr_type === 'sales' ? (
            <>
              {[
                { label:'Visits',      val:dsr.visits },
                { label:'Virtual Mtg', val:dsr.virtual_meetings },
                { label:'Calls',       val:dsr.calls },
                { label:'Follow-ups',  val:dsr.followups },
                { label:'New Leads',   val:dsr.new_leads },
                { label:'Proposals',   val:dsr.proposals },
                { label:'Status',      val:dsr.status },
                { label:'Travel Day',  val:dsr.travel_day ? 'Yes' : 'No' },
              ].map(({ label, val }) => (
                <div key={label}>
                  <div className="text-wep-muted">{label}</div>
                  <div className="font-semibold text-wep-text">{val}</div>
                </div>
              ))}
            </>
          ) : (
            <>
              {[
                { label:'Demos',          val:dsr.demos_conducted },
                { label:'POCs',           val:dsr.pocs_conducted },
                { label:'Prop. Support',  val:dsr.proposals_supported },
                { label:'Tech Disc.',     val:dsr.tech_discussions },
                { label:'Workshops',      val:dsr.workshops_conducted },
                { label:'Training Del.',  val:dsr.trainings_delivered },
                { label:'Training Att.',  val:dsr.trainings_attended },
                { label:'Docs Created',   val:dsr.docs_created },
              ].map(({ label, val }) => (
                <div key={label}>
                  <div className="text-wep-muted">{label}</div>
                  <div className="font-semibold text-wep-text">{val}</div>
                </div>
              ))}
            </>
          )}
          {dsr.notes && (
            <div className="col-span-2 md:col-span-4">
              <div className="text-wep-muted">Notes</div>
              <div className="text-wep-text">{dsr.notes}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function DSRHistory() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const today = new Date()
  const [month, setMonth] = useState(format(today, 'yyyy-MM'))
  const [viewMode, setViewMode] = useState<'mine' | 'team'>('mine')

  const isManager = ['manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')

  // My DSR history
  const { data: myHistory = [], isLoading: myLoading } = useQuery({
    queryKey: ['dsr-history', month],
    queryFn:  () => api.get(`/dsr/history?month=${month}`).then(r => r.data),
    enabled:  viewMode === 'mine',
  })

  // Team pending approvals
  const { data: teamPending = [], isLoading: teamLoading } = useQuery({
    queryKey: ['dsr-team-pending', month],
    queryFn:  () => api.get(`/dsr/team/pending?month=${month}`).then(r => r.data),
    enabled:  viewMode === 'team' && isManager,
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, action, comment }: { id: string; action: string; comment?: string }) =>
      api.post(`/dsr/${id}/approve`, { action, comment }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dsr-team-pending'] })
      qc.invalidateQueries({ queryKey: ['dsr-history'] })
    },
    onError: (e: any) => alert(e?.response?.data?.detail ?? 'Action failed')
  })

  const displayed = viewMode === 'mine' ? myHistory : teamPending
  const isLoading = viewMode === 'mine' ? myLoading : teamLoading

  // Summary stats
  const submitted = displayed.filter((d: any) => d.approval_status === 'submitted').length
  const approved  = displayed.filter((d: any) => d.approval_status === 'approved').length
  const avgRigor  = displayed.length
    ? Math.round(displayed.filter((d: any) => d.rigor_score > 0)
        .reduce((s: number, d: any) => s + d.rigor_score, 0) /
        Math.max(1, displayed.filter((d: any) => d.rigor_score > 0).length))
    : 0

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">📋 DSR History</h1>
          <p className="page-sub">
            {viewMode === 'mine' ? 'Your daily activity log' : 'Team DSRs awaiting approval'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input type="month" className="form-input py-2 text-sm w-40"
            value={month} onChange={e => setMonth(e.target.value)} />
          {isManager && (
            <div className="flex rounded-xl overflow-hidden border border-wep-border">
              {[{ val:'mine', label:'Mine' }, { val:'team', label:'Team Approval' }].map(v => (
                <button key={v.val}
                  onClick={() => setViewMode(v.val as any)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${
                    viewMode === v.val
                      ? 'text-white'
                      : 'text-wep-muted hover:text-wep-text bg-white'
                  }`}
                  style={viewMode === v.val
                    ? { background: 'linear-gradient(135deg,#F0115E,#C2005A)' }
                    : {}}>
                  {v.label}
                  {v.val === 'team' && teamPending.length > 0 && (
                    <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold rounded-full bg-white/20">
                      {submitted}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Summary stats */}
      {displayed.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label:'Total Days',      value: displayed.length,     color:'#1E6FD9' },
            { label:'Pending Approval',value: submitted,            color:'#D97706' },
            { label:'Avg Rigor',       value: avgRigor > 0 ? `${avgRigor}/100` : '—',
                                                                     color: rigorColor(avgRigor) },
          ].map(s => (
            <div key={s.label} className="card text-center py-3">
              <div className="font-display font-black text-2xl" style={{ color: s.color }}>
                {s.value}
              </div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted mt-1">
                {s.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* DSR List */}
      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i=><div key={i} className="skeleton h-24 rounded-2xl"/>)}</div>
      ) : displayed.length === 0 ? (
        <div className="card text-center py-16">
          <div className="text-5xl mb-4">📋</div>
          <p className="font-semibold text-wep-text mb-1">
            {viewMode === 'mine' ? `No DSRs for ${month}` : 'No pending approvals'}
          </p>
          <p className="text-wep-muted text-sm">
            {viewMode === 'mine'
              ? 'Submit your daily DSR from the Submit DSR page.'
              : 'All DSRs for this month have been reviewed.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {viewMode === 'team' && (
            <div className="text-xs text-wep-muted px-1 mb-2">
              Showing {submitted} pending approval · {approved} already approved this month
            </div>
          )}
          {displayed.map((dsr: any) => (
            <div key={dsr.id}>
              {viewMode === 'team' && (
                <div className="text-xs font-semibold text-wep-muted px-1 mb-1">
                  👤 {dsr.rep_name} — {dsr.rep_email}
                </div>
              )}
              <DSRCard
                dsr={dsr}
                canApprove={viewMode === 'team' && isManager}
                onApprove={(id, action, comment) =>
                  approveMutation.mutate({ id, action, comment })}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
