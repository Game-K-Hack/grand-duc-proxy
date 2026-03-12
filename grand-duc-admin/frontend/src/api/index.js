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

// ── Killswitch ────────────────────────────────────────────────────────────────
export const killswitchApi = {
  get:            ()         => api.get('/killswitch'),
  set:            (active)   => api.post('/killswitch', { active }),
  history:        ()         => api.get('/killswitch/history'),
  verifyPassword: (password) => api.post('/killswitch/verify-password', { password }),
}

// ── Contrôle proxy ────────────────────────────────────────────────────────────
export const proxyApi = {
  status:  ()  => api.get('/proxy/status'),
  restart: ()  => api.post('/proxy/restart'),
  logsUrl: ()  => `/api/proxy/logs?token=${localStorage.getItem('token')}`,
}

// ── Certificats CA ────────────────────────────────────────────────────────────
export const certificatesApi = {
  info:     ()                       => api.get('/certificates/info'),
  generate: ()                       => api.post('/certificates/generate'),
  import:   (certFile, keyFile)      => {
    const form = new FormData()
    form.append('cert_file', certFile)
    form.append('key_file',  keyFile)
    return api.post('/certificates/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  history:  ()                       => api.get('/certificates/history'),
  downloadUrl: () => '/api/certificates/ca.crt',
}

// ── TLS Bypass ────────────────────────────────────────────────────────────────
export const tlsBypassApi = {
  list:   ()     => api.get('/tls-bypass'),
  create: (body) => api.post('/tls-bypass', body),
  delete: (id)   => api.delete(`/tls-bypass/${id}`),
}

// ── Paramètres globaux & notifications ───────────────────────────────────────
export const settingsApi = {
  getSmtp:          ()       => api.get('/settings/smtp'),
  updateSmtp:       (body)   => api.put('/settings/smtp', body),
  testSmtp:         (to)     => api.post('/settings/smtp/test', { to }),
  getNotifications: ()       => api.get('/settings/notifications'),
  setNotifications: (body)   => api.put('/settings/notifications', body),
  getRuleWatches:   ()       => api.get('/settings/notifications/rules'),
  getAvailRules:    ()       => api.get('/settings/notifications/rules/available'),
  setRuleWatches:   (ids)    => api.put('/settings/notifications/rules', { rule_ids: ids }),
}

// ── Intégrations RMM ─────────────────────────────────────────────────────────
export const integrationsApi = {
  list:   ()          => api.get('/integrations'),
  create: (body)      => api.post('/integrations', body),
  update: (id, body)  => api.put(`/integrations/${id}`, body),
  delete: (id)        => api.delete(`/integrations/${id}`),
  sync:   (id)        => api.post(`/integrations/${id}/sync`),
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