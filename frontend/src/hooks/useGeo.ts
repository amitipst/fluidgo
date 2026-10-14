import { useQuery } from '@tanstack/react-query'
import api from '@/hooks/useApi'

export type Geo = {
  countries: { code: string; name: string }[]
  states: Record<string, string[]>
  postal_hints: Record<string, string>
  postal_patterns: Record<string, string>
}

/** Country / state / postal-code reference data — static, served by the backend
 * so there is one source of truth for every form that captures an address. */
export function useGeo() {
  return useQuery<Geo>({
    queryKey: ['geo'],
    queryFn: () => api.get('/accounts/geo').then(r => r.data),
    staleTime: Infinity,
  })
}

export function postalError(geo: Geo | undefined, country: string, v: string): string | null {
  const t = v.trim()
  if (!t || !geo) return null
  const pat = geo.postal_patterns[country] ?? geo.postal_patterns._default
  try { return new RegExp(pat).test(t) ? null : `Not valid for this country (${geo.postal_hints[country] ?? geo.postal_hints._default})` }
  catch { return null }
}
