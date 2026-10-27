import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'

// Orders register (v1.6.1) — closed orders with their evidence and invoice status.
// Read-only; invoicing itself happens in the ERP. Backend: GET /orders.

const inr = (n: number | null | undefined) =>
  n == null ? '—'
  : n >= 10000000 ? `₹${(n / 10000000).toFixed(2)} Cr`
  : n >= 100000 ? `₹${(n / 100000).toFixed(1)} L`
  : `₹${Number(n || 0).toLocaleString('en-IN')}`

const FILTERS = [
  { key: 'all', label: 'All orders' },
  { key: 'pending', label: 'Awaiting invoice' },
  { key: 'invoiced', label: 'Invoiced' },
]

export default function Orders() {
  const [status, setStatus] = useState('all')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['orders', status],
    queryFn: () => api.get('/orders', { params: { status } }).then(r => r.data),
  })
  const s = data?.summary
  const rows: any[] = data?.orders ?? []

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6">
      <h1 className="font-display font-bold text-xl text-wep-navy mb-1">📦 Orders</h1>
      <p className="text-xs text-wep-muted mb-4">
        Closed orders with their customer evidence. Invoicing is done in the ERP; the invoice date here is informational.
      </p>

      {s && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="card"><div className="text-[11px] uppercase text-wep-muted">Orders</div><div className="font-bold text-lg">{s.count}</div></div>
          <div className="card"><div className="text-[11px] uppercase text-wep-muted">Order value</div><div className="font-bold text-lg">{inr(s.total)}</div></div>
          <div className="card"><div className="text-[11px] uppercase text-wep-muted">Awaiting invoice</div><div className="font-bold text-lg">{s.pending_count} · {inr(s.pending_total)}</div></div>
          <div className="card"><div className="text-[11px] uppercase text-wep-muted">Missing PO / evidence</div><div className="font-bold text-lg">{s.missing_evidence}</div></div>
        </div>
      )}

      <div className="flex gap-2 mb-3 flex-wrap">
        {FILTERS.map(f => (
          <button key={f.key} onClick={() => setStatus(f.key)}
            className={`px-3 py-1.5 rounded-full text-xs border ${status === f.key ? 'bg-wep-navy text-white' : 'bg-white text-wep-text'}`}>
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <div className="text-sm text-wep-muted">Loading…</div>}
      {isError && <div className="text-sm text-red-600">Could not load orders.</div>}
      {!isLoading && !isError && rows.length === 0 && (
        <div className="card text-sm text-wep-muted">No orders for this filter.</div>
      )}

      <div className="space-y-2">
        {rows.map(r => (
          <div key={r.id} className="card">
            <div className="flex justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="font-semibold text-sm text-wep-text truncate">{r.company}{r.title ? ` — ${r.title}` : ''}</div>
                <div className="text-xs text-wep-muted">
                  Owner {r.owner ?? '—'} · Booked {r.won_date ?? '—'} ·{' '}
                  {r.evidence_missing ? <span className="text-amber-700">Evidence not recorded</span>
                    : <>Basis {r.won_basis}: {r.won_ref}</>}
                </div>
              </div>
              <div className="text-right">
                <div className="font-bold text-sm">{inr(r.total)}</div>
                <div className="text-[11px] text-wep-muted">ARR {inr(r.arr)} · One-time {inr(r.one_time)}</div>
                <div className={`text-[11px] font-medium ${r.invoiced ? 'text-green-700' : 'text-amber-700'}`}>
                  {r.invoiced ? `Invoiced ${r.invoiced_at}${r.invoice_ref ? ` (${r.invoice_ref})` : ''}` : 'Awaiting invoice'}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
