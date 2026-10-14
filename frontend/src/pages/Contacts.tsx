import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import { AddNumberInline, type ContactLite } from '@/components/ContactPicker'
import CompanyForm, { type Company } from '@/components/CompanyForm'
import MarkLeftFlow from '@/components/MarkLeftFlow'
import DeleteRequestDialog from '@/components/DeleteRequestDialog'

type Tab = 'companies' | 'directory' | 'incomplete' | 'requests' | 'bin'
const BIN_ROLES = ['governance', 'super_admin', 'business_head', 'practice_head', 'coo', 'ceo']

function fmt(d?: string | null) { try { return d ? format(new Date(d), 'dd MMM yyyy') : '—' } catch { return '—' } }

export default function Contacts() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const nav = useNavigate()
  const isGov = user?.role === 'governance'
  const [tab, setTab] = useState<Tab>('companies')
  const [q, setQ] = useState('')
  const [addingCo, setAddingCo] = useState(false)
  const [delFor, setDelFor] = useState<ContactLite | null>(null)
  const [leaving, setLeaving] = useState<ContactLite | null>(null)
  const [fixing, setFixing] = useState<string | null>(null)
  const refresh = () => { qc.invalidateQueries({ queryKey: ['contacts'] }); qc.invalidateQueries({ queryKey: ['contact-requests'] }); qc.invalidateQueries({ queryKey: ['accounts'] }) }

  const companies = useQuery({
    queryKey: ['accounts', 'list', q],
    queryFn: () => api.get('/accounts', { params: { q: q || undefined } }).then(r => r.data),
    enabled: tab === 'companies',
  })
  const list = useQuery({
    queryKey: ['contacts', 'list', tab, q],
    queryFn: () => api.get('/contacts', { params: { q: q || undefined, incomplete: tab === 'incomplete' || undefined } }).then(r => r.data),
    enabled: tab === 'directory' || tab === 'incomplete',
  })
  const reqs = useQuery({
    queryKey: ['contact-requests'],
    queryFn: () => api.get('/contacts/delete-requests').then(r => r.data.items as any[]),
  })
  const bin = useQuery({
    queryKey: ['contacts', 'bin'],
    queryFn: () => api.get('/contacts/recycle-bin').then(r => r.data.items as any[]),
    enabled: tab === 'bin' && BIN_ROLES.includes(user?.role ?? ''),
  })
  const reactivate = useMutation({
    mutationFn: (id: string) => api.patch(`/contacts/${id}`, { status: 'active' }).then(r => r.data),
    onSuccess: () => { refresh(); toast.success('Reactivated.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  const decide = useMutation({
    mutationFn: ({ id, decision, comment }: any) => api.post(`/contacts/delete-requests/${id}/decision`, { decision, comment }).then(r => r.data),
    onSuccess: () => { refresh(); toast.success('Decision recorded.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  const restore = useMutation({
    mutationFn: (id: string) => api.post(`/contacts/${id}/restore`).then(r => r.data),
    onSuccess: () => { refresh(); toast.success('Contact restored.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })

  const pendingForMe = (reqs.data ?? []).filter(r => r.status === 'pending' && r.can_decide).length
  const tabs: [Tab, string][] = [['companies', 'Companies'], ['directory', 'All contacts'], ['incomplete', 'Needs number'],
    ['requests', `Delete requests${pendingForMe ? ` (${pendingForMe})` : ''}`]]
  if (BIN_ROLES.includes(user?.role ?? '')) tabs.push(['bin', 'Recycle bin'])
  const rows: any[] = list.data?.items ?? []
  const cos: Company[] = companies.data?.items ?? []

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-wep-text">Companies &amp; Contacts</h1>
          <p className="text-xs text-wep-muted">Add the company first, then the people in it. Deletions need approval.</p>
        </div>
        {!isGov && tab === 'companies' && <button className="btn-primary text-sm" onClick={() => setAddingCo(a => !a)}>+ New company</button>}
      </div>

      {addingCo && <div className="card mb-4"><CompanyForm onSaved={(c) => { setAddingCo(false); refresh(); nav(`/companies/${c.id}`) }} onCancel={() => setAddingCo(false)} /></div>}

      <div className="flex gap-1 mb-3 border-b border-wep-border overflow-x-auto">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 ${tab === k ? 'border-brand-pink text-brand-pink' : 'border-transparent text-wep-muted'}`}>{label}</button>
        ))}
      </div>

      {tab === 'companies' && (
        <>
          <input className="form-input mb-3" placeholder="Search companies…" value={q} onChange={e => setQ(e.target.value)} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {cos.map(c => (
              <Link key={c.id} to={`/companies/${c.id}`} className="card hover:border-wep-border-strong flex items-center justify-between gap-3">
                <div>
                  <div className="font-semibold text-sm">{c.name}</div>
                  <div className="text-xs text-wep-muted">{[c.industry, c.city].filter(Boolean).join(' · ') || '—'}</div>
                </div>
                <span className="text-xs text-wep-muted whitespace-nowrap">{c.contact_count ?? 0} {c.contact_count === 1 ? 'contact' : 'contacts'}</span>
              </Link>
            ))}
            {cos.length === 0 && <div className="card text-center text-sm text-wep-muted md:col-span-2">{companies.isLoading ? 'Loading…' : 'No companies found.'}</div>}
          </div>
        </>
      )}

      {(tab === 'directory' || tab === 'incomplete') && (
        <>
          {tab === 'directory' && <input className="form-input mb-3" placeholder="Search name, email, phone or company…" value={q} onChange={e => setQ(e.target.value)} />}
          {tab === 'incomplete' && <p className="text-xs text-wep-muted mb-3">Imported from earlier meetings and leads. Add a primary number so they can be added to a MOM.</p>}
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] uppercase text-wep-muted border-b border-wep-border">
                <th className="p-2">Name</th><th className="p-2">Company</th><th className="p-2">Designation</th>
                <th className="p-2">Phone</th><th className="p-2">Email</th><th className="p-2">Last activity</th><th className="p-2"></th></tr></thead>
              <tbody>
                {rows.map((c: any) => (
                  <tr key={c.id} className="border-b border-wep-border last:border-0">
                    <td className="p-2 font-medium">{c.salutation ? `${c.salutation} ` : ''}{c.name}{c.status === 'left' && <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-wep-border text-wep-muted">Left</span>}
                      {c.do_not_contact && <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">DNC</span>}</td>
                    <td className="p-2"><Link to={`/companies/${c.account_id}`} className="text-brand-pink">{c.account_name}</Link></td>
                    <td className="p-2">{c.designation ?? '—'}</td>
                    <td className="p-2">{c.phone_primary ?? (fixing === c.id
                      ? <AddNumberInline contact={c} onDone={() => { setFixing(null); refresh() }} />
                      : !isGov && <button className="text-xs text-wep-amber font-semibold" onClick={() => setFixing(c.id)}>⚠️ Add number</button>)}</td>
                    <td className="p-2">{c.email ?? '—'}</td><td className="p-2">{fmt(c.last_activity_at)}</td>
                    <td className="p-2 text-right whitespace-nowrap">
                      {!isGov && <>
                        {c.status === 'left'
                          ? <button className="text-xs text-wep-muted mr-3" onClick={() => reactivate.mutate(c.id)}>Reactivate</button>
                          : <button className="text-xs text-wep-muted mr-3" onClick={() => setLeaving(c)}>Mark as left</button>}
                        <button className="text-xs text-red-600" onClick={() => setDelFor(c)}>Request deletion</button></>}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-wep-muted text-sm">{list.isLoading ? 'Loading…' : 'No contacts found.'}</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'requests' && (
        <div className="space-y-2">
          {(reqs.data ?? []).map(r => (
            <div key={r.id} className="card flex items-start justify-between gap-3 flex-wrap">
              <div className="text-sm">
                <div className="font-semibold">{r.contact_name} <span className="text-xs font-normal text-wep-muted">— requested by {r.requested_by_name} · expires {fmt(r.expires_at)}</span></div>
                <div className="text-xs text-wep-muted mt-0.5">“{r.reason}”</div>
                <div className="text-xs mt-1">Status: <b>{r.status}</b>
                  {r.approvals.map((a: any, i: number) => <span key={i} className="ml-2">· {a.slot}: {a.decision}{a.comment ? ` (${a.comment})` : ''}</span>)}</div>
                {r.status === 'pending' && <div className="text-[11px] text-wep-muted">Needs the reporting manager + one of governance / inside sales.</div>}
              </div>
              {r.can_decide && (
                <div className="flex gap-2">
                  <button className="btn-primary text-xs px-3 py-1.5" onClick={() => decide.mutate({ id: r.id, decision: 'approve' })}>Approve ({r.my_slot})</button>
                  <button className="btn-outline text-xs px-3 py-1.5" onClick={() => {
                    const c = window.prompt('Reason for rejecting (required):'); if (c && c.trim()) decide.mutate({ id: r.id, decision: 'reject', comment: c.trim() })
                  }}>Reject</button>
                </div>
              )}
            </div>
          ))}
          {(reqs.data ?? []).length === 0 && <div className="card text-center text-sm text-wep-muted">No deletion requests.</div>}
        </div>
      )}

      {tab === 'bin' && (
        <div className="space-y-2">
          <p className="text-xs text-wep-muted">Deleted contacts are kept here and can be restored.</p>
          {(bin.data ?? []).map(c => (
            <div key={c.id} className="card flex items-center justify-between">
              <div className="text-sm"><b>{c.name}</b> · {c.account_name} <span className="text-xs text-wep-muted">deleted {fmt(c.deleted_at)}</span></div>
              <button className="btn-outline text-xs px-3 py-1.5" onClick={() => restore.mutate(c.id)}>Restore</button>
            </div>
          ))}
          {(bin.data ?? []).length === 0 && <div className="card text-center text-sm text-wep-muted">Recycle bin is empty.</div>}
        </div>
      )}

      {delFor && <DeleteRequestDialog contact={delFor} onClose={() => setDelFor(null)} />}
      {leaving && <MarkLeftFlow contact={leaving} accountName={(leaving as any).account_name ?? undefined} onClose={() => { setLeaving(null); refresh() }} />}
    </div>
  )
}
