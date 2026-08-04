import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'
import { renderMarkdownLite } from '@/lib/markdown'
import { MOM_STATUS_CFG, DELIVERY_PURPOSES } from '@/pages/Meetings'

// ── Types (draft shapes used while editing — looser than the API's Pydantic
// models so the UI can hold in-progress/invalid rows without blowing up) ────
type AttendeeDraft = { name: string; email?: string; side: 'us' | 'customer' }
type DiscussionPointDraft = {
  point: string
  responsibility_side: 'us' | 'customer'
  responsibility_name: string
  target_date: string
  status: 'open' | 'done' | 'slipped'
}

const DP_STATUS_CFG: Record<string, { label: string; cls: string }> = {
  open:    { label: 'Open',    cls: 'text-sky-700' },
  done:    { label: 'Done',    cls: 'text-emerald-700' },
  slipped: { label: 'Slipped', cls: 'text-red-600' },
}

const ACTION_LABELS: Record<string, string> = {
  generated: 'Generated draft', edited: 'Edited', finalized: 'Finalized',
  attendees_updated: 'Attendees updated', discussion_points_updated: 'Discussion points updated',
}

// Parses either "Name <email@domain.com>" (the common Outlook "To" line
// paste pattern) or a bare "email@domain.com" into {name, email}. Anything
// else is taken as a name-only chip (no email) — validated/flagged by the
// caller, not rejected here, per the UIUX spec's "free-typed text with no
// match still commits as a name-only chip" rule.
function parseAttendeeInput(raw: string): { name: string; email?: string } {
  const trimmed = raw.trim()
  const angled = trimmed.match(/^(.*)<([^>]+)>$/)
  if (angled) {
    const email = angled[2].trim()
    const name = angled[1].trim().replace(/,$/, '') || email.split('@')[0]
    return { name, email }
  }
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
    const local = trimmed.split('@')[0]
    const name = local.replace(/[._]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    return { name, email: trimmed }
  }
  return { name: trimmed }
}

// ── Attendee chip input (Us / Customer) ───────────────────────────────────
function AttendeeChipInput({ side, attendees, onChange, readOnly }: {
  side: 'us' | 'customer'
  attendees: AttendeeDraft[]
  onChange: (next: AttendeeDraft[]) => void
  readOnly: boolean
}) {
  const [draft, setDraft] = useState('')
  const sideAttendees = attendees.filter(a => a.side === side)

  function commit() {
    const raw = draft.trim().replace(/,$/, '')
    if (!raw) return
    const parsed = parseAttendeeInput(raw)
    const emailLower = parsed.email?.toLowerCase()
    // Duplicate email typed twice → silently ignored, per spec (low-stakes,
    // self-evident case, no error needed).
    if (emailLower && sideAttendees.some(a => a.email?.toLowerCase() === emailLower)) {
      setDraft('')
      return
    }
    onChange([...attendees, { ...parsed, side }])
    setDraft('')
  }

  function removeAt(idx: number) {
    const target = sideAttendees[idx]
    onChange(attendees.filter(a => a !== target))
  }

  // Gmail-style re-edit: pull the chip back into the composer rather than a
  // separate inline dual-field editor — simpler to implement reliably and a
  // familiar pattern for anyone who has used a mail client's To/Cc field.
  function editAt(idx: number) {
    const target = sideAttendees[idx]
    onChange(attendees.filter(a => a !== target))
    setDraft(target.email ? `${target.name} <${target.email}>` : target.name)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {sideAttendees.map((a, idx) => {
        const missingEmail = !a.email
        return (
          <span key={`${a.name}-${a.email ?? idx}`}
            onClick={() => !readOnly && editAt(idx)}
            className={`inline-flex items-center gap-1.5 pl-2.5 pr-1 py-1 rounded-full text-xs font-medium border
              ${missingEmail ? 'border-wep-amber' : 'border-wep-border'} bg-wep-surface text-wep-text
              ${!readOnly ? 'cursor-pointer hover:border-wep-border-strong' : ''}`}
            style={{ borderLeftWidth: 3, borderLeftColor: side === 'us' ? '#38BDF8' : '#F0115E' }}
            title={missingEmail ? 'Add an email to include in Send to Customer.' : undefined}>
            {missingEmail && <span aria-hidden>⚠️</span>}
            <span>{a.name}{a.email ? ` · ${a.email}` : ''}</span>
            {!readOnly && (
              <button type="button" onClick={(e) => { e.stopPropagation(); removeAt(idx) }}
                className="w-6 h-6 flex items-center justify-center rounded-full text-wep-muted hover:bg-wep-border/60 hover:text-wep-text leading-none">
                ×
              </button>
            )}
          </span>
        )
      })}
      {!readOnly && (
        <input
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => {
            if (e.key === ',' || e.key === 'Enter') { e.preventDefault(); commit() }
            if (e.key === 'Backspace' && !draft && sideAttendees.length) removeAt(sideAttendees.length - 1)
          }}
          onBlur={commit}
          placeholder={sideAttendees.length ? 'Add another…' : 'Type a name or paste an email, press comma…'}
          className="flex-1 min-w-[180px] text-xs border-none outline-none bg-transparent py-1.5 px-1 text-wep-text placeholder:text-wep-muted"
        />
      )}
      {readOnly && sideAttendees.length === 0 && (
        <span className="text-xs text-wep-muted">None listed.</span>
      )}
    </div>
  )
}

// ── Discussion Points repeater ─────────────────────────────────────────────
function DiscussionPointsTable({ points, onChange, readOnly }: {
  points: DiscussionPointDraft[]
  onChange: (next: DiscussionPointDraft[]) => void
  readOnly: boolean
}) {
  function update(idx: number, patch: Partial<DiscussionPointDraft>) {
    onChange(points.map((p, i) => i === idx ? { ...p, ...patch } : p))
  }
  function addRow() {
    onChange([...points, { point: '', responsibility_side: 'us', responsibility_name: '', target_date: '', status: 'open' }])
  }
  function removeRow(idx: number) {
    onChange(points.filter((_, i) => i !== idx))
  }

  if (readOnly) {
    if (!points.length) return <p className="text-xs text-wep-muted">No discussion points recorded.</p>
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-wep-muted border-b border-wep-border">
              <th className="py-2 pr-3 font-semibold">Point discussed</th>
              <th className="py-2 pr-3 font-semibold">Responsibility</th>
              <th className="py-2 pr-3 font-semibold">Target date</th>
              <th className="py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p, idx) => (
              <tr key={idx} className="border-b border-wep-border/60 last:border-0">
                <td className="py-2 pr-3 text-wep-text">{p.point}</td>
                <td className="py-2 pr-3 text-wep-text">
                  {p.responsibility_side === 'us' ? 'Us' : 'Customer'}: {p.responsibility_name || '—'}
                </td>
                <td className="py-2 pr-3 text-wep-text">{p.target_date || '—'}</td>
                <td className={`py-2 font-semibold ${DP_STATUS_CFG[p.status]?.cls ?? ''}`}>
                  {DP_STATUS_CFG[p.status]?.label ?? p.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (!points.length) {
    return (
      <div className="text-center py-4">
        <p className="text-xs text-wep-muted mb-2">No discussion points yet — add the first one.</p>
        <button type="button" onClick={addRow} className="btn-outline text-xs px-3 py-1.5">+ Add Row</button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {points.map((p, idx) => (
        <div key={idx} className="grid grid-cols-1 md:grid-cols-[1fr_1fr_130px_120px_44px] gap-2 items-start p-2 rounded-xl bg-wep-surface">
          <input className="form-input text-xs py-1.5" placeholder="Point discussed"
            value={p.point} onChange={e => update(idx, { point: e.target.value })} />
          <div className="flex gap-1">
            <select className="form-input text-xs py-1.5 w-[92px]" value={p.responsibility_side}
              onChange={e => update(idx, { responsibility_side: e.target.value as 'us' | 'customer' })}>
              <option value="us">Us</option>
              <option value="customer">Customer</option>
            </select>
            <input className="form-input text-xs py-1.5 flex-1" placeholder="Name"
              value={p.responsibility_name} onChange={e => update(idx, { responsibility_name: e.target.value })} />
          </div>
          <input type="date" className="form-input text-xs py-1.5" value={p.target_date}
            onChange={e => update(idx, { target_date: e.target.value })} />
          <select className="form-input text-xs py-1.5" value={p.status}
            onChange={e => update(idx, { status: e.target.value as DiscussionPointDraft['status'] })}>
            <option value="open">Open</option>
            <option value="done">Done</option>
            <option value="slipped">Slipped</option>
          </select>
          <button type="button" onClick={() => removeRow(idx)}
            className="w-11 h-11 flex items-center justify-center rounded-xl text-wep-muted hover:bg-red-50 hover:text-red-500 justify-self-center">
            ×
          </button>
        </div>
      ))}
      <button type="button" onClick={addRow} className="btn-outline text-xs px-3 py-1.5">+ Add Row</button>
    </div>
  )
}

// ── Revision history entry ─────────────────────────────────────────────────
function RevisionEntry({ r }: { r: any }) {
  const [open, setOpen] = useState(false)
  const isTextDiff = r.action === 'generated' || r.action === 'edited' || r.action === 'finalized'
  return (
    <div className="py-2 border-b border-wep-border/60 last:border-0">
      <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
        <div>
          <span className="font-semibold text-wep-text">{ACTION_LABELS[r.action] ?? r.action}</span>
          <span className="text-wep-muted"> · by {r.actor_name} · {format(new Date(r.created_at), 'dd MMM yyyy, HH:mm')}</span>
        </div>
        <button type="button" onClick={() => setOpen(v => !v)} className="text-brand-pink font-semibold shrink-0">
          {open ? 'Hide diff' : 'View diff'}
        </button>
      </div>
      {open && (
        <div className="mt-1.5 space-y-1 text-[11px]">
          <div className="p-2 rounded-lg bg-red-50 text-red-700 break-words">
            {isTextDiff
              ? (r.before?.ai_mom_summary ?? '(none)').slice(0, 300)
              : JSON.stringify(r.before ?? [])}
          </div>
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700 break-words">
            {isTextDiff
              ? (r.after?.ai_mom_summary ?? '(none)').slice(0, 300)
              : JSON.stringify(r.after ?? [])}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Send to Customer modal ──────────────────────────────────────────────────
function SendMomModal({ meeting, attendees, onClose }: { meeting: any; attendees: AttendeeDraft[]; onClose: () => void }) {
  const [to, setTo] = useState<AttendeeDraft[]>(
    attendees.filter(a => a.side === 'customer' && a.email).map(a => ({ ...a }))
  )
  const [cc, setCc] = useState<AttendeeDraft[]>(
    attendees.filter(a => a.side === 'us' && a.email).map(a => ({ ...a }))
  )
  const [subject, setSubject] = useState(`Minutes of Meeting — ${meeting.company} — ${meeting.date}`)
  const [attachAs, setAttachAs] = useState<'pdf' | 'docx' | 'inline'>('pdf')
  const [sending, setSending] = useState(false)
  const [err, setErr] = useState('')

  const missingEmailCustomers = attendees.filter(a => a.side === 'customer' && !a.email).length

  async function send() {
    if (!to.length) { setErr('Add at least one recipient in To.'); return }
    setSending(true); setErr('')
    try {
      const res = await api.post(`/meetings/${meeting.id}/send`, {
        to: to.map(a => a.email), cc: cc.map(a => a.email),
        subject, attach_as: attachAs,
      })
      toast.success(res.data.sent ? 'Minutes sent.' : 'SMTP not configured — logged instead of sent (dev mode).')
      onClose()
    } catch (e: any) {
      setErr(getErrorMessage(e, 'Could not send'))
    } finally {
      setSending(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9998, background: 'rgba(26,11,46,0.55)', display: 'grid', placeItems: 'center', padding: 16 }}
      onClick={sending ? undefined : onClose}>
      <div className="card" style={{ maxWidth: 480, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-lg text-wep-navy">Send Minutes to Customer</h3>
          {!sending && <button onClick={onClose} className="text-wep-muted text-xl leading-none">×</button>}
        </div>

        {missingEmailCustomers > 0 && (
          <div className="mb-3 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            ⚠️ {missingEmailCustomers} customer attendee{missingEmailCustomers > 1 ? 's' : ''} {missingEmailCustomers > 1 ? 'have' : 'has'} no email — add one on the Attendees section above, or send to just those who do.
          </div>
        )}

        <label className="form-label block mb-1">To</label>
        <div className="form-input h-auto py-1">
          <AttendeeChipInput side="customer" attendees={to} onChange={next => setTo(next)} readOnly={false} />
        </div>

        <label className="form-label block mb-1 mt-3">Cc</label>
        <div className="form-input h-auto py-1">
          <AttendeeChipInput side="us" attendees={cc} onChange={next => setCc(next)} readOnly={false} />
        </div>

        <label className="form-label block mb-1 mt-3">Subject</label>
        <input className="form-input" value={subject} onChange={e => setSubject(e.target.value)} />

        <label className="form-label block mb-1 mt-3">Attach as</label>
        <div className="flex gap-2">
          {[{ v: 'pdf', l: 'PDF' }, { v: 'docx', l: 'Word' }, { v: 'inline', l: 'Inline body only' }].map(o => (
            <label key={o.v} className={`flex-1 text-center text-xs font-medium px-2 py-2 rounded-xl border cursor-pointer
              ${attachAs === o.v ? 'border-brand-pink bg-pink-50 text-brand-pink' : 'border-wep-border text-wep-muted'}`}>
              <input type="radio" className="hidden" checked={attachAs === o.v}
                onChange={() => setAttachAs(o.v as 'pdf' | 'docx' | 'inline')} />
              {o.l}
            </label>
          ))}
        </div>

        {err && <p className="text-red-500 text-xs mt-3">{err}</p>}

        <div className="flex gap-2 mt-5">
          <button onClick={send} disabled={sending || !to.length} className="btn-primary flex-1 disabled:opacity-40">
            {sending ? '⏳ Sending…' : '✉️ Send'}
          </button>
          {!sending && <button onClick={onClose} className="btn-outline">Cancel</button>}
        </div>
      </div>
    </div>
  )
}

// ── /meetings/:id — Minutes of Meeting detail page ─────────────────────────
export default function MeetingDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const isGovernance = user?.role === 'governance'

  const { data: meeting, isLoading } = useQuery({
    queryKey: ['meeting', id],
    queryFn: () => api.get(`/meetings/${id}`).then(r => r.data),
    enabled: !!id,
  })

  const { data: revisions = [] } = useQuery({
    queryKey: ['meeting-revisions', id],
    queryFn: () => api.get(`/meetings/${id}/revisions`).then(r => r.data),
    enabled: !!id,
  })

  const [attendees, setAttendees] = useState<AttendeeDraft[]>([])
  const [committedAttendees, setCommittedAttendees] = useState<AttendeeDraft[]>([])
  const [points, setPoints] = useState<DiscussionPointDraft[]>([])
  const [committedPoints, setCommittedPoints] = useState<DiscussionPointDraft[]>([])
  const [editingMom, setEditingMom] = useState(false)
  const [momDraft, setMomDraft] = useState('')
  // Default collapsed for edit mode, default expanded for governance — the
  // whole reason governance has read access here is to confirm records get
  // kept current over time, not just to see the latest state (UIUX spec §4.4).
  const [revOpen, setRevOpen] = useState(isGovernance)
  const [exportOpen, setExportOpen] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)
  const [showSend, setShowSend] = useState(false)

  // Re-derive the editable draft whenever a *different* meeting loads (not
  // on every refetch of the same one — that would clobber in-progress edits
  // with a network round-trip's worth of staleness).
  useEffect(() => {
    if (!meeting) return
    const a = (meeting.attendees ?? []).map((x: any) => ({ name: x.name, email: x.email, side: x.side }))
    const p = (meeting.discussion_points ?? []).map((x: any) => ({
      point: x.point, responsibility_side: x.responsibility_side,
      responsibility_name: x.responsibility_name, target_date: x.target_date ?? '', status: x.status,
    }))
    setAttendees(a); setCommittedAttendees(a)
    setPoints(p); setCommittedPoints(p)
    setMomDraft(meeting.ai_mom_summary ?? '')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meeting?.id])

  const dirty = JSON.stringify(attendees) !== JSON.stringify(committedAttendees)
    || JSON.stringify(points) !== JSON.stringify(committedPoints)

  const invalidateMeeting = () => {
    qc.invalidateQueries({ queryKey: ['meeting', id] })
    qc.invalidateQueries({ queryKey: ['meeting-revisions', id] })
    qc.invalidateQueries({ queryKey: ['meetings'] })
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload: any = {}
      if (JSON.stringify(attendees) !== JSON.stringify(committedAttendees)) {
        payload.attendees = attendees.map(a => ({ name: a.name, email: a.email || undefined, side: a.side }))
      }
      if (JSON.stringify(points) !== JSON.stringify(committedPoints)) {
        payload.discussion_points = points
          .filter(p => p.point.trim())
          .map(p => ({ ...p, target_date: p.target_date || undefined }))
      }
      return api.patch(`/meetings/${id}`, payload).then(r => r.data)
    },
    onSuccess: () => {
      setCommittedAttendees(attendees)
      setCommittedPoints(points)
      invalidateMeeting()
      toast.success('Minutes updated.')
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not save changes')),
  })

  const generateMom = useMutation({
    mutationFn: () => api.post(`/meetings/${id}/generate-mom`).then(r => r.data),
    onSuccess: (r: any) => { setMomDraft(r.ai_mom_summary); invalidateMeeting() },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not generate MOM')),
  })

  const saveMom = useMutation({
    mutationFn: (finalize: boolean) => api.patch(`/meetings/${id}/mom`, { ai_mom_summary: momDraft, finalize }).then(r => r.data),
    onSuccess: () => { setEditingMom(false); invalidateMeeting(); toast.success('Minutes summary saved.') },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Could not save MOM')),
  })

  async function downloadExport(fmt: 'xlsx' | 'pdf' | 'docx') {
    setExporting(fmt)
    try {
      const res = await api.get(`/meetings/${id}/export`, { params: { format: fmt }, responseType: 'blob' })
      const disposition = res.headers['content-disposition'] as string | undefined
      const match = disposition?.match(/filename="?([^"]+)"?/)
      const filename = match?.[1] ?? `MOM.${fmt}`
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url; a.download = filename
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      toast.error(getErrorMessage(e, 'Could not download export'))
    } finally {
      setExporting(null); setExportOpen(false)
    }
  }

  if (isLoading) {
    return <div className="p-4 md:p-6 max-w-4xl mx-auto"><div className="skeleton h-64 rounded-2xl" /></div>
  }
  if (!meeting) {
    return (
      <div className="p-6 max-w-4xl mx-auto text-center py-16">
        <p className="text-wep-muted">Meeting not found.</p>
        <Link to="/meetings" className="btn-outline mt-4 inline-block">← Back to Meetings</Link>
      </div>
    )
  }

  const purposeLabel = meeting.source === 'service_delivery'
    ? (DELIVERY_PURPOSES.find(p => p.val === meeting.meeting_purpose)?.label ?? meeting.meeting_purpose)
    : (meeting.meeting_purpose ?? 'Sales Discovery')
  const status = MOM_STATUS_CFG[meeting.mom_status] ?? MOM_STATUS_CFG.none
  const readOnly = isGovernance

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <Link to="/meetings" className="text-xs font-semibold text-wep-muted hover:text-wep-text inline-flex items-center gap-1 mb-3">
        ← Back to Meetings
      </Link>

      <div className="page-header">
        <div>
          <h1 className="page-title">🤝 {meeting.company} — {purposeLabel}</h1>
          <p className="page-sub">
            {meeting.date} · {meeting.meeting_type}{meeting.rep_name ? ` · logged by ${meeting.rep_name}` : ''}
          </p>
        </div>
        <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full h-fit ${status.cls}`}>{status.label}</span>
      </div>

      {/* Attendees */}
      <div className="card mb-4">
        <h3 className="font-bold text-sm text-wep-text mb-3">Attendees</h3>
        <div className="space-y-3">
          <div>
            <div className="text-[10px] font-bold text-wep-muted uppercase tracking-wide mb-1">Us</div>
            <AttendeeChipInput side="us" attendees={attendees} onChange={setAttendees} readOnly={readOnly} />
          </div>
          <div>
            <div className="text-[10px] font-bold text-wep-muted uppercase tracking-wide mb-1">Customer</div>
            <AttendeeChipInput side="customer" attendees={attendees} onChange={setAttendees} readOnly={readOnly} />
          </div>
        </div>
      </div>

      {/* Discussion points */}
      <div className="card mb-4">
        <h3 className="font-bold text-sm text-wep-text mb-3">Discussion Points</h3>
        <DiscussionPointsTable points={points} onChange={setPoints} readOnly={readOnly} />
      </div>

      {!readOnly && (
        <div className="flex justify-end mb-4">
          <button onClick={() => saveMutation.mutate()} disabled={!dirty || saveMutation.isPending}
            className="btn-primary disabled:opacity-40">
            {saveMutation.isPending ? '⏳ Saving…' : '💾 Save Changes'}
          </button>
        </div>
      )}

      {/* AI Summary */}
      <div className="card mb-4">
        <div className="flex items-center justify-between gap-2 flex-wrap mb-1">
          <h3 className="font-bold text-sm text-wep-text">AI Minutes Summary</h3>
          {!readOnly && (
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => generateMom.mutate()} disabled={generateMom.isPending}
                className="btn-outline text-xs px-3 py-1.5">
                {generateMom.isPending ? '⏳ Generating…' : meeting.ai_mom_summary ? '🔄 Regenerate' : '✨ Generate'}
              </button>
              {meeting.ai_mom_summary && !editingMom && (
                <button type="button" onClick={() => { setMomDraft(meeting.ai_mom_summary); setEditingMom(true) }}
                  className="btn-outline text-xs px-3 py-1.5">✏️ Edit</button>
              )}
            </div>
          )}
        </div>
        {/* Discussion points are the structured source; the AI panel is a
            generated view of the same meeting, not duplicate data entry —
            said once, briefly, per UIUX spec §4.3. */}
        {points.length > 0 && (
          <p className="text-[10px] text-wep-muted mb-2">Generated from the discussion points above — edit either; regenerate to resync.</p>
        )}

        {!meeting.ai_mom_summary && !generateMom.isPending && (
          <p className="text-xs text-wep-muted">No MOM generated yet.</p>
        )}
        {generateMom.isPending && (
          <p className="text-xs text-wep-muted">⏳ Generating on the local model — this can take a minute or two…</p>
        )}
        {meeting.ai_mom_summary && !editingMom && (
          <div className="text-xs leading-relaxed rounded-lg p-3 bg-wep-surface"
            dangerouslySetInnerHTML={{ __html: renderMarkdownLite(meeting.ai_mom_summary) }} />
        )}
        {editingMom && (
          <>
            <textarea rows={10} className="form-input text-xs font-mono" value={momDraft}
              onChange={e => setMomDraft(e.target.value)} />
            <div className="flex items-center gap-2 flex-wrap mt-2">
              <button type="button" onClick={() => saveMom.mutate(false)} disabled={saveMom.isPending}
                className="btn-outline text-xs px-3 py-1.5">💾 Save draft</button>
              <button type="button" onClick={() => saveMom.mutate(true)} disabled={saveMom.isPending}
                className="text-xs font-bold px-3 py-1.5 rounded-lg text-white disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg,#F0115E,#C2005A)' }}>
                {saveMom.isPending ? '⏳ Saving…' : '✅ Finalize'}
              </button>
              <button type="button" onClick={() => setEditingMom(false)} className="text-xs text-wep-muted">Cancel</button>
            </div>
          </>
        )}
        {meeting.ai_mom_summary && meeting.mom_status === 'generated' && !editingMom && (
          <p className="text-[10px] text-wep-muted mt-2">⚠️ AI draft — please review before finalizing.</p>
        )}
      </div>

      {/* Revision history */}
      <div className="card mb-4">
        <button type="button" onClick={() => setRevOpen(v => !v)}
          className="flex items-center justify-between w-full text-left">
          <h3 className="font-bold text-sm text-wep-text">Revision History ({revisions.length})</h3>
          <span className="text-wep-muted text-xs">{revOpen ? '▲' : '▼'}</span>
        </button>
        {revOpen && (
          <div className="mt-2">
            {revisions.length === 0
              ? <p className="text-xs text-wep-muted">No changes recorded yet.</p>
              : revisions.map((r: any) => <RevisionEntry key={r.id} r={r} />)}
          </div>
        )}
      </div>

      {/* Export / Send footer */}
      <div className="card flex items-center gap-2 flex-wrap relative">
        <div className="relative">
          <button type="button" onClick={() => setExportOpen(v => !v)} className="btn-outline text-sm">
            ⬇ Download ▾
          </button>
          {exportOpen && (
            <div className="absolute z-10 mt-1 bg-white border border-wep-border rounded-xl shadow-lg overflow-hidden min-w-[160px]">
              {[{ f: 'xlsx', l: 'Excel (.xlsx)' }, { f: 'pdf', l: 'PDF' }, { f: 'docx', l: 'Word (.docx)' }].map(o => (
                <button key={o.f} type="button" onClick={() => downloadExport(o.f as 'xlsx' | 'pdf' | 'docx')} disabled={!!exporting}
                  className="block w-full text-left px-3 py-2 text-sm hover:bg-wep-surface disabled:opacity-40">
                  {exporting === o.f ? '⏳ Preparing…' : o.l}
                </button>
              ))}
            </div>
          )}
        </div>
        {/* Governance never sends anything to a customer — viewer only,
            matches the existing "no approval/action authority" pattern
            already established for DSR/DOR/FGA (deny_governance server-side
            too, this is UX affordance removal, not the actual gate). */}
        {!readOnly && (
          <button type="button" onClick={() => setShowSend(true)} className="btn-primary text-sm">
            ✉️ Send to Customer
          </button>
        )}
      </div>

      {showSend && (
        <SendMomModal meeting={meeting} attendees={attendees} onClose={() => setShowSend(false)} />
      )}
    </div>
  )
}
