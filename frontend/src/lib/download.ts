// Blob-download pattern — a plain <a href> can't carry the Authorization
// header the API needs, so this goes through the authenticated `api`
// instance and builds a temporary object URL. Previously duplicated
// independently in Team.tsx, FGAApproval.tsx, SystemHealth.tsx and
// Analytics.tsx (each with its own near-identical copy); centralized here
// for the new Reports page (lib/revenue.ts and lib/business.ts got the same
// treatment this round) rather than adding a fifth copy. The existing four
// are left as-is for now — pure extraction, no behavior change, low-risk
// duplication — flagged for a future cleanup pass same as business.ts's.
import api from '@/hooks/useApi'

export async function downloadFile(path: string, filename: string, params?: Record<string, any>): Promise<void> {
  const res = await api.get(path, { params, responseType: 'blob' })
  const url = URL.createObjectURL(new Blob([res.data as any]))
  const link = document.createElement('a')
  link.href = url; link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
