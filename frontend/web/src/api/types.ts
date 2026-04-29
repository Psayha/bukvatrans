export interface User {
  id: number
  first_name: string | null
  username: string | null
  email: string | null
  is_admin: boolean
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export type TranscriptionStatus = 'pending' | 'processing' | 'done' | 'failed'

export interface Transcription {
  id: string
  status: TranscriptionStatus
  source_type: string
  file_name: string | null
  duration_seconds: number | null
  seconds_charged: number | null
  is_free: boolean
  language: string
  result_text: string | null
  summary_text: string | null
  error_message: string | null
  s3_key: string | null
  created_at: string
  completed_at: string | null
}

export interface PaginatedTranscriptions {
  items: Transcription[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ActiveSubscription {
  plan: string
  label: string
  is_unlimited: boolean
  expires_at: string
  days_left: number
}

export interface GamificationInfo {
  level_name: string
  level_emoji: string
  progress_ratio: number
  current_threshold: number
  next_threshold: number | null
  saved_time: string
}

export interface Profile {
  id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
  email_verified: boolean
  balance_seconds: number
  free_uses_left: number
  free_uses_per_month: number
  active_subscription: ActiveSubscription | null
  gamification: GamificationInfo
  referral_link: string
}

export interface Plan {
  key: string
  label: string
  price_rub: number
  period_days: number
  recommended: boolean
}

export interface TopupOption {
  key: string
  price_rub: number
  seconds: number
  hours: number
}

export interface PlansResponse {
  plans: Plan[]
  topups: TopupOption[]
}
