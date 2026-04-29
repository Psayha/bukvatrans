import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createPromoCode, listPromoCodes, patchPromoCode } from '../api/admin'
import type { PromoCode } from '../api/types'
import Pagination from '../components/Pagination'

export default function PromoCodes() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    code: '',
    type: 'free_seconds',
    value: '',
    max_uses: '',
    expires_at: '',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['admin-promo', page],
    queryFn: () => listPromoCodes(page),
  })

  const create = useMutation({
    mutationFn: () =>
      createPromoCode({
        code: form.code,
        type: form.type,
        value: parseInt(form.value),
        max_uses: form.max_uses ? parseInt(form.max_uses) : undefined,
        expires_at: form.expires_at || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-promo'] })
      setShowForm(false)
      setForm({ code: '', type: 'free_seconds', value: '', max_uses: '', expires_at: '' })
    },
  })

  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      patchPromoCode(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-promo'] }),
  })

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Промокоды</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          + Создать
        </button>
      </div>

      {showForm && (
        <div className="bg-white border rounded p-4 mb-4 space-y-3">
          <h2 className="text-sm font-semibold">Новый промокод</h2>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="КОД (например PROMO2025)"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
              className="border rounded px-2 py-1.5 text-sm"
            />
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="border rounded px-2 py-1.5 text-sm"
            >
              <option value="free_seconds">free_seconds</option>
            </select>
            <input
              placeholder="Значение (секунды)"
              type="number"
              value={form.value}
              onChange={(e) => setForm({ ...form, value: e.target.value })}
              className="border rounded px-2 py-1.5 text-sm"
            />
            <input
              placeholder="Макс. использований (пусто = ∞)"
              type="number"
              value={form.max_uses}
              onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
              className="border rounded px-2 py-1.5 text-sm"
            />
            <input
              type="datetime-local"
              value={form.expires_at}
              onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
              className="border rounded px-2 py-1.5 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => create.mutate()}
              disabled={!form.code || !form.value || create.isPending}
              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
            >
              Создать
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 border rounded text-sm hover:bg-gray-50"
            >
              Отмена
            </button>
          </div>
          {create.isError && (
            <div className="text-red-600 text-sm">
              {(create.error as any)?.response?.data?.detail || 'Ошибка'}
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="text-gray-500 text-sm">Загрузка...</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 text-left text-xs text-gray-500 uppercase">
                  <th className="px-3 py-2">Код</th>
                  <th className="px-3 py-2">Тип</th>
                  <th className="px-3 py-2">Значение</th>
                  <th className="px-3 py-2">Использован</th>
                  <th className="px-3 py-2">Истекает</th>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((p: PromoCode) => (
                  <tr key={p.id} className="border-b">
                    <td className="px-3 py-2 font-mono font-semibold">{p.code}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{p.type}</td>
                    <td className="px-3 py-2">
                      {p.type === 'free_seconds'
                        ? `${Math.round(p.value / 3600)}ч (${p.value}с)`
                        : p.value}
                    </td>
                    <td className="px-3 py-2">
                      {p.used_count}
                      {p.max_uses ? ` / ${p.max_uses}` : ''}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {p.expires_at
                        ? new Date(p.expires_at).toLocaleDateString('ru-RU')
                        : '∞'}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs ${
                          p.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-400'
                        }`}
                      >
                        {p.is_active ? 'Активен' : 'Выкл'}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => toggle.mutate({ id: p.id, is_active: !p.is_active })}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        {p.is_active ? 'Выкл' : 'Вкл'}
                      </button>
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
