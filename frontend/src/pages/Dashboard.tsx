import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import api from '@/hooks/useApi'
import { format } from 'date-fns'
import { useState } from 'react'

function StatCard({ label, value, accent, icon }: { label:string; value:string|number; accent:string; icon:string }) {
  return (
    <div className={`card relative overflow-hidden border-t-2 ${accent}`}>
      <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-2">{label}</div>
      <div className="font-display font-bold text-3xl text-wep-navy">{value}</div>
      <div className="absolute right-4 top-1/2 -translate-y-1/2 text-4xl opacity-10">{icon}</div>
    </div>
  )
}

function AIPanel({ userId }: { userId: string }) {
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(false)

  async function runAI() {
    setLoading(true); setContent('')
    try {
      const res = await api.get(`/ai/dashboard/${userId}`)
      setContent(res.data.content)
    } catch {
      setContent('⚠️ AI analysis unavailable. Ensure Ollama is running with phi3:mini pulled.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ai-panel mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 bg-wep-electric/20 border border-wep-electric/30 text-wep-electric text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-wep-electric animate-pulse inline-block"/>
            AI · Ollama Local
          </span>
          <span className="font-display font-bold text-white text-sm">Performance Intelligence</span>
        </div>
        <button onClick={runAI} disabled={loading}
          className="text-xs text-wep-electric/70 hover:text-wep-electric transition-colors disabled:opacity-50">
          {loading ? '⏳ Analysing...' : '✨ Analyse'}
        </button>
      </div>
      {loading && (
        <div className="flex items-center gap-2 text-white/60 text-sm">
          <span className="flex gap-1">{[0,1,2].map(i=>(
            <span key={i} className="w-1.5 h-1.5 rounded-full bg-wep-electric animate-bounce"
              style={{animationDelay:`${i*0.15}s`}}/>
          ))}</span>
          Querying local LLM...
        </div>
      )}
      {content && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-white/85 leading-relaxed whitespace-pre-wrap"
          dangerouslySetInnerHTML={{__html: content.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br/>')}}/>
      )}
      {!content && !loading && (
        <p className="text-white/40 text-sm">Click Analyse to get AI-powered insights from your local Ollama model.</p>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuthStore()
  const today = format(new Date(), 'yyyy-MM-dd')

  const { data: todayDSR } = useQuery({
    queryKey: ['dsr', today],
    queryFn: () => api.get(`/dsr?date=${today}`).then(r => r.data)
  })
  const { data: analytics } = useQuery({
    queryKey: ['analytics', user?.id],
    queryFn: () => api.get(`/analytics/rep/${user?.id}`).then(r => r.data),
    enabled: !!user?.id
  })

  const totals = analytics?.reduce((acc: any, d: any) => ({
    calls: acc.calls + (d.calls||0),
    visits: acc.visits + (d.visits||0),
    followups: acc.followups + (d.followups||0),
    leads: acc.leads + (d.new_leads||0),
    proposals: acc.proposals + (d.proposals||0),
  }), { calls:0, visits:0, followups:0, leads:0, proposals:0 })

  const avgRigor = analytics?.length
    ? Math.round(analytics.filter((d:any)=>d.rigor_score>=0).reduce((a:number,d:any)=>a+d.rigor_score,0) / analytics.filter((d:any)=>d.rigor_score>=0).length)
    : 0

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-wep-navy text-xl md:text-2xl">
            Good {new Date().getHours()<12?'morning':'afternoon'}, {user?.name?.split(' ')[0]} 👋
          </h1>
          <p className="text-wep-muted text-sm mt-1">
            {format(new Date(),'EEEE, d MMMM yyyy')} · {user?.bu} BU
          </p>
        </div>
        <a href="/dsr" className="btn-primary hidden md:block">✏️ Submit DSR</a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <StatCard label="Visits"     value={totals?.visits    ?? '—'} accent="border-t-wep-teal"    icon="🏢"/>
        <StatCard label="Calls"      value={totals?.calls     ?? '—'} accent="border-t-wep-accent"  icon="📞"/>
        <StatCard label="Follow-Ups" value={totals?.followups ?? '—'} accent="border-t-wep-amber"   icon="🔄"/>
        <StatCard label="Leads"      value={totals?.leads     ?? '—'} accent="border-t-wep-electric" icon="🎯"/>
        <StatCard label="Rigor Score" value={avgRigor ? `${avgRigor}/100` : '—'} accent="border-t-wep-green" icon="⚡"/>
      </div>

      {user?.id && <AIPanel userId={user.id} />}

      {todayDSR && (
        <div className="card">
          <div className="font-semibold text-sm text-wep-navy mb-3">Today's DSR</div>
          <div className="grid grid-cols-3 gap-3 text-center text-sm">
            <div><div className="font-bold text-wep-accent">{todayDSR.calls}</div><div className="text-wep-muted text-xs">Calls</div></div>
            <div><div className="font-bold text-wep-teal">{todayDSR.followups}</div><div className="text-wep-muted text-xs">Follow-ups</div></div>
            <div><div className="font-bold text-wep-amber">{todayDSR.rigor_score}</div><div className="text-wep-muted text-xs">Rigor</div></div>
          </div>
        </div>
      )}
    </div>
  )
}
