import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import { NewContactForm, AddNumberInline, type ContactLite } from '@/components/ContactPicker'

type Tab = 'directory' | 'incomplete' | 'requests' | 'bin'
const BIN_ROLES = ['governance', 'super_admin', 'business_head', 'practice_head', 'coo', 'ceo']

function fmt(d?: string | null) { try { return d ? format(new Date(d), 'dd MMM yyyy') : '—' } catch { return '—' } }

export default function Contacts() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const isGov = user?.role === 'governance'
  const [tab, setTab] = useState<Tab>('directory')
  const [q, setQ] = useState('')
  const [adding, setAdding] = useState(false)
  const [newAccount, setNewAccount] = useState('')
  const [delFor, setDelFor] = useState<any | null>(null)
  const [delReason, setDelReason] = useState('')
  const [fixing, setFixing] = useState<string | null>(null)
  const refresh = () => { qc.invalidateQueries({ queryKey: ['contacts'] }); qc.invalidateQueries({ queryKey: ['contact-requests'] }) }

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

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => api.patch(`/contacts/${id}`, body).then(r => r.data),
    onSuccess: () => { refresh(); toast.success('Updated.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  const reqDelete = useMutation({
    mutationFn: () => api.post(`/contacts/${delFor.id}/delete-request`, { reason: delReason.trim() }).then(r => r.data),
    onSuccess: () => { setDelFor(null); setDelReason(''); refresh(); toast.success('Deletion requested — awaiting approval.') },
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
  const tabs: [Tab, string][] = [['directory', 'Directory'], ['incomplete', 'Needs number'],
    ['requests', `Delete requests${pendingForMe ? ` (${pendingForMe})` : ''}`]]
  if (BIN_ROLES.includes(user?.role ?? '')) tabs.push(['bin', 'Recycle bin'])

  const rows: any[] = list.data?.items ?? []

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-wep-text">Contacts</h1>
          <p className="text-xs text-wep-muted">Customer people, by account. Used for MOM attendees; deletions need approval.</p>
        </div>
        {!isGov && <button className="btn-primary text-sm" onClick={() => setAdding(a => !a)}>+ New contact</button>}
      </div>

      {adding && (
        <div className="card mb-4 space-y-2">
          <input className="form-input" placeholder="Account / company name *" value={newAccount} onChange={e => setNewAccount(e.target.value)} />
          {newAccount.trim() && <NewContactForm accountName={newAccount.trim()}
            onCreated={() => { setAdding(false); setNewAccount(''); refresh() }} onCancel={() => setAdding(false)} />}
        </div>
      )}

      <div className="flex gap-1 mb-3 border-b border-wep-border overflow-x-auto">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 ${tab === k ? 'border-brand-pink text-brand-pink' : 'border-transparent text-wep-muted'}`}>{label}</button>
        ))}
      </div>

      {(tab === 'directory' || tab === 'incomplete') && (
        <>
          {tab === 'directory' && <input className="form-input mb-3" placeholder="Search name, email, phone or account…" value={q} onChange={e => setQ(e.target.value)} />}
          {tab === 'incomplete' && <p className="text-xs text-wep-muted mb-3">Imported from earlier meetings and leads. Add a primary number so they can be added to a MOM.</p>}
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] uppercase text-wep-muted border-b border-wep-border">
                <th className="p-2">Name</th><th className="p-2">Account</th><th className="p-2">Designation</th>
                <th className="p-2">Phone</th><th className="p-2">Email</th><th className="p-2">Last activity</th><th className="p-2"></th></tr></thead>
              <tbody>
                {rows.map((c: ContactLite & any) => (
                  <tr key={c.id} className="border-b border-wep-border last:border-0">
                    <td className="p-2 font-medium">{c.name}{c.status === 'left' && <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-wep-border text-wep-muted">Left</span>}
                      {c.do_not_contact && <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">DNC</span>}</td>
                    <td className="p-2">{c.account_name}</td><td className="p-2">{c.designation ?? '—'}</td>
                    <td className="p-2">{c.phone_primary ?? (fixing === c.id
                      ? <AddNumberInline contact={c} onDone={() => { setFixing(null); refresh() }} />
                      : !isGov && <button className="text-xs text-wep-amber font-semibold" onClick={() => setFixing(c.id)}>⚠️ Add number</button>)}</td>
                    <td className="p-2">{c.email ?? '—'}</td><td className="p-2">{fmt(c.last_activity_at)}</td>
                    <td className="p-2 text-right whitespace-nowrap">
                      {!isGov && <>
                        <button className="text-xs text-wep-muted mr-3" onClick={() => patch.mutate({ id: c.id, body: { status: c.status === 'left' ? 'active' : 'left' } })}>
                          {c.status === 'left' ? 'Mark active' : 'Mark as left'}</button>
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

      {delFor && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setDelFor(null)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-md space-y-3" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold">Request deletion of {delFor.name}</h3>
            <p className="text-xs text-wep-muted">Needs your reporting manager and one of governance / inside sales to approve. If the person simply left the company, use “Mark as left” instead.</p>
            <textarea className="form-input w-full" rows={3} placeholder="Reason (min 5 characters)" value={delReason} onChange={e => setDelReason(e.target.value)} />
            <div className="flex justify-end gap-2">
              <button className="btn-outline text-sm" onClick={() => setDelFor(null)}>Cancel</button>
              <button className="btn-primary text-sm disabled:opacity-40" disabled={delReason.trim().length < 5 || reqDelete.isPending} onClick={() => reqDelete.mutate()}>Send request</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
