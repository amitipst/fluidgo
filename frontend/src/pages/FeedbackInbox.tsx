import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

const CATEGORY_META: Record<string, { icon: string; label: string }> = {
  bug: { icon: '🐞', label: 'Bug' },
  idea: { icon: '💡', label: 'Idea' },
  question: { icon: '❓', label: 'Question' },
  other: { icon: '💬', label: 'Other' },
}

const STATUS_META: Record<string, { label: string; color: string }> = {
  open:        { label: 'Open',        color: '#DC2626' },
  in_progress: { label: 'In Progress', color: '#D97706' },
  resolved:    { label: 'Resolved',    color: '#059669' },
  wont_fix:    { label: "Won't Fix",   color: '#6B7280' },
}

const STATUS_OPTIONS = ['open', 'in_progress', 'resolved', 'wont_fix']

export default function FeedbackInbox() {
  const [filter, setFilter] = useState<string>('')
  const qc = useQueryClient()

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['feedback', filter],
    queryFn: () => api.get('/feedback', { params: filter ? { status: filter } : {} }).then(r => r.data),
    refetchInterval: 60_000,
  })

  const review = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.post(`/feedback/${id}/review`, { status }),
    onSuccess: () => {
      toast.success('Updated.')
      qc.invalidateQueries({ queryKey: ['feedback'] })
      qc.invalidateQueries({ queryKey: ['feedback-badge'] })
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not update status')),
  })

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="mb-5 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">💬 Feedback Inbox</h1>
          <p className="text-wep-muted text-sm">Issues and ideas reported by the team, in one place.</p>
        </div>
        <select className="form-input py-1.5 text-sm w-auto" value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
        </select>
      </div>

      {isLoading && <p className="text-wep-muted text-sm">Loading…</p>}
      {!isLoading && items.length === 0 && (
        <div className="card text-center text-wep-muted text-sm py-8">No feedback here yet.</div>
      )}

      <div className="space-y-3">
        {items.map((f: any) => {
          const cat = CATEGORY_META[f.category] ?? CATEGORY_META.other
          const st = STATUS_META[f.status] ?? STATUS_META.open
          return (
            <div key={f.id} className="card">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-bold text-wep-navy">{cat.icon} {cat.label}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full font-bold text-white"
                      style={{ background: st.color }}>{st.label}</span>
                    {f.jira_issue_key && (
                      <a href={f.jira_issue_url} target="_blank" rel="noreferrer"
                        className="text-xs px-2 py-0.5 rounded-full font-bold"
                        style={{ background: '#EEF2FF', color: '#4338CA' }}>
                        {f.jira_issue_key} ↗
                      </a>
                    )}
                  </div>
                  <p className="text-sm text-wep-text whitespace-pre-wrap">{f.message}</p>
                  <p className="text-xs text-wep-muted mt-1.5">
                    {f.reporter_name} ({f.role}) · {f.page_context || 'unknown page'} ·{' '}
                    {new Date(f.created_at).toLocaleString()}
                  </p>
                </div>
                <select
                  className="form-input py-1.5 text-xs w-auto shrink-0"
                  value={f.status}
                  onChange={e => review.mutate({ id: f.id, status: e.target.value })}>
                  {STATUS_OPTIONS.map(s => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
                </select>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
