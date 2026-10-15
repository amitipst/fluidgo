import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Search, Plus, Building2, Users, UserMinus, Trash2, RotateCcw, ChevronRight, ShieldCheck, Inbox, Archive } from 'lucide-react'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import { type ContactLite } from '@/components/ContactPicker'
import CompanyForm, { type Company } from '@/components/CompanyForm'
import ContactRow from '@/components/ContactRow'
import MarkLeftFlow from '@/components/MarkLeftFlow'
import DeleteRequestDialog from '@/components/DeleteRequestDialog'
import Modal from '@/components/ui/Modal'
import { Avatar, Skeleton, EmptyState, Pill, RowAction } from '@/components/ui/bits'

type Tab = 'companies' | 'directory' | 'incomplete' | 'requests' | 'bin'
const BIN_ROLES = ['governance', 'super_admin', 'business_head', 'practice_head', 'coo', 'ceo']
const STATUS_TONE: Record<string, 'warn' | 'ok' | 'danger' | 'muted'> = { pending: 'warn', approved: 'ok', rejected: 'danger', expired: 'muted', cancelled: 'muted' }

function fmt(d?: string | null) { try { return d ? format(new Date(d), 'dd MMM yyyy') : '—' } catch { return '—' } }

function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative mb-4">
      <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-wep-light" aria-hidden />
      <input className="form-input pl-10 min-h-[44px]" type="search" aria-label={placeholder} placeholder={placeholder} value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function ListSkeleton({ n = 4 }: { n?: number }) {
  return <div className="space-y-2" aria-busy="true">{Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-[72px]" />)}</div>
}

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
  const [rejecting, setRejecting] = useState<any | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [fixing, setFixing] = useState<string | null>(null)
  const refresh = () => { ;['contacts', 'contact-requests', 'accounts', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] })) }

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
    onSuccess: () => { refresh(); setRejecting(null); setRejectReason(''); toast.success('Decision recorded.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  const restore = useMutation({
    mutationFn: (id: string) => api.post(`/contacts/${id}/restore`).then(r => r.data),
    onSuccess: () => { refresh(); toast.success('Contact restored.') },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })

  const pendingForMe = (reqs.data ?? []).filter(r => r.status === 'pending' && r.can_decide).length
  const tabs: [Tab, string, number?][] = [['companies', 'Companies'], ['directory', 'All contacts'], ['incomplete', 'Needs details'],
    ['requests', 'Delete requests', pendingForMe]]
  if (BIN_ROLES.includes(user?.role ?? '')) tabs.push(['bin', 'Recycle bin'])
  const rows: any[] = list.data?.items ?? []
  const cos: Company[] = companies.data?.items ?? []
  const switchTab = (t: Tab) => { setTab(t); setQ('') }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-wep-text">Companies &amp; Contacts</h1>
          <p className="text-xs text-wep-muted mt-0.5">Add the company first, then the people in it. Deletions need approval.</p>
        </div>
        {!isGov && tab === 'companies' && <button className="btn-primary" onClick={() => setAddingCo(true)}><Plus size={16} aria-hidden />New company</button>}
      </div>

      <div role="tablist" aria-label="Contacts sections" className="flex gap-1 mb-4 border-b border-wep-border overflow-x-auto">
        {tabs.map(([k, label, badge]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => switchTab(k)}
            className={`px-3.5 min-h-[44px] text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink
              ${tab === k ? 'border-brand-pink text-brand-pink' : 'border-transparent text-wep-muted hover:text-wep-text'}`}>
            {label}{!!badge && <span className="ml-1.5 text-[10px] font-bold bg-brand-pink text-white rounded-full px-1.5 py-0.5">{badge}</span>}
          </button>
        ))}
      </div>

      {tab === 'companies' && (
        <div role="tabpanel">
          <SearchBox value={q} onChange={setQ} placeholder="Search companies…" />
          {companies.isLoading ? <ListSkeleton /> : cos.length === 0 ? (
            <EmptyState icon={<Building2 size={22} />} title={q ? 'No companies match your search' : 'No companies yet'}
              hint={q ? 'Try a different name.' : 'Start by adding the company, then add the people you meet there.'}
              action={!isGov && !q ? <button className="btn-primary" onClick={() => setAddingCo(true)}><Plus size={16} aria-hidden />Add your first company</button> : undefined} />
          ) : (
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {cos.map(c => (
                <li key={c.id}>
                  <Link to={`/companies/${c.id}`} className="card-hover flex items-center gap-3 !p-3.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink">
                    <Avatar name={c.name} size={44} square />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-sm text-wep-text truncate">{c.name}</div>
                      <div className="text-xs text-wep-muted truncate">{[c.industry, c.city].filter(Boolean).join(' · ') || 'No details yet'}</div>
                    </div>
                    <Pill><Users size={11} aria-hidden />{c.contact_count ?? 0}</Pill>
                    <ChevronRight size={16} className="text-wep-light shrink-0" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(tab === 'directory' || tab === 'incomplete') && (
        <div role="tabpanel">
          {tab === 'directory'
            ? <SearchBox value={q} onChange={setQ} placeholder="Search name, email, phone or company…" />
            : <p className="text-xs text-wep-muted mb-3">These need a primary phone and email (both mandatory) before they can be added to a MOM — most came from earlier meetings and leads.</p>}
          {list.isLoading ? <ListSkeleton /> : rows.length === 0 ? (
            <EmptyState icon={tab === 'incomplete' ? <ShieldCheck size={22} /> : <Users size={22} />}
              title={tab === 'incomplete' ? 'Everything is complete' : q ? 'No contacts match your search' : 'No contacts yet'}
              hint={tab === 'incomplete' ? 'Every contact has a primary phone and email.' : 'Open a company and add the people you meet there.'} />
          ) : (
            <div className="space-y-2">
              {rows.map((c: any) => (
                <ContactRow key={c.id} c={c} showCompany fixing={fixing === c.id} onFix={() => setFixing(c.id)} onFixed={() => { setFixing(null); refresh() }}>
                  {!isGov && <>
                    {c.status === 'left'
                      ? <RowAction icon={<RotateCcw size={13} aria-hidden />} onClick={() => reactivate.mutate(c.id)}>Reactivate</RowAction>
                      : <RowAction icon={<UserMinus size={13} aria-hidden />} onClick={() => setLeaving(c)}>Mark as left</RowAction>}
                    <RowAction danger icon={<Trash2 size={13} aria-hidden />} onClick={() => setDelFor(c)}>Request deletion</RowAction></>}
                </ContactRow>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'requests' && (
        <div role="tabpanel" className="space-y-2.5">
          {reqs.isLoading ? <ListSkeleton n={2} /> : (reqs.data ?? []).length === 0 ? (
            <EmptyState icon={<Inbox size={22} />} title="No deletion requests" hint="Requests to delete a contact appear here for approval." />
          ) : (reqs.data ?? []).map(r => (
            <div key={r.id} className="card !p-4 flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0 flex-1 basis-72">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm">{r.contact_name}</span>
                  <Pill tone={STATUS_TONE[r.status] ?? 'muted'}>{r.status}</Pill>
                </div>
                <div className="text-xs text-wep-muted mt-0.5">Requested by {r.requested_by_name} · expires {fmt(r.expires_at)}</div>
                <blockquote className="text-sm mt-2 pl-3 border-l-2 border-wep-border-strong text-wep-text">{r.reason}</blockquote>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {r.approvals.map((a: any, i: number) => <Pill key={i} tone={a.decision === 'approve' ? 'ok' : 'danger'}>{a.slot.replace('_', ' ')}: {a.decision}{a.comment ? ` — ${a.comment}` : ''}</Pill>)}
                  {r.status === 'pending' && <span className="text-[11px] text-wep-muted self-center">Needs the reporting manager + one of governance / inside sales.</span>}
                </div>
              </div>
              {r.can_decide && (
                <div className="flex gap-2">
                  <button className="btn-primary" disabled={decide.isPending} onClick={() => decide.mutate({ id: r.id, decision: 'approve' })}>Approve ({r.my_slot?.replace('_', ' ')})</button>
                  <button className="btn-outline" onClick={() => setRejecting(r)}>Reject</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'bin' && (
        <div role="tabpanel" className="space-y-2">
          <p className="text-xs text-wep-muted mb-1">Deleted contacts are kept here and can be restored.</p>
          {bin.isLoading ? <ListSkeleton n={2} /> : (bin.data ?? []).length === 0 ? (
            <EmptyState icon={<Archive size={22} />} title="Recycle bin is empty" />
          ) : (bin.data ?? []).map(c => (
            <div key={c.id} className="card !p-3.5 flex items-center gap-3">
              <Avatar name={c.name} /><div className="flex-1 min-w-0 text-sm"><b>{c.name}</b><span className="text-wep-muted"> · {c.account_name}</span><div className="text-xs text-wep-muted">Deleted {fmt(c.deleted_at)}</div></div>
              <button className="btn-outline" onClick={() => restore.mutate(c.id)}><RotateCcw size={14} aria-hidden />Restore</button>
            </div>
          ))}
        </div>
      )}

      {addingCo && <Modal title="New company" subtitle="Add the company first, then its people." onClose={() => setAddingCo(false)} size="lg">
        <CompanyForm onSaved={(c) => { setAddingCo(false); refresh(); nav(`/companies/${c.id}`) }} onCancel={() => setAddingCo(false)} /></Modal>}
      {delFor && <DeleteRequestDialog contact={delFor} onClose={() => setDelFor(null)} />}
      {leaving && <MarkLeftFlow contact={leaving} accountName={(leaving as any).account_name ?? undefined} onClose={() => { setLeaving(null); refresh() }} />}
      {rejecting && (
        <Modal title={`Reject deletion of ${rejecting.contact_name}`} subtitle="Rejecting stops the request. A reason is required." onClose={() => { setRejecting(null); setRejectReason('') }} size="sm">
          <div><label htmlFor="rej" className="form-label block mb-1">Reason <span className="text-brand-pink" aria-hidden>*</span></label>
            <textarea id="rej" className="form-input" rows={3} autoFocus value={rejectReason} onChange={e => setRejectReason(e.target.value)} /></div>
          <div className="flex justify-end gap-2">
            <button className="btn-outline" onClick={() => { setRejecting(null); setRejectReason('') }}>Cancel</button>
            <button className="btn-danger disabled:opacity-50" disabled={!rejectReason.trim() || decide.isPending}
              onClick={() => decide.mutate({ id: rejecting.id, decision: 'reject', comment: rejectReason.trim() })}>Reject request</button>
          </div>
        </Modal>)}
    </div>
  )
}
