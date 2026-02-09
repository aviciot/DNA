/**
 * useTaskProgress Hook
 * =====================
 *
 * Connects to WebSocket for real-time task progress updates.
 * Handles reconnection, error states, and automatic cleanup.
 *
 * Usage:
 * ```tsx
 * const { progress, currentStep, eta, status, error } = useTaskProgress(taskId);
 * ```
 */

import { useState, useEffect, useRef, useCallback } from 'react';

export interface TaskProgress {
  progress: number;  // 0-100
  currentStep: string;
  etaSeconds: number | null;
  etaMessage: string | null;
  elapsedSeconds: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'connecting' | 'disconnected';
  error: string | null;
  errorType: string | null;
  resultSummary: {
    sections?: number;
    fields?: number;
    fixed_sections?: number;
    fillable_sections?: number;
    required_fields?: number;
    completion_estimate_minutes?: number;
    cost_usd?: number;
    duration_seconds?: number;
    llm_provider?: string;
    llm_model?: string;
  } | null;
}

interface UseTaskProgressOptions {
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectInterval?: number; // milliseconds
  wsUrl?: string; // Override default WebSocket URL
}

const DEFAULT_OPTIONS: UseTaskProgressOptions = {
  autoConnect: true,
  reconnectAttempts: 5,
  reconnectInterval: 3000,
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8400',
};

export function useTaskProgress(
  taskId: string | null,
  options: UseTaskProgressOptions = {}
): TaskProgress & { reconnect: () => void; disconnect: () => void } {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  const [progress, setProgress] = useState<TaskProgress>({
    progress: 0,
    currentStep: 'Initializing...',
    etaSeconds: null,
    etaMessage: null,
    elapsedSeconds: 0,
    status: 'connecting',
    error: null,
    errorType: null,
    resultSummary: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectDelayRef = useRef(3000); // Start with 3 seconds, exponential backoff
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isTerminalStateRef = useRef(false); // Track if we're in a terminal state (completed/failed)

  const connect = useCallback(() => {
    if (!taskId) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const wsUrl = `${opts.wsUrl}/ws/tasks/${taskId}`;
      console.log(`[useTaskProgress] Connecting to ${wsUrl}`);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`[useTaskProgress] Connected to task ${taskId}`);
        reconnectCountRef.current = 0;
        reconnectDelayRef.current = 3000; // Reset delay on successful connection

        setProgress((prev) => ({
          ...prev,
          status: prev.status === 'connecting' ? 'pending' : prev.status,
        }));

        // Start heartbeat - send ping every 30 seconds
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
        }
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            console.log('[useTaskProgress] Sending ping');
            ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log(`[useTaskProgress] Received:`, data);

          const messageType = data.type;

          if (messageType === 'task_status') {
            // Initial task status
            setProgress((prev) => ({
              ...prev,
              status: data.status as TaskProgress['status'],
              progress: data.progress || 0,
              currentStep: data.current_step || prev.currentStep,
            }));
          } else if (messageType === 'subscribed') {
            // Subscription confirmation
            console.log(`[useTaskProgress] Subscribed to ${data.channel}`);
          } else if (messageType === 'pong') {
            // Heartbeat pong response
            console.log('[useTaskProgress] Received pong');
          } else if (messageType === 'progress_update') {
            // Progress update with ETA
            setProgress((prev) => ({
              ...prev,
              progress: data.progress || prev.progress,
              currentStep: data.current_step || prev.currentStep,
              etaSeconds: data.eta_seconds ?? prev.etaSeconds,
              etaMessage: data.eta_message ?? prev.etaMessage,
              elapsedSeconds: data.elapsed_seconds || prev.elapsedSeconds,
              status: 'processing',
              error: null,
              errorType: null,
            }));
          } else if (messageType === 'milestone') {
            // Major milestone reached
            console.log(`[useTaskProgress] Milestone: ${data.milestone}`);
            setProgress((prev) => ({
              ...prev,
              currentStep: data.milestone,
            }));
          } else if (messageType === 'task_complete') {
            // Task completed successfully
            isTerminalStateRef.current = true; // Mark as terminal state
            setProgress({
              progress: 100,
              currentStep: data.current_step || 'Completed!',
              etaSeconds: null,
              etaMessage: null,
              elapsedSeconds: data.elapsed_seconds || 0,
              status: 'completed',
              error: null,
              errorType: null,
              resultSummary: data.result_summary || null,
            });

            // Close WebSocket after completion
            setTimeout(() => {
              ws.close();
            }, 1000);
          } else if (messageType === 'task_error') {
            // Task failed with error
            isTerminalStateRef.current = true; // Mark as terminal state
            setProgress({
              progress: 0,
              currentStep: 'Failed',
              etaSeconds: null,
              etaMessage: null,
              elapsedSeconds: data.elapsed_seconds || 0,
              status: 'failed',
              error: data.error || 'Unknown error',
              errorType: data.error_type || 'unknown',
              resultSummary: null,
            });

            // Close WebSocket after error
            setTimeout(() => {
              ws.close();
            }, 1000);
          }
        } catch (err) {
          console.error('[useTaskProgress] Failed to parse message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('[useTaskProgress] WebSocket error:', event);
        setProgress((prev) => ({
          ...prev,
          status: 'disconnected',
          error: 'Connection error',
          errorType: 'connection_error',
        }));
      };

      ws.onclose = (event) => {
        console.log(`[useTaskProgress] Disconnected (code: ${event.code})`);

        // Don't reconnect if task is in a terminal state (completed or failed)
        if (isTerminalStateRef.current) {
          console.log('[useTaskProgress] Task in terminal state, not reconnecting');
          return;
        }

        // Attempt reconnection with exponential backoff
        if (reconnectCountRef.current < (opts.reconnectAttempts || 5)) {
          reconnectCountRef.current += 1;

          // Exponential backoff: 3s → 6s → 12s → 24s → 60s (max)
          const currentDelay = reconnectDelayRef.current;
          console.log(
            `[useTaskProgress] Reconnecting in ${currentDelay/1000}s (attempt ${reconnectCountRef.current}/${opts.reconnectAttempts})...`
          );

          setProgress((prev) => ({
            ...prev,
            status: 'connecting',
          }));

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
            // Double the delay for next time, max 60 seconds
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 60000);
          }, currentDelay);
        } else {
          console.error('[useTaskProgress] Max reconnection attempts reached');
          setProgress((prev) => ({
            ...prev,
            status: 'disconnected',
            error: 'Connection lost',
            errorType: 'connection_lost',
          }));
        }
      };
    } catch (err) {
      console.error('[useTaskProgress] Failed to create WebSocket:', err);
      setProgress((prev) => ({
        ...prev,
        status: 'disconnected',
        error: 'Failed to connect',
        errorType: 'connection_error',
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, opts.wsUrl, opts.reconnectAttempts, opts.reconnectInterval]);

  const disconnect = useCallback(() => {
    // Clear reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear heartbeat interval
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      console.log('[useTaskProgress] Manually disconnecting');
      wsRef.current.close();
      wsRef.current = null;
    }

    setProgress((prev) => ({
      ...prev,
      status: 'disconnected',
    }));
  }, []);

  const reconnect = useCallback(() => {
    console.log('[useTaskProgress] Manual reconnect triggered');
    disconnect();
    reconnectCountRef.current = 0;
    connect();
  }, [connect, disconnect]);

  useEffect(() => {
    if (opts.autoConnect && taskId) {
      connect();
    }

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, opts.autoConnect]);

  return {
    ...progress,
    reconnect,
    disconnect,
  };
}
