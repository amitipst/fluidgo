import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import { SALUTATIONS, phoneError, emailError, nameError, linkedinError, PHONE_HELP } from '@/lib/validation'

export type ContactLite = {
  id: string; name: string; first_name: string; last_name?: string | null; salutation?: string | null
  designation?: string | null; department?: string | null; email?: string | null
  phone_primary?: string | null; phone_secondary?: string | null; linkedin_url?: string | null
  incomplete?: boolean; status?: string; account_id?: string; account_name?: string | null
  left_at?: string | null; previous_contact_id?: string | null
}

function Err({ m }: { m?: string | null }) { return m ? <div className="text-[11px] text-red-600 mt-0.5">{m}</div> : null }

type Prefill = Partial<Pick<ContactLite, 'salutation' | 'first_name' | 'last_name' | 'designation' | 'email' | 'phone_primary' | 'phone_secondary'>>

/** Create (or edit) a person under a company. Company is fixed — contacts are
 * always added from a company. Inline validation mirrors the backend rules.
 * `previousContactId` marks a person who moved here from another company. */
export function ContactForm({ accountId, accountName, initial, prefill, previousContactId, allowAnother = true, onSaved, onCancel }: {
  allowAnother?: boolean; accountId: string; accountName?: string; initial?: ContactLite; prefill?: Prefill; previousContactId?: string
  onSaved: (c: ContactLite, another: boolean) => void; onCancel: () => void
}) {
  const qc = useQueryClient()
  const editing = !!initial
  const seed = initial ?? prefill ?? {}
  const blank = { salutation: '', first_name: '', last_name: '', designation: '', email: '', phone_primary: '', phone_secondary: '', linkedin_url: '' }
  const [f, setF] = useState({
    salutation: seed.salutation ?? '', first_name: seed.first_name ?? '', last_name: seed.last_name ?? '',
    designation: seed.designation ?? '', email: seed.email ?? '', phone_primary: seed.phone_primary ?? '',
    phone_secondary: seed.phone_secondary ?? '', linkedin_url: (initial?.linkedin_url) ?? '',
  })
  const [showAlt, setShowAlt] = useState(!!f.phone_secondary)
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [dups, setDups] = useState<any[] | null>(null)
  const [reason, setReason] = useState('')
  const set = (k: string) => (e: any) => { setDups(null); setF(p => ({ ...p, [k]: e.target.value })) }
  const blur = (k: string) => () => setTouched(t => ({ ...t, [k]: true }))

  const errs = {
    first_name: nameError(f.first_name, true, 'First name'),
    last_name: nameError(f.last_name, false, 'Last name'),
    phone_primary: phoneError(f.phone_primary, true),
    phone_secondary: phoneError(f.phone_secondary, false),
    email: emailError(f.email),
    linkedin_url: linkedinError(f.linkedin_url),
  }
  const bad = Object.values(errs).some(Boolean)

  const save = useMutation({
    mutationFn: async ({ allowReason }: { allowReason?: string; another: boolean }) => {
      const body: any = {
        salutation: f.salutation || undefined, first_name: f.first_name.trim(), last_name: f.last_name.trim() || undefined,
        designation: f.designation.trim() || undefined, email: f.email.trim() || undefined,
        phone_primary: f.phone_primary.trim(), phone_secondary: f.phone_secondary.trim() || undefined,
        linkedin_url: f.linkedin_url.trim() || undefined,
      }
      if (editing) {
        // PATCH: send blanks as null so a field can be cleared (primary phone can't be)
        for (const k of ['salutation', 'last_name', 'designation', 'email', 'phone_secondary', 'linkedin_url']) if (body[k] === undefined) body[k] = null
        return api.patch(`/contacts/${initial!.id}`, body).then(r => r.data)
      }
      body.account_id = accountId
      if (previousContactId) body.previous_contact_id = previousContactId
      if (allowReason) body.allow_duplicate_reason = allowReason
      return api.post('/contacts', body).then(r => r.data)
    },
    onSuccess: (c, vars) => {
      qc.invalidateQueries({ queryKey: ['contacts'] }); qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['account'] })
      toast.success(editing ? 'Contact updated.' : 'Contact added.')
      if (vars.another) { setF(blank); setTouched({}); setDups(null); setShowAlt(false); setReason('') }
      onSaved(c, vars.another)
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      if (e?.response?.status === 409 && d?.duplicates) setDups(d.duplicates)
      else toast.error(getErrorMessage(e, 'Could not save contact'))
    },
  })
  const submit = (another: boolean) => { setTouched({ first_name: true, last_name: true, phone_primary: true, phone_secondary: true, email: true, linkedin_url: true }); if (!bad) save.mutate({ another }) }

  return (
    <div className="border border-wep-border rounded-lg p-3 bg-wep-surface space-y-2">
      {accountName && <div className="text-[11px] text-wep-muted">Company: <b className="text-wep-text">{accountName}</b></div>}
      <div className="grid grid-cols-1 sm:grid-cols-6 gap-2">
        <select className="form-input sm:col-span-1" value={f.salutation} onChange={set('salutation')} aria-label="Salutation">
          <option value="">Title</option>
          {SALUTATIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="sm:col-span-2">
          <input className="form-input" placeholder="First name *" value={f.first_name} onChange={set('first_name')} onBlur={blur('first_name')} />
          {touched.first_name && <Err m={errs.first_name} />}
        </div>
        <div className="sm:col-span-3">
          <input className="form-input" placeholder="Last name" value={f.last_name} onChange={set('last_name')} onBlur={blur('last_name')} />
          {touched.last_name && <Err m={errs.last_name} />}
        </div>
        <input className="form-input sm:col-span-3" placeholder="Designation" value={f.designation} onChange={set('designation')} />
        <div className="sm:col-span-3">
          <input className="form-input" placeholder="Email" type="email" value={f.email} onChange={set('email')} onBlur={blur('email')} />
          {touched.email && <Err m={errs.email} />}
        </div>
        <div className="sm:col-span-3">
          <input className="form-input" placeholder="Primary mobile / phone *" value={f.phone_primary} onChange={set('phone_primary')} onBlur={blur('phone_primary')} inputMode="tel" />
          {touched.phone_primary ? <Err m={errs.phone_primary} /> : <div className="text-[10px] text-wep-muted mt-0.5">{PHONE_HELP}</div>}
        </div>
        <div className="sm:col-span-3">
          {showAlt ? (
            <>
              <input className="form-input" placeholder="Alternate number" value={f.phone_secondary} onChange={set('phone_secondary')} onBlur={blur('phone_secondary')} inputMode="tel" />
              {touched.phone_secondary && <Err m={errs.phone_secondary} />}
            </>
          ) : (
            <button type="button" className="text-xs text-brand-pink font-semibold pt-2" onClick={() => setShowAlt(true)}>+ Add alternate number</button>
          )}
        </div>
        <div className="sm:col-span-6">
          <input className="form-input" placeholder="LinkedIn profile (optional)" value={f.linkedin_url} onChange={set('linkedin_url')} onBlur={blur('linkedin_url')} />
          {touched.linkedin_url && <Err m={errs.linkedin_url} />}
        </div>
      </div>

      {dups && (
        <div className="border border-wep-amber rounded p-2 text-xs space-y-2">
          <div className="font-semibold">This looks like someone already on this company:</div>
          {dups.map(d => (
            <div key={d.id} className="flex items-center justify-between gap-2">
              <span>{d.name}{d.phone_primary ? ` · ${d.phone_primary}` : ''}{d.email ? ` · ${d.email}` : ''}
                <span className="text-wep-muted"> ({d.match_reasons.join(', ')})</span></span>
              <button type="button" className="btn-outline text-xs px-2 py-1" onClick={() => onSaved(d, false)}>Use existing</button>
            </div>
          ))}
          <div className="flex gap-2">
            <input className="form-input flex-1" placeholder="Or create anyway — reason (min 5 chars)" value={reason} onChange={e => setReason(e.target.value)} />
            <button type="button" className="btn-outline text-xs px-2 py-1" disabled={reason.trim().length < 5 || save.isPending}
              onClick={() => save.mutate({ allowReason: reason.trim(), another: false })}>Create anyway</button>
          </div>
        </div>
      )}
      <div className="flex gap-2 justify-end flex-wrap">
        <button type="button" className="btn-outline text-xs px-3 py-1.5" onClick={onCancel}>Cancel</button>
        {!editing && allowAnother && <button type="button" className="btn-outline text-xs px-3 py-1.5 disabled:opacity-40" disabled={save.isPending || !!dups} onClick={() => submit(true)}>Save &amp; add another person</button>}
        <button type="button" className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40" disabled={save.isPending || !!dups} onClick={() => submit(false)}>
          {save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Save contact'}</button>
      </div>
    </div>
  )
}

/** Add a missing primary number to a legacy (incomplete) contact. */
export function AddNumberInline({ contact, onDone }: { contact: ContactLite; onDone: (c: ContactLite) => void }) {
  const qc = useQueryClient()
  const [p, setP] = useState('')
  const err = p ? phoneError(p, true) : null
  const save = useMutation({
    mutationFn: () => api.patch(`/contacts/${contact.id}`, { phone_primary: p.trim() }).then(r => r.data),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ['contacts'] }); qc.invalidateQueries({ queryKey: ['account'] }); toast.success('Number saved.'); onDone(c) },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not save number')),
  })
  return (
    <span className="inline-flex flex-col">
      <span className="inline-flex items-center gap-1">
        <input className="form-input !py-1 !text-xs w-36" placeholder="Primary number" value={p}
          onChange={e => setP(e.target.value)} inputMode="tel" />
        <button type="button" className="btn-primary text-xs px-2 py-1 disabled:opacity-40"
          disabled={!p.trim() || !!err || save.isPending} onClick={() => save.mutate()}>Save</button>
      </span>
      {err && <span className="text-[10px] text-red-600">{err}</span>}
    </span>
  )
}

/** Pick customer attendees from the meeting company's contacts (active only). */
export default function ContactPicker({ accountId, accountName, addedIds, onPick }: {
  accountId: string; accountName?: string; addedIds: string[]
  onPick: (c: ContactLite) => void
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
          <div className="text-wep-muted mb-1">Contacts on {accountName || 'this company'}:</div>
          <div className="flex flex-wrap gap-1.5">
            {items.map(c => (
              <span key={c.id} className="inline-flex items-center gap-1.5">
                {c.incomplete || !c.phone_primary ? (
                  fixing === c.id
                    ? <AddNumberInline contact={c} onDone={(u) => { setFixing(null); onPick(u) }} />
                    : <button type="button" onClick={() => setFixing(c.id)}
                        className="px-2.5 py-1 rounded-full border border-wep-amber text-wep-text bg-wep-surface"
                        title="Add a primary number before adding to the MOM">⚠️ {c.name} — add number</button>
                ) : (
                  <button type="button" onClick={() => onPick(c)}
                    className="px-2.5 py-1 rounded-full border border-wep-border bg-wep-surface hover:border-wep-border-strong">
                    + {c.name}{c.designation ? ` · ${c.designation}` : ''}</button>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
      {adding
        ? <ContactForm accountId={accountId} accountName={accountName}
            onSaved={(c, another) => { if (!another) setAdding(false); onPick(c) }} onCancel={() => setAdding(false)} />
        : <button type="button" className="text-xs text-brand-pink font-semibold" onClick={() => setAdding(true)}>+ Add new contact</button>}
    </div>
  )
}
