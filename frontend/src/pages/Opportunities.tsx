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
        // AI unavailable — show rule-based score only
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

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">🧭 Opportunities</h1>
          <p className="text-wep-muted text-sm">{deals.length} opportunities in view</p>
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

      <div className="space-y-3">
        {deals.map((d: any) => (
          <div key={d.id} className="card">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <div className="font-semibold text-wep-navy">{d.company}</div>
                <div className="text-xs text-wep-muted mt-0.5 flex flex-wrap gap-x-2">
                  {d.practice && <span>🏷️ {d.practice}</span>}
                  {d.oem && <span>· {d.oem}</span>}
                  {d.solution_area && <span>· {d.solution_area}</span>}
                  {d.deal_value && <span>· ₹{Number(d.deal_value).toLocaleString('en-IN')}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-bold px-2 py-1 rounded-lg ${stageColor[d.stage] ?? 'bg-gray-100 text-gray-600'}`}>
                  {d.stage?.replace('_', ' ').toUpperCase()}
                </span>
                {d.ai_deal_health != null && (
                  <span className={`text-[11px] font-bold px-2 py-1 rounded-lg ${healthColor[d.ai_deal_health_label] ?? 'bg-gray-100 text-gray-500'}`}>
                    🩺 {d.ai_deal_health}/100
                  </span>
                )}
              </div>
            </div>

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
                {checkHealth.isPending && checkHealth.variables === d.id ? '⏳ Checking...' : '✨ Check Deal Health'}
              </button>
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
        ))}
        {!isLoading && deals.length === 0 && (
          <div className="card text-center text-wep-muted py-12">No opportunities in view yet.</div>
        )}
      </div>
    </div>
  )
}
