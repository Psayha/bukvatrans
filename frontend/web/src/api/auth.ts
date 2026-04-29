import axios from 'axios'
import type { AuthResponse } from './types'

export async function loginEmail(email: string, password: string): Promise<AuthResponse> {
  const { data } = await axios.post<AuthResponse>('/api/v1/auth/login', { email, password })
  return data
}

export async function register(
  email: string,
  password: string,
  first_name?: string
): Promise<AuthResponse> {
  const { data } = await axios.post<AuthResponse>('/api/v1/auth/register', {
    email,
    password,
    first_name,
  })
  return data
}

export async function loginTelegram(widgetData: Record<string, unknown>): Promise<AuthResponse> {
  const { data } = await axios.post<AuthResponse>('/api/v1/auth/telegram', widgetData)
  return data
}

export async function getAuthConfig(): Promise<{ bot_username: string }> {
  const { data } = await axios.get<{ bot_username: string }>('/api/v1/auth/config')
  return data
}
