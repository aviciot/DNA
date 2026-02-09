/**
 * TemplateUploadProgress Component
 * ==================================
 *
 * Displays real-time progress for template parsing tasks.
 * Shows progress bar, current step, ETA, and result summary.
 *
 * Usage:
 * ```tsx
 * <TemplateUploadProgress
 *   taskId={taskId}
 *   onComplete={(result) => console.log('Done!', result)}
 *   onError={(error) => console.error('Failed:', error)}
 *   onCancel={() => console.log('Cancelled')}
 * />
 * ```
 */

"use client";

import { useEffect } from 'react';
import { useTaskProgress } from '@/hooks/useTaskProgress';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  FileText,
  ListChecks,
  DollarSign,
  X,
  AlertCircle,
  RefreshCw,
  Sparkles,
} from 'lucide-react';

interface TemplateUploadProgressProps {
  taskId: string;
  onComplete?: (result: any) => void;
  onError?: (error: string, errorType: string) => void;
  onCancel?: () => void;
  className?: string;
}

export function TemplateUploadProgress({
  taskId,
  onComplete,
  onError,
  onCancel,
  className = '',
}: TemplateUploadProgressProps) {
  const {
    progress,
    currentStep,
    etaMessage,
    elapsedSeconds,
    status,
    error,
    errorType,
    resultSummary,
    reconnect,
  } = useTaskProgress(taskId);

  // Call callbacks when status changes
  // NOTE: onComplete is NOT called automatically - let user click "Done" button
  // This allows them to see the success screen with results

  useEffect(() => {
    if (status === 'failed' && error && onError) {
      onError(error, errorType || 'unknown');
    }
  }, [status, error, errorType, onError]);

  // Format elapsed time
  const formatElapsedTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  // Render based on status
  const renderContent = () => {
    if (status === 'completed') {
      return (
        <div className="space-y-6">
          {/* Success Header */}
          <div className="flex items-center space-x-3">
            <CheckCircle2 className="w-8 h-8 text-green-500" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Template Parsed Successfully!
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Your document has been analyzed and is ready to use
              </p>
            </div>
          </div>

          {/* Result Summary */}
          {resultSummary && (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-green-900 dark:text-green-100 mb-3">
                Template Details
              </h4>
              <div className="grid grid-cols-2 gap-4">
                {(resultSummary.fixed_sections !== undefined || resultSummary.sections !== undefined) && (
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-green-600 dark:text-green-400" />
                    <div>
                      <p className="text-xs text-green-600 dark:text-green-400">Fixed Sections</p>
                      <p className="text-sm font-semibold text-green-900 dark:text-green-100">
                        {resultSummary.fixed_sections || resultSummary.sections || 0}
                      </p>
                    </div>
                  </div>
                )}
                {(resultSummary.fillable_sections !== undefined || resultSummary.fields !== undefined) && (
                  <div className="flex items-center space-x-2">
                    <ListChecks className="w-4 h-4 text-green-600 dark:text-green-400" />
                    <div>
                      <p className="text-xs text-green-600 dark:text-green-400">Fillable Sections</p>
                      <p className="text-sm font-semibold text-green-900 dark:text-green-100">
                        {resultSummary.fillable_sections || resultSummary.fields || 0}
                      </p>
                    </div>
                  </div>
                )}
                {resultSummary.completion_estimate_minutes !== undefined && (
                  <div className="flex items-center space-x-2">
                    <Clock className="w-4 h-4 text-green-600 dark:text-green-400" />
                    <div>
                      <p className="text-xs text-green-600 dark:text-green-400">Est. Time</p>
                      <p className="text-sm font-semibold text-green-900 dark:text-green-100">
                        ~{resultSummary.completion_estimate_minutes} min
                      </p>
                    </div>
                  </div>
                )}
                {resultSummary.cost_usd !== undefined && (
                  <div className="flex items-center space-x-2">
                    <DollarSign className="w-4 h-4 text-green-600 dark:text-green-400" />
                    <div>
                      <p className="text-xs text-green-600 dark:text-green-400">Cost</p>
                      <p className="text-sm font-semibold text-green-900 dark:text-green-100">
                        ${resultSummary.cost_usd.toFixed(4)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* LLM Model Info */}
          {resultSummary && resultSummary.llm_model && (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                <div className="flex-1">
                  <p className="text-xs text-blue-600 dark:text-blue-400 font-medium">Parsed with AI</p>
                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
                    {resultSummary.llm_provider === 'gemini' ? 'Google Gemini' :
                     resultSummary.llm_provider === 'anthropic' ? 'Anthropic Claude' :
                     resultSummary.llm_provider || 'AI'} - {resultSummary.llm_model}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Processing Time */}
          <div className="text-xs text-gray-500 dark:text-gray-400 text-center">
            Processed in {formatElapsedTime(elapsedSeconds)}
          </div>

          {/* Action Button */}
          <div className="pt-4">
            <button
              onClick={() => {
                // Call onComplete to let parent know we're done (e.g., refresh list)
                if (onComplete && resultSummary) {
                  onComplete(resultSummary);
                }
                // Then close the modal
                onCancel?.();
              }}
              className="w-full px-4 py-3 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center space-x-2"
            >
              <CheckCircle2 className="w-5 h-5" />
              <span>Done</span>
            </button>
          </div>
        </div>
      );
    }

    if (status === 'failed') {
      return (
        <div className="space-y-4">
          {/* Error Header */}
          <div className="flex items-center space-x-3">
            <XCircle className="w-8 h-8 text-red-500" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Parsing Failed
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {error || 'An error occurred while processing your document'}
              </p>
            </div>
          </div>

          {/* Error Type Badge */}
          {errorType && (
            <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300">
              {errorType.replace(/_/g, ' ').toUpperCase()}
            </div>
          )}

          {/* Retry Button */}
          <button
            onClick={reconnect}
            className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Retry</span>
          </button>
        </div>
      );
    }

    if (status === 'disconnected' || status === 'connecting') {
      return (
        <div className="space-y-4">
          {/* Connection Status */}
          <div className="flex items-center space-x-3">
            {status === 'connecting' ? (
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            ) : (
              <AlertCircle className="w-8 h-8 text-yellow-500" />
            )}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {status === 'connecting' ? 'Initializing Parser...' : 'Connection Lost'}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {status === 'connecting'
                  ? 'Preparing to analyze your document'
                  : 'Attempting to reconnect to server...'}
              </p>
            </div>
          </div>

          {status === 'disconnected' && (
            <>
              {/* Loading Spinner */}
              <div className="flex justify-center">
                <Loader2 className="w-8 h-8 text-yellow-500 animate-spin" />
              </div>

              <button
                onClick={reconnect}
                className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Retry Connection</span>
              </button>
            </>
          )}
        </div>
      );
    }

    // Processing or Pending
    return (
      <div className="space-y-6">
        {/* Progress Bar */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {currentStep}
            </span>
            <span className="text-sm font-semibold text-blue-600 dark:text-blue-400">
              {progress}%
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
            <div
              className="bg-blue-600 dark:bg-blue-500 h-full rounded-full transition-all duration-500 ease-out relative overflow-hidden"
              style={{ width: `${progress}%` }}
            >
              {/* Animated shine effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"></div>
            </div>
          </div>
        </div>

        {/* Time Info */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2 text-gray-600 dark:text-gray-400">
            <Clock className="w-4 h-4" />
            <span>Elapsed: {formatElapsedTime(elapsedSeconds)}</span>
          </div>
          {etaMessage && (
            <div className="text-blue-600 dark:text-blue-400 font-medium">
              {etaMessage}
            </div>
          )}
        </div>

        {/* Processing Animation */}
        <div className="flex justify-center">
          <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
        </div>
      </div>
    );
  };

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-6 ${className}`}>
      {/* Header with Close Button */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white">
          Parsing Template
        </h2>
        {onCancel && status !== 'completed' && (
          <button
            onClick={onCancel}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title="Close"
          >
            <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          </button>
        )}
      </div>

      {/* Content */}
      {renderContent()}

      {/* Task ID (for debugging) */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-400 dark:text-gray-600 font-mono">
          Task ID: {taskId}
        </p>
      </div>
    </div>
  );
}

// Add shimmer animation to global CSS or Tailwind config
// @keyframes shimmer {
//   0% { transform: translateX(-100%); }
//   100% { transform: translateX(100%); }
// }
// .animate-shimmer { animation: shimmer 2s infinite; }
