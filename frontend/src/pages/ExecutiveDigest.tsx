import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { format } from 'date-fns'
import api from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

// Executive Intelligence Digest — added 2026-10-24 (R2 of
// fluidgo-services-intelligence-platform-assessment.md, flagged there as
// "genuinely one of the cheapest, highest-visibility wins available").
// Read-only view + "Email me this digest" button — reuses the existing
// /analytics/exec-digest and /analytics/exec-digest/send endpoints, both of
// which are pure reads over existing data (revenue, pipeline, rigor,
// compliance), nothing new underneath.

const inr = (n: number | null | undefined) =>
  n == null ? '—'
  : n >= 10000000 ? `₹${(n / 10000000).toFixed(1)}Cr`
  : n >= 100000 ? `₹${(n / 100000).toFixed(1)}L`
  : `₹${Number(n || 0).toLocaleString('en-IN')}`

function Card({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="card mb-4">
      <div className="font-semibold text-sm text-wep-navy mb-3">{icon} {title}</div>
      {children}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-wep-muted">{label}</div>
      <div className="font-display font-bold text-lg text-wep-text">{value}</div>
    </div>
  )
}

function DealList({ deals, empty, tone }: { deals: any[]; empty: string; tone: 'risk' | 'win' }) {
  if (!deals?.length) return <div className="text-xs text-wep-muted italic py-2">{empty}</div>
  return (
    <div className="space-y-1.5">
      {deals.map(d => (
        <div key={d.id} className="flex items-center justify-between text-sm border-b border-wep-border/50 pb-1.5 last:border-0">
          <span className="text-wep-text">{d.company}</span>
          <span className={`font-semibold ${tone === 'risk' ? 'text-red-600' : 'text-emerald-600'}`}>{inr(d.value)}</span>
        </div>
      ))}
    </div>
  )
}

export default function ExecutiveDigest() {
  const [period, setPeriod] = useState(format(new Date(), 'yyyy-MM'))
  const { data, isLoading, error } = useQuery({
    queryKey: ['exec-digest', period],
    queryFn: () => api.get('/analytics/exec-digest', { params: { period } }).then(r => r.data),
  })

  const send = useMutation({
    mutationFn: () => api.post('/analytics/exec-digest/send', null, { params: { period } }),
    onSuccess: (r) => toast.success(r.data.sent
      ? `Digest emailed to ${r.data.to}`
      : `SMTP not configured — digest logged on the server instead of emailed.`),
    onError: () => toast.error('Could not send the digest.'),
  })

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="mb-5 flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">📊 Executive Digest</h1>
          <p className="text-wep-muted text-sm">Revenue, pipeline, rigor and compliance — in one place, in scope for your role.</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" className="form-input text-sm !w-auto" value={period} onChange={e => setPeriod(e.target.value)} />
          <button className="btn-primary text-sm" disabled={send.isPending} onClick={() => send.mutate()}>
            {send.isPending ? 'Sending…' : '✉️ Email me this'}
          </button>
        </div>
      </div>

      {isLoading && <div className="card text-center text-wep-muted py-10">Loading…</div>}
      {!!error && <div className="card text-center text-red-600 py-10">Could not load the digest for this period.</div>}

      {data && (
        <>
          <Card title="Revenue" icon="💰">
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Achieved" value={inr(data.revenue.achieved)} />
              <Stat label="Target" value={inr(data.revenue.target)} />
              <Stat label="Achievement" value={data.revenue.achievement_pct != null ? `${data.revenue.achievement_pct}%` : 'No target set'} />
            </div>
          </Card>

          <Card title="Pipeline" icon="📈">
            <div className="grid grid-cols-3 gap-4 mb-4">
              <Stat label="Open deals" value={data.pipeline.open_count} />
              <Stat label="Open value" value={inr(data.pipeline.open_value)} />
              <Stat label="Weighted forecast" value={inr(data.pipeline.weighted_forecast)} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-xs font-semibold text-red-600 mb-1.5">⚠️ At-risk (14+ days no activity)</div>
                <DealList deals={data.pipeline.at_risk} empty="None — pipeline is current." tone="risk" />
              </div>
              <div>
                <div className="text-xs font-semibold text-emerald-600 mb-1.5">🏆 Recent wins</div>
                <DealList deals={data.pipeline.recent_wins} empty="No closed-won deals yet this period." tone="win" />
              </div>
            </div>
          </Card>

          <Card title="Team Rigor" icon="🎯">
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Average rigor" value={data.rigor.avg_rigor != null ? `${data.rigor.avg_rigor}/100` : '—'} />
              <Stat label="Weakest component" value={data.rigor.weakest?.label ?? '—'} />
            </div>
          </Card>

          <Card title="Compliance" icon="✅">
            <div className="grid grid-cols-2 gap-4 mb-3">
              <Stat label="Avg DSR/DOR compliance" value={data.compliance.avg_pct != null ? `${data.compliance.avg_pct}%` : '—'} />
              <Stat label="Reps at risk" value={data.compliance.at_risk_count} />
            </div>
            {data.compliance.at_risk_reps?.length > 0 && (
              <div className="space-y-1">
                {data.compliance.at_risk_reps.map((r: any) => (
                  <div key={r.name} className="flex items-center justify-between text-sm">
                    <span>{r.name}</span>
                    <span className="text-red-600">{r.compliance_pct}% · {r.consecutive_missed_days}d missed streak</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
