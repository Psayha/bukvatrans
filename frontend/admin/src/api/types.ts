export interface AuthUser {
  id: number
  first_name: string | null
  username: string | null
  email: string | null
  is_admin: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: AuthUser
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface AdminStats {
  users: {
    total: number
    banned: number
    new_24h: number
    new_7d: number
    new_30d: number
    active_subscribers: number
  }
  transcriptions: {
    done_24h: number
    failed_24h: number
    hours_24h: number
    done_7d: number
    hours_7d: number
  }
  revenue: {
    count_24h: number
    sum_24h: number
    count_7d: number
    sum_7d: number
    count_30d: number
    sum_30d: number
  }
}

export interface ChartPoint {
  date: string
  count: number
  amount?: number
}

export interface AdminUser {
  id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
  balance_seconds: number
  free_uses_left: number
  is_banned: boolean
  is_admin: boolean
  has_active_subscription: boolean
  subscription_plan: string | null
  subscription_expires_at: string | null
  created_at: string
  last_seen_at: string | null
}

export interface AdminUserDetail extends AdminUser {
  consent_at: string | null
  referrer_id: number | null
  transcriptions_count: number
  total_seconds_transcribed: number
  total_spent_rub: number
  subscriptions: {
    id: number
    plan: string
    status: string
    started_at: string
    expires_at: string
  }[]
  recent_transcriptions: {
    id: string
    status: string
    source_type: string
    file_name: string | null
    duration_seconds: number | null
    seconds_charged: number
    is_free: boolean
    created_at: string
  }[]
  recent_transactions: {
    id: string
    type: string
    amount_rub: number | null
    seconds_added: number | null
    status: string
    created_at: string
  }[]
}

export interface AdminTranscription {
  id: string
  user_id: number
  user_display: string
  status: string
  source_type: string
  file_name: string | null
  file_size_bytes: number | null
  duration_seconds: number | null
  seconds_charged: number
  is_free: boolean
  language: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
  result_text?: string
  summary_text?: string
}

export interface AdminTransaction {
  id: string
  user_id: number
  user_display: string
  type: string
  amount_rub: number | null
  seconds_added: number | null
  status: string
  yukassa_id: string | null
  description: string | null
  created_at: string
}

export interface PromoCode {
  id: number
  code: string
  type: string
  value: number
  max_uses: number | null
  used_count: number
  expires_at: string | null
  is_active: boolean
  created_at: string
}
