"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Database,
  Server,
  Cpu,
  Wifi,
  WifiOff,
  XCircle,
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

const getStatusIcon = (status: string, severity: string) => {
  if (status === "healthy") {
    return <CheckCircle className="w-5 h-5 text-green-500" />;
  } else if (severity === "critical") {
    return <XCircle className="w-5 h-5 text-red-500" />;
  } else if (severity === "error") {
    return <AlertCircle className="w-5 h-5 text-red-400" />;
  } else if (severity === "warning") {
    return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
  }
  return <Activity className="w-5 h-5 text-blue-500" />;
};

const getComponentIcon = (component: string) => {
  switch (component) {
    case "database":
      return <Database className="w-5 h-5" />;
    case "redis":
      return <Server className="w-5 h-5" />;
    case "backend":
      return <Cpu className="w-5 h-5" />;
    case "ai-worker":
      return <Cpu className="w-5 h-5" />;
    default:
      return <Activity className="w-5 h-5" />;
  }
};

const getComponentDisplayName = (component: string): string => {
  const names: Record<string, string> = {
    database: "Database (PostgreSQL)",
    redis: "Redis Cache",
    backend: "Backend API",
    "ai-worker": "AI Worker Service",
  };
  return names[component] || component;
};

const getStatusColor = (status: string, severity: string): string => {
  if (status === "healthy") return "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800";
  if (severity === "critical") return "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800";
  if (severity === "error") return "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800";
  if (severity === "warning") return "bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800";
  return "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800";
};

export default function SystemHealth() {
  const [componentStatuses, setComponentStatuses] = useState<ComponentStatuses>({});
  const [alerts, setAlerts] = useState<HealthAlert[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectDelayRef = useRef(3000);

  const connect = useCallback(() => {
    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.hostname}:8400/ws/system/health`;

      console.log("Connecting to System Health WebSocket:", wsUrl);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("System Health WebSocket connected");
        setIsConnected(true);
        reconnectDelayRef.current = 3000; // Reset delay on successful connection
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "subscribed") {
            console.log("Subscribed to health channel:", data.channel);
            return;
          }

          if (data.type === "pong") {
            return; // Ignore pong messages
          }

          // Handle health alert
          const alert: HealthAlert = {
            component: data.component,
            status: data.status,
            message: data.message,
            severity: data.severity,
            timestamp: data.timestamp,
            metadata: data.metadata,
          };

          // Update component status
          setComponentStatuses((prev) => ({
            ...prev,
            [alert.component]: {
              status: alert.status,
              severity: alert.severity,
              message: alert.message,
              lastUpdate: alert.timestamp,
            },
          }));

          // Add to alerts list (keep last 50)
          setAlerts((prev) => [alert, ...prev].slice(0, 50));
        } catch (error) {
          console.error("Error parsing health message:", error);
        }
      };

      ws.onerror = (error) => {
        console.error("System Health WebSocket error:", error);
        setIsConnected(false);
      };

      ws.onclose = () => {
        console.log("System Health WebSocket disconnected");
        setIsConnected(false);
        wsRef.current = null;

        // Reconnect with exponential backoff
        const currentDelay = reconnectDelayRef.current;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 60000);
        }, currentDelay);
      };
    } catch (error) {
      console.error("Error creating WebSocket connection:", error);
      setIsConnected(false);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    } catch {
      return timestamp;
    }
  };

  const sortedComponents = Object.entries(componentStatuses).sort((a, b) => {
    // Sort by severity: critical > error > warning > healthy
    const severityOrder: Record<string, number> = {
      critical: 0,
      error: 1,
      warning: 2,
      info: 3,
    };
    const severityA = severityOrder[a[1].severity] ?? 4;
    const severityB = severityOrder[b[1].severity] ?? 4;
    return severityA - severityB;
  });

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div
        className={`flex items-center space-x-2 px-4 py-3 rounded-lg border ${
          isConnected
            ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
            : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
        }`}
      >
        {isConnected ? (
          <>
            <Wifi className="w-5 h-5 text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium text-green-900 dark:text-green-100">
              Connected to Health Monitor
            </span>
          </>
        ) : (
          <>
            <WifiOff className="w-5 h-5 text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-red-900 dark:text-red-100">
              Disconnected - Reconnecting...
            </span>
          </>
        )}
      </div>

      {/* Component Status Cards */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          System Components
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedComponents.length === 0 ? (
            <div className="col-span-2 text-center py-8 text-gray-500 dark:text-gray-400">
              Waiting for health updates...
            </div>
          ) : (
            sortedComponents.map(([component, status]) => (
              <div
                key={component}
                className={`border rounded-lg p-4 ${getStatusColor(status.status, status.severity)}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    {getComponentIcon(component)}
                    <div>
                      <h4 className="font-medium text-gray-900 dark:text-white">
                        {getComponentDisplayName(component)}
                      </h4>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                        {formatTimestamp(status.lastUpdate)}
                      </p>
                    </div>
                  </div>
                  {getStatusIcon(status.status, status.severity)}
                </div>
                <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">
                  {status.message}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Recent Alerts */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Recent Alerts
        </h3>
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {alerts.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              No alerts yet
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto">
              {alerts.map((alert, index) => (
                <div key={index} className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3 flex-1">
                      {getStatusIcon(alert.status, alert.severity)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-gray-900 dark:text-white">
                            {getComponentDisplayName(alert.component)}
                          </span>
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              alert.status === "healthy"
                                ? "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300"
                                : alert.severity === "critical"
                                ? "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300"
                                : alert.severity === "error"
                                ? "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300"
                                : alert.severity === "warning"
                                ? "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300"
                                : "bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300"
                            }`}
                          >
                            {alert.severity}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                          {alert.message}
                        </p>
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
