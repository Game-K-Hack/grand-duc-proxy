import { defineStore } from 'pinia'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token:    localStorage.getItem('token') || null,
    user:     null,
    loading:  false,
    error:    null,
  }),

  getters: {
    isLoggedIn:   s => !!s.token,
    isAdmin:      s => s.user?.role === 'admin',
    permissions:  s => s.user?.permissions || {},
  },

  actions: {
    hasPermission(key) {
      return !!this.permissions[key]
    },
    hasAnyPermission(...keys) {
      return keys.some(k => !!this.permissions[k])
    },

    async login(username, password) {
      this.loading = true
      this.error   = null
      try {
        const { data } = await authApi.login(username, password)
        this.token = data.access_token
        localStorage.setItem('token', data.access_token)
        await this.fetchMe()
        // Charger le theme de l'utilisateur
        import('@/composables/useTheme').then(({ useTheme }) => {
          useTheme().loadFromServer()
        })
      } catch (e) {
        this.error = e.response?.data?.detail || 'Erreur de connexion'
        throw e
      } finally {
        this.loading = false
      }
    },

    async fetchMe() {
      if (!this.token) return
      if (this._fetchPromise) return this._fetchPromise
      this._fetchPromise = authApi.me().then(({ data }) => {
        this.user = data
        import('@/composables/useTheme').then(({ useTheme }) => {
          useTheme().loadFromServer()
        })
      }).catch(() => {
        this.logout()
      }).finally(() => {
        this._fetchPromise = null
      })
      return this._fetchPromise
    },

    logout() {
      this.token = null
      this.user  = null
      localStorage.removeItem('token')
    },
  },
})
