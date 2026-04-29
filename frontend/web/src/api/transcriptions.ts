import api from './client'
import type { PaginatedTranscriptions, Transcription } from './types'

export async function listTranscriptions(page = 1): Promise<PaginatedTranscriptions> {
  const { data } = await api.get<PaginatedTranscriptions>('/transcriptions', {
    params: { page, per_page: 20 },
  })
  return data
}

export async function getTranscription(id: string): Promise<Transcription> {
  const { data } = await api.get<Transcription>(`/transcriptions/${id}`)
  return data
}

export async function getDownloadUrl(id: string): Promise<{ url: string }> {
  const { data } = await api.get<{ url: string }>(`/transcriptions/${id}/download`)
  return data
}

export async function uploadFile(
  file: File,
  language = 'ru',
  onProgress?: (pct: number) => void
): Promise<{ transcription_id: string; status: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('language', language)
  const { data } = await api.post('/transcriptions/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
  return data
}

export async function submitUrl(
  url: string,
  language = 'ru'
): Promise<{ transcription_id: string; status: string }> {
  const { data } = await api.post('/transcriptions/url', { url, language })
  return data
}
