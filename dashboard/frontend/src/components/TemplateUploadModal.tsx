/**
 * TemplateUploadModal Component
 * ===============================
 *
 * Modal for uploading Word documents and initiating template parsing.
 * Shows file selection, upload progress, and then parsing progress.
 *
 * Usage:
 * ```tsx
 * <TemplateUploadModal
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   onComplete={(result) => console.log('Done!', result)}
 * />
 * ```
 */

"use client";

import { useState, useRef } from 'react';
import { TemplateUploadProgress } from './TemplateUploadProgress';
import { Upload, X, FileText, AlertCircle } from 'lucide-react';
import axios from 'axios';

interface TemplateUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete?: (result: any) => void;
  onError?: (error: string) => void;
}

type UploadState = 'selecting' | 'uploading' | 'parsing' | 'complete' | 'error';

export function TemplateUploadModal({
  isOpen,
  onClose,
  onComplete,
  onError,
}: TemplateUploadModalProps) {
  const [state, setState] = useState<UploadState>('selecting');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isoStandard, setIsoStandard] = useState('ISO 9001:2015');
  const [customRules, setCustomRules] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8400';

  if (!isOpen) return null;

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.name.endsWith('.docx') && !file.name.endsWith('.doc')) {
      setError('Please select a Word document (.docx or .doc)');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      return;
    }

    setSelectedFile(file);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setState('uploading');
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('iso_standard', isoStandard);
      if (customRules) {
        formData.append('custom_rules', customRules);
      }

      // Get auth token from localStorage
      const token = localStorage.getItem('token');

      const response = await axios.post(
        `${apiUrl}/api/v1/templates/upload`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
            'Authorization': token ? `Bearer ${token}` : '',
          },
          onUploadProgress: (progressEvent) => {
            const progress = progressEvent.total
              ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
              : 0;
            setUploadProgress(progress);
          },
        }
      );

      // Upload successful, extract task_id
      const data = response.data;
      setTaskId(data.task_id);
      setState('parsing');
    } catch (err: any) {
      console.error('Upload failed:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Upload failed';
      setError(errorMessage);
      setState('error');
      onError?.(errorMessage);
    }
  };

  const handleParsingComplete = (result: any) => {
    setState('complete');
    onComplete?.(result);
    // Don't auto-close - let user click "Done" button
  };

  const handleParsingError = (errorMsg: string, errorType: string) => {
    setError(`Parsing failed: ${errorMsg}`);
    setState('error');
    onError?.(`Parsing failed: ${errorMsg}`);
  };

  const handleClose = () => {
    // Reset state
    setState('selecting');
    setSelectedFile(null);
    setUploadProgress(0);
    setTaskId(null);
    setError(null);
    setCustomRules('');
    onClose();
  };

  const renderContent = () => {
    if (state === 'parsing' && taskId) {
      return (
        <TemplateUploadProgress
          taskId={taskId}
          onComplete={handleParsingComplete}
          onError={handleParsingError}
          onCancel={handleClose}
        />
      );
    }

    if (state === 'uploading') {
      return (
        <div className="space-y-4">
          <div className="flex items-center space-x-3">
            <Upload className="w-6 h-6 text-blue-500 animate-bounce" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Uploading Document...
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {selectedFile?.name}
              </p>
            </div>
          </div>

          {/* Upload Progress Bar */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Upload Progress
              </span>
              <span className="text-sm font-semibold text-blue-600 dark:text-blue-400">
                {uploadProgress}%
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
              <div
                className="bg-blue-600 dark:bg-blue-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        </div>
      );
    }

    if (state === 'error') {
      return (
        <div className="space-y-4">
          <div className="flex items-center space-x-3">
            <AlertCircle className="w-8 h-8 text-red-500" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Upload Failed
              </h3>
              <p className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setState('selecting');
              setError(null);
            }}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      );
    }

    // File selection
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Upload ISO Template
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Select a Word document (.docx) containing your ISO certification template
          </p>
        </div>

        {/* ISO Standard Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            ISO Standard
          </label>
          <select
            value={isoStandard}
            onChange={(e) => setIsoStandard(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="ISO 9001:2015">ISO 9001:2015 - Quality Management</option>
            <option value="ISO 27001:2022">ISO 27001:2022 - Information Security</option>
            <option value="ISO 14001:2015">ISO 14001:2015 - Environmental Management</option>
            <option value="ISO 45001:2018">ISO 45001:2018 - Occupational Health & Safety</option>
            <option value="Other">Other</option>
          </select>
        </div>

        {/* Custom Rules (Optional) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Custom Parsing Rules (Optional)
          </label>
          <textarea
            value={customRules}
            onChange={(e) => setCustomRules(e.target.value)}
            placeholder="Enter any special instructions for parsing this document..."
            rows={3}
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </div>

        {/* File Selection */}
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 hover:border-blue-500 dark:hover:border-blue-400 transition-colors"
          >
            <div className="flex flex-col items-center space-y-3">
              <FileText className="w-12 h-12 text-gray-400" />
              <div className="text-center">
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  {selectedFile ? selectedFile.name : 'Click to select a file'}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Word documents only (.docx, .doc) - Max 10MB
                </p>
              </div>
            </div>
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex space-x-3">
          <button
            onClick={handleClose}
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!selectedFile}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center justify-center space-x-2"
          >
            <Upload className="w-4 h-4" />
            <span>Upload & Parse</span>
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={state === 'selecting' ? handleClose : undefined}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full">
          {/* Close button (only show when not parsing) */}
          {state !== 'parsing' && state !== 'uploading' && (
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            </button>
          )}

          {/* Content */}
          <div className="p-6">
            {renderContent()}
          </div>
        </div>
      </div>
    </div>
  );
}
