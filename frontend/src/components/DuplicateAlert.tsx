import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '@/hooks/useApi'

type Dup = { id: string; title?: string; company: string; stage_label?: string; stage?: string; owner: string
  same_contact: boolean; viewable: boolean; deal_value?: number | null; requirement?: string }

const inr = (n?: number | null) => (n == null ? '' : `₹ ${Math.round(n).toLocaleString('en-IN')}`)

/** "Alert and allow" duplicate check (v1.6.0): shows what is already open for
 * this company so a parallel lead/deal is a conscious choice, never an accident.
 * Never blocks — parallel deals on one customer are normal. */
export default function DuplicateAlert({ accountId, contactId, excludeId }: {
  accountId?: string; contactId?: string; excludeId?: string
}) {
  const { data } = useQuery<{ deals: Dup[]; leads: Dup[]; count: number }>({
    queryKey: ['dup-check', accountId, contactId], enabled: !!accountId, staleTime: 30_000,
    queryFn: () => api.get('/pipeline/duplicates', { params: { account_id: accountId, contact_id: contactId || undefined } }).then(r => r.data),
  })
  const deals = (data?.deals ?? []).filter(d => d.id !== excludeId)
  const leads = (data?.leads ?? []).filter(l => l.id !== excludeId)
  if (!accountId || deals.length + leads.length === 0) return null
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs" role="status" aria-live="polite">
      <div className="font-semibold text-amber-800 mb-1">
        ℹ️ {deals.length + leads.length} open item{deals.length + leads.length > 1 ? 's' : ''} already exist for this company
      </div>
      <p className="text-amber-800/80 mb-2">Continue if this is a separate opportunity — running two or three deals in parallel is fine. Give it a clear name so they can be told apart.</p>
      <ul className="space-y-1">
        {deals.map(d => (
          <li key={d.id} className="flex flex-wrap gap-x-2">
            <span className="font-medium">{d.title || d.company}</span>
            <span className="text-amber-700">{d.stage_label}</span>
            <span className="text-amber-700">· {d.owner}</span>
            {d.viewable && d.deal_value != null && <span className="text-amber-700">· {inr(d.deal_value)}</span>}
            {d.same_contact && <span className="font-semibold text-amber-900">· same contact</span>}
          </li>))}
        {leads.map(l => (
          <li key={l.id} className="flex flex-wrap gap-x-2">
            <span className="font-medium">Lead: {l.requirement || l.company}</span>
            <span className="text-amber-700">{l.stage}</span><span className="text-amber-700">· {l.owner}</span>
            {l.same_contact && <span className="font-semibold text-amber-900">· same contact</span>}
          </li>))}
      </ul>
      <Link to="/deals" className="inline-block mt-2 underline text-amber-900 font-medium">Open Deals to review</Link>
    </div>
  )
}
