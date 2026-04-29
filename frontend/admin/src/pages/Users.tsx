import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listUsers } from '../api/admin'
import type { AdminUser } from '../api/types'
import Pagination from '../components/Pagination'

function fmtBalance(seconds: number) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
        ok ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
      }`}
    >
      {label}
    </span>
  )
}

export default function Users() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [banned, setBanned] = useState<boolean | null>(null)
  const [hasSub, setHasSub] = useState<boolean | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, debouncedQ, banned, hasSub],
    queryFn: () =>
      listUsers({ page, per_page: 50, q: debouncedQ, banned, has_subscription: hasSub }),
  })

  function handleSearch(v: string) {
    setQ(v)
    clearTimeout((window as any)._userSearchTimer)
    ;(window as any)._userSearchTimer = setTimeout(() => {
      setDebouncedQ(v)
      setPage(1)
    }, 400)
  }

  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold mb-4">Пользователи</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          value={q}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Поиск по имени / username / ID"
          className="border rounded px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={banned === null ? '' : String(banned)}
          onChange={(e) => {
            setBanned(e.target.value === '' ? null : e.target.value === 'true')
            setPage(1)
          }}
          className="border rounded px-2 py-1.5 text-sm"
        >
          <option value="">Все статусы</option>
          <option value="false">Активные</option>
          <option value="true">Забаненные</option>
        </select>
        <select
          value={hasSub === null ? '' : String(hasSub)}
          onChange={(e) => {
            setHasSub(e.target.value === '' ? null : e.target.value === 'true')
            setPage(1)
          }}
          className="border rounded px-2 py-1.5 text-sm"
        >
          <option value="">Все подписки</option>
          <option value="true">С подпиской</option>
          <option value="false">Без подписки</option>
        </select>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-sm">Загрузка...</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 text-left text-xs text-gray-500 uppercase">
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Имя</th>
                  <th className="px-3 py-2">Username</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Баланс</th>
                  <th className="px-3 py-2">Подписка</th>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2">Регистрация</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((u: AdminUser) => (
                  <tr
                    key={u.id}
                    onClick={() => navigate(`/users/${u.id}`)}
                    className="border-b hover:bg-blue-50 cursor-pointer"
                  >
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{u.id}</td>
                    <td className="px-3 py-2 font-medium">{u.first_name || '—'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {u.username ? `@${u.username}` : '—'}
                    </td>
                    <td className="px-3 py-2 text-gray-600">{u.email || '—'}</td>
                    <td className="px-3 py-2">{fmtBalance(u.balance_seconds)}</td>
                    <td className="px-3 py-2">
                      {u.has_active_subscription ? (
                        <Badge ok={true} label={u.subscription_plan || 'active'} />
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {u.is_banned ? (
                        <Badge ok={false} label="Бан" />
                      ) : u.is_admin ? (
                        <Badge ok={true} label="Адм" />
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-400 text-xs">
                      {new Date(u.created_at).toLocaleDateString('ru-RU')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={data?.page || 1}
            pages={data?.pages || 1}
            total={data?.total || 0}
            onPage={setPage}
          />
        </>
      )}
    </div>
  )
}
