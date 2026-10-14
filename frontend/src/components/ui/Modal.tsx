import { useEffect, useId, useRef } from 'react'
import { X } from 'lucide-react'

/** Accessible dialog: Esc closes, focus moves in and is trapped, returns to the
 * trigger on close, body scroll locked. Bottom-sheet on phones, centred card on
 * larger screens. */
export default function Modal({ title, subtitle, onClose, children, size = 'md' }: {
  title: string; subtitle?: string; onClose: () => void; children: React.ReactNode; size?: 'sm' | 'md' | 'lg'
}) {
  const ref = useRef<HTMLDivElement>(null)
  const titleId = useId()
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const el = ref.current
    const focusables = () => Array.from(el?.querySelectorAll<HTMLElement>(
      'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])') ?? [])
    ;(focusables()[0] ?? el)?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return }
      if (e.key !== 'Tab') return
      const f = focusables(); if (!f.length) return
      const first = f[0], last = f[f.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = overflow; prev?.focus?.() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const width = size === 'sm' ? 'sm:max-w-md' : size === 'lg' ? 'sm:max-w-2xl' : 'sm:max-w-lg'
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-wep-navy/50 sm:p-4" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className={`bg-white w-full ${width} rounded-t-2xl sm:rounded-2xl shadow-card-lg max-h-[92vh] overflow-y-auto outline-none motion-safe:animate-[toastIn_0.2s_ease-out]`}>
        <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3 sticky top-0 bg-white rounded-t-2xl z-10">
          <div>
            <h2 id={titleId} className="font-bold text-base text-wep-text leading-snug">{title}</h2>
            {subtitle && <p className="text-xs text-wep-muted mt-0.5">{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close"
            className="shrink-0 w-9 h-9 -mr-2 -mt-1 flex items-center justify-center rounded-lg text-wep-muted hover:bg-wep-surface hover:text-wep-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink">
            <X size={18} aria-hidden />
          </button>
        </div>
        <div className="px-5 pb-5 space-y-3">{children}</div>
      </div>
    </div>
  )
}
