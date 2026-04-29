import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

// Attach Bearer token from localStorage on every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try to refresh once then clear auth.
let _refreshing: Promise<void> | null = null

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }
    original._retry = true

    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) {
      _clearAuth()
      return Promise.reject(error)
    }

    if (!_refreshing) {
      _refreshing = axios
        .post('/api/v1/auth/refresh', { refresh_token: refresh })
        .then((res) => {
          localStorage.setItem('access_token', res.data.access_token)
        })
        .catch(() => _clearAuth())
        .finally(() => { _refreshing = null })
    }

    await _refreshing
    return api(original)
  }
)

function _clearAuth() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('auth_user')
  window.location.href = '/login'
}

export default api
