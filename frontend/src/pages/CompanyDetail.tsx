import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import { useGeo } from '@/hooks/useGeo'
import CompanyForm from '@/components/CompanyForm'
import { ContactForm, AddNumberInline, type ContactLite } from '@/components/ContactPicker'
import MarkLeftFlow from '@/components/MarkLeftFlow'
import DeleteRequestDialog from '@/components/DeleteRequestDialog'

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
  const reactivate = useMutation({
    mutationFn: (cid: string) => api.patch(`/contacts/${cid}`, { status: 'active' }).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['account', id] }); toast.success('Reactivated.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })

  if (isLoading) return <div className="text-sm text-wep-muted p-6">Loading…</div>
  if (error || !co) return <div className="card text-sm">Company not found. <Link to="/contacts" className="text-brand-pink">Back to Contacts</Link></div>

  const canEdit = co.can_edit
  const countryName = geo?.countries.find(c => c.code === co.country)?.name
  const addr = [co.address_line1, co.address_line2, [co.city, co.state].filter(Boolean).join(', '),
    [countryName, co.postal_code].filter(Boolean).join(' – ')].filter(Boolean)
  const active: ContactLite[] = co.contacts.filter((c: any) => c.status === 'active')
  const left: any[] = co.contacts.filter((c: any) => c.status === 'left')
  const refreshAll = () => qc.invalidateQueries({ queryKey: ['account', id] })

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <Link to="/contacts" className="text-xs text-wep-muted">← Companies</Link>
      <div className="card">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-xl font-bold text-wep-text">{co.name}</h1>
            <div className="text-xs text-wep-muted mt-0.5">{[co.industry, co.website].filter(Boolean).join(' · ') || 'No industry or website yet'}</div>
            <div className="text-sm mt-2 leading-snug">{addr.length ? addr.map((l, i) => <div key={i}>{l}</div>) : <span className="text-wep-muted text-xs">No address yet</span>}</div>
          </div>
          {canEdit && <button className="btn-outline text-xs px-3 py-1.5" onClick={() => setEditCo(e => !e)}>{editCo ? 'Close' : 'Edit company'}</button>}
        </div>
        {editCo && <div className="mt-3"><CompanyForm initial={co} onSaved={() => { setEditCo(false); refreshAll() }} onCancel={() => setEditCo(false)} /></div>}
      </div>

      <div className="flex items-center justify-between">
        <h2 className="font-bold text-sm">People ({active.length})</h2>
        {canEdit && !adding && <button className="btn-primary text-sm" onClick={() => setAdding(true)}>+ Add contact</button>}
      </div>
      {adding && <ContactForm accountId={co.id} accountName={co.name} onSaved={(_, another) => { if (!another) setAdding(false); refreshAll() }} onCancel={() => setAdding(false)} />}

      <div className="space-y-2">
        {active.map(c => (
          <div key={c.id}>
            {editing?.id === c.id
              ? <ContactForm accountId={co.id} accountName={co.name} initial={c} onSaved={() => { setEditing(null); refreshAll() }} onCancel={() => setEditing(null)} />
              : (
              <div className="card flex items-start justify-between gap-3 flex-wrap">
                <div className="text-sm">
                  <div className="font-semibold">{c.salutation ? `${c.salutation} ` : ''}{c.name}
                    {(c as any).do_not_contact && <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">DNC</span>}</div>
                  <div className="text-xs text-wep-muted">{c.designation ?? '—'}</div>
                  <div className="text-xs mt-1 space-x-3">
                    {c.phone_primary ? <span>📞 {c.phone_primary}</span>
                      : fixing === c.id ? <AddNumberInline contact={c} onDone={() => { setFixing(null); refreshAll() }} />
                      : canEdit && <button className="text-wep-amber font-semibold" onClick={() => setFixing(c.id)}>⚠️ Add number</button>}
                    {c.phone_secondary && <span>📱 {c.phone_secondary}</span>}
                    {c.email && <span>✉️ {c.email}</span>}
                  </div>
                  {(c as any).moved_from_account && <div className="text-[11px] text-wep-muted mt-1">Formerly at {(c as any).moved_from_account}</div>}
                </div>
                {canEdit && (
                  <div className="text-xs whitespace-nowrap space-x-3">
                    <button className="text-wep-muted" onClick={() => setEditing(c)}>Edit</button>
                    <button className="text-wep-muted" onClick={() => setLeaving(c)}>Mark as left</button>
                    <button className="text-red-600" onClick={() => setDeleting(c)}>Request deletion</button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {active.length === 0 && !adding && <div className="card text-center text-sm text-wep-muted">No active contacts yet.{canEdit && ' Add the first person above.'}</div>}
      </div>

      {left.length > 0 && (
        <>
          <h2 className="font-bold text-sm text-wep-muted">Left the company ({left.length})</h2>
          <div className="space-y-2">
            {left.map(c => (
              <div key={c.id} className="card flex items-center justify-between gap-3 flex-wrap opacity-80">
                <div className="text-sm">
                  <div className="font-medium">{c.name} <span className="text-[10px] px-1.5 py-0.5 rounded bg-wep-border text-wep-muted">Left {fmt(c.left_at)}</span></div>
                  {c.moved_to?.length > 0 && <div className="text-xs mt-0.5">Now at {c.moved_to.map((m: any, i: number) => (
                    <span key={m.id}>{i > 0 && ', '}<Link to={`/companies/${m.account_id}`} className="text-brand-pink font-semibold">{m.account_name}</Link></span>))}</div>}
                </div>
                {canEdit && <div className="text-xs space-x-3 whitespace-nowrap">
                  {!c.moved_to?.length && <button className="text-wep-muted" onClick={() => setLeaving({ ...c, status: 'left' })}>Moved to another company…</button>}
                  <button className="text-wep-muted" onClick={() => reactivate.mutate(c.id)}>Reactivate</button></div>}
              </div>
            ))}
          </div>
        </>
      )}

      {leaving && <MarkLeftFlow contact={leaving} accountName={co.name} onClose={() => { setLeaving(null); refreshAll() }} />}
      {deleting && <DeleteRequestDialog contact={deleting} onClose={() => setDeleting(null)} />}
    </div>
  )
}
