import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Injecte le token JWT à chaque requête
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirige vers /login si 401
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Helpers par domaine ────────────────────────────────────────────────────────

export const authApi = {
  login:   (username, password) =>
    api.post('/auth/login', new URLSearchParams({ username, password })),
  me:      () => api.get('/auth/me'),
}

export const rulesApi = {
  list:    (params) => api.get('/rules', { params }),
  create:  (body)   => api.post('/rules', body),
  update:  (id, b)  => api.put(`/rules/${id}`, b),
  toggle:  (id)     => api.patch(`/rules/${id}/toggle`),
  delete:  (id)     => api.delete(`/rules/${id}`),
}

export const logsApi = {
  list:    (params) => api.get('/logs', { params }),
}

export const statsApi = {
  get:     ()       => api.get('/stats'),
  traffic: (mode)   => api.get('/stats/traffic', { params: { mode } }),
}

export const usersApi = {
  list:    ()       => api.get('/users'),
  create:  (body)   => api.post('/users', body),
  update:  (id, b)  => api.put(`/users/${id}`, b),
  delete:  (id)     => api.delete(`/users/${id}`),
}