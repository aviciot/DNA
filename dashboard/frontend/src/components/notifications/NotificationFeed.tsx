'use client';

import { useEffect, useState } from 'react';
import { StoredNotification } from '@/stores/notificationStore';
import { X, ShieldAlert, AlertTriangle, Info } from 'lucide-react';

interface Props {
  notifications: StoredNotification[];
  onDismiss: (id: string) => void;
  onDismissAll: () => void;
}

const AUTO_DISMISS: Record<string, number> = { critical: 15000, warning: 8000, info: 5000 };

const severityStyles: Record<string, string> = {
  critical: 'from-red-500 to-red-600 border-red-400',
  warning:  'from-amber-500 to-amber-600 border-amber-400',
  info:     'from-blue-500 to-blue-600 border-blue-400',
};

const SeverityIcon = ({ severity }: { severity: string }) => {
  if (severity === 'critical') return <ShieldAlert className="w-5 h-5" />;
  if (severity === 'warning')  return <AlertTriangle className="w-5 h-5" />;
  return <Info className="w-5 h-5" />;
};

const getTimeAgo = (ts: number) => {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
};

export default function NotificationFeed({ notifications, onDismiss, onDismissAll }: Props) {
  const visible = notifications.slice(0, 5);

  useEffect(() => {
    const timers = visible.map(n => {
      if (n.severity === 'critical') return null;
      return setTimeout(() => onDismiss(n.id), AUTO_DISMISS[n.severity] ?? 5000);
    });
    return () => timers.forEach(t => t && clearTimeout(t));
  }, [notifications]);

  if (!visible.length) return null;

  return (
    <div className="fixed left-6 bottom-6 z-[9999] flex flex-col gap-3 max-w-sm w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-500 bg-white/80 backdrop-blur px-3 py-1 rounded-full shadow border border-gray-200">
          {visible.length} alert{visible.length > 1 ? 's' : ''}
        </span>
        <button
          onClick={onDismissAll}
          className="text-xs text-gray-500 hover:text-red-600 bg-white/80 backdrop-blur px-3 py-1 rounded-full shadow border border-gray-200 transition-colors"
        >
          Clear all
        </button>
      </div>

      {visible.map((n, i) => (
        <div
          key={n.id}
          className={`relative overflow-hidden rounded-2xl shadow-2xl border-2 bg-gradient-to-r ${severityStyles[n.severity] ?? severityStyles.info} text-white`}
          style={{ animation: i === 0 ? 'slideInLeft 0.3s ease-out' : 'none' }}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent" />
          <div className="relative p-4">
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="flex items-center gap-2">
                <SeverityIcon severity={n.severity} />
                <div>
                  <p className="font-bold text-sm leading-tight">{n.title}</p>
                  {n.customer_name && (
                    <p className="text-xs opacity-80 mt-0.5">{n.customer_name}</p>
                  )}
                </div>
              </div>
              <button
                onClick={() => onDismiss(n.id)}
                className="text-white/70 hover:text-white hover:bg-white/20 rounded-full p-1 transition-all flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-sm opacity-90 leading-snug mb-2">{n.message}</p>
            <p className="text-xs opacity-70">{getTimeAgo(n.timestamp)}</p>
          </div>
          {n.severity !== 'critical' && (
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20">
              <div
                className="h-full bg-white/50"
                style={{ animation: `shrink ${(AUTO_DISMISS[n.severity] ?? 5000) / 1000}s linear forwards` }}
              />
            </div>
          )}
        </div>
      ))}

      <style jsx>{`
        @keyframes slideInLeft {
          from { transform: translateX(-110%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
        @keyframes shrink {
          from { transform: scaleX(1); transform-origin: left; }
          to   { transform: scaleX(0); transform-origin: left; }
        }
      `}</style>
    </div>
  );
}
