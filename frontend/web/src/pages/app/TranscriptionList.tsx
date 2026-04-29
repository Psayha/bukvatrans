import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'
import { listTranscriptions } from '../../api/transcriptions'
import StatusBadge from '../../components/StatusBadge'

function fmtDuration(s: number | null): string {
  if (!s) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
}

function sourceLabel(type: string): string {
  const MAP: Record<string, string> = {
    youtube: 'YouTube', rutube: 'Rutube', vk: 'VK',
    audio: 'Файл', video: 'Файл', url: 'Ссылка',
  }
  return MAP[type] ?? type
}

export default function TranscriptionList() {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useQuery({
    queryKey: ['transcriptions', page],
    queryFn: () => listTranscriptions(page),
    staleTime: 10_000,
  })

  if (isLoading) {
    return <div className="text-gray-500 text-sm">Загрузка...</div>
  }

  if (!data?.items.length) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500 mb-4">Транскрипций пока нет</p>
        <Link
          to="/app"
          className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          Создать первую
        </Link>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-semibold">История транскрипций</h1>
        <Link
          to="/app"
          className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          + Новая
        </Link>
      </div>

      <div className="space-y-2">
        {data.items.map((t) => (
          <Link
            key={t.id}
            to={`/app/t/${t.id}`}
            className="block bg-white border rounded-lg px-4 py-3 hover:border-blue-300 transition-colors"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">
                  {t.file_name || sourceLabel(t.source_type)}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {sourceLabel(t.source_type)} ·{' '}
                  {formatDistanceToNow(new Date(t.created_at), {
                    addSuffix: true,
                    locale: ru,
                  })}
                  {t.duration_seconds ? ` · ${fmtDuration(t.duration_seconds)}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {t.is_free && (
                  <span className="text-xs text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                    бесплатно
                  </span>
                )}
                <StatusBadge status={t.status} />
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Pagination */}
      {data.pages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 border rounded text-sm disabled:opacity-40"
          >
            ←
          </button>
          <span className="px-3 py-1 text-sm text-gray-600">
            {page} / {data.pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
            disabled={page === data.pages}
            className="px-3 py-1 border rounded text-sm disabled:opacity-40"
          >
            →
          </button>
        </div>
      )}
    </div>
  )
}
