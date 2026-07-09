import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'
import { useAuthStore } from '@/store/authStore'
import api from '@/hooks/useApi'

function MiniStat({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="card text-center">
      <div className="text-xs text-wep-muted uppercase tracking-wide mb-1">{label}</div>
      <div className={`font-display font-bold text-2xl ${color}`}>{value}</div>
    </div>
  )
}

function inr(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`
  return `₹${Math.round(n).toLocaleString('en-IN')}`
}

const STAGE_COLORS = ['#92278E', '#F0115E', '#0EA5E9', '#0D9488']

function ConversionFunnel() {
  const { data } = useQuery({
    queryKey: ['funnel'],
    queryFn: () => api.get('/analytics/funnel').then(r => r.data),
  })
  if (!data) return null
  const stages = data.stages ?? []
  const maxCount = Math.max(...stages.map((s: any) => s.count), 1)

  return (
    <div className="card mb-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="font-semibold text-sm text-wep-navy">
          🎯 {data.is_team ? 'Team' : 'My'} Conversion Funnel
        </div>
        <div className="text-xs text-wep-muted">
          Overall: <strong className="text-wep-navy">{data.overall_conversion}%</strong> meeting→win
          {data.open_pipeline_value > 0 && <> · Open: <strong className="text-wep-navy">{inr(data.open_pipeline_value)}</strong></>}
        </div>
      </div>
      <div className="space-y-2.5">
        {stages.map((s: any, i: number) => {
          const widthPct = Math.max(8, Math.round((s.count / maxCount) * 100))
          return (
            <div key={s.label} className="flex items-center gap-3">
              <div className="w-16 text-xs font-semibold text-wep-muted shrink-0">{s.label}</div>
              <div className="flex-1 flex items-center gap-2">
                <div className="h-8 rounded-lg flex items-center px-3 text-white text-sm font-bold transition-all"
                  style={{ width: `${widthPct}%`, background: STAGE_COLORS[i], minWidth: 44 }}>
                  {s.count}
                </div>
                {s.conv_from_prev != null && (
                  <span className={`text-[11px] font-semibold ${
                    s.conv_from_prev >= 50 ? 'text-teal-600' : s.conv_from_prev >= 25 ? 'text-amber-600' : 'text-red-500'
                  }`}>
                    {s.conv_from_prev}%
                  </span>
                )}
                {s.value != null && s.value > 0 && (
                  <span className="text-[11px] text-wep-muted">· {inr(s.value)}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {maxCount === 1 && stages[0]?.count === 0 && (
        <p className="text-xs text-wep-muted mt-3">
          Log meetings and convert them to leads/deals to see your conversion funnel come alive.
        </p>
      )}
    </div>
  )
}

export default function Analytics() {
  const { user } = useAuthStore()
  const { data: records = [] } = useQuery({
    queryKey: ['analytics', user?.id],
    queryFn: () => api.get(`/analytics/rep/${user?.id}`).then(r => r.data),
    enabled: !!user?.id
  })

  const working = records.filter((d: any) => d.status === 'working')
  const isTeamView = records.length > 0 && records[0]?.is_team_aggregate === true

  const totals = working.reduce((a: any, d: any) => ({
    calls: a.calls + d.calls,
    visits: a.visits + d.visits,
    followups: a.followups + d.followups,
    leads: a.leads + d.new_leads,
    proposals: a.proposals + d.proposals,
  }), { calls: 0, visits: 0, followups: 0, leads: 0, proposals: 0 })

  const avgRigor = working.length
    ? Math.round(working.reduce((a: number, d: any) => a + d.rigor_score, 0) / working.length)
    : 0

  const chartData = records.slice(-15).map((d: any) => ({
    date: d.date?.slice(5),
    calls: d.calls,
    followups: d.followups,
    rigor: d.rigor_score >= 0 ? d.rigor_score : 0,
  }))

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">📈 Analytics</h1>
        <p className="text-wep-muted text-sm">
          {isTeamView ? "Team-wide · " : ''}Funnel conversion & daily activity
        </p>
      </div>

      <ConversionFunnel />

      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
        <MiniStat label="Calls"      value={totals.calls}     color="text-wep-accent"/>
        <MiniStat label="Visits"     value={totals.visits}    color="text-wep-teal"/>
        <MiniStat label="Follow-Ups" value={totals.followups} color="text-wep-amber"/>
        <MiniStat label="Leads"      value={totals.leads}     color="text-wep-electric"/>
        <MiniStat label="Proposals"  value={totals.proposals} color="text-purple-500"/>
        <MiniStat label="Avg Rigor"  value={`${avgRigor}/100`} color={avgRigor >= 80 ? 'text-wep-teal' : avgRigor >= 60 ? 'text-wep-amber' : 'text-wep-red'}/>
      </div>

      <div className="card mb-4">
        <div className="font-semibold text-sm text-wep-navy mb-4">📞 Daily Calls & Follow-Ups</div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ left: -20 }}>
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Bar dataKey="calls"     fill="#0078D4" radius={[3,3,0,0]} name="Calls"/>
            <Bar dataKey="followups" fill="#00C2A8" radius={[3,3,0,0]} name="Follow-ups"/>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="font-semibold text-sm text-wep-navy mb-4">⚡ Rigor Score Trend</div>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={chartData} margin={{ left: -20 }}>
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Line type="monotone" dataKey="rigor" stroke="#00B4E6" strokeWidth={2}
              dot={{ fill: '#00B4E6', r: 3 }} name="Rigor Score"/>
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
