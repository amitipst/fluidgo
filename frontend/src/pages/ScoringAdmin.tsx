import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

interface Param { id?: string; name: string; weight_pct: number; metric_source: string; calc_type: string; sort_order: number }

const ADMIN_ORG_ROLES = ['admin', 'super_admin', 'practice_head']

export default function ScoringAdmin() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [params, setParams] = useState<Param[]>([])
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const authorized = ADMIN_ORG_ROLES.includes(user?.org_role_key ?? '')

  const { data: templates = [] } = useQuery({
    queryKey: ['scoring-templates'],
    queryFn: () => api.get('/scoring/templates').then(r => r.data),
    enabled: authorized
  })
  const { data: metrics = [] } = useQuery({
    queryKey: ['scoring-metrics'],
    queryFn: () => api.get('/scoring/metrics').then(r => r.data),
    enabled: authorized
  })

  if (!authorized) {
    return (
      <div className="p-4 md:p-6 max-w-4xl mx-auto">
        <div className="card text-center text-wep-muted py-12">
          🔒 Scoring Admin is only available to Admin, Super Admin, or Practice Head roles.
        </div>
      </div>
    )
  }

  const selected = templates.find((t: any) => t.id === selectedId)

  useEffect(() => {
    if (selected) setParams(selected.parameters.map((p: any) => ({ ...p })))
  }, [selectedId, templates])

  const totalWeight = params.reduce((a, p) => a + Number(p.weight_pct || 0), 0)

  const save = useMutation({
    mutationFn: () => api.patch(`/scoring/templates/${selectedId}/parameters`,
      params.map(({ name, weight_pct, metric_source, calc_type, sort_order }) =>
        ({ name, weight_pct: Number(weight_pct), metric_source, calc_type, sort_order }))),
    onSuccess: () => {
      setSaved(true); setError('')
      qc.invalidateQueries({ queryKey: ['scoring-templates'] })
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Save failed')
  })

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">⚙️ Scoring Admin</h1>
        <p className="text-wep-muted text-sm">Edit Sales/PreSales FGA weights — config-driven, no code changes needed</p>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {templates.map((t: any) => (
          <button key={t.id} onClick={() => setSelectedId(t.id)}
            className={`text-sm font-medium px-3 py-2 rounded-lg border transition-colors
              ${selectedId === t.id ? 'border-wep-accent bg-wep-accent/10 text-wep-accent' : 'border-wep-border text-wep-muted'}`}>
            {t.name} <span className="text-[10px] opacity-60">(v{t.version})</span>
          </button>
        ))}
      </div>

      {selected && (
        <div className="card">
          <div className="space-y-3">
            {params.map((p, i) => (
              <div key={i} className="flex items-center gap-3 flex-wrap">
                <input className="form-input flex-1 min-w-[160px]" value={p.name}
                  onChange={e => setParams(prev => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                <select className="form-input w-56" value={p.metric_source}
                  onChange={e => setParams(prev => prev.map((x, j) => j === i ? { ...x, metric_source: e.target.value } : x))}>
                  {metrics.map((m: string) => <option key={m} value={m}>{m}</option>)}
                </select>
                <div className="flex items-center gap-1">
                  <input type="number" min="0" max="100" className="form-input w-20 text-center" value={p.weight_pct}
                    onChange={e => setParams(prev => prev.map((x, j) => j === i ? { ...x, weight_pct: Number(e.target.value) } : x))} />
                  <span className="text-sm text-wep-muted">%</span>
                </div>
              </div>
            ))}
          </div>

          <div className={`mt-4 text-sm font-semibold ${totalWeight === 100 ? 'text-wep-teal' : 'text-red-500'}`}>
            Total weight: {totalWeight}% {totalWeight !== 100 && '(must sum to 100 to save)'}
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          {saved && <p className="text-wep-teal text-sm mt-2">✅ Saved</p>}

          <button onClick={() => save.mutate()} disabled={totalWeight !== 100 || save.isPending}
            className="btn-primary mt-4 disabled:opacity-40">
            {save.isPending ? 'Saving...' : 'Save Weights'}
          </button>
        </div>
      )}

      {!selected && templates.length > 0 && (
        <div className="card text-center text-wep-muted py-12">Select a template above to edit its weights.</div>
      )}
    </div>
  )
}
