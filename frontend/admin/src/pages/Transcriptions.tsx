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
                  <th className="px-3 py-2">Файл</th>
                  <th className="px-3 py-2">Длит.</th>
                  <th className="px-3 py-2">Дата</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((t: AdminTranscription) => (
                  <tr key={t.id} className="border-b hover:bg-gray-50">
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
                    <td className="px-3 py-2 text-xs text-gray-500 max-w-[120px] truncate">
                      {t.file_name || '—'}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {t.duration_seconds ? `${Math.round(t.duration_seconds / 60)}м` : '—'}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-400">
                      {new Date(t.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="px-3 py-2">
                      {t.status === 'done' && (
                        <button
                          onClick={() => viewDetail(t.id)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Текст
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

      {/* Text viewer modal */}
      {viewing && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setViewing(null)}
        >
          <div
            className="bg-white rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-sm">
                Транскрибация {viewing.id.slice(0, 8)}…
              </h3>
              <button onClick={() => setViewing(null)} className="text-gray-400 hover:text-gray-600">
                ✕
              </button>
            </div>
            <div className="p-4 overflow-auto flex-1">
              <pre className="text-sm whitespace-pre-wrap text-gray-700">
                {viewing.result_text || '(текст недоступен)'}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
