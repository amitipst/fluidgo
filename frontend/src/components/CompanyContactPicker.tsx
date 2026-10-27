import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, Building2, UserRound, Check, X } from 'lucide-react'
import api from '@/hooks/useApi'
import Modal from '@/components/ui/Modal'
import CompanyForm, { type Company } from '@/components/CompanyForm'
import { ContactForm, type ContactLite } from '@/components/ContactPicker'

export type CompanyContact = {
  accountId: string; accountName: string
  contactId: string; contactName: string
}
export const emptyCompanyContact: CompanyContact = { accountId: '', accountName: '', contactId: '', contactName: '' }

/** Company-first picker (v1.5.0): every lead and deal starts here. Pick the
 * company, then the person; either can be added on the spot so nobody has to
 * leave the form. The chosen pair links the record to the Contacts master. */
export default function CompanyContactPicker({ value, onChange, disabled, suggestName }: {
  value: CompanyContact; onChange: (v: CompanyContact) => void; disabled?: boolean
  /** Customer name already on the record (legacy deal/lead): pre-fills the search and the Add-company form. */
  suggestName?: string
}) {
  const [q, setQ] = useState(suggestName ?? '')
  const [dq, setDq] = useState((suggestName ?? '').trim())
  const [addCompany, setAddCompany] = useState(false)
  const [addContact, setAddContact] = useState(false)
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 250); return () => clearTimeout(t) }, [q])

  const searching = !value.accountId && dq.length >= 1
  const { data: accts } = useQuery({
    queryKey: ['accounts', 'pick', dq],
    queryFn: () => api.get('/accounts', { params: { q: dq, limit: 8 } }).then(r => r.data),
    enabled: searching,
  })
  const { data: ctcs } = useQuery({
    queryKey: ['contacts', 'account', value.accountId],
    queryFn: () => api.get('/contacts', { params: { account_id: value.accountId, include_left: false } }).then(r => r.data),
    enabled: !!value.accountId,
  })
  const contacts: ContactLite[] = ctcs?.items ?? []
  const pickCompany = (a: Company) => { setQ(''); onChange({ ...emptyCompanyContact, accountId: a.id, accountName: a.name }) }
  const pickContact = (c: ContactLite) => onChange({ ...value, contactId: c.id, contactName: c.name })

  return (
    <div className="space-y-3">
      <div>
        <div className="form-label mb-1">Company <span className="text-brand-pink" aria-hidden>*</span></div>
        {value.accountId ? (
          <div className="flex items-center justify-between gap-2 rounded-xl border border-wep-border bg-wep-surface px-3 min-h-[44px]">
            <span className="flex items-center gap-2 text-sm font-semibold text-wep-text min-w-0"><Building2 size={16} className="text-brand-pink shrink-0" aria-hidden /><span className="truncate">{value.accountName}</span></span>
            {!disabled && <button type="button" className="text-xs text-wep-muted inline-flex items-center gap-1 min-h-[36px]" onClick={() => onChange(emptyCompanyContact)}><X size={14} aria-hidden />Change</button>}
          </div>
        ) : (
          <>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-wep-muted" aria-hidden />
              <input className="form-input !pl-9" aria-label="Search company" placeholder="Search company by name…" autoComplete="off" disabled={disabled}
                value={q} onChange={e => setQ(e.target.value)} />
            </div>
            {searching && (
              <div className="mt-1.5 rounded-xl border border-wep-border bg-white divide-y divide-wep-border overflow-hidden">
                {(accts?.items ?? []).map((a: Company) => (
                  <button key={a.id} type="button" onClick={() => pickCompany(a)} className="w-full text-left px-3 min-h-[44px] text-sm hover:bg-wep-surface flex items-center justify-between gap-2">
                    <span className="truncate">{a.name}</span>
                    <span className="text-[11px] text-wep-muted shrink-0">{a.contact_count ?? 0} contact{(a.contact_count ?? 0) === 1 ? '' : 's'}</span>
                  </button>
                ))}
                {accts && accts.items.length === 0 && <div className="px-3 py-2.5 text-xs text-wep-muted">No company matches “{dq}”.</div>}
              </div>
            )}
            <button type="button" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-brand-pink min-h-[36px]" onClick={() => setAddCompany(true)}><Plus size={14} aria-hidden />Add new company</button>
          </>
        )}
      </div>

      {value.accountId && (
        <div>
          <div className="form-label mb-1">Contact <span className="text-brand-pink" aria-hidden>*</span></div>
          <div className="flex flex-wrap gap-1.5">
            {contacts.map(c => {
              const on = c.id === value.contactId
              return (
                <button key={c.id} type="button" disabled={disabled} onClick={() => pickContact(c)} aria-pressed={on}
                  className={`inline-flex items-center gap-1 px-3 min-h-[40px] rounded-full border text-sm transition-colors ${on ? 'border-brand-pink bg-brand-pink/10 text-brand-pink font-semibold' : 'border-wep-border bg-white hover:border-brand-pink'}`}>
                  {on ? <Check size={14} aria-hidden /> : <UserRound size={14} aria-hidden />}{c.name}{c.designation ? <span className="text-wep-muted font-normal"> · {c.designation}</span> : null}
                </button>
              )
            })}
            {ctcs && contacts.length === 0 && <div className="text-xs text-wep-muted py-2">No one added at {value.accountName} yet.</div>}
          </div>
          {!disabled && <button type="button" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-brand-pink min-h-[36px]" onClick={() => setAddContact(true)}><Plus size={14} aria-hidden />Add new contact at {value.accountName}</button>}
        </div>
      )}

      {addCompany && (
        <Modal title="Add company" subtitle="Saved once — then used for leads, deals and meetings." onClose={() => setAddCompany(false)}>
          <CompanyForm prefillName={(q || suggestName || '').trim() || undefined} onSaved={c => { setAddCompany(false); pickCompany(c) }} onCancel={() => setAddCompany(false)} />
        </Modal>
      )}
      {addContact && value.accountId && (
        <Modal title="Add contact" onClose={() => setAddContact(false)}>
          <ContactForm accountId={value.accountId} accountName={value.accountName} allowAnother={false}
            onSaved={c => { setAddContact(false); pickContact(c) }} onCancel={() => setAddContact(false)} />
        </Modal>
      )}
    </div>
  )
}
