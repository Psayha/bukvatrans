import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { loginEmail, loginTelegram, getPublicConfig } from '../api/auth'
import { useAuthStore } from '../stores/authStore'

export default function Login() {
  const { setAuth, user } = useAuthStore()
  const navigate = useNavigate()
  const tgRef = useRef<HTMLDivElement>(null)
  const [tab, setTab] = useState<'telegram' | 'email'>('telegram')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [botUsername, setBotUsername] = useState('')

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  useEffect(() => {
    getPublicConfig().then((c) => setBotUsername(c.bot_username)).catch(() => {})
  }, [])

  useEffect(() => {
    if (tab !== 'telegram' || !botUsername || !tgRef.current) return
    tgRef.current.innerHTML = ''

    ;(window as any).onTelegramAuth = async (data: Record<string, string | number>) => {
      setLoading(true)
      setError('')
      try {
        const res = await loginTelegram(data)
        if (!res.user.is_admin) {
          setError('Нет прав администратора')
          return
        }
        setAuth(res.user, res.access_token, res.refresh_token)
        navigate('/', { replace: true })
      } catch (e: any) {
        setError(e.response?.data?.detail || 'Ошибка входа')
      } finally {
        setLoading(false)
      }
    }

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', 'onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    tgRef.current.appendChild(script)

    return () => {
      delete (window as any).onTelegramAuth
    }
  }, [tab, botUsername, setAuth, navigate])

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await loginEmail(email, password)
      if (!res.user.is_admin) {
        setError('Нет прав администратора')
        return
      }
      setAuth(res.user, res.access_token, res.refresh_token)
      navigate('/', { replace: true })
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Неверные данные')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-lg shadow p-8 w-full max-w-sm">
        <h1 className="text-xl font-bold mb-6 text-center">Littera Admin</h1>

        <div className="flex border-b mb-6">
          {(['telegram', 'email'] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setError('') }}
              className={`flex-1 py-2 text-sm ${
                tab === t
                  ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                  : 'text-gray-500'
              }`}
            >
              {t === 'telegram' ? 'Telegram' : 'Email'}
            </button>
          ))}
        </div>

        {tab === 'telegram' ? (
          <div className="flex justify-center min-h-[48px]">
            {botUsername ? (
              <div ref={tgRef} />
            ) : (
              <div className="text-sm text-gray-400">Загрузка...</div>
            )}
          </div>
        ) : (
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <input
              type="password"
              placeholder="Пароль"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white rounded py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Входим...' : 'Войти'}
            </button>
          </form>
        )}

        {error && (
          <div className="mt-4 text-sm text-red-600 text-center">{error}</div>
        )}
      </div>
    </div>
  )
}
