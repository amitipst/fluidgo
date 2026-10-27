import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '@/hooks/useApi'
import { APP_VERSION } from '@/version'

// Platform overview (v1.6.2) for the super admin, who is the technology/platform admin rather than
// a business leader. Reads /system/health only; data access is unchanged.

export default function PlatformPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['platform-health'],
    queryFn: () => api.get('/system/health').then(r => r.data),
    refetchInterval: 60_000,
  })
  const failed = data?.activity?.failed_logins_24h ?? 0

  return (
    <div className="card mb-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="font-semibold text-sm text-wep-navy">🛠️ Platform overview · v{APP_VERSION}</div>
        <Link to="/system-health" className="text-xs text-wep-pink underline">System health &amp; audit</Link>
      </div>
      {isLoading && <div className="text-sm text-wep-muted">Loading…</div>}
      {isError && <div className="text-sm text-red-600">Could not load platform health.</div>}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div><div className="text-[11px] uppercase text-wep-muted">Active users</div>
            <div className="font-bold text-lg">{data.users.active}</div>
            <div className="text-[11px] text-wep-muted">{data.users.inactive} inactive</div></div>
          <div><div className="text-[11px] uppercase text-wep-muted">Logins (24h)</div>
            <div className="font-bold text-lg">{data.activity.logins_24h}</div></div>
          <div><div className="text-[11px] uppercase text-wep-muted">Failed logins (24h)</div>
            <div className={`font-bold text-lg ${failed > 5 ? 'text-red-600' : ''}`}>{failed}{failed > 5 ? ' — review' : ''}</div></div>
          <div><div className="text-[11px] uppercase text-wep-muted">Audit events (24h)</div>
            <div className="font-bold text-lg">{data.activity.audit_events_24h}</div></div>
          <div><div className="text-[11px] uppercase text-wep-muted">DSRs today</div>
            <div className="font-bold text-lg">{data.activity.dsrs_submitted_today}</div></div>
        </div>
      )}
      <div className="flex gap-3 flex-wrap mt-3 text-xs">
        <Link to="/team" className="underline">Users &amp; roles</Link>
        <Link to="/scoring-admin" className="underline">Scoring admin</Link>
        <Link to="/feedback" className="underline">Feedback inbox</Link>
        <Link to="/governance" className="underline">Governance</Link>
      </div>
    </div>
  )
}
