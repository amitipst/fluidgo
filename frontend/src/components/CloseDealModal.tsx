import { useState } from 'react'
import api from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

// Human-readable labels for the fixed taxonomy (mirrors backend OUTCOME_TAXONOMY)
const OUTCOMES: Record<string, { label: string; color: string; categories: Record<string, string> }> = {
  closed_won: {
    label: '✅ Won', color: '#059669',
    categories: {
      value_fit: 'Best value / solution fit', relationship: 'Strong relationship',
      technical_win: 'Technical superiority', price_win: 'Most competitive price',
      incumbent_advantage: 'Incumbent advantage', other: 'Other',
    },
  },
  closed_lost: {
    label: '❌ Lost', color: '#DC2626',
    categories: {
      price: 'Price / budget too high', competitor: 'Competitor won',
      no_decision: 'No decision / bad timing', lost_champion: 'Lost our champion',
      technical_fit: 'Technical fit gap', in_house: 'Went in-house',
      budget_cut: 'Budget cut', other: 'Other',
    },
  },
  on_hold: {
    label: '⏸ On Hold', color: '#D97706',
    categories: {
      budget_frozen: 'Budget frozen', deprioritized: 'Project deprioritized',
      awaiting_approval: 'Awaiting client approval', contract_cycle: 'Contract cycle timing',
      other: 'Other',
    },
  },
  dropped: {
    label: '🚫 Dropped', color: '#6B7280',
    categories: {
      no_genuine_need: 'No genuine need', unresponsive: 'Client unresponsive',
      not_icp: 'Not our ICP', disqualified: 'Disqualified', duplicate: 'Duplicate',
      other: 'Other',
    },
  },
}

export default function CloseDealModal({ deal, onClose, onDone }: {
  deal: any; onClose: () => void; onDone: () => void
}) {
  const [outcome, setOutcome] = useState<string>('closed_won')
  const [category, setCategory] = useState<string>('')
  const [detail, setDetail] = useState('')
  const [competitor, setCompetitor] = useState('')
  const [contractMonths, setContractMonths] = useState<string>('')
  const [reengageAt, setReengageAt] = useState('')
  const [saving, setSaving] = useState(false)

  const cfg = OUTCOMES[outcome]
  const isCompetitorLoss = outcome === 'closed_lost' && category === 'competitor'
  // Contract capture makes sense for a win, or a loss to a competitor on a term
  const showContract = outcome === 'closed_won' || isCompetitorLoss

  async function submit() {
    if (!category) { toast.error('Please pick a reason.'); return }
    setSaving(true)
    try {
      await api.post(`/pipeline/${deal.id}/close`, {
        outcome, category,
        detail: detail || undefined,
        competitor: competitor || undefined,
        contract_months: contractMonths ? parseInt(contractMonths) : undefined,
        reengage_at: reengageAt || undefined,
      })
      const msg = outcome === 'closed_won'
        ? `${deal.company} marked as Won. 🎉`
        : `${deal.company} closed. AI is analysing what happened — check the post-mortem shortly.`
      toast.success(msg)
      onDone()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Could not close the deal')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9998, background: 'rgba(26,11,46,0.55)',
      display: 'grid', placeItems: 'center', padding: 16,
    }} onClick={onClose}>
      <div className="card" style={{ maxWidth: 520, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-lg text-wep-navy">Close Deal — {deal.company}</h3>
          <button onClick={onClose} className="text-wep-muted text-xl leading-none">×</button>
        </div>

        {/* Outcome selector */}
        <label className="form-label block mb-1.5">Outcome</label>
        <div className="grid grid-cols-2 gap-2 mb-4">
          {Object.entries(OUTCOMES).map(([k, o]) => (
            <button key={k} onClick={() => { setOutcome(k); setCategory('') }}
              className="py-2 rounded-xl text-sm font-bold border-2 transition-all"
              style={{
                borderColor: outcome === k ? o.color : '#E8DFF5',
                color: outcome === k ? '#fff' : o.color,
                background: outcome === k ? o.color : 'transparent',
              }}>
              {o.label}
            </button>
          ))}
        </div>

        {/* Reason category — the structured taxonomy */}
        <label className="form-label block mb-1.5">
          {outcome === 'closed_won' ? 'Why did we win?' : 'What was the main reason?'}
          <span className="text-wep-red"> *</span>
        </label>
        <div className="space-y-1.5 mb-4">
          {Object.entries(cfg.categories).map(([k, lbl]) => (
            <button key={k} onClick={() => setCategory(k)}
              className="w-full text-left px-3 py-2 rounded-lg text-sm border transition-all"
              style={{
                borderColor: category === k ? cfg.color : '#E8DFF5',
                background: category === k ? `${cfg.color}12` : 'transparent',
                fontWeight: category === k ? 700 : 400,
              }}>
              {lbl}
            </button>
          ))}
        </div>

        {/* Competitor name if lost to competitor */}
        {isCompetitorLoss && (
          <div className="mb-4">
            <label className="form-label block mb-1.5">Which competitor won?</label>
            <input className="form-input" value={competitor} onChange={e => setCompetitor(e.target.value)}
              placeholder="e.g. TCS, Wipro, in-house team" />
          </div>
        )}

        {/* Free-text detail — the qualitative learning */}
        <div className="mb-4">
          <label className="form-label block mb-1.5">
            {outcome === 'closed_won' ? 'What clinched it? (optional)' : 'What actually went wrong? (optional but valuable)'}
          </label>
          <textarea className="form-input" rows={3} value={detail} onChange={e => setDetail(e.target.value)}
            placeholder={outcome === 'closed_won'
              ? 'Key factors that won the deal…'
              : 'Be honest — this feeds the AI post-mortem so the team learns.'} />
        </div>

        {/* Contract term → win-back scheduling */}
        {showContract && (
          <div className="mb-4 p-3 rounded-xl" style={{ background: '#F7F3FC', border: '1px solid #E8DFF5' }}>
            <div className="text-xs font-bold text-wep-navy mb-2">
              📅 {isCompetitorLoss ? 'Incumbent contract term' : 'Contract term'} — schedules a win-back alert
            </div>
            <div className="flex gap-2 items-end flex-wrap">
              <div className="flex-1 min-w-[120px]">
                <label className="form-label block mb-1 text-[11px]">Contract length</label>
                <select className="form-input py-1.5 text-sm" value={contractMonths}
                  onChange={e => setContractMonths(e.target.value)}>
                  <option value="">Not a fixed term</option>
                  <option value="12">1 year</option>
                  <option value="24">2 years</option>
                  <option value="36">3 years</option>
                  <option value="60">5 years</option>
                </select>
              </div>
              {contractMonths && (
                <div className="flex-1 min-w-[140px]">
                  <label className="form-label block mb-1 text-[11px]">Re-engage on (default: 4mo before expiry)</label>
                  <input type="date" className="form-input py-1.5 text-sm" value={reengageAt}
                    onChange={e => setReengageAt(e.target.value)} />
                </div>
              )}
            </div>
            {contractMonths && (
              <p className="text-[11px] text-wep-muted mt-2">
                We'll resurface {deal.company} in your alerts before the {isCompetitorLoss ? "competitor's " : ''}
                contract expires, so you can re-engage in time.
              </p>
            )}
          </div>
        )}

        <div className="flex gap-2">
          <button onClick={submit} disabled={saving || !category}
            className="btn-primary flex-1 disabled:opacity-40">
            {saving ? 'Saving…' : 'Close Deal'}
          </button>
          <button onClick={onClose} className="btn-outline">Cancel</button>
        </div>
      </div>
    </div>
  )
}
