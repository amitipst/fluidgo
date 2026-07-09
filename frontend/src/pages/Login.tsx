import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import api from '@/hooks/useApi'
import { getQuoteOfDay } from '@/lib/quotes'

// Simple math captcha — prevents automated login attempts
function generateCaptcha() {
  const a = Math.floor(Math.random() * 9) + 1
  const b = Math.floor(Math.random() * 9) + 1
  return { question: `${a} + ${b} = ?`, answer: a + b }
}

// ── fluidGo logo component (SVG inline for crisp rendering at all sizes) ──
function FluidGoLogo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  // Stripe icon proportions
  const h = size === 'lg' ? 56 : size === 'md' ? 40 : 28
  const scale = h / 64
  const textSize = size === 'lg' ? 36 : size === 'md' ? 26 : 18
  const gap = size === 'lg' ? 16 : size === 'md' ? 12 : 8
  const iconW = Math.round(52 * scale)

  return (
    <div className="flex items-center" style={{ gap }}>
      {/* Stripe icon */}
      <svg width={iconW} height={h} viewBox="0 0 52 64" fill="none"
        xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="0"  y="0"  width="52" height="11" rx="2.5" fill="#F0115E"/>
        <rect x="7"  y="16" width="45" height="11" rx="2.5" fill="#F0115E"/>
        <rect x="14" y="32" width="38" height="11" rx="2.5" fill="#F0115E"/>
        <rect x="21" y="48" width="31" height="10" rx="2.5" fill="#F0115E"/>
        <rect x="0"  y="16" width="5"  height="11" rx="2" fill="#808083" opacity="0.6"/>
        <rect x="0"  y="32" width="12" height="11" rx="2" fill="#808083" opacity="0.6"/>
        <rect x="0"  y="48" width="19" height="10" rx="2" fill="#808083" opacity="0.6"/>
      </svg>
      {/* Wordmark */}
      <div>
        <div className="font-display font-black leading-none tracking-tight text-white"
          style={{ fontSize: textSize }}>
          fluidGo
        </div>
        {size !== 'sm' && (
          <div className="font-medium tracking-widest uppercase leading-none mt-0.5"
            style={{ fontSize: Math.round(textSize * 0.28), color: 'rgba(255,255,255,0.40)' }}>
            Sales Intelligence
          </div>
        )}
      </div>
    </div>
  )
}

// ── Ascent illustration — original on-brand graphic (not a stock photo), echoes
// the ascending-bars motif from the fluidGo mark itself. Inline SVG so it can
// never be corrupted like a standalone .svg file on this machine. ──
function AscentIllustration() {
  return (
    <svg viewBox="0 0 400 170" className="w-full h-auto" aria-hidden="true">
      <defs>
        <linearGradient id="peakA" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#92278E" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#92278E" stopOpacity="0.15" />
        </linearGradient>
        <linearGradient id="peakB" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F0115E" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#F0115E" stopOpacity="0.35" />
        </linearGradient>
      </defs>
      <path d="M0 170 L90 55 L165 140 L230 60 L400 170 Z" fill="url(#peakA)" />
      <path d="M40 170 L150 40 L260 170 Z" fill="url(#peakB)" />
      <path d="M60 165 L100 130 L140 105 L150 42" stroke="#0D9488" strokeWidth="3.5"
        strokeDasharray="1 10" strokeLinecap="round" fill="none" />
      <circle cx="150" cy="40" r="6" fill="#FFFFFF" />
      <path d="M150 40 L150 16" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M150 16 L172 23 L150 30 Z" fill="#0D9488" />
      <g opacity="0.8">
        <rect x="300" y="120" width="16" height="30" rx="4" fill="#F0115E" />
        <rect x="322" y="100" width="16" height="50" rx="4" fill="#F0115E" />
        <rect x="344" y="78"  width="16" height="72" rx="4" fill="#F0115E" />
        <rect x="366" y="56"  width="16" height="94" rx="4" fill="#92278E" opacity="0.7" />
      </g>
    </svg>
  )
}

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showForgot, setShowForgot] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotSent, setForgotSent] = useState(false)
  const [captcha] = useState(generateCaptcha)
  const [captchaVal, setCaptchaVal] = useState('')
  const [quote] = useState(getQuoteOfDay)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    // Captcha validation
    if (parseInt(captchaVal) !== captcha.answer) {
      setError('Captcha incorrect — please try again.')
      setCaptchaVal('')
      return
    }
    setLoading(true); setError('')
    try {
      const res = await api.post('/auth/login', { email, password })
      setAuth(res.data.user, res.data.access_token, res.data.refresh_token)
      navigate('/')
    } catch (err: any) {
      const msg = err?.response?.data?.detail
      setError(msg ?? 'Invalid email or password. Please try again.')
    } finally { setLoading(false) }
  }

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/auth/forgot-password', { email: forgotEmail || email })
      setForgotSent(true)   // always succeeds (server never reveals if email exists)
    } catch {
      // Even on a network error, show the same neutral confirmation —
      // never leak whether the address is registered.
      setForgotSent(true)
    }
  }

  return (
    <div className="min-h-screen flex bg-login-gradient">

      {/* ── Left brand panel ─────────────────────────────────────── */}
      <div className="hidden lg:flex flex-col justify-between w-[460px] shrink-0 px-14 py-16 relative overflow-hidden">

        {/* Background decoration — subtle purple radial */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 120% 80% at -10% 110%, rgba(146,39,142,0.25) 0%, transparent 60%)' }} />

        {/* Logo top-left */}
        <FluidGoLogo size="md" />

        {/* Hero text */}
        <div className="relative z-10">
          {/* WEPSol brand line */}
          <div className="flex items-center gap-2 mb-8">
            <img src="/icon-192.png" alt="" className="w-5 h-5 opacity-50 rounded" />
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: '#F0115E' }}>
              WEP Solutions · Enterprise Platform
            </span>
          </div>

          <h1 className="font-display font-black text-white leading-[1.05] mb-6"
            style={{ fontSize: '3rem' }}>
            Challenge<br />the Norm.<br />
            <span style={{ color: '#F0115E' }}>Elevate</span>{' '}
            <span style={{ color: '#92278E' }}>Sales.</span>
          </h1>

          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.50)' }}>
            AI-powered daily sales reporting — private, on-premise, real-time.
          </p>
        </div>

        {/* Feature list */}
        <div className="space-y-3 relative z-10">
          {[
            { dot: '#4AAB29', text: 'Local AI — zero data leaves your servers' },
            { dot: '#F0115E', text: 'BANT, rigor & deal health scoring' },
            { dot: '#0EA5E9', text: 'Multi-BU · Multi-Role · Gamified' },
          ].map(f => (
            <div key={f.text} className="flex items-center gap-3 text-sm"
              style={{ color: 'rgba(255,255,255,0.55)' }}>
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: f.dot }} />
              <span>{f.text}</span>
            </div>
          ))}
        </div>

        {/* Quote of the day — same for everyone, changes daily */}
        <div className="relative z-10 border-l-2 pl-4 py-1" style={{ borderColor: '#F0115E' }}>
          <p className="text-sm italic leading-relaxed" style={{ color: 'rgba(255,255,255,0.75)' }}>
            "{quote.text}"
          </p>
          <p className="text-[11px] font-semibold uppercase tracking-wider mt-2" style={{ color: '#F0115E' }}>
            — {quote.author}
          </p>
        </div>

        {/* Footer */}
        <div className="flex flex-col gap-2 relative z-10">
          <img src="/wepsol-logo.png" alt="wepsol — elevate work"
            className="h-7 w-auto opacity-70" style={{ maxWidth: 160 }} />
          <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.25)' }}>
            WEP Solutions Ltd · Internal Confidential · All rights reserved 2026
          </p>
        </div>
      </div>

      {/* ── Right login panel ─────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-6 relative">

        {/* Subtle top-right radial */}
        <div className="absolute top-0 right-0 w-96 h-96 pointer-events-none"
          style={{ background: 'radial-gradient(circle at 80% 20%, rgba(240,17,94,0.08) 0%, transparent 60%)' }} />

        <div className="w-full max-w-[420px] relative z-10">

          {/* Mobile logo */}
          <div className="flex lg:hidden justify-center mb-10">
            <FluidGoLogo size="md" />
          </div>

          {/* Hero illustration — above the login card, as requested */}
          <div className="hidden lg:block mb-6 px-4 opacity-90">
            <AscentIllustration />
          </div>

          {/* Form card */}
          <div className="rounded-3xl p-8"
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.11)',
              backdropFilter: 'blur(20px)',
              boxShadow: '0 24px 64px rgba(0,0,0,0.3)'
            }}>

            <div className="mb-8">
              <h2 className="font-display font-bold text-white text-[1.6rem] leading-tight mb-1">
                Welcome back
              </h2>
              <p className="text-sm" style={{ color: 'rgba(255,255,255,0.42)' }}>
                Sign in to your WEP Solutions account
              </p>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">

              {/* Email field */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                  style={{ color: 'rgba(255,255,255,0.45)' }}>
                  Work Email
                </label>
                <input type="email" required autoComplete="email"
                  placeholder="you@fluidpro.in"
                  value={email} onChange={e => setEmail(e.target.value)}
                  className="w-full rounded-xl px-4 py-3.5 text-sm outline-none transition-all"
                  style={{
                    background: 'rgba(255,255,255,0.08)',
                    border: '1.5px solid rgba(255,255,255,0.13)',
                    color: '#fff',
                  }}
                  onFocus={e => { e.target.style.borderColor = '#F0115E'; e.target.style.background = 'rgba(240,17,94,0.06)' }}
                  onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.13)'; e.target.style.background = 'rgba(255,255,255,0.08)' }}
                />
              </div>

              {/* Password field with show/hide eye */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                  style={{ color: 'rgba(255,255,255,0.45)' }}>
                  Password
                </label>
                <div className="relative">
                  <input type={showPw ? 'text' : 'password'} required autoComplete="current-password"
                    placeholder="••••••••"
                    value={password} onChange={e => setPassword(e.target.value)}
                    className="w-full rounded-xl px-4 py-3.5 pr-12 text-sm outline-none transition-all"
                    style={{
                      background: 'rgba(255,255,255,0.08)',
                      border: '1.5px solid rgba(255,255,255,0.13)',
                      color: '#fff',
                    }}
                    onFocus={e => { e.target.style.borderColor = '#F0115E'; e.target.style.background = 'rgba(240,17,94,0.06)' }}
                    onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.13)'; e.target.style.background = 'rgba(255,255,255,0.08)' }}
                  />
                  <button type="button" tabIndex={-1} onClick={() => setShowPw(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-lg opacity-50 hover:opacity-80 transition-opacity"
                    style={{ color: 'white' }}>
                    {showPw ? '🙈' : '👁️'}
                  </button>
                </div>
                <div className="flex justify-end mt-1.5">
                  <button type="button" onClick={() => setShowForgot(v => !v)}
                    className="text-[11px] hover:underline transition-colors"
                    style={{ color: 'rgba(255,255,255,0.40)' }}>
                    Forgot password?
                  </button>
                </div>
              </div>

              {/* Forgot password panel */}
              {showForgot && (
                <div className="rounded-xl p-4 space-y-3"
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)' }}>
                  {!forgotSent ? (
                    <>
                      <p className="text-xs" style={{ color: 'rgba(255,255,255,0.55)' }}>
                        Enter your registered work email. We'll send you a secure link to reset your password.
                      </p>
                      <input type="email" placeholder="your@wepsol.com"
                        value={forgotEmail} onChange={e => setForgotEmail(e.target.value)}
                        className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                        style={{ background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff' }}
                      />
                      <button type="button" onClick={handleForgot}
                        className="text-xs font-bold px-3 py-1.5 rounded-lg"
                        style={{ background: 'rgba(240,17,94,0.30)', color: '#F0115E' }}>
                        Send Reset Link
                      </button>
                    </>
                  ) : (
                    <p className="text-xs text-emerald-400">
                      ✅ If that email is registered, a reset link is on its way. Please check your inbox (and spam). The link expires in 30 minutes.
                    </p>
                  )}
                </div>
              )}

              {/* Captcha */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider mb-2"
                  style={{ color: 'rgba(255,255,255,0.45)' }}>
                  Security Check: {captcha.question}
                </label>
                <input type="number" required placeholder="Answer"
                  value={captchaVal} onChange={e => setCaptchaVal(e.target.value)}
                  className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
                  style={{
                    background: 'rgba(255,255,255,0.08)',
                    border: '1.5px solid rgba(255,255,255,0.13)',
                    color: '#fff',
                  }}
                  onFocus={e => { e.target.style.borderColor = '#F0115E'; e.target.style.background = 'rgba(240,17,94,0.06)' }}
                  onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.13)'; e.target.style.background = 'rgba(255,255,255,0.08)' }}
                />
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 text-sm px-4 py-3 rounded-xl"
                  style={{ background: 'rgba(220,38,38,0.12)', color: '#FCA5A5', border: '1px solid rgba(220,38,38,0.22)' }}>
                  <span className="shrink-0">⚠️</span> {error}
                </div>
              )}

              {/* Submit */}
              <button type="submit" disabled={loading}
                className="w-full font-bold text-sm text-white py-4 rounded-xl transition-all disabled:opacity-50"
                style={{
                  background: loading ? 'rgba(240,17,94,0.5)' : 'linear-gradient(135deg, #F0115E 0%, #C2005A 100%)',
                  boxShadow: loading ? 'none' : '0 6px 20px rgba(240,17,94,0.40)',
                }}>
                {loading ? (
                  <span className="flex items-center justify-center gap-2.5">
                    <span className="flex gap-1">
                      {[0,1,2].map(i => (
                        <span key={i} className="w-1.5 h-1.5 rounded-full bg-white/60 animate-bounce inline-block"
                          style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </span>
                    Signing in…
                  </span>
                ) : 'Sign In →'}
              </button>
            </form>
          </div>

          {/* Caption */}
          <p className="text-center text-[11px] mt-6" style={{ color: 'rgba(255,255,255,0.22)' }}>
            WEP Solutions Ltd · Internal Platform · All data stays on-premise
          </p>
        </div>
      </div>
    </div>
  )
}
