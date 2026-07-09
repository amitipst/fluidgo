import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// v3 role system — all 10 roles
export type Role =
  | 'rep'
  | 'inside_sales'
  | 'pre_sales'
  | 'manager'
  | 'bu_head'
  | 'business_head'
  | 'hr'
  | 'finance'
  | 'ceo'
  | 'super_admin'

export type OrgRoleKey =
  | 'sales' | 'presales' | 'manager' | 'bu_head'
  | 'practice_head' | 'hr' | 'finance' | 'admin' | 'super_admin'
  | null

export interface AuthUser {
  id:           string
  name:         string
  email:        string
  role:         Role
  bu:           string       // legacy
  region?:      string       // India - North | India - West | etc.
  business?:    string
  manager_id?:  string | null
  org_role_key?: OrgRoleKey
  has_direct_reports?: boolean   // dual-hat support — see backend permission_service.py
}

interface AuthState {
  user:         AuthUser | null
  accessToken:  string | null
  refreshToken: string | null
  setAuth:  (user: AuthUser, access: string, refresh: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user:         null,
      accessToken:  null,
      refreshToken: null,
      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken }),
      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: 'fluidgo-auth',
      // Persist user profile + refresh token (access token is short-lived)
      partialize: (s) => ({ user: s.user, refreshToken: s.refreshToken }),
    }
  )
)
