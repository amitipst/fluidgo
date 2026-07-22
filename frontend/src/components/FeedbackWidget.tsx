import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

// Every logged-in role sees this — a bug/idea/question can come from
// anyone, not just field reps. Auto-attaches the page they were on so
// admins don't have to ask "where did this happen?".
const CATEGORIES: { key: string; label: string; icon: string }[] = [
  { key: 'bug',      label: "Something's broken", icon: '🐞' },
  { key: 'idea',     label: 'Idea / suggestion',   icon: '💡' },
  { key: 'question', label: 'Question',            icon: '❓' },
  { key: 'other',    label: 'Other',               icon: '💬' },
]

export default function FeedbackWidget() {
  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState('bug')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const location = useLocation()

  async function submit() {
    if (!message.trim()) { toast.error('Please describe the issue or idea first.'); return }
    setSaving(true)
    try {
      await api.post('/feedback', {
        category, message: message.trim(), page_context: location.pathname,
      })
      toast.success("Thanks — we've got it, and the team's been notified.")
      setMessage('')
      setCategory('bug')
      setOpen(false)
    } catch (e: any) {
      toast.error(getErrorMessage(e, 'Could not send feedback — please try again'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {/* Floating trigger — visible on every screen, every role */}
      <button
        onClick={() => setOpen(true)}
        title="Report an issue or share an idea"
        className="fixed z-40 flex items-center justify-center rounded-full shadow-lg transition-transform hover:scale-105"
        style={{
          right: 20, bottom: 84, width: 48, height: 48,
          background: 'linear-gradient(135deg,#F0115E,#92278E)',
          boxShadow: '0 6px 20px rgba(240,17,94,0.35)',
        }}>
        <span className="text-xl" style={{ color: '#fff' }}>💬</span>
      </button>

      {open && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 9998, background: 'rgba(26,11,46,0.55)', display: 'grid', placeItems: 'center', padding: 16 }}
          onClick={() => !saving && setOpen(false)}>
          <div className="card" style={{ maxWidth: 440, width: '100%' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display font-bold text-lg text-wep-navy">Report an issue or idea</h3>
              <button onClick={() => setOpen(false)} className="text-wep-muted text-xl leading-none">×</button>
            </div>
            <p className="text-wep-muted text-xs mb-3">
              Goes straight to the fluidGo admin team — you'll help make the platform better for everyone.
            </p>

            <label className="form-label block mb-1.5">What's this about?</label>
            <div className="grid grid-cols-2 gap-2 mb-4">
              {CATEGORIES.map(c => (
                <button key={c.key} onClick={() => setCategory(c.key)}
                  className="py-2 rounded-xl text-xs font-bold border-2 transition-all flex items-center justify-center gap-1.5"
                  style={{
                    borderColor: category === c.key ? '#F0115E' : '#E8DFF5',
                    color: category === c.key ? '#fff' : '#F0115E',
                    background: category === c.key ? '#F0115E' : 'transparent',
                  }}>
                  <span>{c.icon}</span> {c.label}
                </button>
              ))}
            </div>

            <label className="form-label block mb-1.5">Tell us more</label>
            <textarea className="form-input" rows={4} value={message} onChange={e => setMessage(e.target.value)}
              placeholder="What happened, or what would help you?" />

            <div className="flex gap-2 mt-4">
              <button onClick={submit} disabled={saving} className="btn-primary flex-1 disabled:opacity-40">
                {saving ? 'Sending…' : 'Send feedback'}
              </button>
              <button onClick={() => setOpen(false)} className="btn-outline">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
