import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import api from '@/hooks/useApi'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const res = await api.post('/auth/login', { email, password })
      setAuth(res.data.user, res.data.access_token, res.data.refresh_token)
      navigate('/')
    } catch {
      setError('Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-wep-navy flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-wep-electric to-wep-accent mb-4">
            <span className="font-display font-bold text-white text-lg">fG</span>
          </div>
          <h1 className="font-display font-bold text-white text-2xl">fluidGo</h1>
          <p className="text-wep-muted text-sm mt-1">FluidPro Sales Intelligence</p>
        </div>

        <form onSubmit={handleLogin} className="bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-6 space-y-4">
          <div>
            <label className="form-label text-white/60">Email</label>
            <input className="form-input mt-1 bg-white/10 border-white/20 text-white placeholder-white/30"
              type="email" placeholder="danish@fluidpro.in" value={email}
              onChange={e => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="form-label text-white/60">Password</label>
            <input className="form-input mt-1 bg-white/10 border-white/20 text-white placeholder-white/30"
              type="password" placeholder="••••••••" value={password}
              onChange={e => setPassword(e.target.value)} required />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" disabled={loading}
            className="w-full btn-primary py-3 text-base disabled:opacity-50">
            {loading ? 'Signing in...' : 'Sign In →'}
          </button>
        </form>

        <p className="text-center text-wep-muted text-xs mt-6">
          WEPSol FluidPro · Secure Internal Platform
        </p>
      </div>
    </div>
  )
}
