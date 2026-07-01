import { useQuery } from '@tanstack/react-query'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

const intentColor: Record<string, string> = {
  hot: 'badge-hot', warm: 'badge-warm', cold: 'badge-cold', engaged: 'badge-engaged'
}
const intentLabel: Record<string, string> = {
  hot: '🔥 Hot', warm: '🌡 Warm', cold: '❄️ Cold', engaged: '💡 Engaged'
}

export default function Meetings() {
  const { data: meetings = [], isLoading } = useQuery({
    queryKey: ['meetings'],
    queryFn: () => api.get('/meetings').then(r => r.data)
  })

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">🤝 Meeting Intelligence</h1>
          <p className="text-wep-muted text-sm">{meetings.length} meetings logged · BANT-scored</p>
        </div>
      </div>

      {isLoading && <p className="text-wep-muted text-sm">Loading...</p>}

      <div className="space-y-3">
        {meetings.map((m: any) => {
          const bant = m.bant || {}
          const bantFilled = bant.bant_filled ?? 0
          return (
            <div key={m.id} className="card">
              <div className="flex items-start justify-between gap-2 flex-wrap">
                <div>
                  <div className="font-semibold text-wep-navy">{m.company}</div>
                  <div className="text-xs text-wep-muted mt-0.5">{m.date} · {m.meeting_type}</div>
                </div>
                <div className="flex items-center gap-2">
                  {m.ai_intent_score && (
                    <span className={intentColor[m.ai_intent_score]}>
                      {intentLabel[m.ai_intent_score]}
                    </span>
                  )}
                  {m.ai_closure_pct != null && (
                    <span className="text-xs font-bold text-wep-accent">{m.ai_closure_pct}%</span>
                  )}
                </div>
              </div>

              {m.discussion && (
                <p className="text-sm text-wep-muted mt-2 leading-relaxed">{m.discussion}</p>
              )}

              {/* BANT bar */}
              <div className="mt-3 flex items-center gap-2">
                <span className="text-[10px] text-wep-muted font-semibold uppercase tracking-wide">BANT</span>
                <div className="flex gap-1 flex-1">
                  {['Budget','Authority','Need','Timeline'].map((label, i) => {
                    const filled = [m.bant_budget, m.bant_authority, m.bant_need, m.bant_timeline][i]
                    return (
                      <div key={label} title={label}
                        className={`h-1.5 flex-1 rounded-full ${filled ? 'bg-wep-teal' : 'bg-wep-border'}`}/>
                    )
                  })}
                </div>
                <span className="text-[10px] text-wep-muted">{bantFilled}/4</span>
                {m.opportunity && <span className="text-[10px] text-wep-teal font-bold">● Opp</span>}
              </div>
            </div>
          )
        })}
        {!isLoading && meetings.length === 0 && (
          <div className="card text-center text-wep-muted py-12">
            No meetings logged yet. Submit your first DSR to add meetings.
          </div>
        )}
      </div>
    </div>
  )
}
