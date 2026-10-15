import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, ArrowRightLeft, Search, Building2, Plus } from 'lucide-react'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import Modal from '@/components/ui/Modal'
import { Avatar } from '@/components/ui/bits'
import CompanyForm, { type Company } from '@/components/CompanyForm'
import { ContactForm, type ContactLite } from '@/components/ContactPicker'

type Step = 'confirm' | 'ask' | 'replacement' | 'pick-company' | 'new-company' | 'moved-contact'

/** When someone leaves a company: mark them left (history and past MOMs stay),
 * then offer to (a) add their replacement here, or (b) record that they moved to
 * another company — already in fluidGo, or a new one — as a NEW contact linked back
 * to the old record, so the team can work opportunities with them in their new role. */
export default function MarkLeftFlow({ contact, accountName, onClose }: {
  contact: ContactLite; accountName?: string; onClose: () => void
}) {
  const qc = useQueryClient()
  const [step, setStep] = useState<Step>(contact.status === 'left' ? 'ask' : 'confirm')
  const [q, setQ] = useState('')
  const [target, setTarget] = useState<Company | null>(null)
  const refresh = () => { ;['contacts', 'accounts', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] })) }
  const where = accountName ?? 'the company'

  const markLeft = useMutation({
    mutationFn: () => api.patch(`/contacts/${contact.id}`, { status: 'left' }).then(r => r.data),
    onSuccess: () => { refresh(); toast.success(`${contact.name} marked as left.`); setStep('ask') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  const { data: list, isLoading } = useQuery({
    queryKey: ['accounts', 'picker', q],
    queryFn: () => api.get('/accounts', { params: { q: q || undefined, limit: 8 } }).then(r => r.data.items as Company[]),
    enabled: step === 'pick-company',
  })
  const others = (list ?? []).filter(a => a.id !== contact.account_id)

  if (step === 'confirm') return (
    <Modal title={`Mark ${contact.name} as left?`} onClose={onClose} size="sm">
      <p className="text-sm text-wep-muted">They stay on record with their history and past MOMs, and won't appear in new-MOM pickers. You can reactivate them any time.</p>
      <div className="flex justify-end gap-2 pt-1">
        <button className="btn-outline" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={markLeft.isPending} onClick={() => markLeft.mutate()}>Mark as left</button>
      </div>
    </Modal>
  )
  if (step === 'ask') return (
    <Modal title={`${contact.name} has left ${where}`} subtitle="What would you like to do next?" onClose={onClose}>
      <button className="w-full text-left flex items-start gap-3 rounded-xl border border-wep-border p-3.5 hover:border-brand-pink hover:bg-brand-pink-lt/40 transition-colors" onClick={() => setStep('replacement')}>
        <span className="w-9 h-9 rounded-lg bg-brand-purple-lt text-brand-purple flex items-center justify-center shrink-0"><UserPlus size={18} aria-hidden /></span>
        <span><span className="block font-semibold text-sm">Add their replacement</span><span className="block text-xs text-wep-muted">Add the new person at {where}.</span></span>
      </button>
      <button className="w-full text-left flex items-start gap-3 rounded-xl border border-wep-border p-3.5 hover:border-brand-pink hover:bg-brand-pink-lt/40 transition-colors" onClick={() => setStep('pick-company')}>
        <span className="w-9 h-9 rounded-lg bg-brand-pink-lt text-brand-pink flex items-center justify-center shrink-0"><ArrowRightLeft size={18} aria-hidden /></span>
        <span><span className="block font-semibold text-sm">They moved to another company</span><span className="block text-xs text-wep-muted">Pick a company already in fluidGo or add a new one — so the team can explore opportunities with them there.</span></span>
      </button>
      <div className="flex justify-end"><button className="btn-ghost" onClick={onClose}>Not now</button></div>
    </Modal>
  )
  if (step === 'replacement') return (
    <Modal title={`Add replacement at ${where}`} onClose={onClose} size="lg">
      <ContactForm accountId={contact.account_id!} accountName={accountName} onSaved={(_, another) => { if (!another) onClose() }} onCancel={onClose} />
    </Modal>
  )
  if (step === 'pick-company') return (
    <Modal title={`Where did ${contact.name} move?`} onClose={onClose}>
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-wep-light" aria-hidden />
        <input className="form-input pl-9 min-h-[44px]" aria-label="Search companies" placeholder="Search companies in fluidGo…" value={q} onChange={e => setQ(e.target.value)} autoFocus />
      </div>
      <div className="space-y-1.5" aria-live="polite">
        {others.map(a => (
          <button key={a.id} className="w-full text-left flex items-center gap-3 rounded-xl border border-wep-border px-3 py-2.5 hover:border-brand-pink transition-colors"
            onClick={() => { setTarget(a); setStep('moved-contact') }}>
            <Avatar name={a.name} size={32} square /><span className="text-sm font-medium">{a.name}{a.city ? <span className="text-xs text-wep-muted font-normal"> · {a.city}</span> : null}</span></button>
        ))}
        {!isLoading && others.length === 0 && <div className="text-xs text-wep-muted flex items-center gap-2 py-2"><Building2 size={14} aria-hidden />No matching company yet.</div>}
      </div>
      <button className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-pink min-h-[44px]" onClick={() => setStep('new-company')}><Plus size={16} aria-hidden />Add as a new company</button>
    </Modal>
  )
  if (step === 'new-company') return (
    <Modal title="New company" subtitle={`${contact.name}'s new employer`} onClose={onClose} size="lg">
      <CompanyForm onSaved={(c) => { setTarget(c); setStep('moved-contact') }} onCancel={() => setStep('pick-company')} />
    </Modal>
  )
  return (
    <Modal title={`${contact.name} at ${target?.name}`} subtitle={`Linked to their record at ${where}.`} onClose={onClose} size="lg">
      <ContactForm accountId={target!.id} accountName={target!.name} previousContactId={contact.id} allowAnother={false}
        prefill={{ salutation: contact.salutation, first_name: contact.first_name, last_name: contact.last_name ?? undefined }}
        onSaved={() => { toast.success(`${contact.name} added at ${target!.name}.`); onClose() }} onCancel={onClose} />
    </Modal>
  )
}
