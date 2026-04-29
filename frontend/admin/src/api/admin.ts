import { api } from './client'
import type {
  AdminStats,
  AdminTransaction,
  AdminTranscription,
  AdminUser,
  AdminUserDetail,
  ChartPoint,
  Paginated,
  PromoCode,
} from './types'

// ── Stats ──────────────────────────────────────────────────────────────────

export const getStats = () =>
  api.get<AdminStats>('/admin/stats').then((r) => r.data)

export const getRevenueChart = (days = 30) =>
  api.get<{ data: ChartPoint[] }>(`/admin/stats/revenue?days=${days}`).then((r) => r.data)

export const getUsersChart = (days = 30) =>
  api.get<{ data: ChartPoint[] }>(`/admin/stats/users-growth?days=${days}`).then((r) => r.data)

// ── Users ──────────────────────────────────────────────────────────────────

export interface UserListParams {
  page?: number
  per_page?: number
  q?: string
  banned?: boolean | null
  has_subscription?: boolean | null
}

export const listUsers = (params: UserListParams = {}) => {
  const p = new URLSearchParams()
  if (params.page) p.set('page', String(params.page))
  if (params.per_page) p.set('per_page', String(params.per_page))
  if (params.q) p.set('q', params.q)
  if (params.banned != null) p.set('banned', String(params.banned))
  if (params.has_subscription != null)
    p.set('has_subscription', String(params.has_subscription))
  return api.get<Paginated<AdminUser>>(`/admin/users?${p}`).then((r) => r.data)
}

export const getUser = (id: number) =>
  api.get<AdminUserDetail>(`/admin/users/${id}`).then((r) => r.data)

export const patchUser = (
  id: number,
  body: { is_banned?: boolean; is_admin?: boolean; add_balance_seconds?: number },
) => api.patch<AdminUser>(`/admin/users/${id}`, body).then((r) => r.data)

// ── Transcriptions ─────────────────────────────────────────────────────────

export interface TranscriptionListParams {
  page?: number
  per_page?: number
  status?: string
  user_id?: number
}

export const listTranscriptions = (params: TranscriptionListParams = {}) => {
  const p = new URLSearchParams()
  if (params.page) p.set('page', String(params.page))
  if (params.per_page) p.set('per_page', String(params.per_page))
  if (params.status && params.status !== 'all') p.set('status', params.status)
  if (params.user_id) p.set('user_id', String(params.user_id))
  return api
    .get<Paginated<AdminTranscription>>(`/admin/transcriptions?${p}`)
    .then((r) => r.data)
}

export const getTranscription = (id: string) =>
  api.get<AdminTranscription>(`/admin/transcriptions/${id}`).then((r) => r.data)

// ── Transactions ───────────────────────────────────────────────────────────

export interface TransactionListParams {
  page?: number
  per_page?: number
  type?: string
  status?: string
  user_id?: number
}

export const listTransactions = (params: TransactionListParams = {}) => {
  const p = new URLSearchParams()
  if (params.page) p.set('page', String(params.page))
  if (params.per_page) p.set('per_page', String(params.per_page))
  if (params.type) p.set('type', params.type)
  if (params.status) p.set('status', params.status)
  if (params.user_id) p.set('user_id', String(params.user_id))
  return api
    .get<Paginated<AdminTransaction>>(`/admin/transactions?${p}`)
    .then((r) => r.data)
}

// ── Promo codes ────────────────────────────────────────────────────────────

export const listPromoCodes = (page = 1) =>
  api.get<Paginated<PromoCode>>(`/admin/promo-codes?page=${page}`).then((r) => r.data)

export const createPromoCode = (body: {
  code: string
  type: string
  value: number
  max_uses?: number
  expires_at?: string
}) => api.post<PromoCode>('/admin/promo-codes', body).then((r) => r.data)

export const patchPromoCode = (id: number, body: { is_active?: boolean; max_uses?: number }) =>
  api.patch<PromoCode>(`/admin/promo-codes/${id}`, body).then((r) => r.data)

// ── Broadcast ─────────────────────────────────────────────────────────────

export const previewBroadcast = (text: string, target: string) =>
  api
    .post<{ target: string; estimated_recipients: number }>('/admin/broadcast/preview', {
      text,
      target,
    })
    .then((r) => r.data)

export const sendBroadcast = (text: string, target: string) =>
  api.post<{ ok: boolean; message: string }>('/admin/broadcast', { text, target }).then((r) => r.data)
