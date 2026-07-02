import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'

function StatCard({ label, value, accent, icon }: { label: string; value: string; accent: string; icon: string }) {
  return (
    <div className={`card relative overflow-hidden border-t-2 ${accent}`}>
      <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">{label}</div>
      <div className="font-display font-bold text-2xl text-wep-navy">{value}</div>
      <div className="absolute right-4 top-1/2 -translate-y-1/2 text-4xl opacity-10">{icon}</div>
    </div>
  )
}

const inr = (n: number) => `₹${Number(n || 0).toLocaleString('en-IN')}`

export default function RevenueIntelligence() {
  const now = new Date()
  const [period, setPeriod] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)

  const { data, isLoading } = useQuery({
    queryKey: ['revenue-analytics', period],
    queryFn: () => api.get('/analytics/revenue', { params: { period } }).then(r => r.data)
  })

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">📊 Revenue Intelligence</h1>
          <p className="text-wep-muted text-sm">Forecast, target achievement &amp; pipeline coverage</p>
        </div>
        <input type="month" value={period} onChange={e => setPeriod(e.target.value)} className="form-input text-sm w-auto" />
      </div>

      {isLoading ? (
        <div className="card text-center text-wep-muted py-12">Loading...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            <StatCard label="Revenue" value={inr(data?.revenue)} accent="border-t-wep-teal" icon="💰" />
            <StatCard label="Target" value={inr(data?.target)} accent="border-t-wep-accent" icon="🎯" />
            <StatCard label="Gap" value={inr(data?.gap)} accent={data?.gap > 0 ? 'border-t-red-400' : 'border-t-wep-teal'} icon="📉" />
            <StatCard label="Target Achievement" value={`${data?.target_achievement_pct ?? 0}%`} accent="border-t-wep-electric" icon="⚡" />
            <StatCard label="Pipeline Coverage" value={`${data?.pipeline_coverage_ratio ?? 0}x`} accent="border-t-wep-amber" icon="🧮" />
            <StatCard label="Win %" value={`${data?.win_pct ?? 0}%`} accent="border-t-purple-400" icon="🏆" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="card">
              <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Avg Deal Size</div>
              <div className="font-display font-bold text-xl text-wep-navy">{inr(data?.avg_deal_size)}</div>
            </div>
            <div className="card">
              <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">Open Pipeline</div>
              <div className="font-display font-bold text-xl text-wep-navy">
                {data?.open_deal_count ?? 0} deals · {inr(data?.pipeline_value)}
              </div>
            </div>
          </div>

          {data?.target === 0 && (
            <p className="text-wep-muted text-xs mt-4 text-center">
              No revenue target set for this period — target/gap will read as 0 until one is added via the scoring/targets API.
            </p>
          )}
        </>
      )}
    </div>
  )
}
