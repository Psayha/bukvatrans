import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getTranscription, listTranscriptions } from '../api/admin'
import type { AdminTranscription } from '../api/types'
import Pagination from '../components/Pagination'

const STATUS_OPTIONS = ['all', 'done', 'failed', 'pending', 'processing', 'cancelled']

export default function Transcriptions() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('all')
  const [viewing, setViewing] = useState<AdminTranscription | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-transcriptions', page, status],
    queryFn: () => listTranscriptions({ page, per_page: 50, status }),
  })

  async function viewDetail(id: string) {
    setLoadingDetail(true)
    try {
      const t = await getTranscription(id)
      setViewing(t)
    } finally {
      setLoadingDetail(false)
    }
  }

  const modalIsError = viewing?.status === 'failed'

  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold mb-4">Транскрибации</h1>

      <div className="flex gap-3 mb-4">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1) }}
          className="border rounded px-2 py-1.5 text-sm"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        {loadingDetail && <span className="text-xs text-gray-400 self-center">Загрузка...</span>}
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
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2">Тип</th>
                  <th className="px-3 py-2">Файл / URL</th>
                  <th className="px-3 py-2">Длит.</th>
                  <th className="px-3 py-2">Дата</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((t: AdminTranscription) => (
                  <tr key={t.id} className={`border-b hover:bg-gray-50 ${t.status === 'failed' ? 'bg-red-50/40' : ''}`}>
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">
                      {t.id.slice(0, 8)}…
                    </td>
                    <td className="px-3 py-2 text-xs">{t.user_display}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs ${
                          t.status === 'done'
                            ? 'bg-green-100 text-green-700'
                            : t.status === 'failed'
                            ? 'bg-red-100 text-red-600'
                            : t.status === 'processing'
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">{t.source_type}</td>
                    <td className="px-3 py-2 text-xs text-gray-500 max-w-[160px]">
                      {t.status === 'failed' && t.error_message ? (
                        <span className="text-red-500 truncate block" title={t.error_message}>
                          {t.error_type ? `[${t.error_type}] ` : ''}{t.error_message}
                        </span>
                      ) : (
                        <span className="truncate block">{t.file_name || '—'}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {t.duration_seconds ? `${Math.round(t.duration_seconds / 60)}м` : '—'}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-400">
                      {new Date(t.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="px-3 py-2">
                      {(t.status === 'done' || t.status === 'failed') && (
                        <button
                          onClick={() => viewDetail(t.id)}
                          className={`text-xs hover:underline ${t.status === 'failed' ? 'text-red-500' : 'text-blue-600'}`}
                        >
                          {t.status === 'failed' ? 'Снапшот' : 'Текст'}
                        </button>
                      )}
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

      {viewing && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setViewing(null)}
        >
          <div
            className="bg-white rounded-lg w-full max-w-3xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`flex items-center justify-between p-4 border-b ${modalIsError ? 'bg-red-50' : ''}`}>
              <div>
                <h3 className="font-semibold text-sm">
                  {modalIsError ? '🔴 Снапшот ошибки' : 'Транскрибация'} — <span className="font-mono">{viewing.id.slice(0, 8)}…</span>
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Пользователь: <span className="font-medium text-gray-600">{viewing.user_display}</span>
                  {' · '}ID пользователя: <span className="font-mono">{viewing.user_id}</span>
                </p>
              </div>
              <button onClick={() => setViewing(null)} className="text-gray-400 hover:text-gray-600 ml-4 text-lg leading-none">✕</button>
            </div>

            <div className="p-4 overflow-auto flex-1 space-y-4">
              {modalIsError ? (
                <>
                  {/* Meta grid */}
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs bg-gray-50 rounded p-3">
                    <div><span className="text-gray-400">Тип источника:</span> <span className="font-medium">{viewing.source_type}</span></div>
                    <div><span className="text-gray-400">Язык:</span> <span className="font-medium">{viewing.language || '—'}</span></div>
                    <div><span className="text-gray-400">Создано:</span> <span className="font-medium">{new Date(viewing.created_at).toLocaleString('ru-RU')}</span></div>
                    <div><span className="text-gray-400">Упало:</span> <span className="font-medium">{viewing.completed_at ? new Date(viewing.completed_at).toLocaleString('ru-RU') : '—'}</span></div>
                    <div><span className="text-gray-400">Списано секунд:</span> <span className="font-medium">{viewing.seconds_charged}</span></div>
                    <div><span className="text-gray-400">Бесплатная:</span> <span className="font-medium">{viewing.is_free ? 'да' : 'нет'}</span></div>
                    {viewing.duration_seconds != null && (
                      <div><span className="text-gray-400">Длительность:</span> <span className="font-medium">{Math.round(viewing.duration_seconds / 60)} мин</span></div>
                    )}
                    {viewing.file_size_bytes != null && (
                      <div><span className="text-gray-400">Размер файла:</span> <span className="font-medium">{(viewing.file_size_bytes / 1024 / 1024).toFixed(1)} МБ</span></div>
                    )}
                  </div>

                  {/* Source */}
                  {(viewing.source_url || viewing.file_name) && (
                    <div>
                      <div className="text-xs font-medium text-gray-500 uppercase mb-1">Источник</div>
                      {viewing.source_url ? (
                        <a href={viewing.source_url} target="_blank" rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:underline break-all">
                          {viewing.source_url}
                        </a>
                      ) : (
                        <div className="text-sm text-gray-700">{viewing.file_name}</div>
                      )}
                    </div>
                  )}

                  {/* Error */}
                  <div>
                    <div className="text-xs font-medium text-gray-500 uppercase mb-1">Ошибка</div>
                    <div className="bg-red-50 border border-red-200 rounded p-3 space-y-1">
                      {viewing.error_type && (
                        <div className="font-mono text-xs text-red-500 font-semibold">{viewing.error_type}</div>
                      )}
                      <div className="text-sm text-red-800">{viewing.error_message || '—'}</div>
                    </div>
                  </div>

                  {/* Traceback */}
                  <div>
                    <div className="text-xs font-medium text-gray-500 uppercase mb-1">Traceback</div>
                    {viewing.error_traceback ? (
                      <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-auto max-h-72 whitespace-pre-wrap leading-relaxed">
                        {viewing.error_traceback}
                      </pre>
                    ) : (
                      <div className="text-xs text-gray-400 italic bg-gray-50 rounded p-3">
                        Traceback недоступен — ошибка произошла до обновления системы мониторинга.
                        Для новых ошибок полный стек будет отображаться здесь.
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <pre className="text-sm whitespace-pre-wrap text-gray-700">
                  {viewing.result_text || '(текст недоступен)'}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
