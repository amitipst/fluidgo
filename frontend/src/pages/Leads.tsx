import { useQuery } from '@tanstack/react-query'
import api from '@/hooks/useApi'

export default function Leads() {
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: () => api.get('/leads').then(r => r.data)
  })

  const sourceIcon: Record<string, string> = {
    Call: '📞', Visit: '🏢', Referral: '🤝', LinkedIn: '💼', Email: '📧'
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-xl text-wep-navy">🎯 New Leads</h1>
          <p className="text-wep-muted text-sm">{leads.length} leads in pipeline</p>
        </div>
      </div>

      <div className="space-y-3">
        {leads.map((l: any) => (
          <div key={l.id} className="card">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <div className="font-semibold text-wep-navy">{l.company}</div>
                <div className="text-xs text-wep-muted mt-0.5">
                  {l.contact_name} · Added {l.date}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs bg-wep-surface border border-wep-border px-2 py-1 rounded-lg text-wep-muted font-medium">
                  {sourceIcon[l.source] ?? '📌'} {l.source}
                </span>
                {l.ai_lead_score != null && (
                  <span className={`text-xs font-bold px-2 py-1 rounded-lg ${
                    l.ai_lead_score >= 70 ? 'bg-teal-50 text-teal-600' :
                    l.ai_lead_score >= 50 ? 'bg-amber-50 text-amber-600' :
                    'bg-gray-100 text-gray-500'
                  }`}>
                    {l.ai_lead_score} score
                  </span>
                )}
              </div>
            </div>
            {l.requirement && (
              <p className="text-sm text-wep-muted mt-2">📋 {l.requirement}</p>
            )}
            {l.next_action && (
              <div className="mt-2 text-xs text-wep-accent font-medium">
                → {l.next_action}
                {l.next_action_date && <span className="text-wep-muted font-normal"> · by {l.next_action_date}</span>}
              </div>
            )}
          </div>
        ))}
        {!isLoading && leads.length === 0 && (
          <div className="card text-center text-wep-muted py-12">
            No leads yet. Add new leads through your DSR submission.
          </div>
        )}
      </div>
    </div>
  )
}
