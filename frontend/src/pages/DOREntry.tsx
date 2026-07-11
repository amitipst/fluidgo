import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { format } from 'date-fns'
import api from '@/hooks/useApi'

const STATUS_OPTS = [
  { val: 'on_track', label: '🟢 On Track' },
  { val: 'at_risk',  label: '🟡 At Risk' },
  { val: 'critical', label: '🔴 Critical' },
]

const emptyForm = {
  date: format(new Date(), 'yyyy-MM-dd'),
  client_account: '', status: 'on_track',
  tickets_open_start: 0, tickets_new: 0, tickets_closed: 0, tickets_overdue: 0,
  escalations_raised: 0, escalations_resolved: 0,
  collection_calls_made: 0, collection_amount: '',
  client_meetings_held: 0,
  resource_deployed: '', resource_available: '',
  blockers_notes: '',
}

function CountField({ field, label, form, setForm }: { field: string; label: string; form: any; setForm: any }) {
  return (
    <div>
      <label className="form-label block mb-1 text-xs">{label}</label>
      <input type="number" min="0" value={form[field]}
        onChange={e => setForm((f: any) => ({ ...f, [field]: Number(e.target.value) }))}
        className="form-input" />
    </div>
  )
}

export default function DOREntry() {
  const qc = useQueryClient()
  const [form, setForm] = useState<any>(emptyForm)
  const [saved, setSaved] = useState(false)

  const { data: history = [] } = useQuery({
    queryKey: ['dor-history'],
    queryFn: () => api.get('/dor/history').then(r => r.data),
  })

  useEffect(() => {
    const todayRow = history.find((d: any) => d.date === form.date)
    if (todayRow) {
      setForm({
        ...todayRow,
        collection_amount: todayRow.collection_amount ?? '',
        resource_deployed: todayRow.resource_deployed ?? '',
        resource_available: todayRow.resource_available ?? '',
        client_account: todayRow.client_account ?? '',
        blockers_notes: todayRow.blockers_notes ?? '',
      })
    }
  }, [history, form.date])

  const submit = useMutation({
    mutationFn: () => api.post('/dor', {
      ...form,
      collection_amount: form.collection_amount === '' ? null : Number(form.collection_amount),
      resource_deployed: form.resource_deployed === '' ? null : Number(form.resource_deployed),
      resource_available: form.resource_available === '' ? null : Number(form.resource_available),
    }),
    onSuccess: () => {
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      qc.invalidateQueries({ queryKey: ['dor-history'] })
    },
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">🛠️ Daily Operations Report</h1>
        <p className="text-wep-muted text-sm">{format(new Date(form.date), 'EEEE, d MMMM yyyy')}</p>
      </div>

      <div className="card space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="form-label block mb-1 text-xs">Date</label>
            <input type="date" value={form.date}
              onChange={e => setForm((f: any) => ({ ...f, date: e.target.value }))}
              className="form-input" />
          </div>
          <div>
            <label className="form-label block mb-1 text-xs">Client / Account</label>
            <input value={form.client_account}
              onChange={e => setForm((f: any) => ({ ...f, client_account: e.target.value }))}
              placeholder="e.g. Team Aviation" className="form-input" />
          </div>
        </div>

        <div>
          <label className="form-label block mb-1 text-xs">Overall Status</label>
          <div className="flex gap-2">
            {STATUS_OPTS.map(s => (
              <label key={s.val} className={`flex-1 text-center py-2 rounded-xl border cursor-pointer text-sm
                ${form.status === s.val ? 'border-wep-orange bg-wep-orange-lt text-wep-orange' : 'border-wep-border text-wep-muted'}`}>
                <input type="radio" checked={form.status === s.val} className="hidden"
                  onChange={() => setForm((f: any) => ({ ...f, status: s.val }))} />
                {s.label}
              </label>
            ))}
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-sm text-wep-navy mb-2">🎫 Tickets</h3>
          <div className="grid grid-cols-2 gap-3">
            <CountField field="tickets_open_start" label="Open at start of day" form={form} setForm={setForm} />
            <CountField field="tickets_new" label="New today" form={form} setForm={setForm} />
            <CountField field="tickets_closed" label="Closed today" form={form} setForm={setForm} />
            <CountField field="tickets_overdue" label="Overdue (>3 days)" form={form} setForm={setForm} />
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-sm text-wep-navy mb-2">⚠️ Escalations</h3>
          <div className="grid grid-cols-2 gap-3">
            <CountField field="escalations_raised" label="Raised today" form={form} setForm={setForm} />
            <CountField field="escalations_resolved" label="Resolved today" form={form} setForm={setForm} />
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-sm text-wep-navy mb-2">💰 Collections & Meetings</h3>
          <div className="grid grid-cols-2 gap-3">
            <CountField field="collection_calls_made" label="Collection calls made" form={form} setForm={setForm} />
            <div>
              <label className="form-label block mb-1 text-xs">Amount collected (₹)</label>
              <input type="number" min="0" value={form.collection_amount}
                onChange={e => setForm((f: any) => ({ ...f, collection_amount: e.target.value }))}
                className="form-input" />
            </div>
            <CountField field="client_meetings_held" label="Client meetings held" form={form} setForm={setForm} />
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-sm text-wep-navy mb-2">👥 Resourcing</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="form-label block mb-1 text-xs">Resources deployed</label>
              <input type="number" min="0" value={form.resource_deployed}
                onChange={e => setForm((f: any) => ({ ...f, resource_deployed: e.target.value }))}
                className="form-input" />
            </div>
            <div>
              <label className="form-label block mb-1 text-xs">Resources available</label>
              <input type="number" min="0" value={form.resource_available}
                onChange={e => setForm((f: any) => ({ ...f, resource_available: e.target.value }))}
                className="form-input" />
            </div>
          </div>
        </div>

        <div>
          <label className="form-label block mb-1 text-xs">Blockers / Notes</label>
          <textarea rows={3} value={form.blockers_notes}
            onChange={e => setForm((f: any) => ({ ...f, blockers_notes: e.target.value }))}
            placeholder="Anything blocking delivery today..." className="form-input" />
        </div>

        <div className="flex items-center gap-3">
          <button onClick={() => submit.mutate()} disabled={submit.isPending} className="btn-primary">
            {submit.isPending ? '⏳ Saving...' : saved ? '✅ Saved' : '💾 Save DOR'}
          </button>
        </div>
      </div>
    </div>
  )
}
