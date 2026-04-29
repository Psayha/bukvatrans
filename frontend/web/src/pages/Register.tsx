import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register } from '../api/auth'
import { useAuthStore } from '../stores/authStore'
import TelegramWidget from '../components/TelegramWidget'

export default function Register() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [firstName, setFirstName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Пароль должен быть не менее 8 символов')
      return
    }
    setLoading(true)
    try {
      const res = await register(email, password, firstName || undefined)
      setAuth(res)
      navigate('/app')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Ошибка при регистрации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
      <Link to="/" className="text-blue-600 font-bold text-xl mb-8">
        Littera
      </Link>
      <div className="bg-white rounded-xl border p-8 w-full max-w-sm">
        <h1 className="text-lg font-semibold mb-1">Создать аккаунт</h1>
        <p className="text-sm text-gray-500 mb-6">3 транскрипции бесплатно, без карты</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Имя (необязательно)</label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              autoFocus
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Как вас зовут?"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Минимум 8 символов"
            />
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Создание...' : 'Создать аккаунт'}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <div className="flex-1 border-t" />
          <span className="text-xs text-gray-400">или войти через</span>
          <div className="flex-1 border-t" />
        </div>

        <TelegramWidget
          onSuccess={() => navigate('/app')}
          onError={(msg) => setError(msg)}
        />

        <p className="text-xs text-gray-400 mt-4 text-center">
          Регистрируясь, вы принимаете{' '}
          <a href="/terms" className="underline">условия использования</a>{' '}
          и{' '}
          <a href="/privacy" className="underline">политику конфиденциальности</a>
        </p>

        <p className="text-center text-sm text-gray-500 mt-4">
          Уже есть аккаунт?{' '}
          <Link to="/login" className="text-blue-600 hover:underline">
            Войти
          </Link>
        </p>
      </div>
    </div>
  )
}
