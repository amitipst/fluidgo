import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { toast } from '@/store/toastStore'

// Auto session logoff — tunable here, nowhere else.
const IDLE_LIMIT_MS = 30 * 60 * 1000   // 30 min of no activity → logout
const WARNING_MS = 60 * 1000            // show a "still there?" warning 60s before

/** Idle-timeout auto-logout. Any mouse/keyboard/touch/scroll activity resets
 * the clock — EXCEPT once the warning banner is already showing, where only
 * an explicit "Stay logged in" click extends the session (not incidental
 * activity), so a stray cursor twitch from another app doesn't silently
 * keep an unattended, logged-in session open. */
export function useIdleLogout() {
  const navigate = useNavigate()
  const { clearAuth, accessToken } = useAuthStore()
  const [showWarning, setShowWarning] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(Math.round(WARNING_MS / 1000))
  const idleTimer = useRef<ReturnType<typeof setTimeout>>()
  const warnTimer = useRef<ReturnType<typeof setTimeout>>()
  const countdownInterval = useRef<ReturnType<typeof setInterval>>()

  function clearAllTimers() {
    if (idleTimer.current) clearTimeout(idleTimer.current)
    if (warnTimer.current) clearTimeout(warnTimer.current)
    if (countdownInterval.current) clearInterval(countdownInterval.current)
  }

  function doLogout() {
    clearAllTimers()
    clearAuth()
    toast.info("You've been logged out after 30 minutes of inactivity.")
    navigate('/login', { replace: true })
  }

  function resetTimers() {
    setShowWarning(false)
    clearAllTimers()
    if (!accessToken) return
    warnTimer.current = setTimeout(() => {
      setShowWarning(true)
      setSecondsLeft(Math.round(WARNING_MS / 1000))
      countdownInterval.current = setInterval(() => {
        setSecondsLeft(s => {
          if (s <= 1) { doLogout(); return 0 }
          return s - 1
        })
      }, 1000)
    }, IDLE_LIMIT_MS - WARNING_MS)
    idleTimer.current = setTimeout(doLogout, IDLE_LIMIT_MS)
  }

  useEffect(() => {
    if (!accessToken) { clearAllTimers(); return }
    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']
    const handler = () => { if (!showWarning) resetTimers() }
    events.forEach(e => window.addEventListener(e, handler, { passive: true }))
    resetTimers()
    return () => {
      events.forEach(e => window.removeEventListener(e, handler))
      clearAllTimers()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken])

  return { showWarning, secondsLeft, stayLoggedIn: resetTimers, logoutNow: doLogout }
}
