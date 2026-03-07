"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Activity, AlertCircle, AlertTriangle, CheckCircle,
  Database, Mail, Server, Cpu, Wifi, WifiOff, XCircle, Power, PowerOff, Globe, Clock,
} from "lucide-react";

interface HealthAlert {
  component: string;
  status: string;
  message: string;
  severity: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

interface ComponentStatus {
  status: string;
  severity: string;
  message: string;
  lastUpdate: string;
}

type ComponentStatuses = Record<string, ComponentStatus>;

// ── Known components — always rendered even if no event received ──────────────
const KNOWN_COMPONENTS: { key: string; label: string; icon: React.ReactNode; group?: string }[] = [
  { key: "database",           label: "Database (PostgreSQL)", icon: <Database className="w-5 h-5" /> },
  { key: "redis",              label: "Redis Cache",           icon: <Server className="w-5 h-5" /> },
  { key: "backend",            label: "Backend API",           icon: <Cpu className="w-5 h-5" /> },
  { key: "ai-worker",          label: "AI Worker Service",     icon: <Cpu className="w-5 h-5" /> },
  { key: "automation-service", label: "Automation Service",    icon: <Mail className="w-5 h-5" /> },
  { key: "customer-portal",    label: "Customer Portal",       icon: <Globe className="w-5 h-5" /> },
];

const STALE_MS = 120_000;

const PENDING: ComponentStatus = { status: "pending", severity: "warning", message: "Waiting for first report…", lastUpdate: "" };

const severityOrder: Record<string, number> = { critical: 0, error: 1, warning: 2, info: 3 };

const getStatusIcon = (status: string, severity: string, small = false) => {
  const cls = small ? "w-4 h-4" : "w-5 h-5";
  if (status === "pending") return <Clock className={`${cls} text-gray-400`} />;
  if (status === "stale")   return <AlertTriangle className={`${cls} text-orange-400`} />;
  if (status === "healthy") return <CheckCircle className={`${cls} text-green-500`} />;
  if (severity === "critical") return <XCircle className={`${cls} text-red-500`} />;
  if (severity === "error")    return <AlertCircle className={`${cls} text-red-400`} />;
  if (severity === "warning")  return <AlertTriangle className={`${cls} text-yellow-500`} />;
  return <Activity className={`${cls} text-blue-500`} />;
};

const getStatusColor = (status: string, severity: string): string => {
  if (status === "pending" || status === "stale") return "bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-700";
  if (status === "healthy") return "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800";
  if (severity === "critical" || severity === "error") return "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800";
  if (severity === "warning") return "bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800";
  return "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800";
};

export default function SystemHealth() {
  const [componentStatuses, setComponentStatuses] = useState<ComponentStatuses>({});
  const [alerts, setAlerts] = useState<HealthAlert[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [monitoringEnabled, setMonitoringEnabled] = useState(true);
  const [now, setNow] = useState(Date.now());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectDelayRef = useRef(3000);

  // Tick every 30s to re-evaluate stale status
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  const getEffectiveStatus = (key: string): ComponentStatus => {
    const s = componentStatuses[key];
    if (!s) return PENDING;
    if (s.lastUpdate && now - new Date(s.lastUpdate).getTime() > STALE_MS) {
      return { ...s, status: "stale", severity: "warning", message: `Last seen ${Math.round((now - new Date(s.lastUpdate).getTime()) / 60000)}m ago — may be down` };
    }
    return s;
  };

  const connect = useCallback(() => {
    if (!monitoringEnabled) return;
    try {
      const apiUrl = new URL(process.env.NEXT_PUBLIC_API_URL!);
      const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${apiUrl.host}/ws/system/health`);
      wsRef.current = ws;

      ws.onopen = () => { setIsConnected(true); reconnectDelayRef.current = 3000; };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "subscribed" || data.type === "pong") return;
          const alert: HealthAlert = {
            component: data.component, status: data.status,
            message: data.message, severity: data.severity,
            timestamp: data.timestamp, metadata: data.metadata,
          };
          setComponentStatuses(prev => ({
            ...prev,
            [alert.component]: { status: alert.status, severity: alert.severity, message: alert.message, lastUpdate: alert.timestamp },
          }));
          setAlerts(prev => [alert, ...prev].slice(0, 50));
        } catch { /* ignore */ }
      };

      ws.onerror = () => setIsConnected(false);
      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        if (monitoringEnabled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 60000);
          }, reconnectDelayRef.current);
        }
      };
    } catch { setIsConnected(false); }
  }, [monitoringEnabled]);

  useEffect(() => {
    if (monitoringEnabled) {
      connect();
    } else {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
      wsRef.current = null;
      setIsConnected(false);
    }
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [connect, monitoringEnabled]);

  const formatTimestamp = (ts: string) => {
    if (!ts) return "never";
    try { return new Date(ts).toLocaleTimeString(); } catch { return ts; }
  };

  // Other components (known + any unknown that arrived)
  const otherKnown = KNOWN_COMPONENTS;
  const unknownArrived = Object.keys(componentStatuses).filter(k => !KNOWN_COMPONENTS.find(c => c.key === k));
  const otherComponents = [
    ...otherKnown.map(c => ({ key: c.key, label: c.label, icon: c.icon, status: getEffectiveStatus(c.key) })),
    ...unknownArrived.map(k => ({ key: k, label: k, icon: <Activity className="w-5 h-5" />, status: getEffectiveStatus(k) })),
  ].sort((a, b) => (severityOrder[a.status.severity] ?? 4) - (severityOrder[b.status.severity] ?? 4));

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="flex items-center justify-between gap-4">
        <div className={`flex-1 flex items-center space-x-2 px-4 py-3 rounded-lg border ${
          !monitoringEnabled ? "bg-gray-50 border-gray-200"
          : isConnected ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
          : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
        }`}>
          {!monitoringEnabled ? <><PowerOff className="w-5 h-5 text-gray-600" /><span className="text-sm font-medium text-gray-900">Monitoring Disabled</span></>
          : isConnected ? <><Wifi className="w-5 h-5 text-green-600 dark:text-green-400" /><span className="text-sm font-medium text-green-900 dark:text-green-100">Connected to Health Monitor</span></>
          : <><WifiOff className="w-5 h-5 text-red-600 dark:text-red-400" /><span className="text-sm font-medium text-red-900 dark:text-red-100">Disconnected — Reconnecting…</span></>}
        </div>
        <button onClick={() => setMonitoringEnabled(!monitoringEnabled)}
          className={`flex items-center space-x-2 px-4 py-3 rounded-lg border transition-colors ${
            monitoringEnabled
              ? "bg-red-50 border-red-200 hover:bg-red-100 text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300"
              : "bg-green-50 border-green-200 hover:bg-green-100 text-green-700 dark:bg-green-900/20 dark:border-green-800 dark:text-green-300"
          }`}>
          {monitoringEnabled ? <><PowerOff className="w-4 h-4" /><span className="text-sm font-medium">Disable</span></>
                             : <><Power className="w-4 h-4" /><span className="text-sm font-medium">Enable</span></>}
        </button>
      </div>

      {/* Component Cards */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">System Components</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {otherComponents.map(({ key, label, icon, status }) => (
            <div key={key} className={`border rounded-lg p-4 ${getStatusColor(status.status, status.severity)}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  {icon}
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white">{label}</h4>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{formatTimestamp(status.lastUpdate)}</p>
                  </div>
                </div>
                {getStatusIcon(status.status, status.severity)}
              </div>
              <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">{status.message}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Alerts */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Alerts</h3>
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {alerts.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">No alerts yet</div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto">
              {alerts.map((alert, i) => (
                <div key={i} className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3 flex-1">
                      {getStatusIcon(alert.status, alert.severity)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900 dark:text-white">
                            {KNOWN_COMPONENTS.find(c => c.key === alert.component)?.label ?? alert.component}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            alert.status === "healthy" ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                            : alert.severity === "critical" || alert.severity === "error" ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                            : alert.severity === "warning" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
                            : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                          }`}>{alert.severity}</span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{alert.message}</p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400 ml-4 whitespace-nowrap">
                      {formatTimestamp(alert.timestamp)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
