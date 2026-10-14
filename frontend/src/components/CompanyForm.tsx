import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import { useGeo, postalError } from '@/hooks/useGeo'
import { websiteError } from '@/lib/validation'

export type Company = {
  id: string; name: string; industry?: string | null; website?: string | null
  address_line1?: string | null; address_line2?: string | null; city?: string | null
  state?: string | null; country?: string | null; postal_code?: string | null
  contact_count?: number
}

function Err({ m }: { m?: string | null }) { return m ? <div className="text-[11px] text-red-600 mt-0.5">{m}</div> : null }

/** Create or edit a company (account) incl. a global address. On a duplicate
 * name the backend returns the existing company: use it, or create anyway with
 * a reason. */
export default function CompanyForm({ initial, onSaved, onCancel }: {
  initial?: Company; onSaved: (c: Company) => void; onCancel: () => void
}) {
  const qc = useQueryClient()
  const { data: geo } = useGeo()
  const editing = !!initial
  const [f, setF] = useState({
    name: initial?.name ?? '', industry: initial?.industry ?? '', website: initial?.website ?? '',
    address_line1: initial?.address_line1 ?? '', address_line2: initial?.address_line2 ?? '',
    city: initial?.city ?? '', state: initial?.state ?? '', country: initial?.country ?? 'IN',
    postal_code: initial?.postal_code ?? '',
  })
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [dups, setDups] = useState<Company[] | null>(null)
  const [reason, setReason] = useState('')
  const set = (k: string) => (e: any) => setF(p => ({ ...p, [k]: e.target.value, ...(k === 'country' ? { state: '', postal_code: '' } : {}) }))
  const blur = (k: string) => () => setTouched(t => ({ ...t, [k]: true }))

  const hasAddr = !!(f.address_line1 || f.address_line2 || f.city || f.state || f.postal_code)
  const errs = {
    name: f.name.trim().length < 2 ? 'Company name is required' : null,
    website: websiteError(f.website),
    postal_code: postalError(geo, f.country, f.postal_code),
    country: hasAddr && !f.country ? 'Select a country' : null,
  }
  const bad = Object.values(errs).some(Boolean)
  const stateList = geo?.states?.[f.country]

  const save = useMutation({
    mutationFn: (allowReason?: string) => {
      const body: any = {
        name: f.name.trim(), industry: f.industry.trim() || undefined, website: f.website.trim() || undefined,
        address_line1: f.address_line1, address_line2: f.address_line2, city: f.city,
        state: f.state, country: f.country || undefined, postal_code: f.postal_code,
      }
      if (allowReason) body.allow_duplicate_reason = allowReason
      return (editing ? api.patch(`/accounts/${initial!.id}`, body) : api.post('/accounts', body)).then(r => r.data)
    },
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ['accounts'] }); toast.success(editing ? 'Company updated.' : 'Company added.'); onSaved(c) },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      if (e?.response?.status === 409 && d?.duplicates) setDups(d.duplicates)
      else toast.error(getErrorMessage(e, 'Could not save company'))
    },
  })

  return (
    <div className="border border-wep-border rounded-lg p-3 bg-wep-surface space-y-2">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="sm:col-span-2">
          <input className="form-input" placeholder="Company name *" value={f.name} onChange={set('name')} onBlur={blur('name')} />
          {touched.name && <Err m={errs.name} />}
        </div>
        <input className="form-input" placeholder="Industry (e.g. BFSI, Healthcare)" value={f.industry} onChange={set('industry')} />
        <div>
          <input className="form-input" placeholder="Website (www.acme.com)" value={f.website} onChange={set('website')} onBlur={blur('website')} />
          {touched.website && <Err m={errs.website} />}
        </div>
        <input className="form-input sm:col-span-2" placeholder="Address line 1" value={f.address_line1} onChange={set('address_line1')} />
        <input className="form-input sm:col-span-2" placeholder="Address line 2" value={f.address_line2} onChange={set('address_line2')} />
        <select className="form-input" value={f.country} onChange={set('country')}>
          <option value="">Country…</option>
          {(geo?.countries ?? []).map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
        </select>
        {stateList
          ? <select className="form-input" value={f.state} onChange={set('state')}>
              <option value="">State / UT…</option>
              {stateList.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          : <input className="form-input" placeholder="State / Province" value={f.state} onChange={set('state')} />}
        <input className="form-input" placeholder="City" value={f.city} onChange={set('city')} />
        <div>
          <input className="form-input" placeholder={f.country === 'US' ? 'ZIP code' : 'Pincode / Postal code'}
            value={f.postal_code} onChange={set('postal_code')} onBlur={blur('postal_code')} inputMode="text" />
          {touched.postal_code && <Err m={errs.postal_code} />}
        </div>
      </div>
      <Err m={touched.country ? errs.country : null} />

      {dups && (
        <div className="border border-wep-amber rounded p-2 text-xs space-y-2">
          <div className="font-semibold">This company already exists:</div>
          {dups.map(d => (
            <div key={d.id} className="flex items-center justify-between gap-2">
              <span>{d.name}{d.city ? ` · ${d.city}` : ''}</span>
              <button type="button" className="btn-outline text-xs px-2 py-1" onClick={() => onSaved(d)}>Use existing</button>
            </div>
          ))}
          <div className="flex gap-2">
            <input className="form-input flex-1" placeholder="Or create anyway — reason (min 5 chars)" value={reason} onChange={e => setReason(e.target.value)} />
            <button type="button" className="btn-outline text-xs px-2 py-1" disabled={reason.trim().length < 5 || save.isPending}
              onClick={() => save.mutate(reason.trim())}>Create anyway</button>
          </div>
        </div>
      )}
      <div className="flex gap-2 justify-end">
        <button type="button" className="btn-outline text-xs px-3 py-1.5" onClick={onCancel}>Cancel</button>
        <button type="button" className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40"
          disabled={bad || !f.name.trim() || save.isPending || !!dups}
          onClick={() => save.mutate(undefined)}>{save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Save company'}</button>
      </div>
    </div>
  )
}
