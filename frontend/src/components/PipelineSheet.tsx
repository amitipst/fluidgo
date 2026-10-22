import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Download, Pencil, Table2 } from 'lucide-react'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import Modal from '@/components/ui/Modal'
import { Skeleton, EmptyState, Pill } from '@/components/ui/bits'

type Row = {
  id: string; company: string; stage: string; status: 'open' | 'hold' | 'won' | 'lost'
  arr: number; one_time: number; total: number; win_probability: number | null; weighted: number
  target: string; closure_eta: string | null; target_note: string | null; history: string[]
}
type Totals = { count: number; arr: number; one_time: number; total: number; weighted: number }
type Group = { rep_id: string; rep_name: string; rows: Row[]; totals: Totals }

const inr = (v: number) => (v ? `₹ ${Math.round(v).toLocaleString('en-US')}` : '')

function TargetCell({ r }: { r: Row }) {
  return (
    <div className="leading-snug">
      {r.history.map((h, i) => <div key={i} className="text-red-600/80 line-through text-xs" title="Earlier target">{h}</div>)}
      <div className={r.status === 'won' ? 'text-emerald-700 font-medium' : r.status === 'lost' ? 'text-wep-muted' : 'text-wep-text'}>{r.target}</div>
    </div>
  )
}

function TargetDialog({ row, onClose, onSaved }: { row: Row; onClose: () => void; onSaved: () => void }) {
  const [month, setMonth] = useState(row.closure_eta ? row.closure_eta.slice(0, 7) : '')
  const [note, setNote] = useState(row.target_note ?? '')
  const [reason, setReason] = useState('')
  const save = useMutation({
    mutationFn: () => api.patch(`/pipeline/${row.id}/forecast`, {
      closure_eta: month ? `${month}-01` : null, target_note: note.trim() || null, reason: reason.trim() || null,
    }),
    onSuccess: () => { toast.success('Target updated.'); onSaved() },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  return (
    <Modal title={`Target month — ${row.company}`} subtitle="The earlier target stays visible, struck through." onClose={onClose} size="sm">
      <div className="space-y-3">
        <div><label htmlFor="tm" className="form-label block mb-1">Target month</label>
          <input id="tm" type="month" className="form-input min-h-[44px]" value={month} onChange={e => setMonth(e.target.value)} /></div>
        <div><label htmlFor="tn" className="form-label block mb-1">Or note <span className="normal-case font-normal text-wep-muted">(e.g. Oct/Nov, Jan-Feb 27)</span></label>
          <input id="tn" className="form-input min-h-[44px]" maxLength={60} value={note} onChange={e => setNote(e.target.value)} /></div>
        <div><label htmlFor="tr" className="form-label block mb-1">Why is it moving? <span className="normal-case font-normal text-wep-muted">(optional)</span></label>
          <input id="tr" className="form-input min-h-[44px]" maxLength={300} value={reason} onChange={e => setReason(e.target.value)} /></div>
        <div className="flex justify-end gap-2 pt-1">
          <button className="btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>Save</button>
        </div>
      </div>
    </Modal>
  )
}

function WinCell({ r, onSaved }: { r: Row; onSaved: () => void }) {
  const [val, setVal] = useState(r.win_probability == null ? '' : String(r.win_probability))
  const locked = r.status === 'won' || r.status === 'lost'
  const save = useMutation({
    mutationFn: (n: number | null) => api.patch(`/pipeline/${r.id}/forecast`, { win_probability: n }),
    onSuccess: onSaved,
    onError: (e: any) => { toast.error(getErrorMessage(e)); setVal(r.win_probability == null ? '' : String(r.win_probability)) },
  })
  if (locked) return <span className={r.status === 'won' ? 'text-emerald-700 font-medium' : 'text-wep-muted'}>{r.win_probability}%</span>
  const commit = () => {
    const t = val.trim()
    const n = t === '' ? null : Number(t)
    if (n !== null && (!Number.isInteger(n) || n < 0 || n > 100)) { toast.error('Win probability must be 0 to 100.'); setVal(r.win_probability == null ? '' : String(r.win_probability)); return }
    if (n !== r.win_probability) save.mutate(n)
  }
  return (
    <label className="inline-flex items-center gap-0.5">
      <span className="sr-only">Win probability for {r.company}</span>
      <input inputMode="numeric" className="form-input !w-16 !py-1 text-center min-h-[36px]" placeholder="—" value={val}
        onChange={e => setVal(e.target.value.replace(/[^\d]/g, '').slice(0, 3))} onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
      <span className="text-wep-muted text-xs">%</span>
    </label>
  )
}

export default function PipelineSheet() {
  const qc = useQueryClient()
  const [includeClosed, setIncludeClosed] = useState(true)
  const [rep, setRep] = useState('')
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [editing, setEditing] = useState<Row | null>(null)
  const [exporting, setExporting] = useState(false)
  const params = { include_closed: includeClosed, rep_id: rep || undefined }
  const sheet = useQuery({
    queryKey: ['pipeline', 'sheet', includeClosed, rep],
    queryFn: () => api.get('/pipeline/sheet', { params }).then(r => r.data as { groups: Group[]; totals: Totals }),
  })
  const reps = useQuery({
    queryKey: ['pipeline', 'sheet', includeClosed, ''],
    queryFn: () => api.get('/pipeline/sheet', { params: { include_closed: includeClosed } }).then(r => r.data as { groups: Group[] }),
    enabled: !!rep,
  })
  const repList = (rep ? reps.data?.groups : sheet.data?.groups) ?? []
  const refresh = () => qc.invalidateQueries({ queryKey: ['pipeline'] })

  const download = async () => {
    setExporting(true)
    try {
      const res = await api.get('/pipeline/sheet.xlsx', { params, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `pipeline-${new Date().toISOString().slice(0, 10)}.xlsx`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) { toast.error(getErrorMessage(e, 'Could not download the sheet.')) } finally { setExporting(false) }
  }

  const data = sheet.data
  return (
    <div>
      <div className="flex items-center gap-3 flex-wrap mb-4">
        {repList.length > 1 || rep ? (
          <div><label htmlFor="rep" className="sr-only">Sales rep</label>
            <select id="rep" className="form-select min-h-[44px] !w-auto" value={rep} onChange={e => setRep(e.target.value)}>
              <option value="">All reps</option>
              {repList.map(g => <option key={g.rep_id} value={g.rep_id}>{g.rep_name}</option>)}
            </select></div>
        ) : null}
        <label className="inline-flex items-center gap-2 text-sm text-wep-text min-h-[44px]">
          <input type="checkbox" className="w-4 h-4 accent-[#F0115E]" checked={includeClosed} onChange={e => setIncludeClosed(e.target.checked)} />
          Show closed deals
        </label>
        <div className="flex-1" />
        <button className="btn-outline" onClick={download} disabled={exporting || !data?.groups.length}>
          <Download size={15} aria-hidden />{exporting ? 'Preparing…' : 'Download Excel'}
        </button>
      </div>

      {sheet.isLoading ? <div className="space-y-2" aria-busy="true"><Skeleton className="h-12" /><Skeleton className="h-40" /></div>
        : sheet.isError ? <div className="card text-sm text-red-600" role="alert">Could not load the pipeline sheet. {getErrorMessage(sheet.error)}</div>
        : !data?.groups.length ? <EmptyState icon={<Table2 size={22} />} title="No deals to show" hint="Add a deal on the Cards view and it appears here under its sales rep." />
        : (
          <div className="space-y-4">
            {data.groups.map(g => {
              const open = !collapsed[g.rep_id]
              return (
                <section key={g.rep_id} className="card !p-0 overflow-hidden">
                  <button type="button" aria-expanded={open} onClick={() => setCollapsed(c => ({ ...c, [g.rep_id]: open }))}
                    className="w-full flex items-center gap-3 px-4 min-h-[52px] bg-brand-purple-lt/50 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink">
                    {open ? <ChevronDown size={16} aria-hidden /> : <ChevronRight size={16} aria-hidden />}
                    <span className="font-semibold text-wep-text">{g.rep_name}</span>
                    <Pill>{g.totals.count} deals</Pill>
                    <span className="flex-1" />
                    <span className="text-sm font-semibold text-wep-text">{inr(g.totals.total) || '₹ 0'}</span>
                    <span className="hidden sm:inline text-xs text-wep-muted">weighted {inr(g.totals.weighted) || '₹ 0'}</span>
                  </button>
                  {open && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm min-w-[720px]">
                        <thead><tr className="text-[11px] uppercase tracking-wide text-wep-muted text-left border-b border-wep-border">
                          <th className="px-4 py-2 font-bold">Pipeline</th>
                          <th className="px-3 py-2 font-bold text-right">ARR</th>
                          <th className="px-3 py-2 font-bold text-right">One time</th>
                          <th className="px-3 py-2 font-bold text-right">Total</th>
                          <th className="px-3 py-2 font-bold text-center">Win %</th>
                          <th className="px-3 py-2 font-bold">Target month</th>
                          <th className="px-2 py-2"><span className="sr-only">Edit</span></th>
                        </tr></thead>
                        <tbody>
                          {g.rows.map(r => (
                            <tr key={r.id} className={`border-b border-wep-border/60 align-top ${r.status === 'won' ? 'bg-emerald-50/70' : r.status === 'lost' ? 'bg-wep-surface/70 text-wep-muted' : ''}`}>
                              <td className="px-4 py-2.5 font-medium">{r.company}{r.status === 'hold' && <span className="ml-2"><Pill tone="warn">Hold</Pill></span>}</td>
                              <td className="px-3 py-2.5 text-right tabular-nums">{inr(r.arr)}</td>
                              <td className="px-3 py-2.5 text-right tabular-nums">{inr(r.one_time)}</td>
                              <td className="px-3 py-2.5 text-right tabular-nums font-medium">{inr(r.total)}</td>
                              <td className="px-3 py-2 text-center"><WinCell r={r} onSaved={refresh} /></td>
                              <td className="px-3 py-2.5"><TargetCell r={r} /></td>
                              <td className="px-2 py-1.5">
                                {(r.status === 'open' || r.status === 'hold') && (
                                  <button type="button" aria-label={`Edit target for ${r.company}`} onClick={() => setEditing(r)}
                                    className="p-2 rounded-lg text-wep-muted hover:bg-wep-surface hover:text-wep-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink">
                                    <Pencil size={14} aria-hidden /></button>)}
                              </td>
                            </tr>))}
                          <tr className="bg-brand-purple-lt/40 font-semibold">
                            <td className="px-4 py-2.5">Total — {g.rep_name}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums">{inr(g.totals.arr)}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums">{inr(g.totals.one_time)}</td>
                            <td className="px-3 py-2.5 text-right tabular-nums">{inr(g.totals.total)}</td>
                            <td colSpan={3} className="px-3 py-2.5 text-xs font-normal text-wep-muted">Weighted {inr(g.totals.weighted) || '₹ 0'} · lost deals not counted</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>)}
                </section>)
            })}
            {data.groups.length > 1 && (
              <div className="card !p-4 flex flex-wrap items-center gap-x-6 gap-y-1 font-semibold bg-brand-pink-lt/40">
                <span>Grand total</span><span className="flex-1" />
                <span>ARR {inr(data.totals.arr) || '₹ 0'}</span><span>One time {inr(data.totals.one_time) || '₹ 0'}</span>
                <span>Total {inr(data.totals.total) || '₹ 0'}</span><span className="text-wep-muted font-normal text-sm">Weighted {inr(data.totals.weighted) || '₹ 0'}</span>
              </div>)}
          </div>)}
      {editing && <TargetDialog row={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refresh() }} />}
    </div>
  )
}
