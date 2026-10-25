// SPANCO Kanban board for Leads — Amit, 2026-10-24: handed over the exact
// column set from WEP Solutions' own live Kylas CRM ("the right SPANCO")
// plus "kanban view is good to have (challenge and see what best can come
// to our platform)". Deliberately NOT a visual copy of Kylas: this uses
// fluidGo's own design tokens (wep-*, card, brand-pink), and uses tap
// forward/back buttons + a stage dropdown instead of drag-and-drop —
// drag-only Kanban boards fail keyboard/screen-reader access (WCAG 2.1 AA,
// per rambo-constitution's UI/UX gate) and are genuinely worse than a
// button on the small touch targets a rep actually uses on a phone between
// client visits (Mobile First, same gate). That's the "standard
// implementation" of the Constitution's three-options rule for this
// feature; an AI-augmented option (stale-in-column highlighting, reusing
// the Executive Digest's STALE_DEAL_DAYS pattern) and a moonshot
// (AI-suggested stage transitions with a confidence score, never
// auto-applied per the AI Governance gate) are deferred to the roadmap —
// see claude/fluidgo-roadmap-v2.md and claude/README.md.
//
// Stages are never hardcoded here — they come from GET /leads/stages
// (app.services.lead_stage_service on the backend), so a different
// customer's stage ladder is a config change, not a code change.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

const sourceIcon: Record<string, string> = {
  Call: '📞', Visit: '🏢', Referral: '🤝', LinkedIn: '💼', Email: '📧',
}

export interface LeadStage {
  key: string
  label: string
  sort_order: number
  is_terminal: boolean
  outcome: 'won' | 'lost' | null
  color: string
}

interface Props {
  leads: any[]
  stages: LeadStage[]
}

export default function LeadsKanbanBoard({ leads, stages }: Props) {
  const qc = useQueryClient()
  const sorted = [...stages].sort((a, b) => a.sort_order - b.sort_order)
  const fallbackKey = sorted[0]?.key

  const moveStage = useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: string }) =>
      api.patch(`/leads/${id}/stage`, { stage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not move the lead')),
  })

  const byStage = (key: string) =>
    leads.filter(l => (l.stage ?? fallbackKey) === key)

  if (sorted.length === 0) {
    return (
      <div className="card text-center py-10 text-wep-muted text-sm">
        No stages configured.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto pb-2 -mx-1 px-1">
      <div className="flex gap-3 min-w-max">
        {sorted.map((stage, idx) => {
          const items = byStage(stage.key)
          return (
            <div key={stage.key} className="w-64 shrink-0">
              <div className="flex items-center gap-2 mb-2 px-1">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: stage.color }} />
                <span className="text-xs font-bold text-wep-text flex-1 truncate" title={stage.label}>
                  {stage.label}
                </span>
                <span className="text-[10px] font-bold text-wep-muted bg-white/70 rounded-full px-2 py-0.5">
                  {items.length}
                </span>
              </div>
              <div className="space-y-2 min-h-[64px]">
                {items.length === 0 ? (
                  <div className="text-[11px] text-wep-muted text-center py-5 border border-dashed border-wep-border rounded-2xl">
                    —
                  </div>
                ) : items.map((l: any) => (
                  <div key={l.id} className="card p-3 text-xs">
                    <div className="font-semibold text-wep-text truncate" title={l.company}>
                      {l.company}
                    </div>
                    {l.contact_name && (
                      <div className="text-wep-muted truncate mt-0.5">{l.contact_name}</div>
                    )}
                    <div className="flex items-center gap-1.5 mt-1 text-[10px] text-wep-muted flex-wrap">
                      <span>{sourceIcon[l.source] ?? '📌'} {l.source}</span>
                      {l.ai_lead_score != null && <span>· {l.ai_lead_score} score</span>}
                    </div>
                    {l.next_action && (
                      <div className="text-[10px] text-brand-pink mt-1 truncate" title={l.next_action}>
                        → {l.next_action}
                      </div>
                    )}
                    <div className="flex items-center justify-between gap-1 mt-2 pt-2 border-t border-wep-border">
                      <button
                        type="button"
                        className="text-[11px] px-1.5 py-0.5 rounded disabled:opacity-30 hover:bg-wep-border/40"
                        disabled={idx === 0 || moveStage.isPending}
                        onClick={() => moveStage.mutate({ id: l.id, stage: sorted[idx - 1].key })}
                        aria-label={`Move ${l.company} back a stage`}
                      >
                        ◀
                      </button>
                      <select
                        className="text-[10px] border border-wep-border rounded px-1 py-0.5 flex-1 min-w-0"
                        value={stage.key}
                        onChange={e => moveStage.mutate({ id: l.id, stage: e.target.value })}
                        aria-label={`Change stage for ${l.company}`}
                      >
                        {sorted.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                      </select>
                      <button
                        type="button"
                        className="text-[11px] px-1.5 py-0.5 rounded disabled:opacity-30 hover:bg-wep-border/40"
                        disabled={idx === sorted.length - 1 || moveStage.isPending}
                        onClick={() => moveStage.mutate({ id: l.id, stage: sorted[idx + 1].key })}
                        aria-label={`Move ${l.company} forward a stage`}
                      >
                        ▶
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
