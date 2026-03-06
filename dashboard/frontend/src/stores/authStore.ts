/**
 * DNA Frontend - Authentication Store
 * =====================================
 * CF Zero Trust mode: no token management -- CF edge handles auth.
 * Dev bypass mode (NEXT_PUBLIC_CF_BYPASS=true): localStorage JWT + auth-service login.
 */

import { create } from 'zustand';
import { api, authApi } from '@/lib/api';
import type { User } from '@/types';

const CF_BYPASS = process.env.NEXT_PUBLIC_CF_BYPASS === 'true';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  /** Dev-only: email/password login against auth-service */
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Fetch current user from /api/v1/auth/me */
  fetchUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email: string, password: string) => {
    if (!CF_BYPASS) {
      throw new Error('Login form is only available in dev mode');
    }
    const response = await authApi.post('/api/v1/auth/login', { email, password });
    const { access_token, refresh_token } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    // fetchUser will pick up the stored token via api.ts interceptor
    const me = await api.get('/api/v1/auth/me');
    set({ user: me.data, isAuthenticated: true, isLoading: false });
  },

  logout: async () => {
    if (CF_BYPASS) {
      try { await authApi.post('/api/v1/auth/logout'); } catch { /* ignore */ }
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      set({ user: null, isAuthenticated: false, isLoading: false });
      window.location.href = '/login';
    } else {
      // CF logout -- clear CF session cookie via the CF logout endpoint
      set({ user: null, isAuthenticated: false, isLoading: false });
      const teamDomain = process.env.NEXT_PUBLIC_CF_TEAM_DOMAIN;
      if (teamDomain) {
        window.location.href = `https://${teamDomain}/cdn-cgi/access/logout`;
      } else {
        window.location.reload();
      }
    }
  },

  fetchUser: async () => {
    if (CF_BYPASS) {
      const token = localStorage.getItem('access_token');
      if (!token) {
        set({ user: null, isAuthenticated: false, isLoading: false });
        return;
      }
    }

    try {
      const response = await api.get('/api/v1/auth/me');
      set({ user: response.data, isAuthenticated: true, isLoading: false });
    } catch {
      if (CF_BYPASS) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
