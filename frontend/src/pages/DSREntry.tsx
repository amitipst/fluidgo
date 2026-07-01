import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { useState } from 'react'
import api from '@/hooks/useApi'

const schema = z.object({
  date: z.string(),
  status: z.enum(['working','leave','holiday','wfh']),
  visits: z.coerce.number().min(0),
  virtual_meetings: z.coerce.number().min(0),
  calls: z.coerce.number().min(0),
  new_leads: z.coerce.number().min(0),
  followups: z.coerce.number().min(0),
  proposals: z.coerce.number().min(0),
  notes: z.string().optional(),
  market_coverage: z.coerce.number().min(0).max(5),
  lead_generation: z.coerce.number().min(0).max(5),
  followup_discipline: z.coerce.number().min(0).max(5),
  quality_of_conv: z.coerce.number().min(0).max(5),
  commitment_to_close: z.coerce.number().min(0).max(5),
})
type FormData = z.infer<typeof schema>

const SCORES = [
  { key: 'market_coverage',      label: 'Market Coverage'        },
  { key: 'lead_generation',      label: 'Lead Generation'        },
  { key: 'followup_discipline',  label: 'Follow-Up Discipline'   },
  { key: 'quality_of_conv',      label: 'Quality of Conversations'},
  { key: 'commitment_to_close',  label: 'Commitment to Closing'  },
]

export default function DSREntry() {
  const today = format(new Date(), 'yyyy-MM-dd')
  const qc = useQueryClient()
  const [submitted, setSubmitted] = useState(false)

  const { data: existing } = useQuery({
    queryKey: ['dsr', today],
    queryFn: () => api.get(`/dsr?date=${today}`).then(r => r.data)
  })

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { date: today, status: 'working', visits:0, virtual_meetings:0,
      calls:0, new_leads:0, followups:0, proposals:0,
      market_coverage:4, lead_generation:4, followup_discipline:4,
      quality_of_conv:4, commitment_to_close:4 }
  })

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      const { market_coverage, lead_generation, followup_discipline, quality_of_conv, commitment_to_close, ...dsr } = data
      return api.post('/dsr', { ...dsr, self_scores: { market_coverage, lead_generation, followup_discipline, quality_of_conv, commitment_to_close } })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dsr'] }); setSubmitted(true) }
  })

  const status = watch('status')

  if (submitted) return (
    <div className="p-6 flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="text-5xl mb-4">✅</div>
      <h2 className="font-display font-bold text-2xl text-wep-navy mb-2">DSR Submitted!</h2>
      <p className="text-wep-muted mb-6">AI analysis running in background — check Dashboard in 30 seconds.</p>
      <button className="btn-primary" onClick={() => setSubmitted(false)}>Submit Another</button>
    </div>
  )

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">✏️ Submit Daily Sales Report</h1>
        <p className="text-wep-muted text-sm mt-1">{format(new Date(), 'EEEE, d MMMM yyyy')}</p>
      </div>

      <form onSubmit={handleSubmit(data => mutation.mutate(data))} className="space-y-4">
        {/* Status */}
        <div className="card">
          <label className="form-label block mb-2">Day Status</label>
          <div className="flex gap-2 flex-wrap">
            {['working','leave','holiday','wfh'].map(s => (
              <label key={s} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm font-medium transition-colors
                ${watch('status')===s ? 'border-wep-accent bg-wep-accent/10 text-wep-accent' : 'border-wep-border text-wep-muted'}`}>
                <input type="radio" value={s} {...register('status')} className="hidden"/>
                {s === 'working' ? '💼' : s === 'leave' ? '🏖️' : s === 'holiday' ? '🎉' : '🏠'}
                {s.charAt(0).toUpperCase()+s.slice(1).replace('_',' ')}
              </label>
            ))}
          </div>
        </div>

        {/* Activity counts */}
        {status === 'working' && (
          <div className="card">
            <h3 className="font-semibold text-sm text-wep-navy mb-3">📊 Activity Counts</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key:'visits',           label:'Customer Visits (Physical)', icon:'🏢' },
                { key:'virtual_meetings', label:'Virtual Meetings',            icon:'💻' },
                { key:'calls',            label:'Phone Calls',                 icon:'📞' },
                { key:'new_leads',        label:'New Leads Added',             icon:'🎯' },
                { key:'followups',        label:'Follow-Ups Completed',        icon:'🔄' },
                { key:'proposals',        label:'Proposals Sent',              icon:'📄' },
              ].map(f => (
                <div key={f.key}>
                  <label className="form-label block mb-1">{f.icon} {f.label}</label>
                  <input type="number" min="0" {...register(f.key as any)}
                    className="form-input text-center text-lg font-bold"/>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Self scoring */}
        {status === 'working' && (
          <div className="card">
            <h3 className="font-semibold text-sm text-wep-navy mb-3">⭐ Self Score (0–5)</h3>
            <div className="space-y-3">
              {SCORES.map(s => (
                <div key={s.key} className="flex items-center gap-3">
                  <span className="text-xs text-wep-muted w-40 shrink-0">{s.label}</span>
                  <input type="range" min="0" max="5" step="1"
                    {...register(s.key as any)}
                    className="flex-1 accent-wep-accent"/>
                  <span className="w-6 text-center font-bold text-wep-accent text-sm">
                    {watch(s.key as any)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        <div className="card">
          <label className="form-label block mb-2">📝 Key Highlights / Notes</label>
          <textarea {...register('notes')} rows={3}
            placeholder="Important updates, wins, blockers..."
            className="form-input resize-none"/>
        </div>

        <button type="submit" disabled={mutation.isPending}
          className="w-full btn-primary py-3 text-base disabled:opacity-50">
          {mutation.isPending ? '⏳ Submitting...' : '✅ Submit DSR'}
        </button>
        {mutation.isError && <p className="text-red-500 text-sm text-center">Submission failed. Check your connection.</p>}
      </form>
    </div>
  )
}
