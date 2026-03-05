'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, X, ShieldCheck, AlertTriangle, Info, CheckCheck, ExternalLink } from 'lucide-react';
import { useNotificationStore, StoredNotification } from '@/stores/notificationStore';

const SeverityIcon = ({ severity }: { severity: string }) => {
  if (severity === 'critical') return <ShieldCheck className="w-4 h-4 text-red-500" />;
  if (severity === 'warning')  return <AlertTriangle className="w-4 h-4 text-amber-500" />;
  return <Info className="w-4 h-4 text-blue-500" />;
};

const severityBg: Record<string, string> = {
  critical: 'bg-red-50 dark:bg-red-900/20',
  warning:  'bg-amber-50 dark:bg-amber-900/20',
  info:     'bg-blue-50 dark:bg-blue-900/20',
};

const getTimeAgo = (ts: number) => {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { notifications, markAsRead, dismiss, dismissAll, getUnreadCount } = useNotificationStore();
  const unread = getUnreadCount();

  const handleClick = (n: StoredNotification) => {
    markAsRead(n.id);
    if (n.customer_id) {
      setOpen(false);
      router.push(`/customers/${n.customer_id}`);
    }
  };

  return (
    <>
      {/* Bell button */}
      <button
        onClick={() => setOpen(o => !o)}
        className="relative p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-all"
      >
        <Bell className="w-5 h-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center animate-pulse">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="fixed right-4 top-14 w-96 max-h-[580px] bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 z-50 flex flex-col"
            style={{ animation: 'slideDown 0.2s ease-out' }}>

            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-t-2xl">
              <div>
                <h3 className="font-bold text-gray-900 dark:text-white">Notifications</h3>
                <p className="text-xs text-gray-500">{unread} unread</p>
              </div>
              <div className="flex items-center gap-1">
                {notifications.length > 0 && (
                  <button
                    onClick={dismissAll}
                    className="flex items-center gap-1 text-xs px-2 py-1 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <CheckCheck className="w-3.5 h-3.5" /> Clear all
                  </button>
                )}
                <button onClick={() => setOpen(false)} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-gray-400">
                  <Bell className="w-10 h-10 mb-3 opacity-30" />
                  <p className="text-sm font-medium">All caught up!</p>
                  <p className="text-xs">No notifications</p>
                </div>
              ) : (
                notifications.map(n => (
                  <div
                    key={n.id}
                    onClick={() => handleClick(n)}
                    className={`flex gap-3 p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${!n.read ? severityBg[n.severity] ?? '' : ''}`}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      <SeverityIcon severity={n.severity} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-sm font-semibold truncate ${!n.read ? 'text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'}`}>
                          {n.title}
                        </p>
                        <button
                          onClick={e => { e.stopPropagation(); dismiss(n.id); }}
                          className="flex-shrink-0 text-gray-300 hover:text-red-500 transition-colors"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.message}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {n.customer_name && (
                          <span className="flex items-center gap-0.5 text-xs px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-300 rounded-full">
                            {n.customer_name}
                            {n.customer_id && <ExternalLink className="w-2.5 h-2.5 opacity-60" />}
                          </span>
                        )}
                        <span className="text-xs text-gray-400">{getTimeAgo(n.timestamp)}</span>
                        {!n.read && <span className="w-1.5 h-1.5 bg-blue-500 rounded-full" />}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      <style jsx>{`
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </>
  );
}
