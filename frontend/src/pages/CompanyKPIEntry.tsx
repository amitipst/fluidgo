import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// Company KPI Entry — added 2026-10-24 alongside the Company Revenue Target
// FGA parameter design. Deliberately separate from ManualKPIEntry.tsx: that
// screen enters a value FOR ONE PERSON; this one enters ONE ORG-WIDE number
// per period (backed by CompanyKPIEntry, not ManualMetricEntry — see that
// model's docstring). No target-user picker here by design — there's only
// one "whole company" to pick.
//
// Friendly labels for known company_manual.* keys — fall back to the raw
// metric_source so a newly-added key still renders (just less prettily)
// without a frontend change, same spirit as ManualKPIEntry driving itself
// off whatever Scoring Admin currently has active.
const FRIENDLY_LABEL: Record<string, string> = {
  'company_manual.revenue_target_achievement_pct':
    'Company Revenue Target — achievement % (vs. company revenue target for the period)',
}

function currentPeriod() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export default function CompanyKPIEntry() {
  const qc = useQueryClient()
  const [period, setPeriod] = useState(currentPeriod())
  const [values, setValues] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})

  const { data: allMetrics = [] } = useQuery({
    queryKey: ['scoring-metrics'],
    queryFn: () => api.get('/scoring/metrics').then(r => r.data),
  })
  const companyMetrics = (allMetrics as string[]).filter(m => m.startsWith('company_manual.'))

  const { data: existing } = useQuery({
    queryKey: ['company-entries', period],
    queryFn: () => api.get('/scoring/company-entry', { params: { period } }).then(r => r.data),
  })

  useEffect(() => {
    if (existing) {
      const v: Record<string, string> = {}
      const n: Record<string, string> = {}
      Object.entries(existing).forEach(([key, entry]: [string, any]) => {
        v[key] = String(entry.value)
        n[key] = entry.notes ?? ''
      })
      setValues(v); setNotes(n)
    } else {
      setValues({}); setNotes({})
    }
  }, [existing, period])

  const save = useMutation({
    mutationFn: (metric_key: string) => api.post('/scoring/company-entry', {
      metric_key, period,
      value: parseFloat(values[metric_key]) || 0,
      notes: notes[metric_key] || null,
    }),
    onSuccess: (_r, metric_key) => {
      setSaved(s => ({ ...s, [metric_key]: true }))
      setTimeout(() => setSaved(s => ({ ...s, [metric_key]: false })), 2000)
      qc.invalidateQueries({ queryKey: ['company-entries'] })
    },
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">🏢 Company KPI Entry</h1>
        <p className="text-wep-muted text-sm">
          One number per period for the whole company — feeds any FGA role whose scoring
          template references it. Not yet used by any live scorecard (see Scoring Admin to
          enable a company-performance parameter on a role).
        </p>
      </div>

      <div className="flex items-center gap-2 mb-5 flex-wrap">
        <input type="month" className="form-input py-2 text-sm w-40"
          value={period} onChange={e => setPeriod(e.target.value)} />
      </div>

      {companyMetrics.length === 0 && (
        <div className="card text-center text-wep-muted py-10">
          No company-wide KPI metrics are defined yet.
        </div>
      )}

      <div className="space-y-3">
        {companyMetrics.map((m: string) => (
          <div key={m} className="card">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-sm text-wep-text">{FRIENDLY_LABEL[m] ?? m}</div>
              {saved[m] && <span className="text-xs text-emerald-600 font-bold">✅ Saved</span>}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <input type="number" step="0.01" placeholder="Achievement %"
                className="form-input w-36 text-right"
                value={values[m] ?? ''}
                onChange={e => setValues(v => ({ ...v, [m]: e.target.value }))} />
              <input placeholder="Notes (optional — source, basis, context)"
                className="form-input flex-1 min-w-[180px]"
                value={notes[m] ?? ''}
                onChange={e => setNotes(n => ({ ...n, [m]: e.target.value }))} />
              <button onClick={() => save.mutate(m)}
                disabled={!values[m] || save.isPending}
                className="btn-primary text-xs px-3 py-2 disabled:opacity-40">
                Save
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
