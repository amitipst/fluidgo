import { useQuery } from '@tanstack/react-query'
import api from '@/hooks/useApi'

export default function Pipeline() {
  const { data: deals = [], isLoading } = useQuery({
    queryKey: ['pipeline'],
    queryFn: () => api.get('/pipeline').then(r => r.data)
  })

  const stageColor: Record<string, string> = {
    hot: 'text-red-600 bg-red-50', warm: 'text-amber-600 bg-amber-50',
    cold: 'text-blue-500 bg-blue-50', closed_won: 'text-green-600 bg-green-50',
    closed_lost: 'text-gray-500 bg-gray-100'
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">📊 Pipeline</h1>
          <p className="text-wep-muted text-sm">{deals.length} active deals</p>
        </div>
      </div>

      <div className="space-y-3">
        {deals.map((d: any) => (
          <div key={d.id} className="card">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-wep-navy">{d.company}</div>
                <div className="text-xs text-wep-muted mt-0.5">
                  ETA: {d.closure_eta ?? 'Not set'}
                  {d.deal_value && ` · ₹${Number(d.deal_value).toLocaleString('en-IN')}`}
                </div>
              </div>
              <span className={`text-[11px] font-bold px-2 py-1 rounded-lg ${stageColor[d.stage] ?? 'bg-gray-100 text-gray-600'}`}>
                {d.stage?.replace('_',' ').toUpperCase()}
              </span>
            </div>
            {d.todays_update && <p className="text-sm text-wep-muted mt-2">{d.todays_update}</p>}
            {d.roadblock && <div className="mt-2 text-xs text-red-500 font-medium">⚠️ Roadblock reported</div>}
            {d.next_step && <div className="mt-1 text-xs text-wep-accent">→ {d.next_step}</div>}
          </div>
        ))}
        {!isLoading && deals.length === 0 && (
          <div className="card text-center text-wep-muted py-12">No pipeline deals yet.</div>
        )}
      </div>
    </div>
  )
}
