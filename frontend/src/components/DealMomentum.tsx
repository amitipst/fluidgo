import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'

// On-demand AI momentum verdict for a deal — has it moved forward, stalled,
// or gone in circles, judged from the pipeline_updates remark sequence?
// Rep-triggered (not auto-run on every save, to keep Ollama load bounded).
// GET hydrates the last cached verdict on open; POST (re-)runs the check
// and both updates the cache and refreshes the query.
export default function DealMomentum({ dealId }: { dealId: string }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['pipeline-momentum', dealId],
    queryFn: () => api.get(`/pipeline/${dealId}/momentum`).then(r => r.data),
    enabled: open,
  })

  const check = useMutation({
    mutationFn: () => api.post(`/pipeline/${dealId}/momentum`).then(r => r.data),
    onSuccess: (result) => {
      qc.setQueryData(['pipeline-momentum', dealId], result)
    },
  })

  const verdictColor = (s?: string) =>
    s?.startsWith('✅') ? 'text-green-700 bg-green-50' :
    s?.startsWith('⚠️') ? 'text-amber-600 bg-amber-50' :
    s?.startsWith('🔁') ? 'text-red-600 bg-red-50' :
    'text-wep-muted bg-wep-surface'

  const shown = check.data?.status === 'ready' ? check.data : data

  return (
    <div className="md:col-span-2 mt-1">
      <button type="button" onClick={() => setOpen(v => !v)}
        className="text-xs font-semibold text-brand-pink hover:opacity-80">
        {open ? '▲ Hide momentum' : '▼ Check momentum'}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {isLoading && <div className="text-xs text-wep-muted">Loading…</div>}

          {shown?.status === 'ready' && (
            <div className={`text-xs rounded-lg p-2 ${verdictColor(shown.summary)}`}>
              {shown.summary}
              {shown.generated_at && (
                <div className="text-[10px] opacity-70 mt-1">
                  Checked {new Date(shown.generated_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                </div>
              )}
            </div>
          )}

          {!isLoading && (!shown || shown.status === 'not_generated') && !check.data && (
            <div className="text-xs text-wep-muted">No momentum check run yet.</div>
          )}

          {check.data?.status === 'insufficient_history' && (
            <div className="text-xs text-wep-muted">{check.data.message}</div>
          )}

          {check.isError && (
            <div className="text-xs text-red-600">{getErrorMessage(check.error, 'Could not check momentum')}</div>
          )}

          <button type="button" onClick={() => check.mutate()} disabled={check.isPending}
            className="btn-outline text-xs px-3 py-1.5">
            {check.isPending ? '⏳ Checking… (can take up to a minute)' : '🧭 Run momentum check'}
          </button>
        </div>
      )}
    </div>
  )
}
