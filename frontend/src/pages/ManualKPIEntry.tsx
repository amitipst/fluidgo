import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// Maps role -> the scoring role_key its FGA template lives under (mirrors
// scoring_engine.py's LEGACY_ROLE_FALLBACK — kept in sync manually since
// there's no endpoint yet that resolves this server-side for the caller).
const ROLE_TO_SCORING_KEY: Record<string, string> = {
  service_delivery_manager: 'service_delivery',
  rep: 'sales', inside_sales: 'sales', pre_sales: 'presales',
}

function currentPeriod() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export default function ManualKPIEntry() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [period, setPeriod] = useState(currentPeriod())
  const [targetUserId, setTargetUserId] = useState(user?.id ?? '')
  const [values, setValues] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})

  const isManagerTier = ['manager', 'service_delivery_manager', 'regional_manager', 'bu_head',
    'business_head', 'coo', 'ceo', 'super_admin'].includes(user?.role ?? '')

  // Team members whose role has a manual-entry FGA template (self always included)
  const { data: allUsers = [] } = useQuery({
    queryKey: ['users-for-kpi-entry'],
    queryFn: () => api.get('/users').then(r => r.data),
    enabled: isManagerTier,
  })
  const targets = isManagerTier
    ? allUsers.filter((u: any) => u.role in ROLE_TO_SCORING_KEY || u.id === user?.id)
    : [{ id: user?.id, name: user?.name, role: user?.role }]

  const targetUser = targets.find((u: any) => u.id === targetUserId) ??
    (user ? { id: user.id, name: user.name, role: user.role } : null)
  const roleKey = targetUser ? ROLE_TO_SCORING_KEY[targetUser.role] : undefined

  // The active template's manual.* fields for this role — adding/removing/
  // disabling a parameter in Scoring Admin changes this form automatically.
  const { data: fields = [] } = useQuery({
    queryKey: ['manual-entry-fields', roleKey],
    queryFn: () => api.get('/scoring/manual-entry/fields', { params: { role_key: roleKey } }).then(r => r.data),
    enabled: !!roleKey,
  })

  const { data: existing } = useQuery({
    queryKey: ['manual-entries', targetUser?.id, period],
    queryFn: () => api.get('/scoring/manual-entry', {
      params: { user_id: targetUser?.id, period },
    }).then(r => r.data),
    enabled: !!targetUser?.id,
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
  }, [existing, targetUser?.id, period])

  const save = useMutation({
    mutationFn: (metric_key: string) => api.post('/scoring/manual-entry', {
      user_id: targetUser?.id, metric_key, period,
      value: parseFloat(values[metric_key]) || 0,
      notes: notes[metric_key] || null,
    }),
    onSuccess: (_r, metric_key) => {
      setSaved(s => ({ ...s, [metric_key]: true }))
      setTimeout(() => setSaved(s => ({ ...s, [metric_key]: false })), 2000)
      qc.invalidateQueries({ queryKey: ['manual-entries'] })
    },
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">📋 Monthly KPI Entry</h1>
        <p className="text-wep-muted text-sm">
          Enter this period's achievement for each FGA parameter — the score is computed
          automatically from these values using the current Scoring Admin tier config.
        </p>
      </div>

      <div className="flex items-center gap-2 mb-5 flex-wrap">
        {isManagerTier && targets.length > 1 && (
          <select className="form-input py-2 text-sm w-56" value={targetUserId || user?.id}
            onChange={e => setTargetUserId(e.target.value)}>
            {targets.map((t: any) => (
              <option key={t.id} value={t.id}>{t.name}{t.id === user?.id ? ' (me)' : ''}</option>
            ))}
          </select>
        )}
        <input type="month" className="form-input py-2 text-sm w-40"
          value={period} onChange={e => setPeriod(e.target.value)} />
      </div>

      {!roleKey && (
        <div className="card text-center text-wep-muted py-10">
          {targetUser?.name ?? 'This role'} has no FGA template with manual KPI fields.
        </div>
      )}

      {roleKey && fields.length === 0 && (
        <div className="card text-center text-wep-muted py-10">
          No manual-entry parameters are active on this template right now — check Scoring Admin.
        </div>
      )}

      <div className="space-y-3">
        {fields.map((f: any) => (
          <div key={f.metric_source} className="card">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-semibold text-sm text-wep-text">{f.name}</div>
                <div className="text-[11px] text-wep-muted">Weight {f.weight_pct}%
                  {f.calc_type === 'tiered' && ' · tiered scoring'}</div>
              </div>
              {saved[f.metric_source] && <span className="text-xs text-emerald-600 font-bold">✅ Saved</span>}
            </div>

            {f.calc_type === 'tiered' && f.tiers?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {f.tiers.map((t: any, ti: number) => (
                  <span key={ti} className="text-[10px] px-2 py-0.5 rounded-full bg-wep-surface text-wep-muted border border-wep-border">
                    {t.label}: {t.formula === 'square' ? '(value/100)²' : `×${t.multiplier}`}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center gap-2 flex-wrap">
              <input type="number" step="0.01" placeholder="Value"
                className="form-input w-32 text-right"
                value={values[f.metric_source] ?? ''}
                onChange={e => setValues(v => ({ ...v, [f.metric_source]: e.target.value }))} />
              <input placeholder="Notes (optional — evidence, source, context)"
                className="form-input flex-1 min-w-[180px]"
                value={notes[f.metric_source] ?? ''}
                onChange={e => setNotes(n => ({ ...n, [f.metric_source]: e.target.value }))} />
              <button onClick={() => save.mutate(f.metric_source)}
                disabled={!values[f.metric_source] || save.isPending}
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
