// Instant-feedback validators for forms. The backend is the authority (same
// rules in contact_service.py / geo_service.py); these only save a round-trip.

export const SALUTATIONS = ['Mr.', 'Ms.', 'Mrs.', 'Mx.', 'Dr.', 'Prof.', 'CA', 'CS', 'Er.']

/** Mirror of contact_service.normalize_phone — returns canonical number or null. */
export function normalizePhone(raw: string): string | null {
  const s = (raw ?? '').trim()
  if (!s || /[A-Za-z]/.test(s) || /[^\d\s\-.()+]/.test(s)) return null
  const intl = s.startsWith('+') || s.startsWith('00')
  let digits = s.replace(/\D/g, '')
  if (s.startsWith('00') && !s.startsWith('+')) digits = digits.slice(2)
  if (intl) {
    if (digits.length < 8 || digits.length > 15) return null
    if (digits.startsWith('91')) {
      const nat = digits.slice(2)
      return nat.length === 10 && nat[0] !== '0' ? `+91${nat}` : null
    }
    return `+${digits}`
  }
  if (digits.length === 10 && '6789'.includes(digits[0])) return `+91${digits}`
  if (digits.length === 11 && digits[0] === '0' && digits[1] !== '0') return `+91${digits.slice(1)}`
  if (digits.length === 12 && digits.startsWith('91') && '6789'.includes(digits[2])) return `+${digits}`
  return null
}

export const PHONE_HELP = '10-digit mobile (e.g. 98765 43210) or +country code number'

export function phoneError(v: string, required: boolean): string | null {
  if (!v.trim()) return required ? 'Primary phone number is required' : null
  return normalizePhone(v) ? null : `Not a valid number — ${PHONE_HELP}`
}

export function emailError(v: string): string | null {
  if (!v.trim()) return null
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()) ? null : 'Enter a valid email (name@company.com)'
}

export function nameError(v: string, required: boolean, label = 'Name'): string | null {
  const t = v.trim()
  if (!t) return required ? `${label} is required` : null
  if (t.length > 100) return `${label} is too long`
  if (/\d/.test(t) || !/^[\p{L}][\p{L}\p{M} .'\-]*$/u.test(t)) return `${label} can contain only letters, spaces, . ' and -`
  return null
}

export function websiteError(v: string): string | null {
  const t = v.trim()
  if (!t) return null
  return /^[^\s]+\.[^\s]{2,}$/.test(t) ? null : 'Website looks invalid (e.g. www.acme.com)'
}

export function linkedinError(v: string): string | null {
  const t = v.trim()
  if (!t) return null
  return /^https?:\/\/([a-z0-9-]+\.)*linkedin\.com\/\S+$/i.test(t) ? null : 'Use a LinkedIn link (https://www.linkedin.com/in/…)'
}
