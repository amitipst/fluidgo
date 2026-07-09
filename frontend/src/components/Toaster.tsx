import { useToast, type ToastKind } from '@/store/toastStore'

const KIND_STYLE: Record<ToastKind, { bg: string; icon: string; ring: string }> = {
  success: { bg: 'linear-gradient(135deg,#0D9488,#0F766E)', icon: '✓', ring: 'rgba(13,148,136,0.4)' },
  error:   { bg: 'linear-gradient(135deg,#DC2626,#B91C1C)', icon: '⚠', ring: 'rgba(220,38,38,0.4)' },
  info:    { bg: 'linear-gradient(135deg,#F0115E,#92278E)', icon: 'ℹ', ring: 'rgba(240,17,94,0.4)' },
}

export default function Toaster() {
  const { toasts, dismiss } = useToast()
  if (toasts.length === 0) return null

  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
      display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 380,
    }}>
      {toasts.map((t) => {
        const s = KIND_STYLE[t.kind]
        return (
          <div key={t.id}
            style={{
              background: s.bg, color: '#fff', borderRadius: 14, padding: '14px 16px',
              boxShadow: `0 10px 30px -8px ${s.ring}, 0 4px 12px rgba(0,0,0,0.15)`,
              display: 'flex', alignItems: 'flex-start', gap: 12,
              animation: 'toastIn 0.25s cubic-bezier(0.16,1,0.3,1)',
            }}>
            <span style={{
              fontSize: 15, fontWeight: 700, lineHeight: '20px',
              width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
              background: 'rgba(255,255,255,0.2)', display: 'grid', placeItems: 'center',
            }}>{s.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontSize: 13.5, lineHeight: '19px', margin: 0, fontWeight: 500 }}>{t.message}</p>
              {t.actionLabel && (
                <button
                  onClick={() => { t.onAction?.(); dismiss(t.id) }}
                  style={{
                    marginTop: 8, background: 'rgba(255,255,255,0.95)', color: '#1A0B2E',
                    border: 'none', borderRadius: 8, padding: '5px 12px',
                    fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  }}>
                  {t.actionLabel} →
                </button>
              )}
            </div>
            <button onClick={() => dismiss(t.id)}
              style={{
                background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.7)',
                fontSize: 16, cursor: 'pointer', lineHeight: '18px', padding: 0, flexShrink: 0,
              }}>×</button>
          </div>
        )
      })}
      <style>{`@keyframes toastIn { from { opacity: 0; transform: translateY(12px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }`}</style>
    </div>
  )
}
