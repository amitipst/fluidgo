import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import CompanyContactPicker, { emptyCompanyContact, type CompanyContact } from '@/components/CompanyContactPicker'
import WonEvidence from '@/components/WonEvidence'
import DuplicateAlert from '@/components/DuplicateAlert'

export type SpRule = { key: string; label: string; default: number; floor: number; category?: string | null }
export type DealRules = {
  stages: SpRule[]; require_company_contact: boolean; require_revenue_split: boolean
  convert_min_stage: string; deal_start_stage: string; new_deal_min_stage: string; forecast_categories: Record<string, string>
}

/** SP ladder + win-% rules from the server (config: feature_flags 'deal_rules'). */
export function useDealRules() {
  return useQuery<DealRules>({
    queryKey: ['deal-rules'], staleTime: 5 * 60_000,
    queryFn: () => api.get('/pipeline/rules').then(r => r.data),
  })
}

const HEAT: [string, string][] = [['cold', 'Cold'], ['warm', 'Warm'], ['qualification', 'Qualification'], ['hot', '🔥 Hot'],
  ['on_hold', '⏸ On Hold'], ['closed_won', '✅ Won'], ['closed_lost', '❌ Lost'], ['dropped', '🚫 Dropped']]
const CLOSED = ['closed_won', 'closed_lost', 'dropped']
const inr = (n: number) => `₹ ${Math.round(n).toLocaleString('en-IN')}`
const num = (s: string) => (s.trim() === '' ? null : Number(s))

/** One form for adding and editing a deal (v1.5.0): company/contact first,
 * ARR and One-time both required, win % that follows the SP stage and can never
 * drop below that stage's floor (Negotiation ≥ 70%). */
export default function DealForm({ deal, onSaved, onCancel }: {
  deal?: any; onSaved: () => void; onCancel: () => void
}) {
  const qc = useQueryClient()
  const editing = !!deal
  const { data: rules } = useDealRules()
  const [cc, setCc] = useState<CompanyContact>(deal?.account_id
    ? { accountId: deal.account_id, accountName: deal.company ?? '', contactId: deal.contact_id ?? '', contactName: deal.primary_contact ?? '' }
    : emptyCompanyContact)
  const [f, setF] = useState({
    stage: deal?.stage ?? 'cold', sp_stage: deal?.sp_stage ?? (editing ? '' : 'sp5_scope_proposal'), title: deal?.title ?? '',
    arr: deal?.recurring_revenue != null ? String(parseFloat(deal.recurring_revenue)) : '',
    once: deal?.one_time_revenue != null ? String(parseFloat(deal.one_time_revenue)) : '',
    win: deal?.win_probability != null ? String(deal.win_probability) : '',
    won_basis: deal?.won_basis ?? '', won_at: deal?.won_at ?? new Date().toISOString().slice(0, 10), won_ref: deal?.won_ref ?? '',
    invoiced_at: deal?.invoiced_at ?? '', invoice_ref: deal?.invoice_ref ?? '',
    closure_eta: deal?.closure_eta ?? '', todays_update: deal?.todays_update ?? '', next_step: deal?.next_step ?? '',
  })
  const [touched, setTouched] = useState(false)
  const [early, setEarly] = useState(false)
  const [earlyReason, setEarlyReason] = useState('')
  const [err, setErr] = useState('')
  const set = (k: string) => (e: any) => setF(p => ({ ...p, [k]: e.target.value }))
  const setStatus = (e: any) => { const v = e.target.value; setF(p => ({ ...p, stage: v, sp_stage: v === 'closed_won' ? 'won' : p.sp_stage === 'won' ? 'sp7_negotiation' : p.sp_stage })) }

  // New deals begin at SP5+ (earlier stages are worked as a Lead). "Start earlier" is an
  // audited escape hatch for the rare deal that arrives already past qualification-less.
  const stageKeys = (rules?.stages ?? []).map(s => s.key)
  const minIdx = Math.max(0, stageKeys.indexOf(rules?.new_deal_min_stage ?? 'sp5_scope_proposal'))
  const belowMin = !editing && stageKeys.indexOf(f.sp_stage) >= 0 && stageKeys.indexOf(f.sp_stage) < minIdx
  const spOptions = (rules?.stages ?? []).filter((s, i) => editing || early || i >= minIdx || s.key === f.sp_stage)
  const rule = useMemo(() => rules?.stages.find(s => s.key === f.sp_stage), [rules, f.sp_stage])
  const closed = CLOSED.includes(f.stage)
  // Picking an SP stage re-derives the win % (never below its floor); the rep can then move it up or down above the floor.
  const pickSp = (key: string) => {
    const r = rules?.stages.find(s => s.key === key)
    // SP "Won" and the Won status are the same thing; leaving Won re-opens the deal.
    setF(p => ({ ...p, sp_stage: key, win: r ? String(Math.max(r.default, r.floor)) : p.win,
      stage: key === 'won' ? 'closed_won' : p.stage === 'closed_won' ? 'hot' : p.stage }))
  }
  // New deal: seed the default win % as soon as the rules arrive.
  useEffect(() => { if (!editing && rule && f.win === '') setF(p => ({ ...p, win: String(Math.max(rule.default, rule.floor)) })) }, [rule]) // eslint-disable-line

  const arr = num(f.arr), once = num(f.once), win = num(f.win)
  const total = (arr ?? 0) + (once ?? 0)
  const errs = {
    early: belowMin && earlyReason.trim().length < 5 ? 'Give a short reason for starting below SP5' : '',
    company: !cc.accountId ? 'Pick the company (add it if it is new)' : '',
    contact: cc.accountId && !cc.contactId ? 'Pick or add a contact' : '',
    arr: arr === null || isNaN(arr) || arr < 0 ? 'Enter ARR (0 if none)' : '',
    once: once === null || isNaN(once) || once < 0 ? 'Enter One-time (0 if none)' : '',
    total: arr !== null && once !== null && !isNaN(total) && total <= 0 ? 'ARR and One-time cannot both be 0' : '',
    win: closed ? '' : win === null || isNaN(win) || win < 0 || win > 100 ? 'Win % must be 0–100'
      : rule && win < rule.floor ? `${rule.label} needs at least ${rule.floor}%` : '',
  }
  const exempt = ['closed_lost', 'dropped', 'on_hold'].includes(f.stage)
  const enteringWon = f.stage === 'closed_won' && deal?.stage !== 'closed_won'
  const wonErr = enteringWon && (!f.won_basis || !f.won_at) ? 'Record the customer’s email / LOI / PO / agreement and its date' : ''
  const blocking = (wonErr ? [['won', wonErr]] : []).concat(Object.entries(errs).filter(([k, v]) => v && !(exempt && ['arr', 'once', 'total'].includes(k)) && !(editing && !deal?.account_id && k === 'company' && !cc.accountId)))
  const show = (k: keyof typeof errs) => touched && errs[k] ? <p className="text-red-500 text-xs mt-1" role="alert">{errs[k]}</p> : null

  const save = useMutation({
    mutationFn: () => {
      const body: any = {
        stage: f.stage,
        recurring_revenue: arr ?? undefined, one_time_revenue: once ?? undefined,
        closure_eta: f.closure_eta || undefined, todays_update: f.todays_update || undefined, next_step: f.next_step || undefined,
      }
      if (f.sp_stage) body.sp_stage = f.sp_stage
      if (f.title.trim()) body.title = f.title.trim()
      if (belowMin) body.stage_override_reason = earlyReason.trim()
      if (!closed && win !== null) body.win_probability = win
      if (f.stage === 'closed_won') {
        if (f.won_basis) { body.won_basis = f.won_basis; body.won_at = f.won_at || undefined; body.won_ref = f.won_ref || undefined }
        if (f.invoiced_at) { body.invoiced_at = f.invoiced_at; body.invoice_ref = f.invoice_ref || undefined }
      }
      if (cc.accountId) { body.account_id = cc.accountId; body.contact_id = cc.contactId || undefined }
      return editing ? api.patch(`/pipeline/${deal.id}`, body) : api.post('/pipeline', body)
    },
    onSuccess: () => {
      ;['pipeline', 'opportunities', 'trends', 'accounts', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] }))
      onSaved()
    },
    onError: (e: any) => setErr(getErrorMessage(e, 'Failed to save deal')),
  })
  const submit = () => { setTouched(true); setErr(''); if (!blocking.length) save.mutate() }

  return (
    <form className="space-y-4" noValidate onSubmit={e => { e.preventDefault(); submit() }}>
      {editing && !deal?.account_id && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs">This deal isn’t linked to a company yet (<b>{deal?.company}</b>). Pick the company below to connect it to Contacts, trends and the company page.</div>
      )}
      <CompanyContactPicker value={cc} onChange={setCc} suggestName={deal?.company} />
      {touched && (errs.company || errs.contact) && <p className="text-red-500 text-xs" role="alert">{errs.company || errs.contact}</p>}
      {!editing && <DuplicateAlert accountId={cc.accountId} contactId={cc.contactId} />}
      <div>
        <label className="form-label block mb-1" htmlFor="df-title">Deal name</label>
        <input id="df-title" className="form-input" maxLength={150} placeholder="e.g. Managed NOC renewal, SOC for Pune plant" value={f.title} onChange={set('title')} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="form-label block mb-1" htmlFor="df-sp">SP stage</label>
          <select id="df-sp" className="form-input" value={f.sp_stage} onChange={e => pickSp(e.target.value)}>
            {editing && !deal?.sp_stage && <option value="">— choose —</option>}
            {spOptions.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          {!editing && (
            <label className="flex items-center gap-1.5 text-xs text-wep-muted mt-1.5 min-h-[28px]">
              <input type="checkbox" checked={early} onChange={e => setEarly(e.target.checked)} />
              Start earlier than SP5 (work early stages as a Lead where possible)
            </label>)}
          {belowMin && (
            <input className="form-input mt-1" placeholder="Reason for starting below SP5" value={earlyReason} onChange={e => setEarlyReason(e.target.value)} />)}
          {touched && errs.early && <p className="text-red-500 text-xs mt-1" role="alert">{errs.early}</p>}
        </div>
        <div>
          <label className="form-label block mb-1" htmlFor="df-stage">Heat / status</label>
          <select id="df-stage" className="form-input" value={f.stage} onChange={setStatus}>
            {HEAT.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="form-label block mb-1" htmlFor="df-arr">ARR (₹) <span className="text-brand-pink">*</span></label>
          <input id="df-arr" type="number" inputMode="decimal" min={0} className="form-input" placeholder="Recurring per year, 0 if none" value={f.arr} onChange={set('arr')} />
          {show('arr')}
        </div>
        <div>
          <label className="form-label block mb-1" htmlFor="df-once">One-time (₹) <span className="text-brand-pink">*</span></label>
          <input id="df-once" type="number" inputMode="decimal" min={0} className="form-input" placeholder="One-time, 0 if none" value={f.once} onChange={set('once')} />
          {show('once')}
        </div>
        <div className="sm:col-span-2 rounded-xl bg-wep-surface px-3 py-2 text-sm flex items-center justify-between">
          <span className="text-wep-muted">Total deal value</span><b className="text-wep-text">{inr(total)}</b>
        </div>
        {show('total')}
        {!closed && (
          <div className="sm:col-span-2">
            <label className="form-label block mb-1" htmlFor="df-win">Win probability: <b>{f.win === '' ? '—' : `${f.win}%`}</b>
              {rule && <span className="text-wep-muted font-normal"> · {rule.label} default {rule.default}%{rule.floor > 0 ? `, minimum ${rule.floor}%` : ''}</span>}</label>
            <input id="df-win" type="range" min={rule?.floor ?? 0} max={100} step={5} className="w-full accent-brand-pink h-10"
              value={f.win === '' ? (rule?.default ?? 0) : Math.max(Number(f.win), rule?.floor ?? 0)} onChange={set('win')} />
            {show('win')}
          </div>
        )}
        {f.stage === 'closed_won' && (
          <div className="sm:col-span-2 space-y-3">
            <WonEvidence value={{ won_basis: f.won_basis, won_at: f.won_at, won_ref: f.won_ref }}
              onChange={v => setF(p => ({ ...p, ...v }))} idPrefix="df-won" />
            {wonErr && touched && <p className="text-red-500 text-xs" role="alert">{wonErr}</p>}
            <div className="rounded-xl border border-wep-border p-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2 text-xs text-wep-muted">Revenue is recognised when the tax invoice is raised — add it when it is.</div>
              <div>
                <label className="form-label block mb-1" htmlFor="df-inv">Tax invoice date</label>
                <input id="df-inv" type="date" className="form-input" value={f.invoiced_at} onChange={set('invoiced_at')} />
              </div>
              <div>
                <label className="form-label block mb-1" htmlFor="df-invref">Invoice number</label>
                <input id="df-invref" className="form-input" value={f.invoice_ref} onChange={set('invoice_ref')} />
              </div>
            </div>
          </div>
        )}
        {closed && <p className="sm:col-span-2 text-xs text-wep-muted">Win probability is set automatically for closed deals ({f.stage === 'closed_won' ? '100%' : '0%'}).</p>}
        <div>
          <label className="form-label block mb-1" htmlFor="df-eta">Expected closure</label>
          <input id="df-eta" type="date" className="form-input" value={f.closure_eta} onChange={set('closure_eta')} />
        </div>
        <div className="sm:col-span-2">
          <label className="form-label block mb-1" htmlFor="df-upd">Today’s update</label>
          <input id="df-upd" className="form-input" placeholder="Brief update on the opportunity" value={f.todays_update} onChange={set('todays_update')} />
        </div>
        <div className="sm:col-span-2">
          <label className="form-label block mb-1" htmlFor="df-next">Next step</label>
          <input id="df-next" className="form-input" placeholder="e.g. Send proposal, arrange demo…" value={f.next_step} onChange={set('next_step')} />
        </div>
      </div>

      {err && <p className="text-red-500 text-sm" role="alert">{err}</p>}
      <div className="flex gap-2 flex-wrap">
        <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? '⏳ Saving…' : editing ? '✅ Save' : '✅ Save deal'}</button>
        <button type="button" className="btn-outline" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}
