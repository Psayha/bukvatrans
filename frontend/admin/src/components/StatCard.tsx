interface Props {
  label: string
  value: string | number
  sub?: string
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple'
}

const colors = {
  blue: 'border-blue-500 text-blue-700',
  green: 'border-green-500 text-green-700',
  red: 'border-red-500 text-red-700',
  yellow: 'border-yellow-500 text-yellow-700',
  purple: 'border-purple-500 text-purple-700',
}

export default function StatCard({ label, value, sub, color = 'blue' }: Props) {
  return (
    <div className={`bg-white rounded border-l-4 p-4 shadow-sm ${colors[color]}`}>
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  )
}
