import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import CompanyForm, { type Company } from '@/components/CompanyForm'
import { ContactForm, type ContactLite } from '@/components/ContactPicker'

type Step = 'confirm' | 'ask' | 'replacement' | 'pick-company' | 'new-company' | 'moved-contact'

function Shell({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl p-5 w-full max-w-lg space-y-3 max-h-[90vh] overflow-y-auto">
        <h3 className="font-bold">{title}</h3>{children}
      </div>
    </div>
  )
}

/** When someone leaves a company: mark them left (history and past MOMs stay),
 * then offer to (a) add their replacement here, or (b) record that they moved to
 * another company — one that is already in fluidGo, or a new one — as a NEW
 * contact linked back to the old record, so the team can work opportunities
 * with them in their new role. */
export default function MarkLeftFlow({ contact, accountName, onClose }: {
  contact: ContactLite; accountName?: string; onClose: () => void
}) {
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>(contact.status === 'left' ? 'ask' : 'confirm')
  const [q, setQ] = useState('')
  const [target, setTarget] = useState<Company | null>(null)
  const refresh = () => { ['contacts', 'accounts', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] })) }

  const markLeft = useMutation({
    mutationFn: () => api.patch(`/contacts/${contact.id}`, { status: 'left' }).then(r => r.data),
    onSuccess: () => { refresh(); toast.success(`${contact.name} marked as left.`); setStep('ask') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  const { data: list } = useQuery({
    queryKey: ['accounts', 'picker', q],
    queryFn: () => api.get('/accounts', { params: { q: q || undefined, limit: 8 } }).then(r => r.data.items as Company[]),
    enabled: step === 'pick-company',
  })
  const others = (list ?? []).filter(a => a.id !== contact.account_id)

  if (step === 'confirm') return (
    <Shell title={`Mark ${contact.name} as left?`}>
      <p className="text-xs text-wep-muted">They stay on record with their history and past MOMs, and are hidden from new-MOM pickers. You can reactivate them anytime.</p>
      <div className="flex justify-end gap-2">
        <button className="btn-outline text-sm" onClick={onClose}>Cancel</button>
        <button className="btn-primary text-sm disabled:opacity-40" disabled={markLeft.isPending} onClick={() => markLeft.mutate()}>Mark as left</button>
      </div>
    </Shell>
  )
  if (step === 'ask') return (
    <Shell title={`${contact.name} has left ${accountName ?? 'the company'}`}>
      <p className="text-sm">What next?</p>
      <div className="space-y-2">
        <button className="w-full text-left border border-wep-border rounded-lg p-3 hover:border-wep-border-strong" onClick={() => setStep('replacement')}>
          <div className="font-semibold text-sm">➕ Add their replacement</div><div className="text-xs text-wep-muted">Add the new person at {accountName ?? 'this company'}.</div></button>
        <button className="w-full text-left border border-wep-border rounded-lg p-3 hover:border-wep-border-strong" onClick={() => setStep('pick-company')}>
          <div className="font-semibold text-sm">➡️ They moved to another company</div><div className="text-xs text-wep-muted">Record their new role — at a company already in fluidGo, or a new one — so the team can explore opportunities there.</div></button>
      </div>
      <div className="flex justify-end"><button className="btn-outline text-sm" onClick={onClose}>Not now</button></div>
    </Shell>
  )
  if (step === 'replacement') return (
    <Shell title={`Add replacement at ${accountName ?? 'this company'}`}>
      <ContactForm accountId={contact.account_id!} accountName={accountName} onSaved={(_, another) => { if (!another) onClose() }} onCancel={onClose} />
    </Shell>
  )
  if (step === 'pick-company') return (
    <Shell title={`Where did ${contact.name} move?`}>
      <input className="form-input" placeholder="Search companies already in fluidGo…" value={q} onChange={e => setQ(e.target.value)} autoFocus />
      <div className="space-y-1">
        {others.map(a => (
          <button key={a.id} className="w-full text-left border border-wep-border rounded px-3 py-2 text-sm hover:border-wep-border-strong"
            onClick={() => { setTarget(a); setStep('moved-contact') }}>
            {a.name}{a.city ? <span className="text-xs text-wep-muted"> · {a.city}</span> : null}</button>
        ))}
        {list && others.length === 0 && <div className="text-xs text-wep-muted">No matching company.</div>}
      </div>
      <button className="text-sm text-brand-pink font-semibold" onClick={() => setStep('new-company')}>+ Add as a new company</button>
      <div className="flex justify-end"><button className="btn-outline text-sm" onClick={onClose}>Cancel</button></div>
    </Shell>
  )
  if (step === 'new-company') return (
    <Shell title="New company">
      <CompanyForm onSaved={(c) => { setTarget(c); setStep('moved-contact') }} onCancel={() => setStep('pick-company')} />
    </Shell>
  )
  return (
    <Shell title={`${contact.name} at ${target?.name}`}>
      <p className="text-xs text-wep-muted">Add their new details. This links back to their record at {accountName ?? 'the previous company'}.</p>
      <ContactForm accountId={target!.id} accountName={target!.name} previousContactId={contact.id} allowAnother={false}
        prefill={{ salutation: contact.salutation, first_name: contact.first_name, last_name: contact.last_name ?? undefined }}
        onSaved={(_, another) => { if (!another) { toast.success(`${contact.name} added at ${target!.name}.`); onClose() } }} onCancel={onClose} />
    </Shell>
  )
}
