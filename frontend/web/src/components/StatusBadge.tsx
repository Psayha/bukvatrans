import type { TranscriptionStatus } from '../api/types'

const MAP: Record<TranscriptionStatus, { label: string; cls: string }> = {
  pending:    { label: 'В очереди',   cls: 'bg-gray-100 text-gray-600' },
  processing: { label: 'Обработка',   cls: 'bg-blue-100 text-blue-700' },
  done:       { label: 'Готово',      cls: 'bg-green-100 text-green-700' },
  failed:     { label: 'Ошибка',      cls: 'bg-red-100 text-red-700' },
}

export default function StatusBadge({ status }: { status: TranscriptionStatus }) {
  const { label, cls } = MAP[status] ?? MAP.failed
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}
