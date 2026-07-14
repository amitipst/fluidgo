import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { getErrorMessage } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'

// Mandatory password-change screen — reached either straight after login
// (must_change_password on the login response) or mid-session if an admin
// resets the password of someone already logged in (see the 403 interceptor
// in useApi.ts). Requires the CURRENT password, unlike the emailed-link
// ResetPassword.tsx flow — this proves the person at the keyboard is really
// the account holder. Backend enforces the same gate independently
// (deps.get_current_user), so this screen is UX, not the security boundary.
const MIN_LENGTH = 10

export default function ChangePassword() {
  const navigate = useNavigate()
  const { user, updateUser, clearAuth } = useAuthStore()

  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const tooShort = newPw.length > 0 && newPw.length < MIN_LENGTH
  const mismatch = confirm.length > 0 && newPw !== confirm
  const sameAsCurrent = newPw.length > 0 && newPw === currentPw

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (newPw.length < MIN_LENGTH) { setError(`Password must be at least ${MIN_LENGTH} characters.`); return }
    if (newPw !== confirm) { setError('Passwords do not match.'); return }
    if (newPw === currentPw) { setError('New password must be different from your current password.'); return }
    setLoading(true)
    try {
      await api.post('/auth/change-password', { current_password: currentPw, new_password: newPw })
      updateUser({ must_change_password: false })
      setDone(true)
      setTimeout(() => navigate('/'), 1200)
    } catch (err: any) {
      setError(getErrorMessage(err, 'Could not update password.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-login-gradient px-4">
      <div className="w-full max-w-[420px] rounded-2xl p-8"
        style={{ background: 'rgba(26,11,46,0.6)', border: '1px solid rgba(255,255,255,0.10)', backdropFilter: 'blur(12px)' }}>

        <div className="mb-6">
          <div className="font-display font-bold text-white text-2xl">fluidGo</div>
          <div className="text-[11px] uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.4)' }}>
            WEP Solutions &middot; Set a New Password
          </div>
        </div>

        {done ? (
          <div className="text-center py-6">
            <div className="text-4xl mb-3">&#9989;</div>
            <p className="text-white font-semibold mb-1">Password updated</p>
            <p className="text-sm" style={{ color: 'rgba(255,255,255,0.55)' }}>
              Taking you to your dashboard&hellip;
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>
              {user?.name ? `Hi ${user.name.split(' ')[0]}, y` : 'Y'}ou need to set your own password
              before continuing{user ? '' : '.'} This is a one-time step — your account was either
              just created or your password was reset by an admin.
            </p>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                style={{ color: 'rgba(255,255,255,0.45)' }}>Current / Temporary Password</label>
              <input type={showPw ? 'text' : 'password'} value={currentPw}
                onChange={e => setCurrentPw(e.target.value)} required autoFocus
                placeholder="The password you just used to log in"
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff' }} />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                style={{ color: 'rgba(255,255,255,0.45)' }}>New Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={newPw}
                  onChange={e => setNewPw(e.target.value)} required
                  placeholder={`At least ${MIN_LENGTH} characters`}
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none pr-10"
                  style={{ background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff' }} />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-sm opacity-50">&#128065;</button>
              </div>
              {tooShort && <p className="text-[11px] mt-1 text-amber-400">Must be at least {MIN_LENGTH} characters.</p>}
              {sameAsCurrent && <p className="text-[11px] mt-1 text-amber-400">Must be different from your current password.</p>}
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                style={{ color: 'rgba(255,255,255,0.45)' }}>Confirm New Password</label>
              <input type={showPw ? 'text' : 'password'} value={confirm}
                onChange={e => setConfirm(e.target.value)} required
                placeholder="Re-enter new password"
                className="w-full rounded-lg px-3 py-2.5 text-sm outline-none"
                style={{ background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff' }} />
              {mismatch && <p className="text-[11px] mt-1 text-amber-400">Passwords don&apos;t match.</p>}
            </div>

            {error && (
              <div className="rounded-lg px-3 py-2 text-xs"
                style={{ background: 'rgba(240,17,94,0.15)', border: '1px solid rgba(240,17,94,0.3)', color: '#ffb3c8' }}>
                &#9888; {error}
              </div>
            )}

            <button type="submit" disabled={loading || tooShort || mismatch || sameAsCurrent}
              className="w-full font-bold py-3 rounded-xl text-white disabled:opacity-40 transition-opacity"
              style={{ background: 'linear-gradient(135deg,#F0115E,#C2005A)' }}>
              {loading ? 'Updating&hellip;' : 'Set New Password →'}
            </button>

            <button type="button" onClick={() => { clearAuth(); navigate('/login') }}
              className="w-full text-center text-[12px] hover:underline"
              style={{ color: 'rgba(255,255,255,0.4)' }}>
              Sign out instead
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
