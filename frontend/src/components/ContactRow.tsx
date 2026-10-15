import { Link } from 'react-router-dom'
import { Phone, Mail, Smartphone, AlertTriangle } from 'lucide-react'
import { Avatar, Pill } from '@/components/ui/bits'
import { CompleteDetailsInline, missingLabel, type ContactLite } from '@/components/ContactPicker'

/** One person: avatar, name, role, tap-to-call / tap-to-email, status pills.
 * `children` renders the actions on the right. Used by the company page and the directory. */
export default function ContactRow({ c, showCompany, fixing, onFix, onFixed, children }: {
  c: ContactLite & { moved_from_account?: string | null; moved_to?: { id: string; account_id: string; account_name: string }[] }
  showCompany?: boolean; fixing?: boolean; onFix?: () => void; onFixed?: () => void; children?: React.ReactNode
}) {
  const left = c.status === 'left'
  const link = 'inline-flex items-center gap-1.5 hover:text-brand-pink hover:underline underline-offset-2 min-h-[28px]'
  return (
    <div className={`card !p-3.5 flex items-start gap-3 flex-wrap ${left ? 'opacity-75' : ''}`}>
      <Avatar name={c.name} />
      <div className="min-w-0 flex-1 basis-56">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-wep-text">{c.salutation ? `${c.salutation} ` : ''}{c.name}</span>
          {left && <Pill>Left</Pill>}
          {c.do_not_contact && <Pill tone="danger">Do not contact</Pill>}
          {c.moved_from_account && <Pill tone="brand">Formerly at {c.moved_from_account}</Pill>}
        </div>
        <div className="text-xs text-wep-muted">
          {[c.designation, showCompany && c.account_name].filter(Boolean).map((t, i) => (
            <span key={i}>{i > 0 && ' · '}{showCompany && t === c.account_name ? <Link to={`/companies/${c.account_id}`} className="text-brand-pink font-medium">{t}</Link> : t}</span>
          ))}{!c.designation && !showCompany && '—'}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-wep-text">
          {c.phone_primary && <a href={`tel:${c.phone_primary}`} className={link}><Phone size={13} className="text-wep-muted" aria-hidden />{c.phone_primary}</a>}
          {c.phone_secondary && <a href={`tel:${c.phone_secondary}`} className={link}><Smartphone size={13} className="text-wep-muted" aria-hidden />{c.phone_secondary}</a>}
          {c.email && <a href={`mailto:${c.email}`} className={`${link} break-all`}><Mail size={13} className="text-wep-muted" aria-hidden />{c.email}</a>}
        </div>
        {c.moved_to && c.moved_to.length > 0 && (
          <div className="mt-1 text-xs">Now at {c.moved_to.map((m, i) => <span key={m.id}>{i > 0 && ', '}<Link to={`/companies/${m.account_id}`} className="text-brand-pink font-semibold">{m.account_name}</Link></span>)}</div>
        )}
        {!left && c.incomplete && (
          <div className="mt-2">
            {fixing
              ? <div className="rounded-xl border border-amber-300 bg-amber-50 p-2.5"><div className="text-[11px] font-semibold mb-1.5">Complete the details to use {c.first_name} in a MOM</div><CompleteDetailsInline contact={c} onDone={() => onFixed?.()} /></div>
              : <button type="button" onClick={onFix} className="inline-flex items-center gap-1.5 text-xs font-semibold text-wep-amber min-h-[32px]"><AlertTriangle size={13} aria-hidden />Needs details — {missingLabel(c)}</button>}
          </div>
        )}
      </div>
      {children && <div className="flex items-center gap-0.5 flex-wrap -mr-1.5">{children}</div>}
    </div>
  )
}
