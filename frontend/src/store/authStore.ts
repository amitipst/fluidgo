import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Role = 'rep' | 'inside_sales' | 'manager' | 'bu_head'
export type OrgRoleKey = 'sales' | 'presales' | 'manager' | 'bu_head' | 'practice_head' | 'hr' | 'admin' | 'super_admin' | null

interface AuthUser {
  id: string
  name: string
  email: string
  role: Role
  bu: string
  org_role_key?: OrgRoleKey
}

interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  setAuth: (user: AuthUser, access: string, refresh: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken }),
      clearAuth: () => set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: 'fluidgo-auth',
      partialize: (s) => ({ user: s.user, refreshToken: s.refreshToken }),
    }
  )
)
