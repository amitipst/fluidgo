export const WON_BASES: [string, string][] = [
  ['email', 'Customer email'], ['loi', 'LOI'], ['po', 'Purchase order'], ['agreement', 'Agreement'],
]
export type WonFields = { won_basis: string; won_at: string; won_ref: string }

/** "Won" = the customer's email / LOI / PO / agreement is in hand (not a verbal yes,
 * not the invoice). Revenue is recognised later, when the tax invoice is raised. */
export default function WonEvidence({ value, onChange, idPrefix = 'won' }: {
  value: WonFields; onChange: (v: WonFields) => void; idPrefix?: string
}) {
  const set = (k: keyof WonFields) => (e: any) => onChange({ ...value, [k]: e.target.value })
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3 space-y-3">
      <div className="text-xs text-emerald-800">A deal is <b>Won</b> when you hold the customer’s email, LOI, PO or agreement. Revenue counts when the tax invoice is raised.</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="form-label block mb-1" htmlFor={`${idPrefix}-basis`}>Customer commitment <span className="text-brand-pink">*</span></label>
          <select id={`${idPrefix}-basis`} className="form-input" value={value.won_basis} onChange={set('won_basis')}>
            <option value="">— choose —</option>
            {WON_BASES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="form-label block mb-1" htmlFor={`${idPrefix}-at`}>Date received <span className="text-brand-pink">*</span></label>
          <input id={`${idPrefix}-at`} type="date" className="form-input" value={value.won_at} onChange={set('won_at')} />
        </div>
        <div className="sm:col-span-2">
          <label className="form-label block mb-1" htmlFor={`${idPrefix}-ref`}>PO / LOI / agreement number (optional)</label>
          <input id={`${idPrefix}-ref`} className="form-input" value={value.won_ref} onChange={set('won_ref')} />
        </div>
      </div>
    </div>
  )
}
