import { useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getTranscription, getDownloadUrl } from '../../api/transcriptions'
import StatusBadge from '../../components/StatusBadge'

function CopyButton({ text }: { text: string }) {
  async function copy() {
    await navigator.clipboard.writeText(text)
  }
  return (
    <button
      onClick={copy}
      className="text-xs px-2 py-1 border rounded hover:bg-gray-50 transition-colors"
    >
      Скопировать
    </button>
  )
}

function fmtSeconds(s: number | null): string {
  if (!s) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}ч ${m}мин ${sec}с`
  if (m > 0) return `${m}мин ${sec}с`
  return `${sec}с`
}

export default function TranscriptionDetail() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()

  const { data: t, isLoading } = useQuery({
    queryKey: ['transcription', id],
    queryFn: () => getTranscription(id!),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'processing' ? 3000 : false
    },
    staleTime: 5000,
  })

  // Invalidate list on completion so history updates without manual refresh.
  useEffect(() => {
    if (t?.status === 'done' || t?.status === 'failed') {
      qc.invalidateQueries({ queryKey: ['transcriptions'] })
    }
  }, [t?.status, qc])

  async function handleDownload() {
    const { url } = await getDownloadUrl(id!)
    window.open(url, '_blank')
  }

  if (isLoading) {
    return <div className="text-gray-500 text-sm">Загрузка...</div>
  }

  if (!t) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500 mb-4">Транскрипция не найдена</p>
        <Link to="/app/list" className="text-blue-600 hover:underline text-sm">
          ← К списку
        </Link>
      </div>
    )
  }

  const isActive = t.status === 'pending' || t.status === 'processing'

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/app/list" className="text-sm text-gray-500 hover:text-gray-700">
          ← История
        </Link>
        <StatusBadge status={t.status} />
        {isActive && (
          <span className="text-xs text-blue-600 animate-pulse">Обрабатывается...</span>
        )}
      </div>

      {/* Meta */}
      <div className="bg-white border rounded-lg p-4 mb-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div>
          <p className="text-xs text-gray-400">Источник</p>
          <p className="font-medium">{t.source_type}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Длительность</p>
          <p className="font-medium">{fmtSeconds(t.duration_seconds)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Списано</p>
          <p className="font-medium">{t.is_free ? 'бесплатно' : fmtSeconds(t.seconds_charged)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Язык</p>
          <p className="font-medium">{t.language}</p>
        </div>
      </div>

      {t.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-sm text-red-700">
          <strong>Ошибка:</strong> {t.error_message || 'Не удалось обработать файл'}
        </div>
      )}

      {isActive && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center text-sm text-blue-700">
          <div className="text-2xl mb-2">⏳</div>
          Транскрипция выполняется. Страница обновится автоматически.
        </div>
      )}

      {/* Summary */}
      {t.summary_text && (
        <div className="bg-white border rounded-lg p-5 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm">AI-конспект</h2>
            <CopyButton text={t.summary_text} />
          </div>
          <div
            className="text-sm text-gray-700 leading-relaxed prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: t.summary_text.replace(/\n/g, '<br/>') }}
          />
        </div>
      )}

      {/* Full text */}
      {t.result_text && (
        <div className="bg-white border rounded-lg p-5 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm">Транскрипция</h2>
            <div className="flex gap-2">
              <CopyButton text={t.result_text} />
              {t.s3_key && (
                <button
                  onClick={handleDownload}
                  className="text-xs px-2 py-1 border rounded hover:bg-gray-50"
                >
                  Скачать TXT
                </button>
              )}
            </div>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
            {t.result_text}
          </p>
        </div>
      )}
    </div>
  )
}
