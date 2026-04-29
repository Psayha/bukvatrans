import { useEffect, useRef, useState } from 'react'
import { getAuthConfig, loginTelegram } from '../api/auth'
import { useAuthStore } from '../stores/authStore'

interface Props {
  onSuccess: () => void
  onError?: (msg: string) => void
}

export default function TelegramWidget({ onSuccess, onError }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [botUsername, setBotUsername] = useState('')
  const setAuth = useAuthStore((s) => s.setAuth)

  useEffect(() => {
    getAuthConfig().then((c) => setBotUsername(c.bot_username)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!ref.current || !botUsername) return

    ;(window as unknown as Record<string, unknown>)['onTelegramLogin'] = async (
      user: Record<string, unknown>
    ) => {
      try {
        const res = await loginTelegram(user)
        setAuth(res)
        onSuccess()
      } catch {
        onError?.('Ошибка входа через Telegram')
      }
    }

    ref.current.innerHTML = ''
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.dataset.telegramLogin = botUsername
    script.dataset.size = 'large'
    script.dataset.onauth = 'onTelegramLogin(user)'
    script.dataset.requestAccess = 'write'
    script.async = true
    ref.current.appendChild(script)

    return () => {
      delete (window as unknown as Record<string, unknown>)['onTelegramLogin']
    }
  }, [botUsername, onSuccess, onError, setAuth])

  if (!botUsername) return null
  return <div ref={ref} className="flex justify-center" />
}
