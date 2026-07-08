import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import api from '@/hooks/useApi'
import { format } from 'date-fns'
import { Link } from 'react-router-dom'
import { getQuoteOfDay } from '@/lib/quotes'

// ── Motivational background motif — ascending bars / momentum, on-brand,
// rendered translucent so it reads as texture, not content. Pure SVG (no
// external image), so there's nothing that can 404 or need hosting.
// IMPORTANT: no `absolute` positioning here — this must render as a normal,
// self-contained block that fills whatever fixed-size wrapper places it,
// never reaching past its own box regardless of ancestor size. ──
function MomentumMotif() {
  return (
    <svg viewBox="0 0 400 160" className="w-full h-full pointer-events-none select-none"
      style={{ opacity: 0.14 }} preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
      <rect x="20"  y="100" width="28" height="60" rx="6" fill="#92278E" />
      <rect x="60"  y="75"  width="28" height="85" rx="6" fill="#92278E" />
      <rect x="100" y="55"  width="28" height="105" rx="6" fill="#F0115E" />
      <rect x="140" y="30"  width="28" height="130" rx="6" fill="#F0115E" />
      <rect x="180" y="5"   width="28" height="155" rx="6" fill="#F0115E" />
      <path d="M20 95 L60 70 L100 50 L140 25 L180 0" stroke="#0D9488" strokeWidth="5"
        fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="180" cy="0" r="9" fill="#0D9488" />
    </svg>
  )
}

// ── KPI Stat Card ─────────────────────────────────────────────────────────────
function KPICard({ label, value, sub, accentColor, icon, loading }: {
  label: string; value: string | number; sub?: string;
  accentColor: string; icon: string; loading?: boolean
}) {
  return (
    <div className="stat-card">
      <div className="stat-card-accent" style={{ background: accentColor }} />
      <div className="text-[10px] font-bold uppercase tracking-widest text-wep-muted mb-3">{label}</div>
      {loading ? (
        <div className="skeleton h-9 w-20 mb-1" />
      ) : (
        <div className={`font-display font-black text-wep-navy leading-none mb-1 ${
          String(value).length > 5 ? 'text-[1.4rem]' : 'text-[2rem]'
        }`}>{value}</div>
      )}
      {sub && <div className="text-xs text-wep-muted mt-1">{sub}</div>}
      <div className="absolute right-4 top-1/2 -translate-y-1/2 text-4xl opacity-[0.06] select-none pointer-events-none">
        {icon}
      </div>
    </div>
  )
}

// ── AI Panel ──────────────────────────────────────────────────────────────────
function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

function AIPanel({ userId }: { userId: string }) {
  const qc = useQueryClient()

  const { data } = useQuery({
    queryKey: ['ai-insight', userId],
    queryFn: () => api.get(`/ai/dashboard/${userId}`).then(r => r.data),
    // Cache reads are instant, but poll while a generation is in flight so
    // the UI updates itself the moment it's ready — no manual refresh needed.
    refetchInterval: (q) => (q.state.data?.status === 'pending' ? 4000 : false),
  })

  const regenerate = useMutation({
    mutationFn: () => api.post(`/ai/dashboard/${userId}/regenerate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-insight', userId] }),
  })

  const status = data?.status
  const isPending = status === 'pending' || regenerate.isPending

  return (
    <div className="ai-panel mb-6" style={{ background: 'linear-gradient(135deg, #1A0B2E 0%, #3D1A6E 100%)' }}>
      {/* Top bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
            style={{ background: 'rgba(14,165,233,0.20)', color: '#38BDF8', border: '1px solid rgba(14,165,233,0.25)' }}>
            <span className="ai-pulse" />
            AI · Ollama Local
          </span>
          <span className="font-display font-bold text-white text-sm">Performance Intelligence</span>
          {status === 'ready' && data?.generated_at && (
            <span className="text-[11px]" style={{ color: 'rgba(255,255,255,0.35)' }}>
              · Generated {timeAgo(data.generated_at)}
            </span>
          )}
        </div>
        <button onClick={() => regenerate.mutate()} disabled={isPending}
          className="text-xs font-semibold transition-colors disabled:opacity-40"
          style={{ color: isPending ? 'rgba(255,255,255,0.4)' : '#F5921E' }}>
          {isPending ? '⏳ Analysing…' : status === 'ready' ? '🔄 Regenerate' : '✨ Run Analysis'}
        </button>
      </div>

      {/* Content */}
      {isPending && (
        <div className="flex items-center gap-2.5 text-sm" style={{ color: 'rgba(255,255,255,0.55)' }}>
          <span className="flex gap-1">
            {[0,1,2].map(i => (
              <span key={i} className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-bounce"
                style={{ animationDelay: `${i*0.15}s` }} />
            ))}
          </span>
          Generating on the local model — this takes about 2-3 minutes on this
          hardware. You can keep working; it saves automatically and appears here
          when ready (no need to wait on this screen).
        </div>
      )}
      {!isPending && status === 'failed' && (
        <p className="text-sm" style={{ color: 'rgba(255,150,150,0.8)' }}>
          ⚠️ Last attempt didn't complete. Click "Run Analysis" to try again.
        </p>
      )}
      {!isPending && !status && (
        <p className="text-sm" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Click "Run Analysis" to get BANT insights, rigor assessment and coaching recommendations
          generated locally by your Ollama model. No data leaves this server.
        </p>
      )}
      {!isPending && status === 'ready' && data?.content && (
        <div className="text-sm leading-relaxed rounded-xl p-4"
          style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', color: 'rgba(255,255,255,0.85)' }}
          dangerouslySetInnerHTML={{
            __html: data.content
              .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#fff">$1</strong>')
              .replace(/^#{1,3}\s(.+)$/gm, '<div style="color:#F5921E;font-weight:700;margin-top:12px;margin-bottom:4px">$1</div>')
              .replace(/\n/g, '<br/>')
          }} />
      )}
    </div>
  )
}


// ── Quick-link tile ───────────────────────────────────────────────────────────
function QuickTile({ to, icon, label, desc }: { to: string; icon: string; label: string; desc: string }) {
  return (
    <Link to={to}
      className="card group flex flex-col gap-2 hover:border-wep-orange transition-all duration-200 cursor-pointer"
      style={{ boxShadow: '0 1px 3px rgba(11,31,58,0.06)' }}>
      <div className="text-2xl">{icon}</div>
      <div className="font-bold text-sm text-wep-navy group-hover:text-wep-orange transition-colors">{label}</div>
      <div className="text-xs text-wep-muted leading-relaxed">{desc}</div>
    </Link>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { user } = useAuthStore()
  const today  = format(new Date(), 'yyyy-MM-dd')
  const hour   = new Date().getHours()
  const isBU   = ['manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const isField = ['rep','inside_sales','pre_sales','manager'].includes(user?.role ?? '')
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const [selectedMonth, setSelectedMonth] = useState(format(new Date(), 'yyyy-MM'))
  const [quote] = useState(getQuoteOfDay)

  const { data: dash, isLoading } = useQuery({
    queryKey: ['dashboard', user?.id, selectedMonth],
    queryFn: () => api.get(`/analytics/dashboard?month=${selectedMonth}`).then(r => r.data),
    enabled: !!user?.id,
  })

  const { data: todayDSR } = useQuery({
    queryKey: ['dsr-today', today],
    queryFn: () => api.get(`/dsr?date=${today}`).then(r => r.data),
  })

  const rigor = dash?.avg_rigor ?? 0
  const rigorColor = rigor >= 80 ? '#059669' : rigor >= 60 ? '#D97706' : rigor > 0 ? '#DC2626' : '#DDE3EE'
  const rigorLabel = rigor >= 80 ? '🏆 Excellent' : rigor >= 60 ? '✅ Good' : rigor > 0 ? '⚠️ Needs focus' : undefined

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="font-display font-black text-wep-navy text-2xl leading-tight">
            {greeting}, {user?.name?.split(' ')[0]} 👋
          </div>
          <div className="text-wep-muted text-sm mt-1 flex items-center gap-2 flex-wrap">
            <span>{format(new Date(), 'EEEE, d MMMM yyyy')}</span>
            <span className="text-wep-border-strong">·</span>
            <span>{user?.bu} BU · {user?.business ?? 'fluidPro'}</span>
            {isBU && dash?.pending_today > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold"
                style={{ background: '#FEF2F2', color: '#DC2626' }}>
                🔴 {dash.pending_today} DSR pending today
              </span>
            )}
          </div>
          <p className="text-xs italic text-wep-muted mt-2 max-w-md">
            "{quote.text}" <span className="not-italic font-semibold">— {quote.author}</span>
          </p>
        </div>
        {/* Motif + controls grouped together, in NORMAL flow (not absolute) —
            this cannot overlap the text block no matter how long the quote or
            greeting gets, because it's a separate flex sibling, not layered on top. */}
        <div className="flex items-start gap-4 shrink-0">
          <div className="hidden md:block w-28 h-14 opacity-90 pointer-events-none">
            <MomentumMotif />
          </div>
          <div className="flex items-center gap-2">
            {isBU && (
              <input type="month" className="form-input py-2 text-sm w-40"
                value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)} />
            )}
            {isField && (
              <Link to="/dsr" className="btn-primary">✏️ Submit DSR</Link>
            )}
          </div>
        </div>
      </div>

      {/* ── KPI Grid ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <KPICard label="Visits"      value={dash?.total_visits    ?? 0} icon="🏢"
          sub={isBU ? `BU · ${selectedMonth}` : selectedMonth}
          accentColor="#0D9488" loading={isLoading} />
        <KPICard label="Calls"       value={dash?.total_calls     ?? 0} icon="📞"
          accentColor="#1E6FD9" loading={isLoading} />
        <KPICard label="Follow-Ups"  value={dash?.total_followups ?? 0} icon="🔄"
          accentColor="#D97706" loading={isLoading} />
        <KPICard label="New Leads"   value={dash?.total_leads     ?? 0} icon="🎯"
          accentColor="#0EA5E9" loading={isLoading} />
        <KPICard label="Avg Rigor"
          value={isLoading ? '…' : rigor > 0 ? `${rigor}/100` : '—'}
          sub={rigorLabel} icon="⚡"
          accentColor={rigorColor} loading={isLoading} />
      </div>

      {/* ── AI Panel ── */}
      {user?.id && <AIPanel userId={user.id} />}

      {/* ── Today's DSR (rep only) ── */}
      {!isBU && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="font-bold text-wep-navy text-sm">📋 Today's DSR</div>
            {!todayDSR && (
              <Link to="/dsr" className="text-xs font-semibold text-wep-orange hover:underline">
                Submit now →
              </Link>
            )}
          </div>
          {todayDSR ? (
            <div className="grid grid-cols-3 gap-4 text-center">
              {[
                { label: 'Calls',      val: todayDSR.calls,     color: '#1E6FD9' },
                { label: 'Follow-ups', val: todayDSR.followups, color: '#0D9488' },
                { label: 'Rigor',      val: `${todayDSR.rigor_score}/100`,
                  color: todayDSR.rigor_score >= 80 ? '#059669' : todayDSR.rigor_score >= 60 ? '#D97706' : '#DC2626' },
              ].map(({ label, val, color }) => (
                <div key={label}>
                  <div className="font-display font-black text-2xl" style={{ color }}>{val}</div>
                  <div className="text-wep-muted text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-wep-muted text-sm mb-4">No DSR submitted yet today.</p>
              <Link to="/dsr" className="btn-primary text-sm">Submit Today's DSR →</Link>
            </div>
          )}
        </div>
      )}

      {/* ── BU Head quick tiles ── */}
      {isBU && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <QuickTile to="/team"          icon="👥" label="Team"         desc="DSR compliance & rigor leaderboard" />
          <QuickTile to="/revenue"       icon="💰" label="Revenue"      desc="Target achievement & pipeline" />
          <QuickTile to="/opportunities" icon="🧭" label="Opportunities" desc="Deal health & BANT scores" />
          <QuickTile to="/fga-approval"  icon="🏆" label="FGA Approval" desc="Score review & Finance export" />
        </div>
      )}
    </div>
  )
}
