// frontend/src/services/api.js
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ==============================
// INTERCEPTOR REQUEST : injecter token access
// ==============================
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('pgcc_access_token');
    if (token && !config.url.includes('/auth/login')) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ==============================
// INTERCEPTOR RESPONSE : refresh auto sur 401
// ==============================
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Si erreur réseau ou non-401, propager directement
    if (!error.response || error.response.status !== 401) {
      return Promise.reject(error);
    }

    // Éviter boucle infinie sur /auth/refresh lui-même
    if (originalRequest._retry || originalRequest.url.includes('/auth/refresh') || originalRequest.url.includes('/auth/logout')) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    const refreshToken = localStorage.getItem('pgcc_refresh_token');
    if (!refreshToken) {
      const authError = new Error('Session expirée : refresh token absent.');
      processQueue(authError, null);
      isRefreshing = false;
      logoutAndRedirect();
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, {
        refresh_token: refreshToken,
      });

      const newAccessToken = data.access_token;
      const newRefreshToken = data.refresh_token;

      localStorage.setItem('pgcc_access_token', newAccessToken);
      localStorage.setItem('pgcc_refresh_token', newRefreshToken);

      apiClient.defaults.headers.common['Authorization'] = `Bearer ${newAccessToken}`;
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

      processQueue(null, newAccessToken);
      return apiClient(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      logoutAndRedirect();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

function logoutAndRedirect() {
  delete apiClient.defaults.headers.common['Authorization'];
  localStorage.removeItem('pgcc_access_token');
  localStorage.removeItem('pgcc_refresh_token');
  localStorage.removeItem('pgcc_user_role');
  localStorage.removeItem('pgcc_permissions');
  window.location.href = '/login';
}

export default apiClient;