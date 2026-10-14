import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, AlertTriangle } from 'lucide-react'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import { SALUTATIONS, phoneError, emailError, nameError, linkedinError, PHONE_HELP } from '@/lib/validation'
import { TextInput, SelectInput, FormSection } from '@/components/ui/Field'

export type ContactLite = {
  id: string; name: string; first_name: string; last_name?: string | null; salutation?: string | null
  designation?: string | null; department?: string | null; email?: string | null
  phone_primary?: string | null; phone_secondary?: string | null; linkedin_url?: string | null
  incomplete?: boolean; missing?: string[]; status?: string; account_id?: string; account_name?: string | null
  left_at?: string | null; previous_contact_id?: string | null; do_not_contact?: boolean
}

type Prefill = Partial<Pick<ContactLite, 'salutation' | 'first_name' | 'last_name' | 'designation' | 'email' | 'phone_primary' | 'phone_secondary'>>

/** Create (or edit) a person under a company. Primary email AND primary phone are
 * mandatory; everything else is optional. `previousContactId` marks a person who
 * moved here from another company. */
export function ContactForm({ accountId, accountName, initial, prefill, previousContactId, allowAnother = true, onSaved, onCancel }: {
  allowAnother?: boolean; accountId: string; accountName?: string; initial?: ContactLite; prefill?: Prefill; previousContactId?: string
  onSaved: (c: ContactLite, another: boolean) => void; onCancel: () => void
}) {
  const qc = useQueryClient()
  const editing = !!initial
  const seed: any = initial ?? prefill ?? {}
  const blank = { salutation: '', first_name: '', last_name: '', designation: '', email: '', phone_primary: '', phone_secondary: '', linkedin_url: '' }
  const [f, setF] = useState({
    salutation: seed.salutation ?? '', first_name: seed.first_name ?? '', last_name: seed.last_name ?? '',
    designation: seed.designation ?? '', email: seed.email ?? '', phone_primary: seed.phone_primary ?? '',
    phone_secondary: seed.phone_secondary ?? '', linkedin_url: initial?.linkedin_url ?? '',
  })
  const [showAlt, setShowAlt] = useState(!!f.phone_secondary)
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [dups, setDups] = useState<any[] | null>(null)
  const [reason, setReason] = useState('')
  const [nonce, setNonce] = useState(0)          // re-focus first field after "save & add another"
  const set = (k: string) => (e: any) => { setDups(null); setF(p => ({ ...p, [k]: e.target.value })) }
  const blur = (k: string) => () => setTouched(t => ({ ...t, [k]: true }))

  const errs = {
    first_name: nameError(f.first_name, true, 'First name'),
    last_name: nameError(f.last_name, false, 'Last name'),
    email: emailError(f.email, true),
    phone_primary: phoneError(f.phone_primary, true),
    phone_secondary: phoneError(f.phone_secondary, false),
    linkedin_url: linkedinError(f.linkedin_url),
  }
  const bad = Object.values(errs).some(Boolean)

  const save = useMutation({
    mutationFn: async ({ allowReason }: { allowReason?: string; another: boolean }) => {
      const body: any = {
        salutation: f.salutation || undefined, first_name: f.first_name.trim(), last_name: f.last_name.trim() || undefined,
        designation: f.designation.trim() || undefined, email: f.email.trim(),
        phone_primary: f.phone_primary.trim(), phone_secondary: f.phone_secondary.trim() || undefined,
        linkedin_url: f.linkedin_url.trim() || undefined,
      }
      if (editing) {
        for (const k of ['salutation', 'last_name', 'designation', 'phone_secondary', 'linkedin_url']) if (body[k] === undefined) body[k] = null
        return api.patch(`/contacts/${initial!.id}`, body).then(r => r.data)
      }
      body.account_id = accountId
      if (previousContactId) body.previous_contact_id = previousContactId
      if (allowReason) body.allow_duplicate_reason = allowReason
      return api.post('/contacts', body).then(r => r.data)
    },
    onSuccess: (c, vars) => {
      ;['contacts', 'accounts', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] }))
      toast.success(editing ? 'Contact updated.' : 'Contact added.')
      if (vars.another) { setF(blank); setTouched({}); setDups(null); setShowAlt(false); setReason(''); setNonce(n => n + 1) }
      onSaved(c, vars.another)
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      if (e?.response?.status === 409 && d?.duplicates) setDups(d.duplicates)
      else toast.error(getErrorMessage(e, 'Could not save contact'))
    },
  })
  const submit = (another: boolean) => {
    setTouched({ first_name: true, last_name: true, phone_primary: true, phone_secondary: true, email: true, linkedin_url: true })
    if (!bad) save.mutate({ another })
  }

  return (
    <form className="space-y-3" onSubmit={e => { e.preventDefault(); submit(false) }} noValidate>
      {accountName && <div className="text-xs text-wep-muted">Adding to <b className="text-wep-text">{accountName}</b></div>}
      <FormSection>Person</FormSection>
      <div className="grid grid-cols-1 sm:grid-cols-6 gap-x-3">
        <SelectInput className="sm:col-span-2" label="Title" value={f.salutation} onChange={set('salutation')}>
          <option value="">—</option>{SALUTATIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </SelectInput>
        <TextInput key={`fn${nonce}`} className="sm:col-span-4" label="First name" required autoFocus autoComplete="off" value={f.first_name} onChange={set('first_name')} onBlur={blur('first_name')}
          error={errs.first_name} showError={touched.first_name} valid />
        <TextInput className="sm:col-span-3" label="Last name" autoComplete="off" value={f.last_name} onChange={set('last_name')} onBlur={blur('last_name')} error={errs.last_name} showError={touched.last_name} valid />
        <TextInput className="sm:col-span-3" label="Designation" placeholder="e.g. CIO, Head of IT" value={f.designation} onChange={set('designation')} />
      </div>

      <FormSection>How to reach them</FormSection>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
        <TextInput label="Primary email" required type="email" inputMode="email" autoCapitalize="none" autoComplete="off" placeholder="name@company.com"
          value={f.email} onChange={set('email')} onBlur={blur('email')} error={errs.email} showError={touched.email} valid />
        <TextInput label="Primary phone" required type="tel" inputMode="tel" autoComplete="off" placeholder="98765 43210 or +44 20 7946 0958"
          value={f.phone_primary} onChange={set('phone_primary')} onBlur={blur('phone_primary')} error={errs.phone_primary} showError={touched.phone_primary} valid
          hint={touched.phone_primary ? undefined : PHONE_HELP} />
        {showAlt
          ? <TextInput label="Alternate phone" type="tel" inputMode="tel" autoComplete="off" value={f.phone_secondary} onChange={set('phone_secondary')} onBlur={blur('phone_secondary')}
              error={errs.phone_secondary} showError={touched.phone_secondary} valid />
          : <div className="pt-1"><button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-pink min-h-[36px]" onClick={() => setShowAlt(true)}><Plus size={14} aria-hidden />Add alternate number</button></div>}
        <TextInput label="LinkedIn" placeholder="https://www.linkedin.com/in/…" inputMode="url" autoCapitalize="none" value={f.linkedin_url} onChange={set('linkedin_url')} onBlur={blur('linkedin_url')}
          error={errs.linkedin_url} showError={touched.linkedin_url} valid />
      </div>

      {dups && (
        <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs space-y-2">
          <div className="font-semibold text-wep-text">This looks like someone already at this company:</div>
          {dups.map(d => (
            <div key={d.id} className="flex items-center justify-between gap-2 bg-white rounded-lg px-3 py-2">
              <span className="text-sm">{d.name}{d.phone_primary ? ` · ${d.phone_primary}` : ''}{d.email ? ` · ${d.email}` : ''}
                <span className="text-wep-muted text-xs"> ({d.match_reasons.join(', ')})</span></span>
              <button type="button" className="btn-outline !py-1.5 text-xs shrink-0" onClick={() => onSaved(d, false)}>Use existing</button>
            </div>
          ))}
          <div className="flex gap-2">
            <input className="form-input flex-1" aria-label="Reason for creating anyway" placeholder="Different person? Reason (min 5 characters)" value={reason} onChange={e => setReason(e.target.value)} />
            <button type="button" className="btn-outline text-xs" disabled={reason.trim().length < 5 || save.isPending} onClick={() => save.mutate({ allowReason: reason.trim(), another: false })}>Create anyway</button>
          </div>
        </div>
      )}

      <div className="flex gap-2 justify-end flex-wrap pt-1">
        <button type="button" className="btn-outline" onClick={onCancel}>Cancel</button>
        {!editing && allowAnother && <button type="button" className="btn-outline" disabled={save.isPending || !!dups} onClick={() => submit(true)}>Save &amp; add another person</button>}
        <button type="submit" className="btn-primary" disabled={save.isPending || !!dups}>{save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Save contact'}</button>
      </div>
    </form>
  )
}

/** Complete a legacy contact: asks only for what's missing (primary phone and/or email). */
export function CompleteDetailsInline({ contact, onDone }: { contact: ContactLite; onDone: (c: ContactLite) => void }) {
  const qc = useQueryClient()
  const needPhone = !contact.phone_primary, needEmail = !contact.email
  const [p, setP] = useState(''), [e, setE] = useState('')
  const pe = needPhone && p ? phoneError(p, true) : null
  const ee = needEmail && e ? emailError(e, true) : null
  const ready = (!needPhone || (p.trim() && !pe)) && (!needEmail || (e.trim() && !ee))
  const save = useMutation({
    mutationFn: () => api.patch(`/contacts/${contact.id}`, { ...(needPhone ? { phone_primary: p.trim() } : {}), ...(needEmail ? { email: e.trim() } : {}) }).then(r => r.data),
    onSuccess: (c) => { ;['contacts', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] })); toast.success('Details saved.'); onDone(c) },
    onError: (err: any) => toast.error(getErrorMessage(err, 'Could not save')),
  })
  return (
    <form className="flex flex-wrap items-start gap-2" onSubmit={ev => { ev.preventDefault(); if (ready) save.mutate() }}>
      {needEmail && <div><input className="form-input !py-1.5 !text-xs w-48" type="email" aria-label="Primary email" placeholder="Primary email *" value={e} onChange={x => setE(x.target.value)} />{ee && <div className="text-[10px] text-red-600 mt-0.5">{ee}</div>}</div>}
      {needPhone && <div><input className="form-input !py-1.5 !text-xs w-40" type="tel" aria-label="Primary phone" placeholder="Primary phone *" value={p} onChange={x => setP(x.target.value)} />{pe && <div className="text-[10px] text-red-600 mt-0.5 max-w-[240px]">{pe}</div>}</div>}
      <button type="submit" className="btn-primary !py-1.5 !px-3 text-xs" disabled={!ready || save.isPending}>Save</button>
    </form>
  )
}

export function missingLabel(c: ContactLite) {
  const m = c.missing ?? [!c.phone_primary && 'phone', !c.email && 'email'].filter(Boolean) as string[]
  return m.length ? `add ${m.join(' & ')}` : 'complete details'
}

/** Pick customer attendees from the meeting company's contacts (active only). */
export default function ContactPicker({ accountId, accountName, addedIds, onPick }: {
  accountId: string; accountName?: string; addedIds: string[]; onPick: (c: ContactLite) => void
}) {
  const [adding, setAdding] = useState(false)
  const [fixing, setFixing] = useState<string | null>(null)
  const { data } = useQuery({
    queryKey: ['contacts', 'account', accountId],
    queryFn: () => api.get('/contacts', { params: { account_id: accountId, include_left: false } }).then(r => r.data),
    enabled: !!accountId,
  })
  const items: ContactLite[] = (data?.items ?? []).filter((c: ContactLite) => !addedIds.includes(c.id))

  return (
    <div className="mt-2 space-y-2">
      {items.length > 0 && (
        <div className="text-xs">
          <div className="text-wep-muted mb-1.5">Contacts at {accountName || 'this company'}</div>
          <div className="flex flex-wrap gap-1.5">
            {items.map(c => c.incomplete ? (
              fixing === c.id
                ? <div key={c.id} className="w-full rounded-xl border border-amber-300 bg-amber-50 p-2"><div className="text-[11px] mb-1.5 font-semibold">{c.name} — complete details to add to this MOM</div>
                    <CompleteDetailsInline contact={c} onDone={(u) => { setFixing(null); onPick(u) }} /></div>
                : <button key={c.id} type="button" onClick={() => setFixing(c.id)} title="Needs a primary phone and email before it can be added to a MOM"
                    className="inline-flex items-center gap-1 px-3 min-h-[36px] rounded-full border border-amber-300 bg-amber-50 text-wep-text hover:border-wep-amber"><AlertTriangle size={13} className="text-wep-amber" aria-hidden />{c.name} · {missingLabel(c)}</button>
            ) : (
              <button key={c.id} type="button" onClick={() => onPick(c)}
                className="inline-flex items-center gap-1 px-3 min-h-[36px] rounded-full border border-wep-border bg-white hover:border-brand-pink hover:text-brand-pink transition-colors">
                <Plus size={13} aria-hidden />{c.name}{c.designation ? <span className="text-wep-muted"> · {c.designation}</span> : null}</button>
            ))}
          </div>
        </div>
      )}
      {adding
        ? <div className="rounded-xl border border-wep-border p-3 bg-wep-surface"><ContactForm accountId={accountId} accountName={accountName}
            onSaved={(c, another) => { if (!another) setAdding(false); onPick(c) }} onCancel={() => setAdding(false)} /></div>
        : <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-pink min-h-[36px]" onClick={() => setAdding(true)}><Plus size={14} aria-hidden />Add new contact</button>}
    </div>
  )
}
