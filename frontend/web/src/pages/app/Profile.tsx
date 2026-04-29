import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getProfile, applyPromo } from '../../api/profile'

function fmtBalance(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h} ч ${m} мин` : `${m} мин`
}

export default function Profile() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['profile'], queryFn: getProfile })
  const [promo, setPromo] = useState('')
  const [promoMsg, setPromoMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const applyMutation = useMutation({
    mutationFn: () => applyPromo(promo.trim().toUpperCase()),
    onSuccess: (res) => {
      setPromoMsg({ ok: true, text: `+${Math.round(res.seconds_added / 3600)} ч начислено!` })
      setPromo('')
      qc.invalidateQueries({ queryKey: ['profile'] })
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Неверный промокод'
      setPromoMsg({ ok: false, text: msg })
    },
  })

  if (isLoading || !data) {
    return <div className="text-gray-500 text-sm">Загрузка...</div>
  }

  return (
    <div className="max-w-xl space-y-5">
      <h1 className="text-xl font-semibold">Профиль</h1>

      {/* User card */}
      <div className="bg-white border rounded-lg p-5 space-y-2">
        <p className="font-medium">
          {data.first_name || data.username || 'Пользователь'}
          {data.username && <span className="text-gray-400 font-normal ml-1">@{data.username}</span>}
        </p>
        {data.email && (
          <p className="text-sm text-gray-500">
            {data.email}
            {!data.email_verified && (
              <span className="ml-2 text-xs text-yellow-600 bg-yellow-50 px-1.5 py-0.5 rounded">
                не подтверждён
              </span>
            )}
          </p>
        )}
        <p className="text-xs text-gray-400">
          {data.gamification.level_emoji} {data.gamification.level_name} ·{' '}
          {data.gamification.saved_time} сэкономлено
        </p>
      </div>

      {/* Balance / subscription */}
      <div className="bg-white border rounded-lg p-5">
        <h2 className="font-semibold text-sm mb-3">Баланс и подписка</h2>
        {data.active_subscription ? (
          <div className="space-y-1">
            <p className="text-sm font-medium text-green-700">
              ✓ {data.active_subscription.label}
            </p>
            <p className="text-xs text-gray-500">
              Действует ещё {data.active_subscription.days_left} дн.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            <p className="text-sm">
              Баланс: <strong>{fmtBalance(data.balance_seconds)}</strong>
            </p>
            <p className="text-xs text-gray-500">
              Бесплатных использований: {data.free_uses_left} из {data.free_uses_per_month}
            </p>
          </div>
        )}
        <Link
          to="/app/plans"
          className="mt-4 inline-block px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          Пополнить / подписка →
        </Link>
      </div>

      {/* Gamification progress */}
      <div className="bg-white border rounded-lg p-5">
        <h2 className="font-semibold text-sm mb-3">Уровень</h2>
        <div className="flex items-center gap-3">
          <span className="text-2xl">{data.gamification.level_emoji}</span>
          <div className="flex-1">
            <p className="text-sm font-medium">{data.gamification.level_name}</p>
            <div className="mt-1.5 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${Math.round(data.gamification.progress_ratio * 100)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Promo code */}
      <div className="bg-white border rounded-lg p-5">
        <h2 className="font-semibold text-sm mb-3">Промокод</h2>
        <form
          onSubmit={(e) => { e.preventDefault(); applyMutation.mutate() }}
          className="flex gap-2"
        >
          <input
            value={promo}
            onChange={(e) => { setPromo(e.target.value); setPromoMsg(null) }}
            placeholder="ПРОМОКОД"
            className="flex-1 border rounded px-3 py-1.5 text-sm font-mono uppercase focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={!promo.trim() || applyMutation.isPending}
            className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
          >
            Применить
          </button>
        </form>
        {promoMsg && (
          <p className={`mt-2 text-sm ${promoMsg.ok ? 'text-green-600' : 'text-red-500'}`}>
            {promoMsg.text}
          </p>
        )}
      </div>

      {/* Referral */}
      <div className="bg-white border rounded-lg p-5">
        <h2 className="font-semibold text-sm mb-2">Реферальная ссылка</h2>
        <p className="text-xs text-gray-500 mb-2">
          Поделитесь ссылкой — друг получит 3 бесплатные транскрипции через бот
        </p>
        <div className="flex gap-2">
          <input
            readOnly
            value={data.referral_link}
            className="flex-1 border rounded px-3 py-1.5 text-xs font-mono bg-gray-50"
          />
          <button
            onClick={() => navigator.clipboard.writeText(data.referral_link)}
            className="px-3 py-1.5 border rounded text-xs hover:bg-gray-50"
          >
            Копировать
          </button>
        </div>
      </div>
    </div>
  )
}
