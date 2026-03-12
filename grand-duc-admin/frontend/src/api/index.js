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

// ── Cache simple avec TTL ────────────────────────────────────────────────────
const _cache = new Map()

function cachedGet(url, ttlMs = 30_000) {
  const now = Date.now()
  const entry = _cache.get(url)
  if (entry && now - entry.ts < ttlMs) {
    return Promise.resolve(entry.data)
  }
  // Dédupliquer les appels concurrents
  if (entry?.pending) return entry.pending
  const pending = api.get(url).then(res => {
    _cache.set(url, { data: res, ts: Date.now(), pending: null })
    return res
  }).catch(err => {
    _cache.delete(url)
    throw err
  })
  _cache.set(url, { ...(entry || {}), pending })
  return pending
}

export function invalidateCache(urlPrefix) {
  for (const key of _cache.keys()) {
    if (key.startsWith(urlPrefix)) _cache.delete(key)
  }
}

export default api

export const authApi = {
  login: (username, password) =>
    api.post('/auth/login', new URLSearchParams({ username, password })),
  me: () => api.get('/auth/me'),
}

export const rulesApi = {
  list:   (params) => api.get('/rules', { params }),
  create: (body)   => { invalidateCache('/rules'); return api.post('/rules', body) },
  update: (id, b)  => { invalidateCache('/rules'); return api.put(`/rules/${id}`, b) },
  toggle: (id)     => { invalidateCache('/rules'); return api.patch(`/rules/${id}/toggle`) },
  delete: (id)     => { invalidateCache('/rules'); return api.delete(`/rules/${id}`) },
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
  create: (body)   => { invalidateCache('/users'); return api.post('/users', body) },
  update: (id, b)  => { invalidateCache('/users'); return api.put(`/users/${id}`, b) },
  delete: (id)     => { invalidateCache('/users'); return api.delete(`/users/${id}`) },
}

// ── Groupes de clients ────────────────────────────────────────────────────────
export const groupsApi = {
  list:       ()             => cachedGet('/client-groups', 15_000),
  create:     (body)         => { invalidateCache('/client-groups'); return api.post('/client-groups', body) },
  update:     (id, body)     => { invalidateCache('/client-groups'); return api.put(`/client-groups/${id}`, body) },
  delete:     (id)           => { invalidateCache('/client-groups'); return api.delete(`/client-groups/${id}`) },
  // Règles du groupe
  listRules:  (id)           => api.get(`/client-groups/${id}/rules`),
  addRule:    (id, body)     => { invalidateCache('/client-groups'); return api.post(`/client-groups/${id}/rules`, body) },
  deleteRule: (id, ruleId)   => { invalidateCache('/client-groups'); return api.delete(`/client-groups/${id}/rules/${ruleId}`) },
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
  getSmtp:          ()       => cachedGet('/settings/smtp', 30_000),
  updateSmtp:       (body)   => { invalidateCache('/settings/smtp'); return api.put('/settings/smtp', body) },
  testSmtp:         (to)     => api.post('/settings/smtp/test', { to }),
  getNotifications: ()       => api.get('/settings/notifications'),
  setNotifications: (body)   => api.put('/settings/notifications', body),
  getRuleWatches:   ()       => api.get('/settings/notifications/rules'),
  getAvailRules:    ()       => cachedGet('/settings/notifications/rules/available', 30_000),
  setRuleWatches:   (ids)    => { invalidateCache('/settings/notifications'); return api.put('/settings/notifications/rules', { rule_ids: ids }) },
  getTheme:            ()         => api.get('/settings/theme'),
  setTheme:            (theme)    => api.put('/settings/theme', { theme }),
  getEmailTemplate:    ()         => api.get('/settings/email-template'),
  setEmailTemplate:    (template) => api.put('/settings/email-template', { template }),
  resetEmailTemplate:  ()         => api.delete('/settings/email-template'),
  previewEmailTemplate:(template) => api.post('/settings/email-template/preview', { template }),
}

// ── Intégrations RMM ─────────────────────────────────────────────────────────
export const integrationsApi = {
  list:   ()          => cachedGet('/integrations', 30_000),
  create: (body)      => { invalidateCache('/integrations'); return api.post('/integrations', body) },
  update: (id, body)  => { invalidateCache('/integrations'); return api.put(`/integrations/${id}`, body) },
  delete: (id)        => { invalidateCache('/integrations'); return api.delete(`/integrations/${id}`) },
  sync:   (id)        => api.post(`/integrations/${id}/sync`),
}

// ── Rôles ────────────────────────────────────────────────────────────────────
export const rolesApi = {
  list:        ()          => cachedGet('/roles', 30_000),
  permissions: ()          => cachedGet('/roles/permissions', 120_000),
  create:      (body)      => { invalidateCache('/roles'); return api.post('/roles', body) },
  update:      (id, body)  => { invalidateCache('/roles'); return api.put(`/roles/${id}`, body) },
  delete:      (id)        => { invalidateCache('/roles'); return api.delete(`/roles/${id}`) },
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
