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
    isLoggedIn: s => !!s.token,
    isAdmin:    s => s.user?.role === 'admin',
  },

  actions: {
    async login(username, password) {
      this.loading = true
      this.error   = null
      try {
        const { data } = await authApi.login(username, password)
        this.token = data.access_token
        localStorage.setItem('token', data.access_token)
        await this.fetchMe()
      } catch (e) {
        this.error = e.response?.data?.detail || 'Erreur de connexion'
        throw e
      } finally {
        this.loading = false
      }
    },

    async fetchMe() {
      if (!this.token) return
      try {
        const { data } = await authApi.me()
        this.user = data
      } catch {
        this.logout()
      }
    },

    logout() {
      this.token = null
      this.user  = null
      localStorage.removeItem('token')
    },
  },
})