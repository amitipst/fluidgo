import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '@/hooks/useApi'

// Leadership rollup (v1.6.2) for business head / COO / CEO. Company-wide or one business at a
// time, with every business and its head(s) side by side. Reads /analytics/exec-digest, so it is
// scoped by the same rule as every other screen and needs no new aggregation.

const inr = (n: number | null | undefined) =>
  n == null ? '—'
  : n >= 10000000 ? `₹${(n / 10000000).toFixed(2)} Cr`
  : n >= 100000 ? `₹${(n / 100000).toFixed(1)} L`
  : `₹${Number(n || 0).toLocaleString('en-IN')}`

const label = (b: string) => b.charAt(0).toUpperCase() + b.slice(1)

export default function LeadershipPanel() {
  const [business, setBusiness] = useState('all')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['leadership-rollup', business],
    queryFn: () => api.get('/analytics/exec-digest', { params: { business } }).then(r => r.data),
  })
  const businesses: string[] = data?.businesses ?? []
  const rows: any[] = data?.by_business ?? []

  return (
    <div className="card mb-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="font-semibold text-sm text-wep-navy">🏢 Company overview{data?.period ? ` · ${data.period}` : ''}</div>
        <div className="flex items-center gap-2">
          <select className="form-input text-sm !w-auto" value={business} onChange={e => setBusiness(e.target.value)}
                  aria-label="Business">
            <option value="all">All businesses</option>
            {businesses.map(b => <option key={b} value={b}>{label(b)}</option>)}
          </select>
          <Link to="/exec-digest" className="text-xs text-wep-pink underline">Full digest</Link>
        </div>
      </div>

      {isLoading && <div className="text-sm text-wep-muted">Loading…</div>}
      {isError && <div className="text-sm text-red-600">Could not load the overview.</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <div><div className="text-[11px] uppercase text-wep-muted">Won this month</div>
              <div className="font-bold text-lg">{inr(data.revenue?.achieved)}</div>
              <div className="text-[11px] text-wep-muted">{data.revenue?.target ? `${data.revenue.achievement_pct}% of ${inr(data.revenue.target)}` : 'No target set'}</div></div>
            <div><div className="text-[11px] uppercase text-wep-muted">Open pipeline</div>
              <div className="font-bold text-lg">{inr(data.pipeline?.open_value)}</div>
              <div className="text-[11px] text-wep-muted">{data.pipeline?.open_count} open deals</div></div>
            <div><div className="text-[11px] uppercase text-wep-muted">At-risk deals</div>
              <div className="font-bold text-lg">{data.pipeline?.at_risk?.length ?? 0}</div>
              <div className="text-[11px] text-wep-muted">no activity in 14+ days</div></div>
            <div><div className="text-[11px] uppercase text-wep-muted">DSR compliance</div>
              <div className="font-bold text-lg">{data.compliance?.avg_pct != null ? `${data.compliance.avg_pct}%` : '—'}</div>
              <div className="text-[11px] text-wep-muted">{data.compliance?.at_risk_count ?? 0} reps at risk</div></div>
          </div>

          {rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase text-wep-muted">
                    <th className="py-1 pr-3">Business</th><th className="pr-3">Head</th>
                    <th className="pr-3 text-right">Won (month)</th><th className="pr-3 text-right">Open pipeline</th>
                    <th className="text-right">Open deals</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.business} className="border-t border-wep-border/50">
                      <td className="py-1.5 pr-3 font-medium">
                        <button className="underline-offset-2 hover:underline" onClick={() => setBusiness(r.business)}>{label(r.business)}</button>
                      </td>
                      <td className="pr-3 text-wep-muted">{r.heads?.length ? r.heads.join(', ') : '—'}</td>
                      <td className="pr-3 text-right">{inr(r.won_value)}</td>
                      <td className="pr-3 text-right">{inr(r.open_value)}</td>
                      <td className="text-right">{r.open_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
