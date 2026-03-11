import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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

export const authApi = {
  login: (username, password) =>
    api.post('/auth/login', new URLSearchParams({ username, password })),
  me: () => api.get('/auth/me'),
}

export const rulesApi = {
  list:   (params) => api.get('/rules', { params }),
  create: (body)   => api.post('/rules', body),
  update: (id, b)  => api.put(`/rules/${id}`, b),
  toggle: (id)     => api.patch(`/rules/${id}/toggle`),
  delete: (id)     => api.delete(`/rules/${id}`),
}

export const logsApi = {
  list: (params) => api.get('/logs', { params }),
}

export const statsApi = {
  get:     ()     => api.get('/stats'),
  traffic: (mode) => api.get('/stats/traffic', { params: { mode } }),
}

export const usersApi = {
  list:   ()       => api.get('/users'),
  create: (body)   => api.post('/users', body),
  update: (id, b)  => api.put(`/users/${id}`, b),
  delete: (id)     => api.delete(`/users/${id}`),
}

// ── Groupes de clients ────────────────────────────────────────────────────────
export const groupsApi = {
  list:       ()             => api.get('/client-groups'),
  create:     (body)         => api.post('/client-groups', body),
  update:     (id, body)     => api.put(`/client-groups/${id}`, body),
  delete:     (id)           => api.delete(`/client-groups/${id}`),
  // Règles du groupe
  listRules:  (id)           => api.get(`/client-groups/${id}/rules`),
  addRule:    (id, body)     => api.post(`/client-groups/${id}/rules`, body),
  deleteRule: (id, ruleId)   => api.delete(`/client-groups/${id}/rules/${ruleId}`),
}

// ── Utilisateurs clients (IP) ─────────────────────────────────────────────────
export const clientUsersApi = {
  list:       ()             => api.get('/client-users'),
  create:     (body)         => api.post('/client-users', body),
  update:     (id, body)     => api.put(`/client-users/${id}`, body),
  delete:     (id)           => api.delete(`/client-users/${id}`),
  // Gestion des groupes de l'utilisateur
  getGroups:  (id)           => api.get(`/client-users/${id}/groups`),
  setGroups:  (id, groupIds) => api.put(`/client-users/${id}/groups`, { group_ids: groupIds }),
  // Test d'accès
  testAccess: (body)         => api.post('/client-users/test-access', body),
}