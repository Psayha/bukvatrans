import axios from 'axios'
import type { TokenResponse } from './types'

const _base = axios.create({ baseURL: '/api/v1/auth' })

export const loginTelegram = (data: Record<string, string | number>) =>
  _base.post<TokenResponse>('/telegram', data).then((r) => r.data)

export const loginEmail = (email: string, password: string) =>
  _base.post<TokenResponse>('/login', { email, password }).then((r) => r.data)

export const register = (email: string, password: string, first_name?: string) =>
  _base.post<TokenResponse>('/register', { email, password, first_name }).then((r) => r.data)

export const getPublicConfig = () =>
  _base.get<{ bot_username: string }>('/config').then((r) => r.data)
