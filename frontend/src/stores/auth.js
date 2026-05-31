import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: localStorage.getItem('access_token') || '',
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
  },

  actions: {
    async login(username, password) {
      const { data } = await api.post('/auth/login', { username, password })
      this.token = data.access_token
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      await this.fetchUser()
    },

    async fetchUser() {
      const { data } = await api.get('/auth/me')
      this.user = data
    },

    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    },
  },
})
