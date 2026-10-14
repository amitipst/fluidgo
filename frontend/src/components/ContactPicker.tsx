import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

export type ContactLite = {
  id: string; name: string; first_name: string; last_name?: string | null
  designation?: string | null; email?: string | null; phone_primary?: string | null
  incomplete?: boolean; status?: string; account_name?: string | null
}

/** New-contact form. Primary number is mandatory (Contacts master rule). On a
 * 409 the backend returns the likely duplicates: the user either picks one
 * ("use existing") or creates anyway with a written reason. */
export function NewContactForm({ accountId, accountName, onCreated, onCancel }: {
  accountId?: string; accountName?: string
  onCreated: (c: ContactLite) => void; onCancel: () => void
}) {
  const qc = useQueryClient()
  const [f, setF] = useState({ first_name: '', last_name: '', designation: '', email: '', phone_primary: '' })
  const [dups, setDups] = useState<any[] | null>(null)
  const [reason, setReason] = useState('')
  const set = (k: string) => (e: any) => setF(p => ({ ...p, [k]: e.target.value }))

  const create = useMutation({
    mutationFn: (allowReason?: string) => api.post('/contacts', {
      ...(accountId ? { account_id: accountId } : { account_name: accountName }),
      first_name: f.first_name.trim(), last_name: f.last_name.trim() || undefined,
      designation: f.designation.trim() || undefined, email: f.email.trim() || undefined,
      phone_primary: f.phone_primary.trim(), allow_duplicate_reason: allowReason || undefined,
    }).then(r => r.data),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ['contacts'] }); toast.success('Contact added.'); onCreated(c) },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      if (e?.response?.status === 409 && d?.duplicates) setDups(d.duplicates)
      else toast.error(getErrorMessage(e, 'Could not add contact'))
    },
  })
  const valid = f.first_name.trim() && f.phone_primary.trim()

  return (
    <div className="border border-wep-border rounded-lg p-3 bg-wep-surface space-y-2">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <input className="form-input" placeholder="First name *" value={f.first_name} onChange={set('first_name')} />
        <input className="form-input" placeholder="Last name" value={f.last_name} onChange={set('last_name')} />
        <input className="form-input" placeholder="Designation" value={f.designation} onChange={set('designation')} />
        <input className="form-input" placeholder="Email" type="email" value={f.email} onChange={set('email')} />
        <input className="form-input sm:col-span-2" placeholder="Primary mobile / phone * (e.g. 98765 43210)"
          value={f.phone_primary} onChange={set('phone_primary')} inputMode="tel" />
      </div>
      {dups && (
        <div className="border border-wep-amber rounded p-2 text-xs space-y-2">
          <div className="font-semibold">This looks like someone already on the account:</div>
          {dups.map(d => (
            <div key={d.id} className="flex items-center justify-between gap-2">
              <span>{d.name}{d.phone_primary ? ` · ${d.phone_primary}` : ''}{d.email ? ` · ${d.email}` : ''}
                <span className="text-wep-muted"> ({d.match_reasons.join(', ')})</span></span>
              <button type="button" className="btn-outline text-xs px-2 py-1" onClick={() => onCreated(d)}>Use existing</button>
            </div>
          ))}
          <div className="flex gap-2">
            <input className="form-input flex-1" placeholder="Or create anyway — reason (min 5 chars)"
              value={reason} onChange={e => setReason(e.target.value)} />
            <button type="button" className="btn-outline text-xs px-2 py-1" disabled={reason.trim().length < 5 || create.isPending}
              onClick={() => create.mutate(reason.trim())}>Create anyway</button>
          </div>
        </div>
      )}
      <div className="flex gap-2 justify-end">
        <button type="button" className="btn-outline text-xs px-3 py-1.5" onClick={onCancel}>Cancel</button>
        <button type="button" className="btn-primary text-xs px-3 py-1.5 disabled:opacity-40"
          disabled={!valid || create.isPending || !!dups} onClick={() => create.mutate(undefined)}>
          {create.isPending ? 'Saving…' : 'Save contact'}
        </button>
      </div>
    </div>
  )
}

/** Add a missing primary number to a legacy (incomplete) contact. */
export function AddNumberInline({ contact, onDone }: { contact: ContactLite; onDone: (c: ContactLite) => void }) {
  const qc = useQueryClient()
  const [p, setP] = useState('')
  const save = useMutation({
    mutationFn: () => api.patch(`/contacts/${contact.id}`, { phone_primary: p.trim() }).then(r => r.data),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ['contacts'] }); toast.success('Number saved.'); onDone(c) },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not save number')),
  })
  return (
    <span className="inline-flex items-center gap-1">
      <input className="form-input !py-1 !text-xs w-36" placeholder="Primary number" value={p}
        onChange={e => setP(e.target.value)} inputMode="tel" />
      <button type="button" className="btn-primary text-xs px-2 py-1 disabled:opacity-40"
        disabled={!p.trim() || save.isPending} onClick={() => save.mutate()}>Save</button>
    </span>
  )
}

/** Pick customer attendees from the meeting account's contacts. */
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
          <div className="text-wep-muted mb-1">Contacts on {accountName || 'this account'}:</div>
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
        ? <NewContactForm accountId={accountId} accountName={accountName}
            onCreated={(c) => { setAdding(false); onPick(c) }} onCancel={() => setAdding(false)} />
        : <button type="button" className="text-xs text-brand-pink font-semibold" onClick={() => setAdding(true)}>+ Add new contact</button>}
    </div>
  )
}
