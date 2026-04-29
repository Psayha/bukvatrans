import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthUser } from '../api/types'

interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  setAuth: (user: AuthUser, access: string, refresh: string) => void
  setTokens: (access: string, refresh: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setAuth: (user, access, refresh) =>
        set({ user, accessToken: access, refreshToken: refresh }),
      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),
      logout: () => set({ user: null, accessToken: null, refreshToken: null }),
    }),
    { name: 'littera-admin-auth' },
  ),
)
