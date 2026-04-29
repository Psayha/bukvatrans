import api from './client'
import type { PlansResponse } from './types'

export async function getPlans(): Promise<PlansResponse> {
  const { data } = await api.get<PlansResponse>('/payments/plans')
  return data
}

export async function buySubscription(
  plan_key: string,
  return_url: string
): Promise<{ confirmation_url: string; payment_id: string }> {
  const { data } = await api.post('/payments/subscription', { plan_key, return_url })
  return data
}

export async function buyTopup(
  topup_key: string,
  return_url: string
): Promise<{ confirmation_url: string; payment_id: string }> {
  const { data } = await api.post('/payments/topup', { topup_key, return_url })
  return data
}
