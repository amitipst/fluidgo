import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import api from '@/hooks/useApi'
import { downloadFile } from '@/lib/download'
import { toast } from '@/store/toastStore'

type Gran = 'weekly' | 'monthly' | 'quarterly' | 'yearly'
const TABS: { key: Gran; label: string; ranges: { n: number; label: string }[]; def: number }[] = [
  { key: 'weekly', label: 'Weekly', def: 12, ranges: [{ n: 8, label: '8 wks' }, { n: 12, label: '12 wks' }, { n: 26, label: '26 wks' }, { n: 52, label: '52 wks' }] },
  { key: 'monthly', label: 'Monthly', def: 12, ranges: [{ n: 6, label: '6 mo' }, { n: 12, label: '12 mo' }, { n: 24, label: '24 mo' }, { n: 36, label: '3 yrs' }] },
  { key: 'quarterly', label: 'Quarterly', def: 8, ranges: [{ n: 4, label: '4 qtrs' }, { n: 8, label: '8 qtrs' }, { n: 12, label: '12 qtrs' }] },
  { key: 'yearly', label: 'Yearly', def: 3, ranges: [{ n: 3, label: 'Last 3 yrs' }, { n: 5, label: '5 yrs' }] },
]
const C = { arr: '#F0115E', once: '#92278E', leads: '#0EA5E9', conv: '#059669', grey: '#9CA3AF' }

const cr = (v: number) => v >= 1e7 ? `₹${(v / 1e7).toFixed(2)}Cr` : v >= 1e5 ? `₹${(v / 1e5).toFixed(1)}L` : v >= 1e3 ? `₹${(v / 1e3).toFixed(0)}K` : `₹${Math.round(v)}`
const pct = (v: number | null | undefined) => v == null ? '—' : `${v}%`

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-wep-border bg-white px-3 py-2.5 min-w-0">
      <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted truncate">{label}</div>
      <div className="font-display font-bold text-lg text-wep-text truncate">{value}</div>
      {sub && <div className="text-[10px] text-wep-light truncate">{sub}</div>}
    </div>
  )
}

/** Trends (v1.5.0): wins, revenue (ARR + One-time), leads and conversion by week,
 * month, quarter or year (India FY) — incl. the last 3 years. */
export default function TrendsPanel() {
  const [gran, setGran] = useState<Gran>('monthly')
  const tab = TABS.find(t => t.key === gran)!
  const [periods, setPeriods] = useState<Record<Gran, number>>({ weekly: 12, monthly: 12, quarterly: 8, yearly: 3 })
  const n = periods[gran]
  const { data, isLoading, isError } = useQuery({
    queryKey: ['trends', gran, n],
    queryFn: () => api.get('/trends', { params: { granularity: gran, periods: n } }).then(r => r.data),
  })
  // Won deals that have no ARR / One-time split yet (older deals) would draw as zero; show them as their own
  // grey segment so the chart agrees with the Won (booked) tile.
  const series: any[] = (data?.series ?? []).map((r: any) => ({
    ...r, won_unsplit: Math.max(0, (r.won_revenue ?? 0) - (r.won_arr ?? 0) - (r.won_one_time ?? 0)),
  }))
  const t = data?.totals
  const last = series[series.length - 1], prev = series[series.length - 2]
  const delta = last && prev && prev.won_revenue > 0 ? Math.round(((last.won_revenue - prev.won_revenue) / prev.won_revenue) * 100) : null
  const [busy, setBusy] = useState(false)
  const download = async () => {
    setBusy(true)
    try { await downloadFile('/trends/export.csv', `trends_${gran}.csv`, { granularity: gran, periods: n }) }
    catch { toast.error('Could not generate the CSV.') }
    finally { setBusy(false) }
  }
  const tip = { contentStyle: { fontSize: 12, borderRadius: 8 } }

  return (
    <div className="card mb-6">
      <div className="flex items-start justify-between gap-2 flex-wrap mb-3">
        <div>
          <div className="font-semibold text-sm text-wep-navy">📈 Trends — wins, revenue, leads, conversion</div>
          <p className="text-xs text-wep-muted">Quarters and years follow the India financial year (Apr–Mar). Your visible team only.</p>
        </div>
        <button className="btn-outline text-sm min-h-[40px]" disabled={busy} onClick={download}>{busy ? 'Preparing…' : '⬇️ CSV'}</button>
      </div>

      <div role="tablist" aria-label="Trend period" className="inline-flex rounded-xl border border-wep-border overflow-hidden mb-2 max-w-full overflow-x-auto">
        {TABS.map(x => (
          <button key={x.key} role="tab" aria-selected={gran === x.key} onClick={() => setGran(x.key)}
            className={`px-3.5 min-h-[44px] text-sm font-medium whitespace-nowrap ${gran === x.key ? 'bg-brand-pink text-white' : 'text-wep-muted hover:bg-wep-surface'}`}>{x.label}</button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 mb-4">
        {tab.ranges.map(r => (
          <button key={r.n} onClick={() => setPeriods(p => ({ ...p, [gran]: r.n }))} aria-pressed={n === r.n}
            className={`px-3 min-h-[36px] rounded-full border text-xs font-medium ${n === r.n ? 'border-brand-pink text-brand-pink bg-brand-pink/5' : 'border-wep-border text-wep-muted'}`}>{r.label}</button>
        ))}
      </div>

      {isLoading && <div className="skeleton h-48 rounded-xl" />}
      {isError && <p className="text-sm text-red-500">Could not load trends.</p>}
      {data && t && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
            <Tile label="Won (booked)" value={cr(t.won_revenue)} sub={delta == null ? 'customer email / LOI / PO' : `${delta >= 0 ? '▲' : '▼'} ${Math.abs(delta)}% vs previous (this period is still open)`} />
            <Tile label="Invoiced revenue" value={cr(t.invoiced_revenue ?? 0)} sub={`${t.invoiced_count ?? 0} tax invoices`} />
            <Tile label="Won, not invoiced" value={cr(t.won_awaiting_invoice_value ?? 0)} sub={`${t.won_awaiting_invoice_count ?? 0} deals`} />
            <Tile label="Deals won" value={String(t.won_count)} sub={`${t.lost_count} lost · ${t.dropped_count ?? 0} dropped`} />
            <Tile label="Win rate" value={pct(t.win_rate_pct)} />
            <Tile label="Leads created" value={String(t.leads_created)} sub={`${t.leads_converted} converted`} />
            <Tile label="Lead → deal" value={pct(t.lead_conversion_pct)} />
            <Tile label="Avg deal size" value={t.avg_deal_size ? cr(t.avg_deal_size) : '—'} />
          </div>

          <div className="text-xs font-semibold text-wep-text mb-1">Won (booked) — ARR vs One-time, by date the customer committed</div>
          <div className="h-56 mb-5" role="img" aria-label="Won revenue by period, split into ARR and one-time">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={cr} width={56} />
                <Tooltip {...tip} formatter={(v: any) => cr(Number(v))} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="won_arr" name="ARR" stackId="r" fill={C.arr} />
                <Bar dataKey="won_one_time" name="One-time" stackId="r" fill={C.once} />
                <Bar dataKey="won_unsplit" name="Not split yet" stackId="r" fill="#9CA3AF" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="text-xs font-semibold text-wep-text mb-1">Invoiced revenue — recognised when the tax invoice is raised</div>
          <div className="h-48 mb-5" role="img" aria-label="Invoiced revenue by period">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={cr} width={56} />
                <Tooltip {...tip} formatter={(v: any) => cr(Number(v))} />
                <Bar dataKey="invoiced_revenue" name="Invoiced" fill={C.conv} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="text-xs font-semibold text-wep-text mb-1">Leads and conversion</div>
          <div className="h-56 mb-5" role="img" aria-label="Leads created, leads converted and conversion percentage by period">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis yAxisId="n" tick={{ fontSize: 10 }} allowDecimals={false} width={32} />
                <YAxis yAxisId="p" orientation="right" tick={{ fontSize: 10 }} unit="%" width={36} domain={[0, 100]} />
                <Tooltip {...tip} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="n" type="monotone" dataKey="leads_created" name="Leads" stroke={C.leads} strokeWidth={2} dot={false} />
                <Line yAxisId="n" type="monotone" dataKey="won_count" name="Wins" stroke={C.arr} strokeWidth={2} dot={false} />
                <Line yAxisId="p" type="monotone" dataKey="lead_conversion_pct" name="Lead→deal %" stroke={C.conv} strokeWidth={2} strokeDasharray="4 3" dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-xs min-w-[720px]">
              <thead>
                <tr className="text-left text-wep-muted border-b border-wep-border">
                  {['Period', 'Meetings', 'Leads', 'Conv %', 'Deals added', 'Won', 'ARR', 'One-time', 'Won total', 'Invoiced', 'Win rate'].map(h => <th key={h} className="py-1.5 px-1.5 font-semibold whitespace-nowrap">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {[...series].reverse().map(r => (
                  <tr key={r.period} className="border-b border-wep-border/60">
                    <td className="py-1.5 px-1.5 font-medium whitespace-nowrap">{r.label}</td>
                    <td className="px-1.5">{r.meetings}</td><td className="px-1.5">{r.leads_created}</td><td className="px-1.5">{pct(r.lead_conversion_pct)}</td>
                    <td className="px-1.5">{r.deals_created}</td><td className="px-1.5">{r.won_count}</td>
                    <td className="px-1.5">{cr(r.won_arr)}</td><td className="px-1.5">{cr(r.won_one_time)}</td>
                    <td className="px-1.5 font-semibold">{cr(r.won_revenue)}</td><td className="px-1.5">{cr(r.invoiced_revenue ?? 0)}</td><td className="px-1.5">{pct(r.win_rate_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
