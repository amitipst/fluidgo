import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'

// Collapsible remark timeline for a deal, newest first. Reads
// GET /pipeline/{dealId}/updates, which pipeline.py's update_deal()
// appends to every time a Save carries a new "Today's Update" — so this
// is the retained history behind what used to be an overwrite-in-place
// field. Same ordered sequence is the input for future AI trend analysis
// (stall detection, momentum summaries).
export default function PipelineHistory({ dealId }: { dealId: string }) {
  const [open, setOpen] = useState(false)

  const { data: entries = [], isLoading, error } = useQuery({
    queryKey: ['pipeline-history', dealId],
    queryFn: () => api.get(`/pipeline/${dealId}/updates`).then(r => r.data),
    enabled: open,
  })

  return (
    <div className="md:col-span-2 mt-1">
      <button type="button" onClick={() => setOpen(v => !v)}
        className="text-xs font-semibold text-brand-pink hover:opacity-80">
        {open ? '▲ Hide history' : '▼ Show history'}
        {entries.length > 0 ? ` (${entries.length})` : ''}
      </button>

      {open && (
        <div className="mt-2 space-y-2 max-h-64 overflow-y-auto pr-1">
          {isLoading && <div className="text-xs text-wep-muted">Loading…</div>}
          {!!error && <div className="text-xs text-red-600">{getErrorMessage(error, 'Could not load history')}</div>}
          {!isLoading && !error && entries.length === 0 && (
            <div className="text-xs text-wep-muted">No updates logged yet.</div>
          )}
          {entries.map((e: any) => (
            <div key={e.id} className="rounded-lg border border-wep-border p-2 bg-wep-surface/50">
              <div className="flex items-center justify-between text-[10px] text-wep-muted">
                <span>{e.author_name ?? 'Unknown'}</span>
                <span>{e.created_at ? new Date(e.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : ''}</span>
              </div>
              <div className="text-xs text-wep-text mt-0.5">{e.update_text}</div>
              {e.next_step && (
                <div className="text-xs mt-0.5"><span className="text-brand-pink">→ {e.next_step}</span></div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
