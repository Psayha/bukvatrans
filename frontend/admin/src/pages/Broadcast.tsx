import { useState } from 'react'
import { previewBroadcast, sendBroadcast } from '../api/admin'

type Target = 'all' | 'subscribers' | 'non_subscribers'

const TARGETS: { value: Target; label: string }[] = [
  { value: 'all', label: 'Все пользователи' },
  { value: 'subscribers', label: 'Только подписчики' },
  { value: 'non_subscribers', label: 'Без активной подписки' },
]

export default function Broadcast() {
  const [text, setText] = useState('')
  const [target, setTarget] = useState<Target>('all')
  const [preview, setPreview] = useState<number | null>(null)
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handlePreview() {
    if (!text.trim()) return
    setLoading(true)
    try {
      const r = await previewBroadcast(text, target)
      setPreview(r.estimated_recipients)
    } catch {
      setError('Ошибка превью')
    } finally {
      setLoading(false)
    }
  }

  async function handleSend() {
    if (!text.trim() || preview === null) return
    if (!confirm(`Отправить ${preview} пользователям?`)) return
    setLoading(true)
    setError('')
    try {
      await sendBroadcast(text, target)
      setSent(true)
      setText('')
      setPreview(null)
    } catch {
      setError('Ошибка отправки')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-lg font-semibold mb-4">Рассылка</h1>

      <div className="bg-white border rounded p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Аудитория</label>
          <div className="flex gap-3">
            {TARGETS.map((t) => (
              <label key={t.value} className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  value={t.value}
                  checked={target === t.value}
                  onChange={() => { setTarget(t.value); setPreview(null) }}
                />
                {t.label}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            Текст сообщения (HTML разметка: &lt;b&gt;, &lt;i&gt;, &lt;a href=…&gt;)
          </label>
          <textarea
            value={text}
            onChange={(e) => { setText(e.target.value); setPreview(null); setSent(false) }}
            rows={6}
            placeholder="Введите текст рассылки..."
            className="w-full border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="text-xs text-gray-400 mt-1">{text.length} символов</div>
        </div>

        {sent && (
          <div className="text-green-600 text-sm font-medium">
            ✓ Рассылка отправлена в очередь
          </div>
        )}

        {error && <div className="text-red-600 text-sm">{error}</div>}

        {preview !== null && (
          <div className="text-sm text-gray-600">
            Получателей: <strong>{preview}</strong>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handlePreview}
            disabled={!text.trim() || loading}
            className="px-4 py-2 border rounded text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            Превью
          </button>
          <button
            onClick={handleSend}
            disabled={preview === null || loading || !text.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Отправка...' : `Отправить${preview !== null ? ` (${preview})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}
