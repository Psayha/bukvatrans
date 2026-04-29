import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useQuery } from '@tanstack/react-query'
import { getProfile } from '../api/profile'

function Balance() {
  const { data } = useQuery({ queryKey: ['profile'], queryFn: getProfile, staleTime: 30_000 })
  if (!data) return null
  const h = Math.floor(data.balance_seconds / 3600)
  const m = Math.floor((data.balance_seconds % 3600) / 60)
  const label = data.active_subscription
    ? `${data.active_subscription.label} · ${data.active_subscription.days_left} дн.`
    : `${h}ч ${m}мин`
  return (
    <Link
      to="/app/plans"
      className="text-sm text-gray-600 hover:text-blue-600 transition-colors"
      title="Баланс / подписка"
    >
      {label}
    </Link>
  )
}

const NAV = [
  { to: '/app', label: 'Транскрибировать', end: true },
  { to: '/app/list', label: 'История' },
  { to: '/app/plans', label: 'Тарифы' },
  { to: '/app/profile', label: 'Профиль' },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/app" className="text-blue-600 font-bold text-lg tracking-tight">
              Littera
            </Link>
            <nav className="hidden sm:flex gap-4">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    `text-sm transition-colors ${isActive ? 'text-blue-600 font-medium' : 'text-gray-600 hover:text-gray-900'}`
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <Balance />
            <span className="text-sm text-gray-500">{user?.first_name || user?.username}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6">{children}</main>
    </div>
  )
}
