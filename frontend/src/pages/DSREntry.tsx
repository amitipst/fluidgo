import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { useState } from 'react'
import api from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// ── Schemas ───────────────────────────────────────────────────────────────────
const salesSchema = z.object({
  date: z.string(),
  status: z.enum(['working','leave','holiday','wfh']),
  visits: z.coerce.number().min(0),
  virtual_meetings: z.coerce.number().min(0),
  calls: z.coerce.number().min(0),
  new_leads: z.coerce.number().min(0),
  followups: z.coerce.number().min(0),
  proposals: z.coerce.number().min(0),
  proposal_value: z.coerce.number().min(0).optional(),
  travel_day: z.boolean().default(false),
  notes: z.string().optional(),
  // Sales self-scores
  market_coverage:    z.coerce.number().min(0).max(5),
  lead_generation:    z.coerce.number().min(0).max(5),
  followup_discipline:z.coerce.number().min(0).max(5),
  quality_of_conv:    z.coerce.number().min(0).max(5),
  commitment_to_close:z.coerce.number().min(0).max(5),
})

const presalesSchema = z.object({
  date: z.string(),
  status: z.enum(['working','leave','holiday','wfh']),
  virtual_meetings: z.coerce.number().min(0),
  demos_conducted:     z.coerce.number().min(0),
  pocs_conducted:      z.coerce.number().min(0),
  proposals_supported: z.coerce.number().min(0),
  tech_discussions:    z.coerce.number().min(0),
  workshops_conducted: z.coerce.number().min(0),
  trainings_delivered: z.coerce.number().min(0),
  trainings_attended:  z.coerce.number().min(0),
  docs_created:        z.coerce.number().min(0),
  linked_opportunity_id: z.string().optional(),
  notes: z.string().optional(),
  // Pre-Sales self-scores
  solution_support:       z.coerce.number().min(0).max(5),
  technical_conversion:   z.coerce.number().min(0).max(5),
  knowledge_excellence:   z.coerce.number().min(0).max(5),
  operational_excellence: z.coerce.number().min(0).max(5),
})

type SalesForm    = z.infer<typeof salesSchema>
type PresalesForm = z.infer<typeof presalesSchema>

// ── Field config ──────────────────────────────────────────────────────────────
const SALES_FIELDS = [
  { key:'visits',           label:'Customer Visits (Physical)', icon:'🏢' },
  { key:'virtual_meetings', label:'Virtual Meetings',           icon:'💻' },
  { key:'calls',            label:'Phone Calls',                icon:'📞' },
  { key:'new_leads',        label:'New Leads Added',            icon:'🎯' },
  { key:'followups',        label:'Follow-Ups Completed',       icon:'🔄' },
  { key:'proposals',        label:'Proposals Sent',             icon:'📄' },
]
const PRESALES_FIELDS = [
  { key:'demos_conducted',     label:'Demos Conducted',       icon:'🖥️' },
  { key:'pocs_conducted',      label:'POCs Conducted',        icon:'🔬' },
  { key:'proposals_supported', label:'Proposal Support',      icon:'📝' },
  { key:'tech_discussions',    label:'Technical Discussions', icon:'💬' },
  { key:'workshops_conducted', label:'Workshops / Sessions',  icon:'🎓' },
  { key:'trainings_delivered', label:'Trainings Delivered',   icon:'📚' },
  { key:'trainings_attended',  label:'Trainings Attended',    icon:'📖' },
  { key:'docs_created',        label:'Docs / Artifacts',      icon:'📋' },
  { key:'virtual_meetings',    label:'Virtual Meetings',      icon:'💻' },
]
const SALES_SCORES = [
  { key:'market_coverage',     label:'Market Coverage'        },
  { key:'lead_generation',     label:'Lead Generation'        },
  { key:'followup_discipline', label:'Follow-Up Discipline'   },
  { key:'quality_of_conv',     label:'Quality of Conversations'},
  { key:'commitment_to_close', label:'Commitment to Closing'  },
]
const PRESALES_SCORES = [
  { key:'solution_support',       label:'Solution Support'       },
  { key:'technical_conversion',   label:'Technical Conversion'   },
  { key:'knowledge_excellence',   label:'Knowledge Excellence'   },
  { key:'operational_excellence', label:'Operational Excellence' },
]

// ── Number input with large display ──────────────────────────────────────────
function CountField({ icon, label, name, register }: any) {
  return (
    <div>
      <label className="form-label block mb-1">{icon} {label}</label>
      <input type="number" min="0" {...register(name)}
        className="form-input text-center text-xl font-bold py-3" />
    </div>
  )
}

// ── Score slider row ──────────────────────────────────────────────────────────
function ScoreSlider({ label, name, register, watch }: { label: string; name: string; register: any; watch: any }) {
  const val = watch(name)
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-wep-muted w-44 shrink-0">{label}</span>
      <input type="range" min="0" max="5" step="1" {...register(name)}
        className="flex-1 accent-wep-orange" />
      <span className="w-6 text-center font-bold text-wep-orange text-sm">{val}</span>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function DSREntry() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const today = format(new Date(), 'yyyy-MM-dd')
  const [submitted, setSubmitted] = useState(false)
  const [lastRigor, setLastRigor] = useState<number | null>(null)

  const isPresales = user?.role === 'pre_sales'

  const { data: existing } = useQuery({
    queryKey: ['dsr', today],
    queryFn: () => api.get(`/dsr?date=${today}`).then(r => r.data)
  })

  // ── Sales form ───────────────────────────────────────────────────────────
  const salesForm = useForm<SalesForm>({
    resolver: zodResolver(salesSchema),
    defaultValues: { date: today, status: 'working', visits:0, virtual_meetings:0,
      calls:0, new_leads:0, followups:0, proposals:0, travel_day: false,
      market_coverage:4, lead_generation:4, followup_discipline:4,
      quality_of_conv:4, commitment_to_close:4 }
  })

  // ── Pre-Sales form ───────────────────────────────────────────────────────
  const psForm = useForm<PresalesForm>({
    resolver: zodResolver(presalesSchema),
    defaultValues: { date: today, status: 'working',
      demos_conducted:0, pocs_conducted:0, proposals_supported:0,
      tech_discussions:0, workshops_conducted:0, trainings_delivered:0,
      trainings_attended:0, docs_created:0, virtual_meetings:0,
      solution_support:4, technical_conversion:4,
      knowledge_excellence:4, operational_excellence:4 }
  })

  const mutation = useMutation({
    mutationFn: async (data: SalesForm | PresalesForm) => {
      if (isPresales) {
        const { solution_support, technical_conversion, knowledge_excellence,
                operational_excellence, ...dsr } = data as PresalesForm
        return api.post('/dsr', { ...dsr, self_scores: {
          solution_support, technical_conversion,
          knowledge_excellence, operational_excellence
        }})
      } else {
        const { market_coverage, lead_generation, followup_discipline,
                quality_of_conv, commitment_to_close, ...dsr } = data as SalesForm
        return api.post('/dsr', { ...dsr, self_scores: {
          market_coverage, lead_generation, followup_discipline,
          quality_of_conv, commitment_to_close
        }})
      }
    },
    onSuccess: (res) => {
      setLastRigor(res.data?.rigor_score ?? null)
      qc.invalidateQueries({ queryKey: ['dsr'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      setSubmitted(true)
    }
  })

  const sStatus = salesForm.watch('status')
  const pStatus = psForm.watch('status')
  const activeStatus = isPresales ? pStatus : sStatus

  // ── Success state ────────────────────────────────────────────────────────
  if (submitted) return (
    <div className="p-6 flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="text-5xl mb-4">✅</div>
      <h2 className="font-display font-bold text-2xl text-wep-navy mb-2">DSR Submitted!</h2>
      {lastRigor !== null && lastRigor >= 0 && (
        <div className="mb-4">
          <span className="text-lg font-bold"
            style={{ color: lastRigor >= 80 ? '#059669' : lastRigor >= 60 ? '#D97706' : '#DC2626' }}>
            Rigor Score: {lastRigor}/100
          </span>
          <div className="text-sm text-wep-muted mt-1">
            {lastRigor >= 80 ? '🏆 Excellent' : lastRigor >= 60 ? '✅ Good' : '⚠️ Needs improvement'}
          </div>
        </div>
      )}
      <p className="text-wep-muted mb-6">Dashboard and team views updated in real time.</p>
      <button className="btn-primary" onClick={() => setSubmitted(false)}>Submit Another</button>
    </div>
  )

  // ── Status selector (shared) ──────────────────────────────────────────────
  const StatusSelector = ({ registerFn, watchFn }: any) => (
    <div className="card mb-4">
      <label className="form-label block mb-2">Day Status</label>
      <div className="flex gap-2 flex-wrap">
        {[
          { val:'working', label:'Working',  icon:'💼' },
          { val:'leave',   label:'Leave',    icon:'🏖️' },
          { val:'holiday', label:'Holiday',  icon:'🎉' },
          { val:'wfh',     label:'WFH',      icon:'🏠' },
        ].map(s => (
          <label key={s.val} className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border
            cursor-pointer text-sm font-medium transition-all
            ${watchFn('status') === s.val
              ? 'border-wep-orange bg-wep-orange-lt text-wep-orange'
              : 'border-wep-border text-wep-muted'}`}>
            <input type="radio" value={s.val} {...registerFn('status')} className="hidden"/>
            {s.icon} {s.label}
          </label>
        ))}
      </div>
    </div>
  )

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">
          {isPresales ? '🔬 Pre-Sales Daily Report' : '✏️ Submit Daily Sales Report'}
        </h1>
        <p className="text-wep-muted text-sm mt-1">
          {format(new Date(), 'EEEE, d MMMM yyyy')}
          {existing && <span className="ml-2 text-wep-teal font-medium">· Already submitted today</span>}
        </p>
      </div>

      {/* ── SALES DSR FORM ─────────────────────────────────────────────────── */}
      {!isPresales && (
        <form onSubmit={salesForm.handleSubmit(d => mutation.mutate(d))} className="space-y-4">
          <StatusSelector registerFn={salesForm.register} watchFn={salesForm.watch} />

          {sStatus === 'working' && (
            <>
              <div className="card">
                <h3 className="font-semibold text-sm text-wep-navy mb-3">📊 Activity Counts</h3>
                <div className="grid grid-cols-2 gap-3">
                  {SALES_FIELDS.map(f => (
                    <CountField key={f.key} icon={f.icon} label={f.label} name={f.key} register={salesForm.register} />
                  ))}
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <label className="form-label block mb-1">💰 Proposal Value (₹)</label>
                    <input type="number" min="0" {...salesForm.register('proposal_value')}
                      className="form-input" placeholder="e.g. 500000" />
                  </div>
                  <div className="flex items-end pb-1">
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" {...salesForm.register('travel_day')}
                        className="accent-wep-orange w-4 h-4" />
                      <span className="text-wep-muted">✈️ Travel Day</span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="card">
                <h3 className="font-semibold text-sm text-wep-navy mb-3">⭐ Self Score (0–5)</h3>
                <div className="space-y-3">
                  {SALES_SCORES.map(s => (
                    <ScoreSlider
                      key={s.key}
                      label={s.label}
                      name={s.key}
                      register={salesForm.register}
                      watch={salesForm.watch}
                    />
                  ))}
                </div>
              </div>
            </>
          )}

          <div className="card">
            <label className="form-label block mb-2">📝 Notes / Highlights</label>
            <textarea {...salesForm.register('notes')} rows={3}
              placeholder="Key wins, blockers, next steps..." className="form-input resize-none"/>
          </div>

          <button type="submit" disabled={mutation.isPending}
            className="w-full btn-primary py-3 text-base disabled:opacity-50">
            {mutation.isPending ? '⏳ Submitting...' : '✅ Submit DSR'}
          </button>
          {mutation.isError && (
            <p className="text-red-500 text-sm text-center">
              Submission failed — check your connection.
            </p>
          )}
        </form>
      )}

      {/* ── PRE-SALES DSR FORM ──────────────────────────────────────────────── */}
      {isPresales && (
        <form onSubmit={psForm.handleSubmit(d => mutation.mutate(d))} className="space-y-4">
          <StatusSelector registerFn={psForm.register} watchFn={psForm.watch} />

          {pStatus === 'working' && (
            <>
              <div className="card">
                <h3 className="font-semibold text-sm text-wep-navy mb-3">🔬 Pre-Sales Activities</h3>
                <div className="grid grid-cols-2 gap-3">
                  {PRESALES_FIELDS.map(f => (
                    <CountField key={f.key} icon={f.icon} label={f.label} name={f.key} register={psForm.register} />
                  ))}
                </div>
                <div className="mt-3">
                  <label className="form-label block mb-1">🔗 Linked Opportunity ID (optional)</label>
                  <input {...psForm.register('linked_opportunity_id')}
                    className="form-input" placeholder="Opportunity UUID or name" />
                </div>
              </div>

              <div className="card">
                <h3 className="font-semibold text-sm text-wep-navy mb-3">⭐ Self Score (0–5)</h3>
                <div className="space-y-3">
                  {PRESALES_SCORES.map(s => (
                    <ScoreSlider
                      key={s.key}
                      label={s.label}
                      name={s.key}
                      register={psForm.register}
                      watch={psForm.watch}
                    />
                  ))}
                </div>
              </div>
            </>
          )}

          <div className="card">
            <label className="form-label block mb-2">📝 Notes / Highlights</label>
            <textarea {...psForm.register('notes')} rows={3}
              placeholder="POC outcomes, technical blockers, next steps..."
              className="form-input resize-none"/>
          </div>

          <button type="submit" disabled={mutation.isPending}
            className="w-full btn-primary py-3 text-base disabled:opacity-50">
            {mutation.isPending ? '⏳ Submitting...' : '✅ Submit Pre-Sales DSR'}
          </button>
          {mutation.isError && (
            <p className="text-red-500 text-sm text-center">Submission failed.</p>
          )}
        </form>
      )}
    </div>
  )
}
