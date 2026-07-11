import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

interface Tier {
  label: string
  min?: number | null
  max?: number | null
  multiplier?: number | null
  formula?: string | null   // "square" = multiplier = (value/100)**2
}
interface Param {
  id?: string
  name: string
  weight_pct: number
  metric_source: string
  calc_type: 'pct' | 'tiered'
  tiers?: Tier[] | null
  is_active: boolean
  sort_order: number
}

// Roles that can access Scoring Admin
const SCORING_ROLES = ['regional_manager', 'bu_head', 'business_head', 'practice_head', 'ceo', 'super_admin']

const blankParam = (sort_order: number): Param => ({
  name: '', weight_pct: 0, metric_source: '', calc_type: 'pct', tiers: null, is_active: true, sort_order,
})
const blankTier = (): Tier => ({ label: '', min: null, max: null, multiplier: 0, formula: null })

export default function ScoringAdmin() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [params, setParams] = useState<Param[]>([])
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [showNewTemplate, setShowNewTemplate] = useState(false)
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newRoleKey, setNewRoleKey] = useState('')
  const authorized = SCORING_ROLES.includes(user?.role ?? '')

  const { data: templates = [] } = useQuery({
    queryKey: ['scoring-templates'],
    queryFn: () => api.get('/scoring/templates').then(r => r.data),
    enabled: authorized,
  })
  const { data: metrics = [] } = useQuery({
    queryKey: ['scoring-metrics'],
    queryFn: () => api.get('/scoring/metrics').then(r => r.data),
    enabled: authorized,
  })

  if (!authorized) {
    return (
      <div className="p-4 md:p-6 max-w-4xl mx-auto">
        <div className="card text-center text-wep-muted py-12">
          🔒 Scoring Admin is available to Regional Manager, Business Head, Practice Head, CEO, and Super Admin.
        </div>
      </div>
    )
  }

  const selected = templates.find((t: any) => t.id === selectedId)

  useEffect(() => {
    if (selected) {
      setParams(selected.parameters.map((p: any) => ({
        ...p, tiers: p.tiers ? p.tiers.map((t: any) => ({ ...t })) : null,
      })))
    }
  }, [selectedId, templates])

  // Only ACTIVE parameters need to sum to 100 — matches backend validation.
  const activeWeight = params.filter(p => p.is_active).reduce((a, p) => a + Number(p.weight_pct || 0), 0)

  const save = useMutation({
    mutationFn: () => api.patch(`/scoring/templates/${selectedId}/parameters`,
      params.map(({ name, weight_pct, metric_source, calc_type, tiers, is_active, sort_order }) => ({
        name, weight_pct: Number(weight_pct), metric_source, calc_type,
        tiers: calc_type === 'tiered' ? tiers : null, is_active, sort_order,
      }))),
    onSuccess: () => {
      setSaved(true); setError('')
      qc.invalidateQueries({ queryKey: ['scoring-templates'] })
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (err: any) => setError(getErrorMessage(err, 'Save failed')),
  })

  const createTemplate = useMutation({
    mutationFn: () => api.post('/scoring/templates', {
      name: newTemplateName, role_key: newRoleKey,
      parameters: [{ name: 'New Parameter', weight_pct: 100, metric_source: '',
                     calc_type: 'pct', is_active: true, sort_order: 1 }],
    }),
    onSuccess: (r: any) => {
      qc.invalidateQueries({ queryKey: ['scoring-templates'] })
      setShowNewTemplate(false); setNewTemplateName(''); setNewRoleKey('')
      setSelectedId(r.data.id)
    },
    onError: (err: any) => setError(getErrorMessage(err, 'Could not create template')),
  })

  function updateParam(i: number, patch: Partial<Param>) {
    setParams(prev => prev.map((x, j) => j === i ? { ...x, ...patch } : x))
  }
  function addParam() {
    setParams(prev => [...prev, blankParam(prev.length + 1)])
  }
  function removeParam(i: number) {
    setParams(prev => prev.filter((_, j) => j !== i))
  }
  function setCalcType(i: number, calc_type: 'pct' | 'tiered') {
    setParams(prev => prev.map((x, j) => j !== i ? x : {
      ...x, calc_type,
      tiers: calc_type === 'tiered' ? (x.tiers?.length ? x.tiers : [blankTier()]) : null,
    }))
  }
  function updateTier(pi: number, ti: number, patch: Partial<Tier>) {
    setParams(prev => prev.map((p, j) => j !== pi ? p : {
      ...p, tiers: (p.tiers || []).map((t, k) => k === ti ? { ...t, ...patch } : t),
    }))
  }
  function addTier(pi: number) {
    setParams(prev => prev.map((p, j) => j !== pi ? p : { ...p, tiers: [...(p.tiers || []), blankTier()] }))
  }
  function removeTier(pi: number, ti: number) {
    setParams(prev => prev.map((p, j) => j !== pi ? p : { ...p, tiers: (p.tiers || []).filter((_, k) => k !== ti) }))
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <datalist id="metric-source-options">
        {metrics.map((m: string) => <option key={m} value={m} />)}
      </datalist>

      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">⚙️ Scoring Admin</h1>
        <p className="text-wep-muted text-sm">Edit FGA weights — config-driven, any number of parameters, no code changes needed</p>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap items-center">
        {templates.map((t: any) => (
          <button key={t.id} onClick={() => setSelectedId(t.id)}
            className={`text-sm font-medium px-3 py-2 rounded-lg border transition-colors
              ${selectedId === t.id ? 'border-wep-accent bg-wep-accent/10 text-wep-accent' : 'border-wep-border text-wep-muted'}`}>
            {t.name} <span className="text-[10px] opacity-60">(v{t.version})</span>
          </button>
        ))}
        <button onClick={() => setShowNewTemplate(v => !v)} className="btn-outline text-sm">
          {showNewTemplate ? '✕ Cancel' : '➕ New Template'}
        </button>
      </div>

      {showNewTemplate && (
        <div className="card mb-4 flex items-center gap-2 flex-wrap">
          <input placeholder="Template name e.g. 'Service Delivery FGA v1'" value={newTemplateName}
            onChange={e => setNewTemplateName(e.target.value)} className="form-input flex-1 min-w-[220px]" />
          <input placeholder="role_key e.g. 'service_delivery'" value={newRoleKey}
            onChange={e => setNewRoleKey(e.target.value)} className="form-input w-56" />
          <button onClick={() => createTemplate.mutate()}
            disabled={!newTemplateName || !newRoleKey || createTemplate.isPending}
            className="btn-primary text-sm disabled:opacity-40">
            {createTemplate.isPending ? 'Creating…' : 'Create'}
          </button>
        </div>
      )}

      {selected && (
        <div className="card">
          <div className="space-y-3">
            {params.map((p, i) => (
              <div key={i} className={`border rounded-xl p-3 ${p.is_active ? 'border-wep-border' : 'border-wep-border/40 bg-wep-surface/40 opacity-60'}`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <input placeholder="Parameter name" value={p.name}
                    onChange={e => updateParam(i, { name: e.target.value })}
                    className="form-input flex-1 min-w-[180px]" />

                  <select value={p.calc_type} onChange={e => setCalcType(i, e.target.value as 'pct' | 'tiered')}
                    className="form-input w-44">
                    <option value="pct">Simple % achievement</option>
                    <option value="tiered">Tiered / Banded</option>
                  </select>

                  <input list="metric-source-options" placeholder="metric key or manual.xyz"
                    value={p.metric_source} onChange={e => updateParam(i, { metric_source: e.target.value })}
                    className="form-input w-56" />

                  <div className="flex items-center gap-1">
                    <input type="number" min="0" max="100" className="form-input w-20 text-center"
                      value={p.weight_pct}
                      onChange={e => updateParam(i, { weight_pct: Number(e.target.value) })} />
                    <span className="text-sm text-wep-muted">%</span>
                  </div>

                  <label className="flex items-center gap-1.5 text-xs font-medium text-wep-muted">
                    <input type="checkbox" checked={p.is_active}
                      onChange={e => updateParam(i, { is_active: e.target.checked })} />
                    {p.is_active ? 'Active' : 'Disabled'}
                  </label>

                  <button onClick={() => removeParam(i)} title="Remove parameter"
                    className="text-red-500 hover:bg-red-50 rounded-lg px-2 py-1 text-xs font-bold">🗑️</button>
                </div>

                {p.calc_type === 'tiered' && (
                  <div className="mt-3 pl-3 border-l-2 border-wep-border space-y-2">
                    <div className="text-[10px] uppercase tracking-wide text-wep-muted font-bold">
                      Tier bands — achievement value → multiplier (weight × multiplier = contribution)
                    </div>
                    {(p.tiers || []).map((t, ti) => (
                      <div key={ti} className="flex items-center gap-2 flex-wrap text-sm">
                        <input placeholder="Label e.g. '<80%'" value={t.label}
                          onChange={e => updateTier(i, ti, { label: e.target.value })}
                          className="form-input w-32 py-1" />
                        <input type="number" placeholder="Min" value={t.min ?? ''}
                          onChange={e => updateTier(i, ti, { min: e.target.value === '' ? null : Number(e.target.value) })}
                          className="form-input w-20 py-1" />
                        <span className="text-wep-muted text-xs">to</span>
                        <input type="number" placeholder="Max (blank=open)" value={t.max ?? ''}
                          onChange={e => updateTier(i, ti, { max: e.target.value === '' ? null : Number(e.target.value) })}
                          className="form-input w-28 py-1" />
                        {t.formula === 'square' ? (
                          <span className="text-xs px-2 py-1 rounded bg-wep-accent/10 text-wep-accent font-medium">
                            = (value/100)²
                          </span>
                        ) : (
                          <input type="number" step="0.05" placeholder="Multiplier" value={t.multiplier ?? ''}
                            onChange={e => updateTier(i, ti, { multiplier: e.target.value === '' ? null : Number(e.target.value) })}
                            className="form-input w-24 py-1" />
                        )}
                        <label className="flex items-center gap-1 text-[11px] text-wep-muted">
                          <input type="checkbox" checked={t.formula === 'square'}
                            onChange={e => updateTier(i, ti, {
                              formula: e.target.checked ? 'square' : null,
                              multiplier: e.target.checked ? null : (t.multiplier ?? 0),
                            })} />
                          square of achievement
                        </label>
                        <button onClick={() => removeTier(i, ti)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                      </div>
                    ))}
                    <button onClick={() => addTier(i)} className="text-xs text-wep-accent font-semibold">+ Add tier</button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <button onClick={addParam} className="btn-outline text-sm mt-3">➕ Add Parameter</button>

          <div className={`mt-4 text-sm font-semibold ${activeWeight === 100 ? 'text-wep-teal' : 'text-red-500'}`}>
            Total weight (active only): {activeWeight}% {activeWeight !== 100 && '(active weights must sum to 100 to save)'}
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          {saved && <p className="text-wep-teal text-sm mt-2">✅ Saved</p>}

          <button onClick={() => save.mutate()} disabled={activeWeight !== 100 || save.isPending}
            className="btn-primary mt-4 disabled:opacity-40">
            {save.isPending ? 'Saving...' : 'Save Weights'}
          </button>
        </div>
      )}

      {!selected && templates.length > 0 && (
        <div className="card text-center text-wep-muted py-12">Select a template above to edit its weights, or create a new one.</div>
      )}
    </div>
  )
}
