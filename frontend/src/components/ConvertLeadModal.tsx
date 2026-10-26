import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import Modal from '@/components/ui/Modal'
import CompanyContactPicker, { emptyCompanyContact, type CompanyContact } from '@/components/CompanyContactPicker'
import { useDealRules } from '@/components/DealForm'
import DuplicateAlert from '@/components/DuplicateAlert'

const inr = (n: number) => `₹ ${Math.round(n).toLocaleString('en-IN')}`
const num = (s: string) => (s.trim() === '' ? null : Number(s))

/** Lead → deal (v1.5.0): carries the company/contact link, and asks for ARR and
 * One-time (both required) and the SP stage / win % (Negotiation ≥ 70%). */
export default function ConvertLeadModal({ lead, onClose, onDone }: {
  lead: any; onClose: () => void; onDone: (message: string) => void
}) {
  const qc = useQueryClient()
  const { data: rules } = useDealRules()
  // v1.6.0: a lead becomes a deal once qualified (default SP4); the deal opens at SP5 or the lead's own later stage.
  const keys = (rules?.stages ?? []).map(s => s.key)
  const idx = (k?: string) => keys.indexOf(k ?? '')
  const leadIdx = lead.stage === 'won' ? idx('sp7_negotiation') : idx(lead.stage)
  const startKey = rules?.deal_start_stage ?? 'sp5_scope_proposal'
  const startSp = leadIdx > idx(startKey) ? keys[leadIdx] : startKey
  const belowGate = !!rules && idx(lead.stage) < idx(rules.convert_min_stage)
  const exited = ['hold', 'closed_unqualified', 'closed_lost'].includes(lead.stage)
  const [cc, setCc] = useState<CompanyContact>(lead.account_id
    ? { accountId: lead.account_id, accountName: lead.company ?? '', contactId: lead.contact_id ?? '', contactName: lead.contact_name ?? '' }
    : emptyCompanyContact)
  const [sp, setSp] = useState<string>('')
  const [f, setF] = useState({ arr: '', once: '', win: '', eta: '', next: lead.next_action ?? '', title: (lead.requirement ?? '').slice(0, 150), reason: '' })
  const [touched, setTouched] = useState(false)
  const [err, setErr] = useState('')

  const spKey = sp || startSp
  const rule = rules?.stages.find(s => s.key === spKey)
  const win = f.win === '' ? (rule ? Math.max(rule.default, rule.floor) : null) : Number(f.win)
  const arr = num(f.arr), once = num(f.once)
  const total = (arr ?? 0) + (once ?? 0)
  const problems = [
    exited ? 'This lead is on hold or closed — reopen it before converting' : '',
    belowGate && !exited && f.reason.trim().length < 5 ? 'Give a short reason for converting before qualification' : '',
    !cc.accountId ? 'Pick the company' : !cc.contactId ? 'Pick or add a contact' : '',
    arr === null || isNaN(arr) || arr < 0 ? 'Enter ARR (0 if none)' : '',
    once === null || isNaN(once) || once < 0 ? 'Enter One-time (0 if none)' : '',
    arr !== null && once !== null && total <= 0 ? 'ARR and One-time cannot both be 0' : '',
    rule && win !== null && win < rule.floor ? `${rule.label} needs at least ${rule.floor}% win probability` : '',
  ].filter(Boolean)

  const convert = useMutation({
    mutationFn: () => api.post(`/leads/${lead.id}/convert-to-deal`, {
      account_id: cc.accountId, contact_id: cc.contactId, sp_stage: spKey, title: f.title || undefined,
      override_reason: belowGate ? f.reason.trim() : undefined,
      recurring_revenue: arr, one_time_revenue: once, win_probability: win,
      closure_eta: f.eta || undefined, next_step: f.next || undefined,
    }).then(r => r.data),
    onSuccess: (d) => { ;['leads', 'pipeline', 'opportunities', 'accounts', 'trends'].forEach(k => qc.invalidateQueries({ queryKey: [k] })); onDone(d.message) },
    onError: (e: any) => setErr(getErrorMessage(e, 'Could not convert to deal')),
  })
  const submit = () => { setTouched(true); setErr(''); if (!problems.length) convert.mutate() }

  return (
    <Modal title="Convert to deal" subtitle={lead.company} onClose={onClose}>
      <form className="space-y-4 px-5 pb-5" noValidate onSubmit={e => { e.preventDefault(); submit() }}>
        {belowGate && !exited && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs">
            <b>This lead hasn’t been qualified yet.</b> Leads normally convert once they reach {rules?.stages.find(s => s.key === rules.convert_min_stage)?.label}. You can still convert it — say why, and it is logged.
            <input className="form-input mt-2" aria-label="Reason for converting early" placeholder="Reason (e.g. customer issued PO directly)" value={f.reason} onChange={e => setF(p => ({ ...p, reason: e.target.value }))} />
          </div>)}
        <CompanyContactPicker value={cc} onChange={setCc} />
        <DuplicateAlert accountId={cc.accountId} contactId={cc.contactId} />
        <div>
          <label className="form-label block mb-1" htmlFor="cl-title">Deal name</label>
          <input id="cl-title" className="form-input" maxLength={150} value={f.title} onChange={e => setF(p => ({ ...p, title: e.target.value }))} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="sm:col-span-2">
            <label className="form-label block mb-1" htmlFor="cl-sp">SP stage</label>
            <select id="cl-sp" className="form-input" value={spKey} onChange={e => {
              const r = rules?.stages.find(s => s.key === e.target.value)
              setSp(e.target.value); setF(p => ({ ...p, win: r ? String(Math.max(r.default, r.floor)) : '' }))
            }}>{(rules?.stages ?? []).filter((s, i) => s.key !== 'won' && i >= idx(startKey)).map(s => <option key={s.key} value={s.key}>{s.label}</option>)}</select>
          </div>
          <div>
            <label className="form-label block mb-1" htmlFor="cl-arr">ARR (₹) <span className="text-brand-pink">*</span></label>
            <input id="cl-arr" type="number" inputMode="decimal" min={0} className="form-input" placeholder="0 if none" value={f.arr} onChange={e => setF(p => ({ ...p, arr: e.target.value }))} />
          </div>
          <div>
            <label className="form-label block mb-1" htmlFor="cl-once">One-time (₹) <span className="text-brand-pink">*</span></label>
            <input id="cl-once" type="number" inputMode="decimal" min={0} className="form-input" placeholder="0 if none" value={f.once} onChange={e => setF(p => ({ ...p, once: e.target.value }))} />
          </div>
          <div className="sm:col-span-2 rounded-xl bg-wep-surface px-3 py-2 text-sm flex justify-between"><span className="text-wep-muted">Total deal value</span><b>{inr(total)}</b></div>
          <div className="sm:col-span-2">
            <label className="form-label block mb-1" htmlFor="cl-win">Win probability: <b>{win ?? '—'}%</b>
              {rule && <span className="text-wep-muted font-normal"> · {rule.label} default {rule.default}%{rule.floor > 0 ? `, minimum ${rule.floor}%` : ''}</span>}</label>
            <input id="cl-win" type="range" min={rule?.floor ?? 0} max={100} step={5} className="w-full accent-brand-pink h-10"
              value={win ?? 0} onChange={e => setF(p => ({ ...p, win: e.target.value }))} />
          </div>
          <div>
            <label className="form-label block mb-1" htmlFor="cl-eta">Expected closure</label>
            <input id="cl-eta" type="date" className="form-input" value={f.eta} onChange={e => setF(p => ({ ...p, eta: e.target.value }))} />
          </div>
          <div>
            <label className="form-label block mb-1" htmlFor="cl-next">Next step</label>
            <input id="cl-next" className="form-input" value={f.next} onChange={e => setF(p => ({ ...p, next: e.target.value }))} />
          </div>
        </div>
        {touched && problems.length > 0 && <ul className="text-red-500 text-xs space-y-0.5" role="alert">{problems.map(p => <li key={p as string}>• {p}</li>)}</ul>}
        {err && <p className="text-red-500 text-sm" role="alert">{err}</p>}
        <div className="flex gap-2 justify-end flex-wrap">
          <button type="button" className="btn-outline" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={convert.isPending}>{convert.isPending ? '⏳ Converting…' : '→ Convert to deal'}</button>
        </div>
      </form>
    </Modal>
  )
}
