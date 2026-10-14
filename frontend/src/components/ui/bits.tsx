import { Link } from 'react-router-dom'

const TONES = [
  'bg-brand-purple-lt text-brand-purple', 'bg-brand-pink-lt text-brand-pink',
  'bg-teal-50 text-wep-teal', 'bg-sky-50 text-wep-accent', 'bg-amber-50 text-wep-amber',
]
function tone(seed: string) { let h = 0; for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return TONES[h % TONES.length] }

/** Initials tile — colour is derived from the name so the same person/company always looks the same. */
export function Avatar({ name, size = 40, square = false }: { name: string; size?: number; square?: boolean }) {
  const parts = name.replace(/[^\p{L}\p{N} ]/gu, '').split(/\s+/).filter(Boolean)
  const initials = ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
  return (
    <div aria-hidden style={{ width: size, height: size, fontSize: size * 0.38 }}
      className={`${tone(name)} ${square ? 'rounded-xl' : 'rounded-full'} shrink-0 flex items-center justify-center font-bold select-none`}>{initials}</div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`bg-wep-border/70 rounded-lg motion-safe:animate-pulse ${className}`} />
}

export function EmptyState({ icon, title, hint, action }: { icon: React.ReactNode; title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="card text-center py-10 px-4">
      <div className="mx-auto w-12 h-12 rounded-full bg-brand-purple-lt text-brand-purple flex items-center justify-center mb-3" aria-hidden>{icon}</div>
      <div className="font-semibold text-sm text-wep-text">{title}</div>
      {hint && <p className="text-xs text-wep-muted mt-1 max-w-sm mx-auto">{hint}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

export function Pill({ children, tone: t = 'muted' }: { children: React.ReactNode; tone?: 'muted' | 'warn' | 'danger' | 'ok' | 'brand' }) {
  const cls = { muted: 'bg-wep-border/60 text-wep-muted', warn: 'bg-amber-50 text-wep-amber', danger: 'bg-red-50 text-red-600', ok: 'bg-emerald-50 text-emerald-700', brand: 'bg-brand-purple-lt text-brand-purple' }[t]
  return <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cls}`}>{children}</span>
}

/** Subtle icon+label action used in dense rows; ≥44px tap height on touch screens. */
export function RowAction({ onClick, icon, children, danger, to }: {
  onClick?: () => void; icon?: React.ReactNode; children: React.ReactNode; danger?: boolean; to?: string
}) {
  const cls = `inline-flex items-center gap-1.5 px-2.5 min-h-[36px] md:min-h-0 md:py-1 rounded-lg text-xs font-medium transition-colors
    focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink ${danger ? 'text-red-600 hover:bg-red-50' : 'text-wep-muted hover:bg-wep-surface hover:text-wep-text'}`
  return to ? <Link to={to} className={cls}>{icon}{children}</Link>
    : <button type="button" onClick={onClick} className={cls}>{icon}{children}</button>
}
