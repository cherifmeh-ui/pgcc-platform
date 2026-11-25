// frontend/src/stores/auth.js
import { defineStore } from 'pinia';
import apiClient, { setAccessToken } from '@/services/api';

let restorePromise = null;

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: null,
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
      setAccessToken(this.accessToken);
      this.user = sessionData.user;
      this.role = sessionData.user.role;

      // Remove legacy browser-readable bearer credentials during migration.
      localStorage.removeItem('pgcc_access_token');
      localStorage.removeItem('pgcc_refresh_token');
      localStorage.setItem('pgcc_user_role', this.role);
    },

    async restoreSession() {
      if (this.accessToken) return true;
      if (restorePromise) return restorePromise;

      restorePromise = (async () => {
        this.isLoading = true;
        try {
          const { data } = await apiClient.post('/auth/refresh', {}, { withCredentials: true });
          this.accessToken = data.access_token;
          setAccessToken(this.accessToken);
          this.user = data.user;
          this.role = data.user.role;
          localStorage.removeItem('pgcc_access_token');
          localStorage.removeItem('pgcc_refresh_token');
          localStorage.setItem('pgcc_user_role', this.role);
          await this.fetchPermissions();
          return true;
        } catch {
          this.accessToken = null;
          setAccessToken(null);
          localStorage.removeItem('pgcc_access_token');
          localStorage.removeItem('pgcc_refresh_token');
          localStorage.removeItem('pgcc_user_role');
          localStorage.removeItem('pgcc_permissions');
          this.role = null;
          this.permissions = {};
          return false;
        } finally {
          this.isLoading = false;
        }
      })();

      try {
        return await restorePromise;
      } finally {
        restorePromise = null;
      }
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
      try {
        await apiClient.post('/auth/logout', {}, { withCredentials: true });
      } catch (err) {
        // Local logout must succeed even if server revocation is unavailable.
        console.warn('Révocation serveur de la session impossible:', err);
      }
      [
        'pgcc_access_token',
        'pgcc_refresh_token',
        'pgcc_user_role',
        'pgcc_permissions',
      ].forEach((key) => localStorage.removeItem(key));
      setAccessToken(null);
      delete apiClient.defaults.headers.common['Authorization'];
      this.$reset();
      window.location.href = '/login';
    },
  },
});