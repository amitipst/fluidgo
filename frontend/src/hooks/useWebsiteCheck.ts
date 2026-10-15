import { useCallback, useRef, useState } from 'react'
import api from '@/hooks/useApi'
import { websiteError } from '@/lib/validation'
import type { FieldStatus } from '@/components/ui/Field'

/** Advisory live check of a company website. Never blocks saving: it only tells
 * the user "✓ live" or "⚠ couldn't reach — check the address" so wrong sites get
 * corrected at entry time. Stale responses are ignored. */
export function useWebsiteCheck() {
  const [status, setStatus] = useState<FieldStatus>(null)
  const seq = useRef(0)
  const reset = useCallback(() => { seq.current++; setStatus(null) }, [])
  const check = useCallback(async (value: string, onNormalized?: (url: string) => void) => {
    const v = value.trim()
    if (!v || websiteError(v)) { reset(); return }
    const n = ++seq.current
    setStatus({ kind: 'checking', text: 'Checking the website…' })
    try {
      const r = (await api.post('/accounts/check-website', { url: v })).data
      if (n !== seq.current) return
      if (r.ok) {
        setStatus({ kind: 'ok', text: r.message })
        if (r.url && r.url !== v) onNormalized?.(r.url)
      } else {
        setStatus({ kind: 'warn', text: `${r.message}. You can still save, but please double-check it.` })
      }
    } catch (e: any) {
      if (n !== seq.current) return
      setStatus({ kind: 'warn', text: e?.response?.status === 429 ? 'Too many checks — try again in a minute.' : "Couldn't verify the website right now." })
    }
  }, [reset])
  return { status, check, reset }
}
