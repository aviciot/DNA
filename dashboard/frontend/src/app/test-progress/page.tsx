/**
 * Test Progress Page
 * ===================
 *
 * Demo page for testing the TemplateUploadProgress component.
 * Can be accessed at /test-progress
 */

"use client";

import { useState } from 'react';
import { TemplateUploadProgress } from '@/components/TemplateUploadProgress';
import { Upload, X } from 'lucide-react';

export default function TestProgressPage() {
  const [taskId, setTaskId] = useState<string>('');
  const [showProgress, setShowProgress] = useState(false);
  const [testTaskId, setTestTaskId] = useState('');

  const handleStartTest = () => {
    if (!testTaskId.trim()) {
      alert('Please enter a task ID');
      return;
    }
    setTaskId(testTaskId);
    setShowProgress(true);
  };

  const handleComplete = (result: any) => {
    console.log('Task completed:', result);
    // Could navigate to template view here
  };

  const handleError = (error: string, errorType: string) => {
    console.error('Task failed:', error, errorType);
  };

  const handleCancel = () => {
    setShowProgress(false);
    setTaskId('');
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Template Upload Progress Test
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Test the real-time progress component with a task ID
          </p>
        </div>

        {/* Input Form */}
        {!showProgress && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 p-6">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Task ID
            </label>
            <input
              type="text"
              value={testTaskId}
              onChange={(e) => setTestTaskId(e.target.value)}
              placeholder="Enter task ID (UUID)"
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <div className="mt-4 flex space-x-4">
              <button
                onClick={handleStartTest}
                className="flex items-center space-x-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <Upload className="w-4 h-4" />
                <span>Start Monitoring</span>
              </button>
              <button
                onClick={() => setTestTaskId('test-uuid-' + Math.random().toString(36).substr(2, 9))}
                className="px-6 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-lg transition-colors"
              >
                Generate Random ID
              </button>
            </div>
            <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <p className="text-sm text-blue-900 dark:text-blue-100">
                <strong>How to test:</strong>
              </p>
              <ol className="mt-2 text-sm text-blue-800 dark:text-blue-200 list-decimal list-inside space-y-1">
                <li>Run the end-to-end test to create a real task</li>
                <li>Copy the task ID from the test output</li>
                <li>Paste it here and click "Start Monitoring"</li>
                <li>Watch the progress update in real-time</li>
              </ol>
            </div>
          </div>
        )}

        {/* Progress Component */}
        {showProgress && (
          <div>
            <TemplateUploadProgress
              taskId={taskId}
              onComplete={handleComplete}
              onError={handleError}
              onCancel={handleCancel}
            />
          </div>
        )}

        {/* Instructions */}
        {!showProgress && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Testing Instructions
            </h2>
            <div className="space-y-4 text-sm text-gray-600 dark:text-gray-400">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  1. Create a Real Task
                </h3>
                <pre className="bg-gray-100 dark:bg-gray-900 p-3 rounded text-xs overflow-x-auto">
                  {`cd DNA
python tests/test_end_to_end.py`}
                </pre>
                <p className="mt-2">
                  This will create a task and show its ID in the output.
                </p>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  2. Use the Task ID
                </h3>
                <p>
                  Copy the task ID from the test output and paste it into the field above.
                </p>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  3. Watch the Progress
                </h3>
                <p>
                  The component will connect via WebSocket and display:
                </p>
                <ul className="list-disc list-inside ml-4 mt-2 space-y-1">
                  <li>Real-time progress (0-100%)</li>
                  <li>Current processing step</li>
                  <li>Estimated time remaining</li>
                  <li>Elapsed time</li>
                  <li>Result summary on completion</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
