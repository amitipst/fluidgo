import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import api from '@/hooks/useApi'

const ACTIONS = ['', 'LOGIN', 'LOGIN_FAILED', 'CREATE', 'UPDATE', 'DSR_APPROVE', 'DSR_REJECT']

function StatCard({ label, value, icon, color }: { label:string; value:string|number; icon:string; color:string }) {
  return (
    <div className="stat-card">
      <div className="stat-card-accent" style={{ background: color }} />
      <div className="text-2xl mb-1">{icon}</div>
      <div className="font-display font-black text-2xl" style={{ color }}>{value}</div>
      <div className="text-[10px] font-bold uppercase tracking-wide text-wep-muted mt-1">{label}</div>
    </div>
  )
}

const ACTION_COLORS: Record<string, string> = {
  LOGIN: '#059669', LOGIN_FAILED: '#DC2626', CREATE: '#1E6FD9',
  UPDATE: '#D97706', DSR_APPROVE: '#059669', DSR_REJECT: '#DC2626',
}

export default function SystemHealth() {
  const today = new Date().toISOString().slice(0,10)
  const [dateFrom, setDateFrom] = useState(today)
  const [dateTo, setDateTo]     = useState(today)
  const [action, setAction]     = useState('')
  const [userFilter, setUserFilter] = useState('')

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.get('/system/health').then(r => r.data),
    refetchInterval: 30_000,   // auto-refresh every 30s
  })

  const { data: logs = [], isLoading: logsLoading, refetch } = useQuery({
    queryKey: ['audit-trail', dateFrom, dateTo, action, userFilter],
    queryFn: () => api.get('/system/audit', {
      params: {
        date_from: dateFrom || undefined,
        date_to:   dateTo   || undefined,
        action:    action   || undefined,
        user_email: userFilter || undefined,
        limit: 200,
      }
    }).then(r => r.data),
  })

  const downloadCSV = useMutation({
    mutationFn: async () => {
      const res = await api.get('/system/audit/download', {
        params: { date_from: dateFrom, date_to: dateTo },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `fluidgo_audit_${dateFrom}_to_${dateTo}.csv`
      a.click()
      URL.revokeObjectURL(url)
    }
  })

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="page-header">
        <div>
          <h1 className="page-title">⚙️ System Health</h1>
          <p className="page-sub">Live system status · audit trail · 90-day retention</p>
        </div>
        <span className="text-xs text-wep-muted">
          {health?.timestamp ? `Updated ${new Date(health.timestamp).toLocaleTimeString()}` : ''}
        </span>
      </div>

      {/* Health snapshot */}
      {healthLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[1,2,3,4].map(i => <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard label="Active Users"     value={health?.users?.active ?? 0}          icon="👥" color="#059669" />
          <StatCard label="Inactive Users"   value={health?.users?.inactive ?? 0}        icon="🚫" color="#6B7280" />
          <StatCard label="DSRs Today"       value={health?.activity?.dsrs_submitted_today ?? 0} icon="📋" color="#1E6FD9" />
          <StatCard label="Logins (24h)"     value={health?.activity?.logins_24h ?? 0}   icon="🔑" color="#D97706" />
          <StatCard label="Failed Logins"    value={health?.activity?.failed_logins_24h ?? 0} icon="⚠️" color="#DC2626" />
          <StatCard label="Audit Events 24h" value={health?.activity?.audit_events_24h ?? 0}  icon="📊" color="#7B2D8B" />
          <StatCard label="Retention Policy" value="90 days" icon="🗓️" color="#0D9488" />
          <StatCard label="Total Users"      value={health?.users?.total ?? 0}           icon="🏢" color="#F0115E" />
        </div>
      )}

      {/* Audit Trail */}
      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="font-bold text-wep-text">📜 Audit Trail</h3>
          <button onClick={() => downloadCSV.mutate()} disabled={downloadCSV.isPending}
            className="btn-outline text-sm py-2">
            {downloadCSV.isPending ? '⏳ Preparing…' : '⬇️ Download CSV'}
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <div>
            <label className="text-[10px] font-bold text-wep-muted uppercase block mb-1">From</label>
            <input type="date" className="form-input py-1.5 text-sm"
              value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] font-bold text-wep-muted uppercase block mb-1">To</label>
            <input type="date" className="form-input py-1.5 text-sm"
              value={dateTo} onChange={e => setDateTo(e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] font-bold text-wep-muted uppercase block mb-1">Action</label>
            <select className="form-input py-1.5 text-sm" value={action} onChange={e => setAction(e.target.value)}>
              {ACTIONS.map(a => <option key={a} value={a}>{a || 'All Actions'}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-[160px]">
            <label className="text-[10px] font-bold text-wep-muted uppercase block mb-1">User Email</label>
            <input type="search" className="form-input py-1.5 text-sm w-full"
              placeholder="Search by email…"
              value={userFilter} onChange={e => setUserFilter(e.target.value)} />
          </div>
        </div>

        {/* Logs table */}
        {logsLoading ? (
          <div className="space-y-2">{[1,2,3,4,5].map(i => <div key={i} className="skeleton h-10 rounded-lg" />)}</div>
        ) : logs.length === 0 ? (
          <div className="text-center py-10 text-wep-muted text-sm">No audit events for this filter.</div>
        ) : (
          <div className="overflow-x-auto -mx-2">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-wep-muted border-b border-wep-border">
                  <th className="px-2 py-2 font-semibold">Time</th>
                  <th className="px-2 py-2 font-semibold">User</th>
                  <th className="px-2 py-2 font-semibold">Action</th>
                  <th className="px-2 py-2 font-semibold">Entity</th>
                  <th className="px-2 py-2 font-semibold">Summary</th>
                  <th className="px-2 py-2 font-semibold">IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log: any) => (
                  <tr key={log.id} className="border-b border-wep-border/40 hover:bg-wep-surface/50">
                    <td className="px-2 py-2 whitespace-nowrap text-wep-muted">
                      {new Date(log.created_at).toLocaleString('en-IN', { dateStyle:'short', timeStyle:'short' })}
                    </td>
                    <td className="px-2 py-2">
                      <div className="font-medium text-wep-text">{log.user_email}</div>
                      <div className="text-wep-muted text-[10px]">{log.user_role}</div>
                    </td>
                    <td className="px-2 py-2">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                        style={{
                          background: `${ACTION_COLORS[log.action] ?? '#6B7280'}15`,
                          color: ACTION_COLORS[log.action] ?? '#6B7280'
                        }}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-wep-muted">{log.entity_type}</td>
                    <td className="px-2 py-2 text-wep-text max-w-[240px] truncate">{log.summary}</td>
                    <td className="px-2 py-2 text-wep-muted font-mono">{log.ip_address}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
