import api from './client'
import type { Profile } from './types'

export async function getProfile(): Promise<Profile> {
  const { data } = await api.get<Profile>('/profile')
  return data
}

export async function applyPromo(code: string): Promise<{
  ok: boolean
  seconds_added: number
  new_balance_seconds: number
}> {
  const { data } = await api.post('/promo', { code })
  return data
}
