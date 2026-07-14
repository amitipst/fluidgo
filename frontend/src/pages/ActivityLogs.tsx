import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { format } from 'date-fns'
import api from '@/hooks/useApi'

// Read-only rigor-score + log view for roles that need audit visibility but
// no action buttons — HR and Finance. Deliberately reuses the same backend
// endpoints DSRHistory.tsx / Team.tsx already call (both already accessible
// to HR/Finance at role_level 25, since those endpoints just require level
// 20+) rather than adding new permission code — this page just renders them
// without any approve/reject/edit affordances, so there's no risk of an HR
// user accidentally getting a manager-only action.
const today = new Date()
const currentPeriod = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`

const rigorColor = (s: number) =>
  s >= 80 ? '#059669' : s >= 60 ? '#D97706' : s > 0 ? '#DC2626' : '#9CA3AF'

const DOR_STATUS_CFG: Record<string, { label: string; bg: string; text: string }> = {
  on_track: { label: 'On Track', bg: '#ECFDF5', text: '#065F46' },
  at_risk:  { label: 'At Risk',  bg: '#FFFBEB', text: '#92400E' },
  critical: { label: 'Critical', bg: '#FEF2F2', text: '#B91C1C' },
}

export default function ActivityLogs() {
  const [period, setPeriod] = useState(currentPeriod)
  const [tab, setTab] = useState<'sales' | 'presales' | 'dor'>('sales')

  // Both endpoints already power existing manager views (DSRHistory.tsx,
  // Team.tsx) — status=all here means "every DSR this month regardless of
  // approval state," which is exactly the audit view HR needs.
  const { data: dsrRows = [], isLoading: dsrLoading } = useQuery({
    queryKey: ['activity-log-dsr', period],
    queryFn: () => api.get(`/dsr/team/pending?month=${period}&status=all`).then(r => r.data),
    enabled: tab === 'sales' || tab === 'presales',
  })

  const { data: dorRows = [], isLoading: dorLoading } = useQuery({
    queryKey: ['activity-log-dor', period],
    queryFn: () => api.get(`/dor/team?month=${period}`).then(r => r.data),
    enabled: tab === 'dor',
  })

  const salesRows    = dsrRows.filter((d: any) => d.dsr_type !== 'presales')
  const presalesRows = dsrRows.filter((d: any) => d.dsr_type === 'presales')

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="page-header">
        <div>
          <h1 className="page-title">🗂️ Activity Logs</h1>
          <p className="page-sub">Rigor scores and daily logs — read-only</p>
        </div>
        <input type="month" className="form-input py-2 text-sm w-40"
          value={period} onChange={e => setPeriod(e.target.value)} />
      </div>

      <div className="flex gap-2 mb-5">
        {[
          { val: 'sales',    label: '📋 Sales DSR' },
          { val: 'presales', label: '🔧 Pre-Sales DMR' },
          { val: 'dor',      label: '🛠️ Service Delivery DOR' },
        ].map(t => (
          <button key={t.val} onClick={() => setTab(t.val as any)}
            className={`text-sm font-semibold px-4 py-2 rounded-xl border transition-colors ${
              tab === t.val
                ? 'border-wep-accent bg-wep-accent/10 text-wep-accent'
                : 'border-wep-border text-wep-muted hover:bg-wep-surface'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {(tab === 'sales' || tab === 'presales') && (
        dsrLoading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-16 rounded-2xl" />)}</div>
        ) : (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-wep-border">
                  {['Rep','Date','Rigor','Calls/Demos','Visits/POCs','Follow-ups','Status'].map(h => (
                    <th key={h} className="text-left text-[10px] font-bold uppercase tracking-wide text-wep-muted py-2 px-4 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(tab === 'sales' ? salesRows : presalesRows).length === 0 ? (
                  <tr><td colSpan={7} className="py-8 text-center text-wep-muted">No entries for {period}.</td></tr>
                ) : (tab === 'sales' ? salesRows : presalesRows).map((d: any) => (
                  <tr key={d.id} className="border-b border-wep-border/50 hover:bg-wep-surface transition-colors">
                    <td className="py-2.5 px-4 font-medium text-wep-navy">{d.rep_name}</td>
                    <td className="py-2.5 px-4 text-wep-muted">{format(new Date(d.date), 'd MMM')}</td>
                    <td className="py-2.5 px-4 font-bold" style={{ color: rigorColor(d.rigor_score) }}>
                      {d.rigor_score > 0 ? d.rigor_score : '—'}
                    </td>
                    <td className="py-2.5 px-4">{tab === 'sales' ? d.calls : d.demos_conducted}</td>
                    <td className="py-2.5 px-4">{tab === 'sales' ? d.visits : d.pocs_conducted}</td>
                    <td className="py-2.5 px-4">{tab === 'sales' ? d.followups : d.tech_discussions}</td>
                    <td className="py-2.5 px-4">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 capitalize">
                        {d.approval_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === 'dor' && (
        dorLoading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-16 rounded-2xl" />)}</div>
        ) : (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-wep-border">
                  {['Member','Date','Status','Tickets Closed','Escalations','Client Meetings'].map(h => (
                    <th key={h} className="text-left text-[10px] font-bold uppercase tracking-wide text-wep-muted py-2 px-4 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dorRows.length === 0 ? (
                  <tr><td colSpan={6} className="py-8 text-center text-wep-muted">No entries for {period}.</td></tr>
                ) : dorRows.map((d: any) => {
                  const cfg = DOR_STATUS_CFG[d.status] ?? DOR_STATUS_CFG.on_track
                  return (
                    <tr key={d.id} className="border-b border-wep-border/50 hover:bg-wep-surface transition-colors">
                      <td className="py-2.5 px-4 font-medium text-wep-navy">{d.name}</td>
                      <td className="py-2.5 px-4 text-wep-muted">{format(new Date(d.date), 'd MMM')}</td>
                      <td className="py-2.5 px-4">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: cfg.bg, color: cfg.text }}>
                          {cfg.label}
                        </span>
                      </td>
                      <td className="py-2.5 px-4">{d.tickets_closed}</td>
                      <td className="py-2.5 px-4">{d.escalations_raised}</td>
                      <td className="py-2.5 px-4">{d.client_meetings_held}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  )
}
