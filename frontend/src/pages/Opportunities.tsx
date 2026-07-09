import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'

const healthColor: Record<string, string> = {
  healthy: 'text-teal-600 bg-teal-50', watch: 'text-amber-600 bg-amber-50',
  at_risk: 'text-orange-600 bg-orange-50', critical: 'text-red-600 bg-red-50',
}
const stageColor: Record<string, string> = {
  hot: 'text-red-600 bg-red-50', warm: 'text-amber-600 bg-amber-50',
  cold: 'text-blue-500 bg-blue-50', closed_won: 'text-green-600 bg-green-50',
  closed_lost: 'text-gray-500 bg-gray-100'
}

// Funnel stage order for the progress bar. Deals converted from leads start at
// 'qualification'; the classic pipeline stages flow left→right toward close.
const STAGE_FLOW = ['qualification', 'cold', 'warm', 'hot', 'closed_won']
const STAGE_LABEL: Record<string, string> = {
  qualification: 'Qualify', cold: 'Cold', warm: 'Warm', hot: 'Hot', closed_won: 'Won',
}

function inr(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`
  return `₹${n.toLocaleString('en-IN')}`
}

function StageProgress({ stage }: { stage: string }) {
  // closed_lost is a dead end — show it distinctly
  if (stage === 'closed_lost') {
    return <div className="text-[11px] font-bold text-gray-400 mt-2">✕ Closed Lost</div>
  }
  const idx = STAGE_FLOW.indexOf(stage)
  const activeIdx = idx === -1 ? 0 : idx
  return (
    <div className="mt-3">
      <div className="flex items-center gap-1">
        {STAGE_FLOW.map((s, i) => {
          const done = i <= activeIdx
          const isCurrent = i === activeIdx
          return (
            <div key={s} className="flex-1 flex flex-col items-center gap-1">
              <div className="w-full h-1.5 rounded-full transition-colors"
                style={{ background: done ? (isCurrent ? '#F0115E' : '#0D9488') : '#E8DFF5' }} />
              <span className={`text-[9px] font-semibold ${isCurrent ? 'text-brand-pink' : done ? 'text-teal-600' : 'text-wep-muted'}`}>
                {STAGE_LABEL[s]}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Opportunities() {
  const qc = useQueryClient()
  const [practice, setPractice] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [healthContent, setHealthContent] = useState<Record<string, string>>({})

  const { data: deals = [], isLoading } = useQuery({
    queryKey: ['opportunities', practice, riskLevel],
    queryFn: () => api.get('/opportunities', {
      params: { practice: practice || undefined, risk_level: riskLevel || undefined }
    }).then(r => r.data)
  })

  const [healthError, setHealthError] = useState<Record<string, string>>({})

  const checkHealth = useMutation({
    mutationFn: (id: string) => api.get(`/opportunities/${id}/health`),
    onSuccess: (res, id) => {
      const rec = res.data.recommendation ?? res.data.ai_recommendation
      if (rec && !rec.toLowerCase().includes('unavailable')) {
        setHealthContent(prev => ({ ...prev, [id]: rec }))
        setHealthError(prev => ({ ...prev, [id]: '' }))
      } else {
        const score = res.data.deal_health ?? res.data.ai_deal_health ?? '—'
        setHealthError(prev => ({ ...prev, [id]: `Deal health score: ${score}/100. AI coaching unavailable (Ollama model loading — try again in a few minutes).` }))
      }
      qc.invalidateQueries({ queryKey: ['opportunities'] })
    },
    onError: (_err, id) => {
      setHealthError(prev => ({ ...prev, [id]: 'AI analysis unavailable right now. The local Ollama model may still be loading. Deal health score is shown above.' }))
    }
  })

  const practices = Array.from(new Set(deals.map((d: any) => d.practice).filter(Boolean))) as string[]

  // ── Portfolio summary (the value-add for a Business Head at a glance) ──────
  const openDeals = deals.filter((d: any) => !['closed_won', 'closed_lost'].includes(d.stage))
  const totalValue = openDeals.reduce((s: number, d: any) => s + Number(d.deal_value || 0), 0)
  // Weighted forecast: value × closure probability (falls back to deal-health as a proxy)
  const weighted = openDeals.reduce((s: number, d: any) => {
    const pct = d.ai_closure_pct ?? d.ai_deal_health ?? 0
    return s + Number(d.deal_value || 0) * (pct / 100)
  }, 0)
  const atRisk = deals.filter((d: any) =>
    ['at_risk', 'critical'].includes(d.ai_deal_health_label) || d.risk_level === 'high' || d.risk_level === 'critical'
  ).length
  const wonValue = deals.filter((d: any) => d.stage === 'closed_won')
    .reduce((s: number, d: any) => s + Number(d.deal_value || 0), 0)

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">🧭 Opportunities</h1>
          <p className="text-wep-muted text-sm">{deals.length} opportunities · {openDeals.length} open</p>
        </div>
        <div className="flex gap-2">
          <select className="form-input text-sm" value={practice} onChange={e => setPractice(e.target.value)}>
            <option value="">All practices</option>
            {practices.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <select className="form-input text-sm" value={riskLevel} onChange={e => setRiskLevel(e.target.value)}>
            <option value="">All risk levels</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>

      {/* Portfolio summary bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card py-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-wep-muted">Open Pipeline</div>
          <div className="font-display font-bold text-xl text-wep-navy mt-1">{inr(totalValue)}</div>
        </div>
        <div className="card py-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-wep-muted">Weighted Forecast</div>
          <div className="font-display font-bold text-xl mt-1" style={{ color: '#0D9488' }}>{inr(weighted)}</div>
          <div className="text-[9px] text-wep-muted">value × closure %</div>
        </div>
        <div className="card py-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-wep-muted">At Risk</div>
          <div className="font-display font-bold text-xl mt-1" style={{ color: atRisk > 0 ? '#DC2626' : '#0D9488' }}>{atRisk}</div>
          <div className="text-[9px] text-wep-muted">deals need attention</div>
        </div>
        <div className="card py-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-wep-muted">Won</div>
          <div className="font-display font-bold text-xl mt-1" style={{ color: '#059669' }}>{inr(wonValue)}</div>
        </div>
      </div>

      <div className="space-y-3">
        {deals.map((d: any) => {
          const closurePct = d.ai_closure_pct ?? d.ai_deal_health
          return (
          <div key={d.id} className="card">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div className="min-w-0">
                <div className="font-semibold text-wep-navy">{d.company}</div>
                <div className="text-xs text-wep-muted mt-0.5 flex flex-wrap gap-x-2">
                  {d.practice && <span>🏷️ {d.practice}</span>}
                  {d.solution_area && <span>· {d.solution_area}</span>}
                  {d.deal_value ? <span className="font-semibold text-wep-text">· {inr(Number(d.deal_value))}</span> : <span className="text-amber-600">· no value set</span>}
                  {d.closure_eta && <span>· 🎯 {d.closure_eta}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`text-[11px] font-bold px-2 py-1 rounded-lg ${stageColor[d.stage] ?? 'bg-purple-50 text-purple-600'}`}>
                  {d.stage?.replace('_', ' ').toUpperCase()}
                </span>
                {d.ai_deal_health != null && (
                  <span className={`text-[11px] font-bold px-2 py-1 rounded-lg ${healthColor[d.ai_deal_health_label] ?? 'bg-gray-100 text-gray-500'}`}>
                    🩺 {d.ai_deal_health}/100
                  </span>
                )}
              </div>
            </div>

            <StageProgress stage={d.stage} />

            {d.todays_update && (
              <p className="text-xs text-wep-muted mt-2.5 line-clamp-1">📝 {d.todays_update}</p>
            )}
            {d.next_step && (
              <p className="text-xs mt-1"><span className="text-brand-pink">→ {d.next_step}</span></p>
            )}

            {(d.risk_level || d.decision_maker || d.competition) && (
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-wep-muted">
                {d.risk_level && <span>⚠️ Risk: {d.risk_level}</span>}
                {d.decision_maker && <span>👤 DM: {d.decision_maker}</span>}
                {d.competition && <span>⚔️ vs {d.competition}</span>}
              </div>
            )}

            <div className="mt-3 flex items-center justify-between">
              <button
                onClick={() => checkHealth.mutate(d.id)}
                disabled={checkHealth.isPending}
                className="text-xs text-wep-accent hover:text-wep-electric transition-colors font-medium disabled:opacity-50">
                {checkHealth.isPending && checkHealth.variables === d.id ? '⏳ Checking...' : '✨ AI Deal Health Coaching'}
              </button>
              {closurePct != null && (
                <span className="text-[11px] text-wep-muted">Closure likelihood: <strong className="text-wep-text">{closurePct}%</strong></span>
              )}
            </div>

            {healthContent[d.id] && (
              <div className="mt-3 bg-wep-surface border border-wep-border rounded-xl p-3 text-xs text-wep-text leading-relaxed whitespace-pre-wrap">
                {healthContent[d.id]}
              </div>
            )}
            {healthError[d.id] && (
              <div className="mt-3 flex items-start gap-2 px-3 py-2.5 rounded-xl text-xs"
                style={{ background: '#FEF3C7', color: '#92400E', border: '1px solid #FDE68A' }}>
                <span className="shrink-0">⚠️</span>
                <span>{healthError[d.id]}</span>
              </div>
            )}
          </div>
          )
        })}
        {!isLoading && deals.length === 0 && (
          <div className="card text-center text-wep-muted py-12">No opportunities in view yet.</div>
        )}
      </div>
    </div>
  )
}
