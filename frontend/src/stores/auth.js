// frontend/src/stores/auth.js
import { defineStore } from 'pinia';
import apiClient from '@/services/api'; // ← Vérifie bien ce chemin (avec / après @)

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('pgcc_access_token') || null,
    refreshToken: localStorage.getItem('pgcc_refresh_token') || null,
    user: null,
    role: localStorage.getItem('pgcc_user_role') || null,
    permissions: JSON.parse(localStorage.getItem('pgcc_permissions') || '{}'),
    preAuthToken: null,
    mfaSecret: null,
    isLoading: false,
    error: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    isAdmin: (state) => state.role === 'admin',
    canAccessModule: (state) => (module, action = 'read') => {
      const modPerms = state.permissions[module];
      return Array.isArray(modPerms) && modPerms.includes(action);
    },
  },

  actions: {
    async login(email, password) {
      this.isLoading = true;
      this.error = null;
      try {
        const { data } = await apiClient.post('/auth/login', { email, password });
        this.preAuthToken = data.pre_auth_token;
        return data;
      } catch (err) {
        this.error = err.response?.data?.detail || 'Erreur de connexion.';
        throw err;
      } finally {
        this.isLoading = false;
      }
    },

    async startMfaEnrollment(preAuthToken) {
      this.isLoading = true;
      this.error = null;
      try {
        const { data } = await apiClient.post('/auth/start-enrollment', {}, {
          headers: { Authorization: `Bearer ${preAuthToken}` },
        });
        this.mfaSecret = data.secret;
        return data;
      } catch (err) {
        this.error = err.response?.data?.detail || 'Erreur démarrage MFA.';
        throw err;
      } finally {
        this.isLoading = false;
      }
    },

    async confirmMfa(preAuthToken, mfaCode) {
      this.isLoading = true;
      this.error = null;
      try {
        const { data } = await apiClient.post('/auth/confirm-mfa', {
          pre_auth_token: preAuthToken,
          mfa_code: mfaCode,
        });

        this.setSession(data);
        await this.fetchPermissions();
        return data;
      } catch (err) {
        this.error = err.response?.data?.detail || 'Confirmation MFA échouée.';
        throw err;
      } finally {
        this.isLoading = false;
      }
    },

    setSession(sessionData) {
      this.accessToken = sessionData.access_token;
      this.refreshToken = sessionData.refresh_token;
      this.user = sessionData.user;
      this.role = sessionData.user.role;

      localStorage.setItem('pgcc_access_token', this.accessToken);
      localStorage.setItem('pgcc_refresh_token', this.refreshToken);
      localStorage.setItem('pgcc_user_role', this.role);
    },

    async fetchPermissions() {
      try {
        const { data } = await apiClient.get('/me/permissions');
        this.permissions = data.permissions || {};
        localStorage.setItem('pgcc_permissions', JSON.stringify(this.permissions));
      } catch (err) {
        console.warn('Impossible de charger les permissions:', err);
        this.permissions = {};
      }
    },

    async logout() {
      const refreshToken = this.refreshToken || localStorage.getItem('pgcc_refresh_token');
      if (refreshToken) {
        try {
          await apiClient.post('/auth/logout', { refresh_token: refreshToken });
        } catch (err) {
          // Local logout must succeed even if server revocation is unavailable.
          console.warn('Révocation serveur de la session impossible:', err);
        }
      }
      [
        'pgcc_access_token',
        'pgcc_refresh_token',
        'pgcc_user_role',
        'pgcc_permissions',
      ].forEach((key) => localStorage.removeItem(key));
      // Reset after storage cleanup so state() cannot reload stale credentials.
      this.$reset();
      window.location.href = '/login';
    },
  },
});