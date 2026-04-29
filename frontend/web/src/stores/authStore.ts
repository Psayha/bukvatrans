import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthResponse, User } from '../api/types'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  setAuth: (res: AuthResponse) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      setAuth(res: AuthResponse) {
        localStorage.setItem('access_token', res.access_token)
        localStorage.setItem('refresh_token', res.refresh_token)
        set({ user: res.user, isAuthenticated: true })
      },

      logout() {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, isAuthenticated: false })
      },
    }),
    {
      name: 'littera-auth',
      partialize: (s) => ({ user: s.user, isAuthenticated: s.isAuthenticated }),
    }
  )
)
