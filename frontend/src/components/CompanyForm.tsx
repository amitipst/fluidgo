import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import { useGeo, postalError } from '@/hooks/useGeo'
import { useWebsiteCheck } from '@/hooks/useWebsiteCheck'
import { websiteError } from '@/lib/validation'
import { TextInput, SelectInput, FormSection } from '@/components/ui/Field'

export type Company = {
  id: string; name: string; industry?: string | null; website?: string | null
  address_line1?: string | null; address_line2?: string | null; city?: string | null
  state?: string | null; country?: string | null; postal_code?: string | null
  contact_count?: number
}

/** Create or edit a company (account) incl. a global address. Website is optional
 * but live-checked (advisory). A duplicate name offers the existing company. */
export default function CompanyForm({ initial, onSaved, onCancel }: {
  initial?: Company; onSaved: (c: Company) => void; onCancel: () => void
}) {
  const qc = useQueryClient()
  const { data: geo } = useGeo()
  const web = useWebsiteCheck()
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
  const set = (k: string) => (e: any) => {
    setDups(null)
    setF(p => ({ ...p, [k]: e.target.value, ...(k === 'country' ? { state: '', postal_code: '' } : {}) }))
    if (k === 'website') web.reset()
  }
  const blur = (k: string) => () => {
    setTouched(t => ({ ...t, [k]: true }))
    if (k === 'website') web.check(f.website, (u) => setF(p => ({ ...p, website: u })))
  }

  const hasAddr = !!(f.address_line1 || f.address_line2 || f.city || f.state || f.postal_code)
  const errs = {
    name: f.name.trim().length < 2 ? 'Company name is required' : null,
    website: websiteError(f.website),
    postal_code: postalError(geo, f.country, f.postal_code),
    country: hasAddr && !f.country ? 'Select a country for this address' : null,
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
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ['accounts'] }); qc.invalidateQueries({ queryKey: ['account'] }); toast.success(editing ? 'Company updated.' : 'Company added.'); onSaved(c) },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      if (e?.response?.status === 409 && d?.duplicates) setDups(d.duplicates)
      else toast.error(getErrorMessage(e, 'Could not save company'))
    },
  })
  const submit = () => { setTouched({ name: true, website: true, postal_code: true, country: true }); if (!bad) save.mutate(undefined) }

  return (
    <form className="space-y-3" onSubmit={e => { e.preventDefault(); submit() }} noValidate>
      <FormSection>Company</FormSection>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
        <TextInput className="sm:col-span-2" label="Company name" required autoFocus placeholder="e.g. Wep Solutions Ltd"
          value={f.name} onChange={set('name')} onBlur={blur('name')} error={errs.name} showError={touched.name} valid />
        <TextInput label="Industry" placeholder="e.g. BFSI, Healthcare, IT" value={f.industry} onChange={set('industry')} />
        <TextInput label="Website" placeholder="www.company.com" inputMode="url" autoCapitalize="none" hint="Optional — we'll check that it's live."
          value={f.website} onChange={set('website')} onBlur={blur('website')} error={errs.website} showError={touched.website} status={web.status} valid={web.status?.kind === 'ok'} />
      </div>

      <FormSection>Address</FormSection>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
        <TextInput className="sm:col-span-2" label="Address line 1" placeholder="Building, street" autoComplete="address-line1" value={f.address_line1} onChange={set('address_line1')} />
        <TextInput className="sm:col-span-2" label="Address line 2" placeholder="Area, landmark (optional)" autoComplete="address-line2" value={f.address_line2} onChange={set('address_line2')} />
        <SelectInput label="Country" value={f.country} onChange={set('country')} error={errs.country} showError={touched.country}>
          <option value="">Select country…</option>
          {(geo?.countries ?? []).map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
        </SelectInput>
        {stateList
          ? <SelectInput label="State / UT" value={f.state} onChange={set('state')}>
              <option value="">Select state…</option>
              {stateList.map(s => <option key={s} value={s}>{s}</option>)}
            </SelectInput>
          : <TextInput label="State / Province" value={f.state} onChange={set('state')} autoComplete="address-level1" />}
        <TextInput label="City" value={f.city} onChange={set('city')} autoComplete="address-level2" />
        <TextInput label={f.country === 'US' ? 'ZIP code' : 'Pincode / Postal code'} value={f.postal_code} onChange={set('postal_code')} onBlur={blur('postal_code')}
          error={errs.postal_code} showError={touched.postal_code} valid autoComplete="postal-code" hint={geo?.postal_hints?.[f.country] ? `e.g. ${geo.postal_hints[f.country]}` : undefined} />
      </div>

      {dups && (
        <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs space-y-2">
          <div className="font-semibold text-wep-text">This company already exists — use it instead?</div>
          {dups.map(d => (
            <div key={d.id} className="flex items-center justify-between gap-2 bg-white rounded-lg px-3 py-2">
              <span className="text-sm">{d.name}{d.city ? <span className="text-wep-muted"> · {d.city}</span> : null}</span>
              <button type="button" className="btn-outline !py-1.5 text-xs" onClick={() => onSaved(d)}>Use existing</button>
            </div>
          ))}
          <div className="flex gap-2">
            <input className="form-input flex-1" aria-label="Reason for creating a separate company" placeholder="Different legal entity? Reason (min 5 characters)" value={reason} onChange={e => setReason(e.target.value)} />
            <button type="button" className="btn-outline text-xs" disabled={reason.trim().length < 5 || save.isPending} onClick={() => save.mutate(reason.trim())}>Create anyway</button>
          </div>
        </div>
      )}

      <div className="flex gap-2 justify-end pt-1">
        <button type="button" className="btn-outline" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn-primary" disabled={save.isPending || !!dups}>{save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Save company'}</button>
      </div>
    </form>
  )
}
