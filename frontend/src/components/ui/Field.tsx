import { useId } from 'react'
import { Check, AlertCircle, Loader2, AlertTriangle } from 'lucide-react'

export type FieldStatus = { kind: 'checking' | 'ok' | 'warn'; text: string } | null

type Common = {
  label: string; required?: boolean; hint?: string
  /** error message — shown only when `showError` is true (i.e. after the field was touched) */
  error?: string | null; showError?: boolean
  /** green tick when valid & non-empty (touched) */
  valid?: boolean
  status?: FieldStatus
  className?: string
}

function Frame({ id, label, required, hint, error, showError, status, className, children }: Common & { id: string; children: React.ReactNode }) {
  const err = showError ? error : null
  return (
    <div className={className}>
      <label htmlFor={id} className="form-label block mb-1">{label}{required && <span className="text-brand-pink" aria-hidden> *</span>}{required && <span className="sr-only"> (required)</span>}</label>
      {children}
      <div id={`${id}-msg`} className="min-h-[16px] mt-1 text-[11px] leading-snug" aria-live="polite">
        {err ? <span className="text-red-600 inline-flex items-start gap-1"><AlertCircle size={12} className="mt-[1px] shrink-0" aria-hidden />{err}</span>
          : status ? (
            <span className={`inline-flex items-start gap-1 ${status.kind === 'ok' ? 'text-wep-green' : status.kind === 'warn' ? 'text-wep-amber' : 'text-wep-muted'}`}>
              {status.kind === 'checking' ? <Loader2 size={12} className="mt-[1px] shrink-0 motion-safe:animate-spin" aria-hidden />
                : status.kind === 'ok' ? <Check size={12} className="mt-[1px] shrink-0" aria-hidden /> : <AlertTriangle size={12} className="mt-[1px] shrink-0" aria-hidden />}
              {status.text}</span>)
          : hint ? <span className="text-wep-light">{hint}</span> : null}
      </div>
    </div>
  )
}

export function TextInput({ label, required, hint, error, showError, valid, status, className, ...input }:
  Common & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'className'>) {
  const id = useId()
  const err = showError && !!error
  const ok = !err && valid && !!String(input.value ?? '').trim()
  return (
    <Frame id={id} {...{ label, required, hint, error, showError, status, className }}>
      <div className="relative">
        <input id={id} {...input} required={undefined} aria-required={required || undefined} aria-invalid={err || undefined} aria-describedby={`${id}-msg`}
          className={`form-input min-h-[44px] ${err ? '!border-red-500 !shadow-[0_0_0_3px_rgba(220,38,38,0.10)]' : ''} ${ok || status ? 'pr-9' : ''}`} />
        {ok && <Check size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-wep-green" aria-hidden />}
        {!ok && status?.kind === 'checking' && <Loader2 size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-wep-muted motion-safe:animate-spin" aria-hidden />}
      </div>
    </Frame>
  )
}

export function SelectInput({ label, required, hint, error, showError, className, children, ...sel }:
  Common & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'className'>) {
  const id = useId()
  const err = showError && !!error
  return (
    <Frame id={id} {...{ label, required, hint, error, showError, className }}>
      <select id={id} {...sel} aria-invalid={err || undefined} aria-describedby={`${id}-msg`}
        className={`form-select min-h-[44px] ${err ? '!border-red-500' : ''}`}>{children}</select>
    </Frame>
  )
}

/** Small section heading inside long forms. */
export function FormSection({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold uppercase tracking-wider text-wep-light pt-1 border-t border-wep-border first:border-0 first:pt-0">{children}</div>
}
