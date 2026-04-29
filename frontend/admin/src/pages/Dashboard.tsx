import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid,
} from 'recharts'
import { getStats, getRevenueChart, getUsersChart } from '../api/admin'
import StatCard from '../components/StatCard'

function fmt(n: number) {
  return n.toLocaleString('ru-RU')
}
function fmtRub(n: number) {
  return `${n.toLocaleString('ru-RU')}₽`
}

export default function Dashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: getStats,
    refetchInterval: 60_000,
  })
  const { data: revenue } = useQuery({
    queryKey: ['revenue-chart'],
    queryFn: () => getRevenueChart(30),
  })
  const { data: usersGrowth } = useQuery({
    queryKey: ['users-chart'],
    queryFn: () => getUsersChart(30),
  })

  if (isLoading || !stats) {
    return <div className="p-8 text-gray-500">Загрузка...</div>
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold">Дашборд</h1>

      {/* Row 1 — users */}
      <section>
        <h2 className="text-sm font-medium text-gray-500 mb-3">Пользователи</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Всего" value={fmt(stats.users.total)} color="blue" />
          <StatCard label="Новых 24ч" value={fmt(stats.users.new_24h)} color="green" />
          <StatCard label="Новых 7д" value={fmt(stats.users.new_7d)} color="green" />
          <StatCard label="Новых 30д" value={fmt(stats.users.new_30d)} color="green" />
          <StatCard label="Подписчики" value={fmt(stats.users.active_subscribers)} color="purple" />
          <StatCard label="Забанены" value={fmt(stats.users.banned)} color="red" />
        </div>
      </section>

      {/* Row 2 — transcriptions */}
      <section>
        <h2 className="text-sm font-medium text-gray-500 mb-3">Транскрибации</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <StatCard label="Готово 24ч" value={fmt(stats.transcriptions.done_24h)} color="blue" />
          <StatCard label="Ошибок 24ч" value={fmt(stats.transcriptions.failed_24h)} color="red" />
          <StatCard label="Часов 24ч" value={stats.transcriptions.hours_24h} color="yellow" />
          <StatCard label="Готово 7д" value={fmt(stats.transcriptions.done_7d)} color="blue" />
          <StatCard label="Часов 7д" value={stats.transcriptions.hours_7d} color="yellow" />
        </div>
      </section>

      {/* Row 3 — revenue */}
      <section>
        <h2 className="text-sm font-medium text-gray-500 mb-3">Выручка</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Оплат 24ч" value={fmt(stats.revenue.count_24h)} color="green" />
          <StatCard label="Сумма 24ч" value={fmtRub(stats.revenue.sum_24h)} color="green" />
          <StatCard label="Оплат 7д" value={fmt(stats.revenue.count_7d)} color="green" />
          <StatCard label="Сумма 7д" value={fmtRub(stats.revenue.sum_7d)} color="green" />
          <StatCard label="Оплат 30д" value={fmt(stats.revenue.count_30d)} color="green" />
          <StatCard label="Сумма 30д" value={fmtRub(stats.revenue.sum_30d)} color="green" />
        </div>
      </section>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded shadow-sm p-4">
          <h3 className="text-sm font-medium mb-3">Выручка за 30 дней (₽)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={revenue?.data || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `${v}₽`} />
              <Bar dataKey="amount" fill="#3b82f6" name="₽" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded shadow-sm p-4">
          <h3 className="text-sm font-medium mb-3">Новые пользователи за 30 дней</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={usersGrowth?.data || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#10b981" dot={false} name="Юзеры" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
