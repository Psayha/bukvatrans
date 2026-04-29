import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadFile, submitUrl } from '../../api/transcriptions'

type Tab = 'file' | 'url'

const ACCEPT = '.mp3,.mp4,.m4a,.ogg,.wav,.webm,.aac,.flac,.mkv,.mov,.avi,.wma'

export default function NewTranscription() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('file')
  const [url, setUrl] = useState('')
  const [lang, setLang] = useState('ru')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  async function handleFile(file: File) {
    setError('')
    setLoading(true)
    setProgress(0)
    try {
      const { transcription_id } = await uploadFile(file, lang, setProgress)
      navigate(`/app/t/${transcription_id}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Ошибка загрузки файла')
    } finally {
      setLoading(false)
    }
  }

  async function handleUrl(e: React.FormEvent) {
    e.preventDefault()
    if (!url.trim()) return
    setError('')
    setLoading(true)
    try {
      const { transcription_id } = await submitUrl(url.trim(), lang)
      navigate(`/app/t/${transcription_id}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Ошибка: проверьте ссылку')
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">Новая транскрипция</h1>

      {/* Tabs */}
      <div className="flex border-b mb-6">
        {(['file', 'url'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError('') }}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'file' ? 'Загрузить файл' : 'Ссылка на видео'}
          </button>
        ))}
      </div>

      {/* Language picker */}
      <div className="mb-5">
        <label className="block text-sm font-medium mb-1">Язык аудио</label>
        <select
          value={lang}
          onChange={(e) => setLang(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="ru">Русский</option>
          <option value="en">English</option>
          <option value="auto">Определить автоматически</option>
        </select>
      </div>

      {tab === 'file' && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !loading && fileRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
          } ${loading ? 'pointer-events-none opacity-70' : ''}`}
        >
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          <div className="text-4xl mb-3">🎵</div>
          {loading ? (
            <div>
              <p className="text-sm text-gray-600 mb-2">Загрузка... {progress}%</p>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          ) : (
            <>
              <p className="text-gray-700 font-medium">Перетащите файл или нажмите</p>
              <p className="text-sm text-gray-400 mt-1">
                MP3, MP4, M4A, WAV, OGG, FLAC, MKV, MOV до 500 МБ
              </p>
            </>
          )}
        </div>
      )}

      {tab === 'url' && (
        <form onSubmit={handleUrl} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Ссылка на видео или аудио</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              autoFocus
              placeholder="https://youtube.com/watch?v=..."
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              YouTube · Rutube · VK Видео · прямая ссылка на MP3/MP4
            </p>
          </div>
          <button
            type="submit"
            disabled={loading || !url.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Отправка...' : 'Транскрибировать'}
          </button>
        </form>
      )}

      {error && <p className="mt-4 text-red-500 text-sm">{error}</p>}
    </div>
  )
}
