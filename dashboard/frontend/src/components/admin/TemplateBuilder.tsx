"use client";

import {
  Upload, FileText, Wand2, Eye, CheckCircle, XCircle,
  Edit2, Trash2, Plus, AlertCircle, Loader2, Download
} from "lucide-react";
import { useState, useEffect } from "react";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface ReplacementSuggestion {
  original_text: string;
  placeholder: string;
  question: string;
  question_context: string;
  field_type: string;
}

interface TemplateFile {
  id: string;
  file_name: string;
  file_type: string;
  uploaded_at: string;
}

interface AnalysisTask {
  task_id: string;
  status: string;
  progress: number;
  result?: {
    replacements: ReplacementSuggestion[];
  };
}

export default function TemplateBuilder() {
  const [step, setStep] = useState<'upload' | 'analyze' | 'review' | 'preview' | 'approve'>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedFileId, setUploadedFileId] = useState<string>('');
  const [analysisTaskId, setAnalysisTaskId] = useState<string>('');
  const [recommendations, setRecommendations] = useState<ReplacementSuggestion[]>([]);
  const [templateId, setTemplateId] = useState<string>('');
  const [templateName, setTemplateName] = useState<string>('');
  const [templateDescription, setTemplateDescription] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [taskStatus, setTaskStatus] = useState<AnalysisTask | null>(null);

  // Step 1: Upload File
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setError('');
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('file_type', 'reference');

      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE}/api/v1/template-files/upload`,
        formData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'multipart/form-data'
          }
        }
      );

      setUploadedFileId(response.data.id);
      setTemplateName(selectedFile.name.replace('.docx', ''));
      setStep('analyze');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Analyze
  const handleAnalyze = async () => {
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE}/api/v1/template-analysis/analyze`,
        { template_file_id: uploadedFileId },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setAnalysisTaskId(response.data.task_id);

      // Poll for task completion
      pollTaskStatus(response.data.task_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Analysis failed');
      setLoading(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const token = localStorage.getItem('access_token');

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(
          `${API_BASE}/api/v1/template-analysis/tasks/${taskId}/status`,
          { headers: { Authorization: `Bearer ${token}` } }
        );

        setTaskStatus(response.data);

        if (response.data.status === 'completed') {
          clearInterval(interval);
          // Fetch recommendations
          const recsResponse = await axios.get(
            `${API_BASE}/api/v1/template-analysis/${uploadedFileId}/recommendations`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          setRecommendations(recsResponse.data.replacements);
          setStep('review');
          setLoading(false);
        } else if (response.data.status === 'failed') {
          clearInterval(interval);
          setError(response.data.error || 'Analysis failed');
          setLoading(false);
        }
      } catch (err) {
        clearInterval(interval);
        setError('Failed to check task status');
        setLoading(false);
      }
    }, 2000); // Poll every 2 seconds
  };

  // Step 3: Review & Edit Recommendations
  const handleUpdateRecommendation = (index: number, field: keyof ReplacementSuggestion, value: string) => {
    const updated = [...recommendations];
    updated[index] = { ...updated[index], [field]: value };
    setRecommendations(updated);
  };

  const handleAddRecommendation = () => {
    setRecommendations([
      ...recommendations,
      {
        original_text: '',
        placeholder: '{{}}',
        question: '',
        question_context: '',
        field_type: 'text'
      }
    ]);
  };

  const handleDeleteRecommendation = (index: number) => {
    setRecommendations(recommendations.filter((_, i) => i !== index));
  };

  const handleSaveRecommendations = async () => {
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      await axios.put(
        `${API_BASE}/api/v1/template-analysis/${uploadedFileId}/recommendations`,
        { replacements: recommendations },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert('Recommendations saved!');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setLoading(false);
    }
  };

  // Step 4: Apply Recommendations
  const handleApply = async () => {
    if (!templateName.trim()) {
      setError('Template name is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE}/api/v1/template-analysis/${uploadedFileId}/apply`,
        {
          template_name: templateName,
          template_description: templateDescription
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setTemplateId(response.data.template_id);
      setStep('approve');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply');
    } finally {
      setLoading(false);
    }
  };

  // Step 5: Approve/Reject
  const handleApprove = async (approved: boolean) => {
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      await axios.post(
        `${API_BASE}/api/v1/template-analysis/${templateId}/approve`,
        { approved, notes: '' },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert(approved ? 'Template approved!' : 'Template rejected');
      // Reset workflow
      resetWorkflow();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve');
    } finally {
      setLoading(false);
    }
  };

  const resetWorkflow = () => {
    setStep('upload');
    setSelectedFile(null);
    setUploadedFileId('');
    setAnalysisTaskId('');
    setRecommendations([]);
    setTemplateId('');
    setTemplateName('');
    setTemplateDescription('');
    setTaskStatus(null);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Template Builder
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            AI-assisted template creation from reference documents
          </p>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {[
              { key: 'upload', label: 'Upload', icon: Upload },
              { key: 'analyze', label: 'Analyze', icon: Wand2 },
              { key: 'review', label: 'Review', icon: Edit2 },
              { key: 'approve', label: 'Approve', icon: CheckCircle }
            ].map((s, idx) => {
              const Icon = s.icon;
              const isActive = step === s.key;
              const isCompleted = ['upload', 'analyze', 'review', 'approve'].indexOf(step) > idx;

              return (
                <div key={s.key} className="flex items-center">
                  <div className={`flex items-center justify-center w-12 h-12 rounded-full ${
                    isActive ? 'bg-blue-600 text-white' :
                    isCompleted ? 'bg-green-600 text-white' :
                    'bg-gray-300 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                  }`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className={`ml-2 text-sm font-medium ${
                    isActive ? 'text-blue-600 dark:text-blue-400' :
                    isCompleted ? 'text-green-600 dark:text-green-400' :
                    'text-gray-600 dark:text-gray-400'
                  }`}>
                    {s.label}
                  </span>
                  {idx < 3 && (
                    <div className={`w-24 h-1 mx-4 ${
                      isCompleted ? 'bg-green-600' : 'bg-gray-300 dark:bg-gray-700'
                    }`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900 bg-opacity-20 border border-red-200 dark:border-red-800 rounded-lg flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mr-3 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
          {/* Step 1: Upload */}
          {step === 'upload' && (
            <div className="text-center">
              <FileText className="w-16 h-16 text-blue-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                Upload Reference Document
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-8">
                Upload a Word document (.docx) to analyze and convert into a template
              </p>

              <div className="max-w-md mx-auto">
                <label className="block w-full px-6 py-8 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:border-blue-500 dark:hover:border-blue-400 transition-colors">
                  <input
                    type="file"
                    accept=".docx"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-700 dark:text-gray-300">
                    {selectedFile ? selectedFile.name : 'Click to select file'}
                  </p>
                </label>

                {selectedFile && (
                  <button
                    onClick={handleUpload}
                    disabled={loading}
                    className="mt-6 w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-5 h-5 mr-2" />
                        Upload & Continue
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Step 2: Analyze */}
          {step === 'analyze' && (
            <div className="text-center">
              <Wand2 className="w-16 h-16 text-purple-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                AI Analysis
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-8">
                Let AI analyze the document and suggest placeholders
              </p>

              {!loading && !analysisTaskId && (
                <button
                  onClick={handleAnalyze}
                  className="px-8 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors flex items-center mx-auto"
                >
                  <Wand2 className="w-5 h-5 mr-2" />
                  Analyze Document
                </button>
              )}

              {loading && (
                <div className="max-w-md mx-auto">
                  <Loader2 className="w-12 h-12 text-purple-600 mx-auto mb-4 animate-spin" />
                  <p className="text-gray-700 dark:text-gray-300 mb-2">
                    {taskStatus?.status === 'processing' ? 'Analyzing document...' : 'Queued...'}
                  </p>
                  {taskStatus?.progress !== undefined && (
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-purple-600 h-2 rounded-full transition-all"
                        style={{ width: `${taskStatus.progress}%` }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 3: Review Recommendations */}
          {step === 'review' && (
            <div>
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Review AI Recommendations
                </h2>
                <div className="flex gap-2">
                  <button
                    onClick={handleAddRecommendation}
                    className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg flex items-center"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add
                  </button>
                  <button
                    onClick={handleSaveRecommendations}
                    disabled={loading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center disabled:opacity-50"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Save
                  </button>
                </div>
              </div>

              <div className="space-y-4 mb-8 max-h-[600px] overflow-y-auto">
                {recommendations.map((rec, idx) => (
                  <div key={idx} className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Original Text
                        </label>
                        <input
                          type="text"
                          value={rec.original_text}
                          onChange={(e) => handleUpdateRecommendation(idx, 'original_text', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Placeholder
                        </label>
                        <input
                          type="text"
                          value={rec.placeholder}
                          onChange={(e) => handleUpdateRecommendation(idx, 'placeholder', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Interview Question
                        </label>
                        <input
                          type="text"
                          value={rec.question}
                          onChange={(e) => handleUpdateRecommendation(idx, 'question', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Question Context
                        </label>
                        <textarea
                          value={rec.question_context}
                          onChange={(e) => handleUpdateRecommendation(idx, 'question_context', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                          rows={2}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Field Type
                        </label>
                        <select
                          value={rec.field_type}
                          onChange={(e) => handleUpdateRecommendation(idx, 'field_type', e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        >
                          <option value="text">Text</option>
                          <option value="textarea">Textarea</option>
                          <option value="date">Date</option>
                          <option value="email">Email</option>
                        </select>
                      </div>
                      <div className="flex items-end justify-end">
                        <button
                          onClick={() => handleDeleteRecommendation(idx)}
                          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  Template Details
                </h3>
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Template Name *
                    </label>
                    <input
                      type="text"
                      value={templateName}
                      onChange={(e) => setTemplateName(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      placeholder="e.g., ISMS 20 Patch Management"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Description
                    </label>
                    <input
                      type="text"
                      value={templateDescription}
                      onChange={(e) => setTemplateDescription(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      placeholder="Optional description"
                    />
                  </div>
                </div>

                <button
                  onClick={handleApply}
                  disabled={loading || !templateName.trim()}
                  className="w-full px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Creating Template...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5 mr-2" />
                      Apply & Create Template
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Approve */}
          {step === 'approve' && (
            <div className="text-center">
              <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                Template Created Successfully!
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-2">
                Template ID: <span className="font-mono text-sm">{templateId}</span>
              </p>
              <p className="text-gray-600 dark:text-gray-400 mb-8">
                Review and approve the template to make it available
              </p>

              <div className="flex gap-4 justify-center">
                <button
                  onClick={() => handleApprove(false)}
                  disabled={loading}
                  className="px-8 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center"
                >
                  <XCircle className="w-5 h-5 mr-2" />
                  Reject
                </button>
                <button
                  onClick={() => handleApprove(true)}
                  disabled={loading}
                  className="px-8 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Approving...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5 mr-2" />
                      Approve
                    </>
                  )}
                </button>
              </div>

              <button
                onClick={resetWorkflow}
                className="mt-8 text-blue-600 dark:text-blue-400 hover:underline"
              >
                Create Another Template
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
