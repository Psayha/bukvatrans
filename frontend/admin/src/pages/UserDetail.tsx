import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getUser, patchUser } from '../api/admin'

function fmtBalance(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

export default function UserDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: user, isLoading } = useQuery({
    queryKey: ['admin-user', id],
    queryFn: () => getUser(Number(id)),
    enabled: !!id,
  })

  const patch = useMutation({
    mutationFn: (body: Parameters<typeof patchUser>[1]) => patchUser(Number(id), body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-user', id] }),
  })

  const [addSeconds, setAddSeconds] = useState('')

  if (isLoading || !user)
    return <div className="p-8 text-gray-500">Загрузка...</div>

  return (
    <div className="p-6 max-w-4xl">
      <button
        onClick={() => navigate(-1)}
        className="text-sm text-blue-600 hover:underline mb-4 block"
      >
        ← Назад
      </button>

      <div className="flex items-start gap-4 mb-6">
        <div className="w-12 h-12 rounded-full bg-blue-600 text-white flex items-center justify-center text-lg font-bold">
          {(user.first_name || user.username || '?')[0].toUpperCase()}
        </div>
        <div>
          <h1 className="text-xl font-semibold">
            {user.first_name} {user.last_name}
          </h1>
          <div className="text-sm text-gray-500 space-x-3">
            {user.username && <span>@{user.username}</span>}
            <span className="font-mono">ID {user.id}</span>
            {user.email && <span>{user.email}</span>}
          </div>
          <div className="flex gap-2 mt-2">
            {user.is_banned && (
              <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Забанен</span>
            )}
            {user.is_admin && (
              <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">Админ</span>
            )}
            {user.has_active_subscription && (
              <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">
                {user.subscription_plan}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded border p-3">
          <div className="text-xs text-gray-500">Баланс</div>
          <div className="text-lg font-semibold">{fmtBalance(user.balance_seconds)}</div>
        </div>
        <div className="bg-white rounded border p-3">
          <div className="text-xs text-gray-500">Транскрибаций</div>
          <div className="text-lg font-semibold">{user.transcriptions_count}</div>
        </div>
        <div className="bg-white rounded border p-3">
          <div className="text-xs text-gray-500">Потрачено</div>
          <div className="text-lg font-semibold">{user.total_spent_rub.toFixed(0)}₽</div>
        </div>
      </div>

      {/* Actions */}
      <div className="bg-white rounded border p-4 mb-6">
        <h2 className="text-sm font-semibold mb-3">Действия</h2>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => patch.mutate({ is_banned: !user.is_banned })}
            className={`px-3 py-1.5 rounded text-sm font-medium ${
              user.is_banned
                ? 'bg-green-600 text-white hover:bg-green-700'
                : 'bg-red-600 text-white hover:bg-red-700'
            }`}
          >
            {user.is_banned ? 'Разбанить' : 'Забанить'}
          </button>
          <button
            onClick={() => patch.mutate({ is_admin: !user.is_admin })}
            className="px-3 py-1.5 rounded text-sm font-medium bg-purple-600 text-white hover:bg-purple-700"
          >
            {user.is_admin ? 'Снять права адм.' : 'Сделать адм.'}
          </button>
          <div className="flex gap-2 items-center">
            <input
              value={addSeconds}
              onChange={(e) => setAddSeconds(e.target.value)}
              placeholder="Секунды (например 3600)"
              className="border rounded px-2 py-1.5 text-sm w-48"
            />
            <button
              onClick={() => {
                const s = parseInt(addSeconds)
                if (!isNaN(s)) {
                  patch.mutate({ add_balance_seconds: s })
                  setAddSeconds('')
                }
              }}
              className="px-3 py-1.5 rounded text-sm bg-blue-600 text-white hover:bg-blue-700"
            >
              Начислить
            </button>
          </div>
        </div>
      </div>

      {/* Recent transcriptions */}
      <div className="bg-white rounded border p-4 mb-6">
        <h2 className="text-sm font-semibold mb-3">Последние транскрибации</h2>
        <table className="w-full text-xs">
          <thead className="text-gray-500 uppercase">
            <tr>
              <th className="text-left py-1">Статус</th>
              <th className="text-left py-1">Тип</th>
              <th className="text-left py-1">Файл</th>
              <th className="text-left py-1">Длит.</th>
              <th className="text-left py-1">Дата</th>
            </tr>
          </thead>
          <tbody>
            {user.recent_transcriptions.map((t) => (
              <tr key={t.id} className="border-t">
                <td className="py-1.5">
                  <span
                    className={`px-1.5 rounded ${
                      t.status === 'done'
                        ? 'bg-green-100 text-green-700'
                        : t.status === 'failed'
                        ? 'bg-red-100 text-red-600'
                        : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="py-1.5 text-gray-600">{t.source_type}</td>
                <td className="py-1.5 text-gray-600 max-w-[140px] truncate">
                  {t.file_name || '—'}
                </td>
                <td className="py-1.5">
                  {t.duration_seconds ? `${Math.round(t.duration_seconds / 60)}м` : '—'}
                </td>
                <td className="py-1.5 text-gray-400">
                  {new Date(t.created_at).toLocaleDateString('ru-RU')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent transactions */}
      <div className="bg-white rounded border p-4">
        <h2 className="text-sm font-semibold mb-3">Последние платежи</h2>
        <table className="w-full text-xs">
          <thead className="text-gray-500 uppercase">
            <tr>
              <th className="text-left py-1">Тип</th>
              <th className="text-left py-1">Сумма</th>
              <th className="text-left py-1">Статус</th>
              <th className="text-left py-1">Дата</th>
            </tr>
          </thead>
          <tbody>
            {user.recent_transactions.map((t) => (
              <tr key={t.id} className="border-t">
                <td className="py-1.5 text-gray-600">{t.type}</td>
                <td className="py-1.5">{t.amount_rub ? `${t.amount_rub}₽` : '—'}</td>
                <td className="py-1.5">
                  <span
                    className={`px-1.5 rounded ${
                      t.status === 'success'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="py-1.5 text-gray-400">
                  {new Date(t.created_at).toLocaleDateString('ru-RU')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
