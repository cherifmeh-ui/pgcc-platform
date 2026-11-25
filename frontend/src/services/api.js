// frontend/src/services/api.js
import axios from 'axios';

let accessToken = null;
export function setAccessToken(token) {
  accessToken = token || null;
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ==============================
// INTERCEPTOR REQUEST : injecter token access
// ==============================
apiClient.interceptors.request.use(
  (config) => {
    if (accessToken && !config.url.includes('/auth/login')) {
      config.headers.Authorization = `Bearer ${accessToken}`;
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

    try {
      const { data } = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, {}, {
        withCredentials: true,
      });

      const newAccessToken = data.access_token;
      setAccessToken(newAccessToken);
      localStorage.removeItem('pgcc_access_token');
      localStorage.removeItem('pgcc_refresh_token');
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
  setAccessToken(null);
  localStorage.removeItem('pgcc_access_token');
  localStorage.removeItem('pgcc_refresh_token');
  localStorage.removeItem('pgcc_user_role');
  localStorage.removeItem('pgcc_permissions');
  window.location.href = '/login';
}

export default apiClient;