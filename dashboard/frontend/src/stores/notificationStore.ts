import { create } from 'zustand';
import api from '@/lib/api';

export interface StoredNotification {
  id: string;
  type: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  message: string;
  customer_id?: number;
  customer_name?: string;
  task_id?: string;
  created_by_name?: string;
  timestamp: number;  // ms epoch (from created_at)
  read: boolean;
  dismissed: boolean;
}

interface NotificationStore {
  notifications: StoredNotification[];
  loading: boolean;
  fetchNotifications: () => Promise<void>;
  addNotification: (n: StoredNotification) => void;
  markAsRead: (id: string) => void;
  dismiss: (id: string) => void;
  dismissAll: () => void;
  getUnreadCount: () => number;
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  loading: false,

  fetchNotifications: async () => {
    set({ loading: true });
    try {
      const res = await api.get('/api/v1/notifications');
      const notifications: StoredNotification[] = res.data.map((n: any) => ({
        ...n,
        timestamp: new Date(n.created_at).getTime(),
      }));
      set({ notifications });
    } catch (e) {
      console.error('Failed to fetch notifications', e);
    } finally {
      set({ loading: false });
    }
  },

  addNotification: (n) => {
    set(state => ({
      notifications: [n, ...state.notifications].slice(0, 100),
    }));
  },

  markAsRead: (id) => {
    api.patch(`/api/v1/notifications/${id}/read`).catch(() => {});
    set(state => ({
      notifications: state.notifications.map(n => n.id === id ? { ...n, read: true } : n),
    }));
  },

  dismiss: (id) => {
    api.patch(`/api/v1/notifications/${id}/dismiss`).catch(() => {});
    set(state => ({
      notifications: state.notifications.filter(n => n.id !== id),
    }));
  },

  dismissAll: () => {
    api.patch('/api/v1/notifications/dismiss-all').catch(() => {});
    set({ notifications: [] });
  },

  getUnreadCount: () => get().notifications.filter(n => !n.read).length,
}));
