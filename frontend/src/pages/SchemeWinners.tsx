import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api, { getErrorMessage } from '@/hooks/useApi'

// HR sign-off queue for incentive scheme achievers. Cash rewards land here
// as status='pending_hr' when Gamification.tsx's "Detect Winners" button is
// run on a scheme (POST /incentives/schemes/{id}/detect-winners); points/
// badge/recognition auto-approve and never show up here at all. Mirrors the
// DSR/DOR approval pattern already established elsewhere in the app.

const REWARD_LABELS: Record<string,string> = {
  cash: '💵 Cash', points: '🏅 Points', badge: '🎖 Badge', recognition: '🌟 Recognition',
}

const STATUS_CFG: Record<string, { label: string; bg: string; text: string }> = {
  pending_hr: { label: 'Pending Review', bg: '#EFF6FF', text: '#1E40AF' },
  approved:   { label: '✅ Approved',     bg: '#ECFDF5', text: '#065F46' },
  rejected:   { label: '↩ Rejected',     bg: '#FEF2F2', text: '#B91C1C' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CFG[status] ?? STATUS_CFG.pending_hr
  return (
    <span className="text-[11px] font-bold px-2.5 py-1 rounded-full"
      style={{ background: cfg.bg, color: cfg.text }}>
      {cfg.label}
    </span>
  )
}

export default function SchemeWinners() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<'pending_hr' | 'approved' | 'rejected'>('pending_hr')
  const [comment, setComment] = useState<Record<string, string>>({})

  const { data: winners = [], isLoading } = useQuery({
    queryKey: ['scheme-winners', statusFilter],
    queryFn: () => api.get(`/incentives/winners?status=${statusFilter}`).then(r => r.data),
  })

  const review = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' }) =>
      api.post(`/incentives/winners/${id}/review`, { action, comment: comment[id] || undefined }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheme-winners'] }),
    onError: (e: any) => alert(getErrorMessage(e, 'Could not review winner')),
  })

  const markPaid = useMutation({
    mutationFn: (id: string) => api.post(`/incentives/winners/${id}/mark-paid`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheme-winners'] }),
    onError: (e: any) => alert(getErrorMessage(e, 'Could not mark as paid')),
  })

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="page-header">
        <div>
          <h1 className="page-title">🏆 Scheme Winners</h1>
          <p className="page-sub">Cash reward sign-off — points/badges auto-credit and never need review</p>
        </div>
        <div className="flex rounded-xl overflow-hidden border border-wep-border">
          {[
            { val: 'pending_hr', label: 'Pending' },
            { val: 'approved',   label: 'Approved' },
            { val: 'rejected',   label: 'Rejected' },
          ].map(v => (
            <button key={v.val}
              onClick={() => setStatusFilter(v.val as any)}
              className={`px-3 py-2 text-sm font-medium transition-colors ${
                statusFilter === v.val ? 'text-white' : 'text-wep-muted hover:text-wep-text bg-white'
              }`}
              style={statusFilter === v.val
                ? { background: 'linear-gradient(135deg,#F0115E,#C2005A)' } : {}}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-2xl" />)}</div>
      ) : winners.length === 0 ? (
        <div className="card text-center py-16">
          <div className="text-5xl mb-4">🏆</div>
          <p className="font-semibold text-wep-text mb-1">
            {statusFilter === 'pending_hr' ? 'Nothing waiting on you' :
             statusFilter === 'approved' ? 'No approved cash winners yet' : 'Nothing rejected'}
          </p>
          <p className="text-wep-muted text-sm">
            Winners show up here after a manager runs "Detect Winners" on a cash-reward scheme.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {winners.map((w: any) => (
            <div key={w.id} className="card">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-bold text-wep-text">{w.rep_name}</span>
                    <StatusBadge status={w.status} />
                  </div>
                  <div className="text-sm text-wep-muted">
                    {w.scheme_name} · {w.period} · {REWARD_LABELS[w.reward_type] ?? w.reward_type}
                    {w.reward_value != null && ` ₹${Number(w.reward_value).toLocaleString('en-IN')}`}
                  </div>
                  <div className="text-xs text-wep-muted mt-1">
                    Achieved {w.achieved_value.toLocaleString('en-IN')} of {w.target_value.toLocaleString('en-IN')} target
                  </div>
                  {w.hr_comment && (
                    <div className="mt-1.5 text-xs px-2.5 py-1.5 rounded-lg"
                      style={{ background: w.status === 'approved' ? '#ECFDF5' : '#FEF2F2',
                               color: w.status === 'approved' ? '#065F46' : '#7F1D1D' }}>
                      💬 {w.hr_comment}
                    </div>
                  )}
                  {w.paid && (
                    <div className="mt-1.5 text-xs text-emerald-600 font-semibold">
                      💰 Paid {w.paid_at ? new Date(w.paid_at).toLocaleDateString('en-IN') : ''}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {w.status === 'pending_hr' && (
                    <>
                      <input className="form-input py-1 text-xs w-40"
                        placeholder="Comment (optional)"
                        value={comment[w.id] || ''}
                        onChange={e => setComment(c => ({ ...c, [w.id]: e.target.value }))} />
                      <button onClick={() => review.mutate({ id: w.id, action: 'approve' })}
                        disabled={review.isPending}
                        className="text-xs font-bold px-3 py-1.5 rounded-lg text-white" style={{ background: '#059669' }}>
                        ✅ Approve
                      </button>
                      <button onClick={() => review.mutate({ id: w.id, action: 'reject' })}
                        disabled={review.isPending}
                        className="text-xs font-bold px-3 py-1.5 rounded-lg text-white" style={{ background: '#DC2626' }}>
                        ↩ Reject
                      </button>
                    </>
                  )}
                  {w.status === 'approved' && !w.paid && (
                    <button onClick={() => markPaid.mutate(w.id)} disabled={markPaid.isPending}
                      className="text-xs font-bold px-3 py-1.5 rounded-lg text-white" style={{ background: '#0D9488' }}>
                      💰 Mark Paid
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
