import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '@/hooks/useApi'

type Item = { id: string; type: 'deal' | 'lead'; title: string; company: string; owner: string; detail: string; value: number; stage: string; action?: string }
type Finding = { key: string; severity: 'high' | 'medium' | 'low'; title: string; why: string; action: string; count: number; value: number; items: Item[] }
type Rep = { user_id: string; name: string; open_count: number; open_value: number; weighted: number; stalled: number; past_eta: number; no_next_step: number; attention: number }
type Report = {
  scope: 'me' | 'team' | 'all'; headlines: string[]; findings: Finding[]; reps: Rep[]; my_actions: Item[]; presales_queue: Item[]
  summary: { open_count: number; open_value: number; weighted_value: number; open_leads: number
    by_category: Record<string, { count: number; value: number; weighted: number }>
    by_stage: { key: string; label: string; count: number; value: number }[] }
}

const inr = (n: number) => n >= 1e7 ? `₹${(n / 1e7).toFixed(2)} Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)} L` : `₹${Math.round(n).toLocaleString('en-IN')}`
// Severity is colour AND text, never colour alone.
const SEV = {
  high:   { label: 'Act now', cls: 'border-red-300 bg-red-50', chip: 'bg-red-100 text-red-700' },
  medium: { label: 'Fix this week', cls: 'border-amber-300 bg-amber-50', chip: 'bg-amber-100 text-amber-800' },
  low:    { label: 'Housekeeping', cls: 'border-wep-border bg-wep-surface', chip: 'bg-gray-100 text-gray-600' },
} as const

function ItemRow({ i }: { i: Item }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs py-1.5 border-t border-black/5 first:border-t-0">
      <Link to={i.type === 'lead' ? '/leads' : '/deals'} className="font-semibold text-wep-text underline-offset-2 hover:underline">{i.title}</Link>
      <span className="text-wep-muted">{i.company !== i.title ? i.company : ''}</span>
      <span className="text-wep-muted">· {i.stage}</span>
      {i.owner && <span className="text-wep-muted">· {i.owner}</span>}
      {i.value > 0 && <span className="font-medium">· {inr(i.value)}</span>}
      <span className="basis-full text-wep-muted">{i.detail}{i.action ? ` → ${i.action}` : ''}</span>
    </li>)
}

/** Weak-area radar (v1.6.0). One payload, role-aware: reps and inside sales see
 * "my actions", presales their queue, managers and leaders the ranked weak areas
 * and the people table. Rules-based and explainable — every card says what was
 * measured, why it matters and what to do. */
export default function WeakAreasPanel() {
  const { data, isLoading, isError } = useQuery<Report>({
    queryKey: ['deal-insights'], staleTime: 60_000,
    queryFn: () => api.get('/deal-insights').then(r => r.data),
  })
  const [open, setOpen] = useState<string | null>(null)
  if (isLoading) return <div className="space-y-3">{[1, 2, 3].map(i => <div key={i} className="skeleton h-20 rounded-2xl" />)}</div>
  if (isError || !data) return <div className="card text-sm text-wep-muted">Could not load insights. Try again in a moment.</div>
  const { summary: s, findings, reps, my_actions, presales_queue, headlines } = data
  const leaderView = data.scope !== 'me'
  const cats: [string, string][] = [['commit', 'Commit'], ['best_case', 'Best case'], ['pipeline', 'Pipeline']]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
        {[['Open pipeline', inr(s.open_value), `${s.open_count} deals`], ['Weighted forecast', inr(s.weighted_value), 'value × win %'],
          ['Commit', inr(s.by_category.commit?.value ?? 0), `${s.by_category.commit?.count ?? 0} deals · weighted ${inr(s.by_category.commit?.weighted ?? 0)}`],
          ['Open leads', String(s.open_leads), 'not yet deals']].map(([l, v, sub]) => (
          <div key={l} className="card py-3"><div className="text-xs text-wep-muted">{l}</div><div className="font-display font-bold text-lg">{v}</div><div className="text-[11px] text-wep-muted">{sub}</div></div>))}
      </div>

      {leaderView && headlines.length > 0 && (
        <div className="card border-brand-pink/30">
          <h3 className="font-bold text-sm mb-2">Where to look first</h3>
          <ul className="text-sm space-y-1 list-disc pl-5">{headlines.map(h => <li key={h}>{h}</li>)}</ul>
        </div>)}

      {my_actions.length > 0 && (
        <section aria-labelledby="my-actions">
          <h3 id="my-actions" className="font-bold text-sm mb-2">My actions today ({my_actions.length})</h3>
          <ul className="card py-2">{my_actions.map(a => <ItemRow key={a.id} i={a} />)}</ul>
        </section>)}

      {presales_queue.length > 0 && (
        <section aria-labelledby="presales-q">
          <h3 id="presales-q" className="font-bold text-sm mb-2">Presales queue ({presales_queue.length})</h3>
          <ul className="card py-2">{presales_queue.map(a => <ItemRow key={a.id} i={a} />)}</ul>
        </section>)}

      <section aria-labelledby="weak">
        <h3 id="weak" className="font-bold text-sm mb-2">{leaderView ? 'Weak areas' : 'What needs attention'}</h3>
        {findings.length === 0
          ? <div className="card text-sm text-wep-muted">Nothing needs attention right now. ✅</div>
          : <div className="space-y-2">{findings.map(f => {
            const v = SEV[f.severity], isOpen = open === f.key
            return (
              <div key={f.key} className={`rounded-2xl border p-3 ${v.cls}`}>
                <button className="w-full text-left min-h-[44px]" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : f.key)}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${v.chip}`}>{v.label}</span>
                    <span className="font-semibold text-sm">{f.title}</span>
                    <span className="text-xs text-wep-muted">· {f.count}{f.value > 0 ? ` · ${inr(f.value)}` : ''}</span>
                    <span className="ml-auto text-xs" aria-hidden>{isOpen ? '▲' : '▼'}</span>
                  </div>
                  <p className="text-xs text-wep-muted mt-1">{f.why}</p>
                </button>
                {isOpen && (<div className="mt-2">
                  <p className="text-xs font-medium mb-1">Do this: {f.action}</p>
                  <ul>{f.items.map(i => <ItemRow key={i.id} i={i} />)}</ul>
                  {f.count > f.items.length && <p className="text-[11px] text-wep-muted mt-1">Showing the {f.items.length} largest of {f.count}.</p>}
                </div>)}
              </div>)
          })}</div>}
      </section>

      {leaderView && (
        <section aria-labelledby="funnel">
          <h3 id="funnel" className="font-bold text-sm mb-2">Pipeline by stage</h3>
          <div className="card space-y-1.5">
            {s.by_stage.map(st => {
              const max = Math.max(1, ...s.by_stage.map(x => x.value))
              return (
                <div key={st.key} className="flex items-center gap-2 text-xs">
                  <span className="w-40 shrink-0 truncate">{st.label}</span>
                  <div className="flex-1 h-3 rounded bg-wep-surface overflow-hidden"><div className="h-full bg-brand-pink/70" style={{ width: `${(st.value / max) * 100}%` }} /></div>
                  <span className="w-28 text-right tabular-nums">{st.count} · {inr(st.value)}</span>
                </div>)
            })}
            <div className="flex flex-wrap gap-3 pt-2 border-t border-wep-border text-xs text-wep-muted">
              {cats.map(([k, l]) => <span key={k}>{l}: <b className="text-wep-text">{inr(s.by_category[k]?.value ?? 0)}</b> ({s.by_category[k]?.count ?? 0})</span>)}
            </div>
          </div>
        </section>)}

      {leaderView && reps.length > 1 && (
        <section aria-labelledby="people">
          <h3 id="people" className="font-bold text-sm mb-2">By owner — most attention first</h3>
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-wep-muted border-b border-wep-border">
                {['Owner', 'Open', 'Pipeline', 'Weighted', 'Stalled', 'Past date', 'No next step'].map(h => <th key={h} className="px-3 py-2 font-medium whitespace-nowrap">{h}</th>)}</tr></thead>
              <tbody>{reps.map(r => (
                <tr key={r.user_id} className="border-b border-wep-border/60 last:border-0">
                  <td className="px-3 py-2 font-medium whitespace-nowrap">{r.name || '—'}</td><td className="px-3 py-2">{r.open_count}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{inr(r.open_value)}</td><td className="px-3 py-2 whitespace-nowrap">{inr(r.weighted)}</td>
                  <td className={`px-3 py-2 ${r.stalled ? 'text-red-600 font-semibold' : ''}`}>{r.stalled}</td>
                  <td className={`px-3 py-2 ${r.past_eta ? 'text-red-600 font-semibold' : ''}`}>{r.past_eta}</td>
                  <td className={`px-3 py-2 ${r.no_next_step ? 'text-amber-700 font-semibold' : ''}`}>{r.no_next_step}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </section>)}
    </div>
  )
}
