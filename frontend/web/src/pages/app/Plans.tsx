import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPlans, buySubscription } from '../../api/payments'

export default function Plans() {
  const { data, isLoading } = useQuery({ queryKey: ['plans'], queryFn: getPlans, staleTime: 60_000 })
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState('')

  async function handleBuy(key: string) {
    setError('')
    setLoading(key)
    try {
      const returnUrl = `${window.location.origin}/app/profile`
      const { confirmation_url } = await buySubscription(key, returnUrl)
      window.location.href = confirmation_url
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Ошибка при создании платежа')
    } finally {
      setLoading(null)
    }
  }

  if (isLoading) return <div className="text-gray-500 text-sm">Загрузка...</div>

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold mb-2">Тарифы и пополнение</h1>
      <p className="text-sm text-gray-500 mb-8">
        Безлимитная транскрибация — ни минутных лимитов, ни очередей
      </p>

      {error && <p className="mb-4 text-red-500 text-sm">{error}</p>}

      {/* Subscription plans */}
      <h2 className="font-semibold mb-4">Подписка (безлимит)</h2>
      <div className="grid sm:grid-cols-3 gap-4 mb-10">
        {data?.plans.map((p) => (
          <div
            key={p.key}
            className={`rounded-xl border p-5 flex flex-col ${
              p.recommended ? 'border-blue-500 shadow-md' : ''
            }`}
          >
            {p.recommended && (
              <span className="text-xs font-semibold text-blue-600 mb-2 uppercase tracking-wide">
                Популярный
              </span>
            )}
            <p className="text-2xl font-bold">{p.price_rub} ₽</p>
            <p className="text-sm text-gray-500 mb-3">{p.label}</p>
            <p className="text-sm flex-1">Безлимитная транскрибация</p>
            <button
              onClick={() => handleBuy(p.key)}
              disabled={loading === p.key}
              className={`mt-4 w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                p.recommended
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'border hover:bg-gray-50'
              } disabled:opacity-50`}
            >
              {loading === p.key ? 'Переход...' : 'Оплатить'}
            </button>
          </div>
        ))}
      </div>

      {/* Topup options */}
      {data?.topups && data.topups.length > 0 && (
        <>
          <h2 className="font-semibold mb-4">Пополнение баланса (по минутам)</h2>
          <div className="grid sm:grid-cols-3 gap-4">
            {data.topups.map((t) => (
              <div key={t.key} className="rounded-xl border p-5">
                <p className="text-xl font-bold">{t.price_rub} ₽</p>
                <p className="text-sm text-gray-500 mb-4">{t.hours} часов</p>
                <button
                  onClick={async () => {
                    setError('')
                    setLoading(t.key)
                    try {
                      const { buyTopup } = await import('../../api/payments')
                      const { confirmation_url } = await buyTopup(
                        t.key,
                        `${window.location.origin}/app/profile`
                      )
                      window.location.href = confirmation_url
                    } catch (err: unknown) {
                      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                      setError(msg || 'Ошибка')
                    } finally {
                      setLoading(null)
                    }
                  }}
                  disabled={loading === t.key}
                  className="w-full py-2 border rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  {loading === t.key ? 'Переход...' : 'Пополнить'}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
