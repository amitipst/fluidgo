// Extracted from Dashboard.tsx's AI panel (had its own private copy) so
// every "saved/generated Xm ago" indicator in the app reads the same way
// instead of each screen reinventing relative-time formatting.
export function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}
