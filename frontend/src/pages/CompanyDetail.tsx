import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { ChevronLeft, Pencil, Globe, MapPin, UserPlus, UserMinus, Trash2, Users, RotateCcw, ExternalLink } from 'lucide-react'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import { useGeo } from '@/hooks/useGeo'
import CompanyForm from '@/components/CompanyForm'
import { ContactForm, type ContactLite } from '@/components/ContactPicker'
import ContactRow from '@/components/ContactRow'
import MarkLeftFlow from '@/components/MarkLeftFlow'
import DeleteRequestDialog from '@/components/DeleteRequestDialog'
import Modal from '@/components/ui/Modal'
import { Avatar, Skeleton, EmptyState, Pill, RowAction } from '@/components/ui/bits'

function fmt(d?: string | null) { try { return d ? format(new Date(d), 'dd MMM yyyy') : '' } catch { return '' } }

export default function CompanyDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { data: geo } = useGeo()
  const [editCo, setEditCo] = useState(false)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<ContactLite | null>(null)
  const [leaving, setLeaving] = useState<ContactLite | null>(null)
  const [deleting, setDeleting] = useState<ContactLite | null>(null)
  const [fixing, setFixing] = useState<string | null>(null)

  const { data: co, isLoading, error } = useQuery({
    queryKey: ['account', id],
    queryFn: () => api.get(`/accounts/${id}`).then(r => r.data),
    enabled: !!id,
  })
  const refreshAll = () => qc.invalidateQueries({ queryKey: ['account', id] })
  const reactivate = useMutation({
    mutationFn: (cid: string) => api.patch(`/contacts/${cid}`, { status: 'active' }).then(r => r.data),
    onSuccess: () => { refreshAll(); toast.success('Reactivated.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })

  if (isLoading) return (
    <div className="max-w-5xl mx-auto space-y-4" aria-busy="true">
      <Skeleton className="h-4 w-24" /><Skeleton className="h-36" /><Skeleton className="h-20" /><Skeleton className="h-20" />
    </div>)
  if (error || !co) return (
    <div className="max-w-5xl mx-auto"><EmptyState icon={<Users size={22} />} title="Company not found" hint="It may have been removed, or you may not have access."
      action={<Link to="/contacts" className="btn-outline">Back to Companies</Link>} /></div>)

  const canEdit: boolean = co.can_edit
  const countryName = geo?.countries.find(c => c.code === co.country)?.name
  const addr = [co.address_line1, co.address_line2, [co.city, co.state].filter(Boolean).join(', '),
    [countryName, co.postal_code].filter(Boolean).join(' – ')].filter(Boolean)
  const active: any[] = co.contacts.filter((c: any) => c.status === 'active')
  const left: any[] = co.contacts.filter((c: any) => c.status === 'left')
  const siteHref = co.website ? (co.website.startsWith('http') ? co.website : `https://${co.website}`) : null

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <Link to="/contacts" className="inline-flex items-center gap-1 text-xs text-wep-muted hover:text-brand-pink min-h-[32px]"><ChevronLeft size={14} aria-hidden />Companies</Link>

      <section className="card" aria-label="Company details">
        <div className="flex items-start gap-4 flex-wrap">
          <Avatar name={co.name} size={56} square />
          <div className="min-w-0 flex-1 basis-64">
            <h1 className="text-xl font-bold text-wep-text leading-tight">{co.name}</h1>
            <div className="flex items-center gap-2 flex-wrap mt-1.5">
              {co.industry && <Pill tone="brand">{co.industry}</Pill>}
              {siteHref && <a href={siteHref} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-brand-pink font-medium hover:underline"><Globe size={13} aria-hidden />{co.website.replace(/^https?:\/\//, '')}<ExternalLink size={11} aria-hidden /><span className="sr-only">(opens in a new tab)</span></a>}
              <Pill>{active.length} {active.length === 1 ? 'person' : 'people'}</Pill>
            </div>
            <div className="mt-3 flex items-start gap-2 text-sm text-wep-text">
              <MapPin size={15} className="text-wep-muted mt-0.5 shrink-0" aria-hidden />
              {addr.length ? <address className="not-italic leading-snug">{addr.map((l, i) => <div key={i}>{l}</div>)}</address>
                : <span className="text-xs text-wep-muted">No address yet{canEdit && <> — <button className="text-brand-pink font-semibold" onClick={() => setEditCo(true)}>add one</button></>}</span>}
            </div>
          </div>
          {canEdit && <button className="btn-outline" onClick={() => setEditCo(true)}><Pencil size={14} aria-hidden />Edit company</button>}
        </div>
      </section>

      <section aria-label="People">
        <div className="flex items-center justify-between mb-2.5">
          <h2 className="font-bold text-sm text-wep-text">People <span className="text-wep-muted font-medium">({active.length})</span></h2>
          {canEdit && <button className="btn-primary" onClick={() => setAdding(true)}><UserPlus size={16} aria-hidden />Add contact</button>}
        </div>
        <div className="space-y-2">
          {active.map(c => (
            <ContactRow key={c.id} c={c} fixing={fixing === c.id} onFix={() => setFixing(c.id)} onFixed={() => { setFixing(null); refreshAll() }}>
              {canEdit && <>
                <RowAction icon={<Pencil size={13} aria-hidden />} onClick={() => setEditing(c)}>Edit</RowAction>
                <RowAction icon={<UserMinus size={13} aria-hidden />} onClick={() => setLeaving(c)}>Mark as left</RowAction>
                <RowAction danger icon={<Trash2 size={13} aria-hidden />} onClick={() => setDeleting(c)}>Request deletion</RowAction></>}
            </ContactRow>
          ))}
          {active.length === 0 && (
            <EmptyState icon={<Users size={22} />} title="No contacts at this company yet" hint="Add the people you meet here so they can be picked in your MOMs."
              action={canEdit ? <button className="btn-primary" onClick={() => setAdding(true)}><UserPlus size={16} aria-hidden />Add the first contact</button> : undefined} />)}
        </div>
      </section>

      {left.length > 0 && (
        <details className="group" open={left.length <= 3}>
          <summary className="cursor-pointer list-none flex items-center gap-2 text-sm font-bold text-wep-muted mb-2.5 select-none min-h-[32px]">
            <ChevronLeft size={14} className="transition-transform -rotate-90 group-open:rotate-90" aria-hidden />Left the company ({left.length})</summary>
          <div className="space-y-2">
            {left.map(c => (
              <ContactRow key={c.id} c={c}>
                <span className="text-[11px] text-wep-light px-1.5">{fmt(c.left_at) && `Left ${fmt(c.left_at)}`}</span>
                {canEdit && <>
                  {!c.moved_to?.length && <RowAction icon={<UserPlus size={13} aria-hidden />} onClick={() => setLeaving(c)}>Moved to another company…</RowAction>}
                  <RowAction icon={<RotateCcw size={13} aria-hidden />} onClick={() => reactivate.mutate(c.id)}>Reactivate</RowAction></>}
              </ContactRow>
            ))}
          </div>
        </details>
      )}

      {editCo && <Modal title="Edit company" onClose={() => setEditCo(false)} size="lg"><CompanyForm initial={co} onSaved={() => { setEditCo(false); refreshAll() }} onCancel={() => setEditCo(false)} /></Modal>}
      {adding && <Modal title="Add contact" subtitle={co.name} onClose={() => { setAdding(false); refreshAll() }} size="lg">
        <ContactForm accountId={co.id} accountName={co.name} onSaved={(_, another) => { if (!another) setAdding(false); refreshAll() }} onCancel={() => setAdding(false)} /></Modal>}
      {editing && <Modal title={`Edit ${editing.name}`} subtitle={co.name} onClose={() => setEditing(null)} size="lg">
        <ContactForm accountId={co.id} accountName={co.name} initial={editing} onSaved={() => { setEditing(null); refreshAll() }} onCancel={() => setEditing(null)} /></Modal>}
      {leaving && <MarkLeftFlow contact={leaving} accountName={co.name} onClose={() => { setLeaving(null); refreshAll() }} />}
      {deleting && <DeleteRequestDialog contact={deleting} onClose={() => setDeleting(null)} />}
    </div>
  )
}
