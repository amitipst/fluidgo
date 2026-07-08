import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '@/hooks/useApi'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''

  const [pw, setPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!token) setError('This reset link is missing its token. Please use the link from your email, or request a new one.')
  }, [token])

  const tooShort = pw.length > 0 && pw.length < 8
  const mismatch = confirm.length > 0 && pw !== confirm

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (pw.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (pw !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, new_password: pw })
      setDone(true)
      setTimeout(() => navigate('/login'), 2500)
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not reset password. The link may have expired.')
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
            WEP Solutions &middot; Reset Password
          </div>
        </div>

        {done ? (
          <div className="text-center py-6">
            <div className="text-4xl mb-3">&#9989;</div>
            <p className="text-white font-semibold mb-1">Password reset complete</p>
            <p className="text-sm" style={{ color: 'rgba(255,255,255,0.55)' }}>
              Redirecting you to sign in&hellip;
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Choose a new password for your account.
            </p>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                style={{ color: 'rgba(255,255,255,0.45)' }}>New Password</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={pw}
                  onChange={e => setPw(e.target.value)} required disabled={!token}
                  placeholder="At least 8 characters"
                  className="w-full rounded-lg px-3 py-2.5 text-sm outline-none pr-10"
                  style={{ background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff' }} />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-sm opacity-50">&#128065;</button>
              </div>
              {tooShort && <p className="text-[11px] mt-1 text-amber-400">Must be at least 8 characters.</p>}
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                style={{ color: 'rgba(255,255,255,0.45)' }}>Confirm Password</label>
              <input type={showPw ? 'text' : 'password'} value={confirm}
                onChange={e => setConfirm(e.target.value)} required disabled={!token}
                placeholder="Re-enter password"
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

            <button type="submit" disabled={loading || !token || tooShort || mismatch}
              className="w-full font-bold py-3 rounded-xl text-white disabled:opacity-40 transition-opacity"
              style={{ background: 'linear-gradient(135deg,#F0115E,#C2005A)' }}>
              {loading ? 'Resetting&hellip;' : 'Reset Password →'}
            </button>

            <button type="button" onClick={() => navigate('/login')}
              className="w-full text-center text-[12px] hover:underline"
              style={{ color: 'rgba(255,255,255,0.4)' }}>
              Back to sign in
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
