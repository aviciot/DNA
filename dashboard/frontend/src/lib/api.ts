/**
 * DNA Frontend - API Client Configuration
 * ==========================================
 * In CF Zero Trust production mode (NEXT_PUBLIC_CF_BYPASS != 'true'):
 *   - No Authorization header -- CF edge handles authentication transparently
 *   - 401 redirects to CF login (not /login page)
 *
 * In local dev mode (NEXT_PUBLIC_CF_BYPASS=true):
 *   - Adds Authorization: Bearer <token> from localStorage
 *   - 401 redirects to /login
 */

import axios from 'axios';

const CF_BYPASS = process.env.NEXT_PUBLIC_CF_BYPASS === 'true';
const API_URL = process.env.NEXT_PUBLIC_API_URL;
const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL;

if (!API_URL) throw new Error('NEXT_PUBLIC_API_URL is not set');
if (!AUTH_URL) throw new Error('NEXT_PUBLIC_AUTH_URL is not set');

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  withCredentials: true,  // required for CF Access session cookie
});

export const authApi = axios.create({
  baseURL: AUTH_URL,
  timeout: 10000,
  withCredentials: true,
});

// In dev bypass mode: inject stored Bearer token
if (CF_BYPASS) {
  const injectToken = (config: any) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  };
  api.interceptors.request.use(injectToken, (e) => Promise.reject(e));
  authApi.interceptors.request.use(injectToken, (e) => Promise.reject(e));
}

// 401 handler
const handleUnauthorized = () => {
  if (typeof window === 'undefined') return;
  if (CF_BYPASS) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
  } else {
    // Let CF Access handle re-authentication
    window.location.reload();
  }
};

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) handleUnauthorized();
    return Promise.reject(error);
  },
);

authApi.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) handleUnauthorized();
    return Promise.reject(error);
  },
);

export default api;
