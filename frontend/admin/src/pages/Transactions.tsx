import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listTransactions } from '../api/admin'
import type { AdminTransaction } from '../api/types'
import Pagination from '../components/Pagination'

export default function Transactions() {
  const [page, setPage] = useState(1)
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['admin-transactions', page, type, status],
    queryFn: () => listTransactions({ page, per_page: 50, type: type || undefined, status: status || undefined }),
  })

  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold mb-4">Транзакции</h1>

      <div className="flex gap-3 mb-4">
        <select
          value={type}
          onChange={(e) => { setType(e.target.value); setPage(1) }}
          className="border rounded px-2 py-1.5 text-sm"
        >
          <option value="">Все типы</option>
          <option value="subscription">subscription</option>
          <option value="topup">topup</option>
          <option value="refund">refund</option>
          <option value="referral_bonus">referral_bonus</option>
        </select>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1) }}
          className="border rounded px-2 py-1.5 text-sm"
        >
          <option value="">Все статусы</option>
          <option value="success">success</option>
          <option value="pending">pending</option>
          <option value="failed">failed</option>
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
                  <th className="px-3 py-2">Пользователь</th>
                  <th className="px-3 py-2">Тип</th>
                  <th className="px-3 py-2">Сумма</th>
                  <th className="px-3 py-2">Секунды</th>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2">Дата</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((t: AdminTransaction) => (
                  <tr key={t.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">
                      {t.id.slice(0, 8)}…
                    </td>
                    <td className="px-3 py-2 text-xs">{t.user_display}</td>
                    <td className="px-3 py-2 text-xs text-gray-600">{t.type}</td>
                    <td className="px-3 py-2 font-medium">
                      {t.amount_rub != null ? `${t.amount_rub}₽` : '—'}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {t.seconds_added != null ? `+${t.seconds_added}с` : '—'}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs ${
                          t.status === 'success'
                            ? 'bg-green-100 text-green-700'
                            : t.status === 'failed'
                            ? 'bg-red-100 text-red-600'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-400">
                      {new Date(t.created_at).toLocaleDateString('ru-RU')}
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
