import { useState } from 'react'
import { format } from 'date-fns'
import { downloadFile } from '@/lib/download'
import { toast } from '@/store/toastStore'

// Reports module v1 — added 2026-10-23, Amit: "there is no report section
// still". Scoped before building (see claude/README.md's v1.4.4 section):
// a CATALOG, not a new reporting engine. The first four cards relink
// exports that already existed, scattered across Team/Analytics/FGA — no
// new backend for those. The last three are new, backed by
// backend/app/routers/reports.py, each reusing an already-tested
// computation rather than inventing new logic (see that file's docstrings).
type ReportDef = {
  id: string
  icon: string
  title: string
  description: string
}

const LEGACY_REPORTS: ReportDef[] = [
  { id: 'dsr', icon: '📋', title: 'Monthly DSR', description: 'Per-rep daily activity for the selected month — visits, calls, follow-ups, new leads, proposals, rigor.' },
  { id: 'compliance', icon: '✅', title: 'Compliance', description: 'DSR/DOR/FGA submission coverage for the selected month, per rep.' },
  { id: 'performance', icon: '📈', title: 'Performance Report', description: 'Revenue achieved vs target and activity, per rep, for the selected month. (Needs business_head+ access — a manager running this will see an error, same as the Analytics page export today.)' },
  { id: 'fga', icon: '🏆', title: 'FGA Scoring', description: 'Approved FGA scores for the selected month.' },
]

export default function Reports() {
  const [period, setPeriod] = useState(format(new Date(), 'yyyy-MM'))
  const [running, setRunning] = useState<Record<string, boolean>>({})

  const [revGranularity, setRevGranularity] = useState<'monthly' | 'weekly'>('monthly')
  const [revPeriods, setRevPeriods] = useState(6)
  const [rigorGranularity, setRigorGranularity] = useState<'weekly' | 'monthly'>('weekly')
  const [rigorPeriods, setRigorPeriods] = useState(8)

  async function run(id: string, fn: () => Promise<void>) {
    setRunning(r => ({ ...r, [id]: true }))
    try {
      await fn()
    } catch (e: any) {
      const msg = e?.response?.status === 404
        ? 'Nothing to export for this selection.'
        : e?.response?.status === 403
        ? "You don't have access to this report."
        : 'Could not generate the report.'
      toast.error(msg)
    } finally {
      setRunning(r => ({ ...r, [id]: false }))
    }
  }

  const legacyAction: Record<string, () => Promise<void>> = {
    dsr: () => downloadFile('/dsr/team/export', `team_dsr_${period}.csv`, { month: period }),
    compliance: () => downloadFile('/compliance/export', `compliance_${period}.csv`, { period }),
    performance: () => downloadFile('/analytics/performance/export', `performance_${period}.csv`, { period }),
    fga: () => downloadFile('/fga/export', `fga_approved_${period}.csv`, { period }),
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="mb-5">
        <h1 className="font-display font-bold text-xl text-wep-navy">📑 Reports</h1>
        <p className="text-wep-muted text-sm">One place for every export — revenue, activity, rigor and win-loss.</p>
      </div>

      <div className="card mb-6">
        <div className="font-semibold text-sm text-wep-navy mb-3">Existing reports</div>
        <div className="flex items-center gap-2 mb-4">
          <label htmlFor="period" className="text-xs text-wep-muted">Month</label>
          <input id="period" type="month" className="form-input text-sm !w-auto" value={period}
            onChange={e => setPeriod(e.target.value)} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {LEGACY_REPORTS.map(r => (
            <div key={r.id} className="border border-wep-border rounded-xl p-3 flex flex-col gap-2">
              <div className="font-semibold text-sm text-wep-navy">{r.icon} {r.title}</div>
              <div className="text-xs text-wep-muted flex-1">{r.description}</div>
              <button className="btn-outline text-sm self-start"
                disabled={!!running[r.id]}
                onClick={() => run(r.id, legacyAction[r.id])}>
                {running[r.id] ? 'Preparing…' : '⬇️ Download CSV'}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="card mb-6">
        <div className="font-semibold text-sm text-wep-navy mb-1">💰 Revenue vs Target</div>
        <p className="text-xs text-wep-muted mb-3">
          Per-rep ARR, One-time and Total vs target, across several periods. Weekly shows actual revenue booked
          per week in the current month — there's no weekly target to compare against (targets are set monthly/
          quarterly/yearly), so weekly is a cadence view, not an achievement %.
        </p>
        <div className="flex items-center gap-3 flex-wrap mb-3">
          <select className="form-input text-sm !w-auto" value={revGranularity}
            onChange={e => setRevGranularity(e.target.value as any)}>
            <option value="monthly">Monthly (vs target)</option>
            <option value="weekly">Weekly (actuals, current month)</option>
          </select>
          {revGranularity === 'monthly' && (
            <label className="flex items-center gap-1.5 text-xs text-wep-muted">
              Last
              <input type="number" min={1} max={12} className="form-input text-sm !w-16"
                value={revPeriods} onChange={e => setRevPeriods(Math.max(1, Math.min(12, Number(e.target.value) || 1)))} />
              months
            </label>
          )}
        </div>
        <button className="btn-outline text-sm"
          disabled={!!running.revenue}
          onClick={() => run('revenue', () => downloadFile('/reports/revenue-vs-target.csv',
            `revenue_vs_target_${revGranularity}.csv`,
            { granularity: revGranularity, periods: revPeriods }))}>
          {running.revenue ? 'Preparing…' : '⬇️ Download CSV'}
        </button>
      </div>

      <div className="card mb-6">
        <div className="font-semibold text-sm text-wep-navy mb-1">🎯 Rigor Trend</div>
        <p className="text-xs text-wep-muted mb-3">
          Per-rep average rigor score by week or month, with the single weakest component (Visits/Calls/
          Follow-ups/New leads/Proposals) called out as the concrete improvement lever — same computation as
          each rep's own rigor trend, for the whole team at once.
        </p>
        <div className="flex items-center gap-3 flex-wrap mb-3">
          <select className="form-input text-sm !w-auto" value={rigorGranularity}
            onChange={e => setRigorGranularity(e.target.value as any)}>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
          <label className="flex items-center gap-1.5 text-xs text-wep-muted">
            Last
            <input type="number" min={1} max={26} className="form-input text-sm !w-16"
              value={rigorPeriods} onChange={e => setRigorPeriods(Math.max(1, Math.min(26, Number(e.target.value) || 1)))} />
            {rigorGranularity === 'weekly' ? 'weeks' : 'months'}
          </label>
        </div>
        <button className="btn-outline text-sm"
          disabled={!!running.rigor}
          onClick={() => run('rigor', () => downloadFile('/reports/rigor-trend.csv',
            `rigor_trend_${rigorGranularity}.csv`,
            { granularity: rigorGranularity, periods: rigorPeriods }))}>
          {running.rigor ? 'Preparing…' : '⬇️ Download CSV'}
        </button>
      </div>

      <div className="card">
        <div className="font-semibold text-sm text-wep-navy mb-1">📉 Win-Loss Analysis</div>
        <p className="text-xs text-wep-muted mb-3">
          One row per closed deal (won, lost, on hold, dropped) with outcome category, detail and competitor —
          the detail behind the Opportunities page's Win-Loss summary.
        </p>
        <button className="btn-outline text-sm"
          disabled={!!running.winloss}
          onClick={() => run('winloss', () => downloadFile('/reports/win-loss.csv', 'win_loss_analysis.csv'))}>
          {running.winloss ? 'Preparing…' : '⬇️ Download CSV'}
        </button>
      </div>
    </div>
  )
}
