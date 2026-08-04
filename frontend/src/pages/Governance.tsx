import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import api from '@/hooks/useApi'

// ── Governance — validation-only role: DSR/DMR/DOR + FGA submission
// compliance, org-wide. Deliberately shows NO revenue/incentive/score
// figures anywhere on this page — every number here is a submission
// status/percentage, matching what the backend (/api/governance/*) is
// allowed to return for this role. See fluidgo-data-quality-and-release-
// plan.md §8.2 for the full design rationale.

function ComplianceBar({ pct }: { pct: number }) {
  const color = pct >= 90 ? '#059669' : pct >= 70 ? '#D97706' : '#DC2626'
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 rounded-full bg-wep-border overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      </div>
      <span className="text-xs font-semibold tabular-nums" style={{ color }}>{pct}%</span>
    </div>
  )
}

function ReviewButton({ kind, id, currentFlag }: { kind: 'dsr' | 'dor' | 'fga'; id: string; currentFlag?: boolean }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [comment, setComment] = useState('')

  const review = useMutation({
    mutationFn: (flag: boolean) => api.post(`/governance/${kind}/${id}/review`, { flag, comment: comment || undefined }),
    onSuccess: () => {
      setOpen(false); setComment('')
      qc.invalidateQueries({ queryKey: ['governance-compliance'] })
      qc.invalidateQueries({ queryKey: ['governance-fga-queue'] })
    },
  })

  if (open) {
    return (
      <div className="flex items-center gap-1">
        <input className="form-input py-1 text-xs w-40" placeholder="Note (optional)"
          value={comment} onChange={e => setComment(e.target.value)} />
        <button className="text-xs px-2 py-1 rounded-lg font-semibold" style={{ background: '#ECFDF5', color: '#059669' }}
          disabled={review.isPending} onClick={() => review.mutate(false)}>✓ Validate</button>
        <button className="text-xs px-2 py-1 rounded-lg font-semibold" style={{ background: '#FEF2F2', color: '#DC2626' }}
          disabled={review.isPending} onClick={() => review.mutate(true)}>🚩 Flag</button>
        <button className="text-xs px-2 py-1 text-wep-muted" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    )
  }
  return (
    <button className="text-xs px-2 py-1 rounded-lg font-medium border border-wep-border hover:bg-wep-surface"
      onClick={() => setOpen(true)}>
      {currentFlag ? '🚩 Flagged — re-review' : 'Review'}
    </button>
  )
}

export default function Governance() {
  const [tab, setTab] = useState<'compliance' | 'fga'>('compliance')
  const [period, setPeriod] = useState(format(new Date(), 'yyyy-MM'))
  const [reportType, setReportType] = useState<'all' | 'dsr' | 'dor'>('all')

  const { data: compliance, isLoading: complianceLoading } = useQuery({
    queryKey: ['governance-compliance', period, reportType],
    queryFn: () => api.get(`/governance/compliance?period=${period}&report_type=${reportType}`).then(r => r.data),
    enabled: tab === 'compliance',
  })

  const { data: fgaQueue = [], isLoading: fgaLoading } = useQuery({
    queryKey: ['governance-fga-queue', period],
    queryFn: () => api.get(`/governance/fga-queue?period=${period}`).then(r => r.data),
    enabled: tab === 'fga',
  })

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <div className="page-header">
        <div>
          <div className="page-title">🛡️ Governance — Submission Validation</div>
          <div className="page-sub">
            DSR / DMR / DOR / FGA compliance, org-wide · No revenue, incentive, or score figures shown by design
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input type="month" className="form-input py-2 text-sm w-40"
            value={period} onChange={e => setPeriod(e.target.value)} />
          {tab === 'compliance' && (
            <select className="form-input py-2 text-sm" value={reportType}
              onChange={e => setReportType(e.target.value as any)}>
              <option value="all">All (DSR + DMR + DOR)</option>
              <option value="dsr">DSR / DMR only</option>
              <option value="dor">DOR only</option>
            </select>
          )}
          {tab === 'compliance' && (
            <a className="btn-outline text-sm"
              href={`${api.defaults.baseURL}/compliance/export?period=${period}&report_type=${reportType}`}
              target="_blank" rel="noreferrer">⬇️ Export CSV</a>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-wep-border">
        {(['compliance', 'fga'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              tab === t ? 'border-brand-pink text-brand-pink' : 'border-transparent text-wep-muted'
            }`}>
            {t === 'compliance' ? '📋 DSR/DMR/DOR Compliance' : '🏆 FGA Submission Status'}
          </button>
        ))}
      </div>

      {tab === 'compliance' && (
        <>
          {/* Summary cards — counts/percentages only, no money */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <div className="stat-card">
              <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">Team Size</div>
              <div className="font-display font-black text-wep-navy text-2xl">{compliance?.summary?.total_reps ?? '—'}</div>
            </div>
            <div className="stat-card">
              <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">Avg Compliance</div>
              <div className="font-display font-black text-wep-navy text-2xl">{compliance?.summary?.avg_compliance_pct ?? '—'}%</div>
            </div>
            <div className="stat-card">
              <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">At Risk</div>
              <div className="font-display font-black text-2xl" style={{ color: '#DC2626' }}>
                {compliance?.summary?.at_risk_count ?? '—'}
              </div>
            </div>
            <div className="stat-card">
              <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">Expected Days</div>
              <div className="font-display font-black text-wep-navy text-2xl">{compliance?.expected_days ?? '—'}</div>
            </div>
          </div>

          {/* Region rollup */}
          {!!compliance?.summary?.by_region?.length && (
            <div className="card mb-6 overflow-x-auto">
              <div className="font-display font-bold text-wep-navy text-sm mb-3">By Region</div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-wep-muted text-xs uppercase tracking-wide">
                    <th className="pb-2">Region</th><th className="pb-2">Team</th>
                    <th className="pb-2">Avg Compliance</th><th className="pb-2">At Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {compliance.summary.by_region.map((r: any) => (
                    <tr key={r.region} className="border-t border-wep-border">
                      <td className="py-2 font-medium">{r.region}</td>
                      <td className="py-2">{r.team_size}</td>
                      <td className="py-2"><ComplianceBar pct={r.avg_compliance_pct} /></td>
                      <td className="py-2">{r.at_risk_count > 0 ? <span className="text-red-600 font-semibold">{r.at_risk_count}</span> : '0'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Per-rep table */}
          <div className="card overflow-x-auto">
            <div className="font-display font-bold text-wep-navy text-sm mb-3">By Rep — worst compliance first</div>
            {complianceLoading ? (
              <div className="text-wep-muted text-sm py-6 text-center">Loading…</div>
            ) : !compliance?.reps?.length ? (
              <div className="text-wep-muted text-sm py-6 text-center">No submitters in scope for this period.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-wep-muted text-xs uppercase tracking-wide">
                    <th className="pb-2">Name</th><th className="pb-2">Type</th><th className="pb-2">Region</th>
                    <th className="pb-2">Submitted / Expected</th><th className="pb-2">Compliance</th>
                    <th className="pb-2">Late</th><th className="pb-2">Last Filed</th><th className="pb-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {compliance.reps.map((r: any) => (
                    <tr key={r.user_id} className="border-t border-wep-border">
                      <td className="py-2">
                        <div className="font-medium">{r.name}</div>
                        <div className="text-xs text-wep-muted">{r.email}</div>
                      </td>
                      <td className="py-2">
                        <span className="text-xs font-semibold px-1.5 py-0.5 rounded"
                          style={{ background: '#EEF2FF', color: '#4338CA' }}>{r.report_type}</span>
                      </td>
                      <td className="py-2 text-xs">{r.region ?? '—'}</td>
                      <td className="py-2 tabular-nums">{r.submitted_days} / {r.expected_days}</td>
                      <td className="py-2"><ComplianceBar pct={r.compliance_pct} /></td>
                      <td className="py-2 tabular-nums">{r.late_days}</td>
                      <td className="py-2 text-xs">{r.last_submitted_date ?? '—'}</td>
                      <td className="py-2">
                        {r.at_risk && (
                          <span className="text-xs font-semibold" style={{ color: '#DC2626' }}>⚠️ At risk</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {tab === 'fga' && (
        <div className="card overflow-x-auto">
          <div className="font-display font-bold text-wep-navy text-sm mb-3">
            FGA submission status — {period} (status/stage only, no score)
          </div>
          {fgaLoading ? (
            <div className="text-wep-muted text-sm py-6 text-center">Loading…</div>
          ) : !fgaQueue.length ? (
            <div className="text-wep-muted text-sm py-6 text-center">No FGA scores frozen for this period yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-wep-muted text-xs uppercase tracking-wide">
                  <th className="pb-2">Name</th><th className="pb-2">Stage</th>
                  <th className="pb-2">Mgr</th><th className="pb-2">HR</th><th className="pb-2">VP</th>
                  <th className="pb-2">Governance</th><th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {fgaQueue.map((r: any) => (
                  <tr key={r.result_id} className="border-t border-wep-border">
                    <td className="py-2">
                      <div className="font-medium">{r.name}</div>
                      <div className="text-xs text-wep-muted">{r.role}</div>
                    </td>
                    <td className="py-2 text-xs">{r.approval_status}</td>
                    <td className="py-2">{r.manager_reviewed ? '✅' : '—'}</td>
                    <td className="py-2">{r.hr_reviewed ? '✅' : '—'}</td>
                    <td className="py-2">{r.vp_reviewed ? '✅' : '—'}</td>
                    <td className="py-2">{r.governance_reviewed ? (r.governance_flag ? '🚩' : '✅') : '—'}</td>
                    <td className="py-2"><ReviewButton kind="fga" id={r.result_id} currentFlag={r.governance_flag} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
