import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

const api = axios.create({ baseURL: '/api' })

// ── Request: attach access token ──────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Track if a refresh is already in-flight to prevent race conditions
let _refreshing: Promise<string> | null = null

// ── Response: handle 401 → try refresh → retry once ──────────────────────
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    const { refreshToken, setAuth, clearAuth, user } = useAuthStore.getState()

    // Only attempt refresh on 401, and only once per original request
    if (error.response?.status === 401 && !original._retried && refreshToken && user) {
      original._retried = true

      // If another request is already refreshing, wait for it
      if (!_refreshing) {
        _refreshing = axios
          .post('/api/auth/refresh', { refresh_token: refreshToken })
          .then(res => {
            setAuth(res.data.user, res.data.access_token, res.data.refresh_token)
            return res.data.access_token
          })
          .catch(() => {
            // Refresh itself failed → full logout
            clearAuth()
            window.location.href = '/login'
            return Promise.reject(new Error('Session expired'))
          })
          .finally(() => { _refreshing = null })
      }

      try {
        const newToken = await _refreshing!
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      } catch {
        return Promise.reject(error)
      }
    }

    // 403 is an authorisation issue (not auth) — don't redirect, let component handle it
    return Promise.reject(error)
  }
)

export default api
