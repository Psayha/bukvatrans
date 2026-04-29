import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const nav = [
  { to: '/', label: 'Дашборд', exact: true },
  { to: '/users', label: 'Пользователи' },
  { to: '/transcriptions', label: 'Транскрибации' },
  { to: '/transactions', label: 'Транзакции' },
  { to: '/promo', label: 'Промокоды' },
  { to: '/broadcast', label: 'Рассылка' },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-52 bg-gray-900 text-gray-100 flex flex-col flex-shrink-0">
        <div className="px-4 py-4 border-b border-gray-700">
          <span className="font-bold text-white">Littera Admin</span>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-2">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm ${
                  isActive
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-700 text-xs text-gray-500">
          <div className="truncate">{user?.first_name || user?.username || 'Admin'}</div>
          <button
            onClick={handleLogout}
            className="mt-1 text-gray-400 hover:text-white"
          >
            Выйти
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
