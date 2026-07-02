import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 403 && String(error.response?.data?.detail).includes('deactivated')) {
      useAuthStore.getState().clearAuth()
      window.location.href = '/login'
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      const { refreshToken, setAuth, clearAuth, user } = useAuthStore.getState()
      if (refreshToken && user) {
        try {
          const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
          setAuth(res.data.user, res.data.access_token, res.data.refresh_token)
          error.config.headers.Authorization = `Bearer ${res.data.access_token}`
          return axios(error.config)
        } catch {
          clearAuth()
          window.location.href = '/login'
        }
      } else {
        clearAuth()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
