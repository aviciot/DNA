'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useNotificationStore, StoredNotification } from '@/stores/notificationStore';
import NotificationFeed from '@/components/notifications/NotificationFeed';

export default function GlobalNotificationProvider() {
  const pathname = usePathname();
  const wsRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef(false);
  const [toasts, setToasts] = useState<StoredNotification[]>([]);
  const { addNotification, dismiss, dismissAll, fetchNotifications } = useNotificationStore();

  const isAuthPage = pathname === '/login';

  useEffect(() => {
    if (isAuthPage) return;
    fetchNotifications();
    connect();
    return () => { wsRef.current?.close(); wsRef.current = null; };
  }, [isAuthPage]);

  const connect = () => {
    if (connectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) return;
    connectingRef.current = true;

    const token = localStorage.getItem('access_token') || localStorage.getItem('token');
    if (!token) { connectingRef.current = false; return; }

    const wsUrl = process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws') ?? 'ws://localhost:3010';
    const ws = new WebSocket(`${wsUrl}/ws/notifications?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => { connectingRef.current = false; };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'notification') {
          const n: StoredNotification = { ...msg.payload, read: false, dismissed: false };
          addNotification(n);
          setToasts(prev => [n, ...prev]);
        }
      } catch {}
    };

    ws.onerror = () => { connectingRef.current = false; };

    ws.onclose = () => {
      connectingRef.current = false;
      wsRef.current = null;
      if (!isAuthPage) setTimeout(connect, 5000);
    };
  };

  const dismissToast = (id: string) => setToasts(prev => prev.filter(n => n.id !== id));
  const dismissAllToasts = () => { setToasts([]); dismissAll(); };

  if (isAuthPage) return null;

  return (
    <NotificationFeed
      notifications={toasts}
      onDismiss={dismissToast}
      onDismissAll={dismissAllToasts}
    />
  );
}
