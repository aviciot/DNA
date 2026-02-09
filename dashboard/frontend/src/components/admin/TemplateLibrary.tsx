"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Upload,
  FileText,
  Download,
  Trash2,
  RefreshCw,
  Check,
  X,
  Loader2,
  FolderOpen,
  Hammer,
  Eye,
} from "lucide-react";
import { TemplateUploadProgress } from "../TemplateUploadProgress";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface ISOStandard {
  id: string;
  code: string;
  name: string;
  active: boolean;
}

interface TemplateFile {
  id: string;
  filename: string;
  original_filename: string;
  file_size_bytes: number;
  description: string | null;
  version: string | null;
  status: string;
  uploaded_at: string;
  built_templates_count: number;
}

export default function TemplateLibrary() {
  const [templates, setTemplates] = useState<TemplateFile[]>([]);
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [buildingTaskId, setBuildingTaskId] = useState<string | null>(null);
  const [buildingFileName, setBuildingFileName] = useState<string>("");
  const [buildingFileId, setBuildingFileId] = useState<string | null>(null); // Track which file is building

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDescription, setUploadDescription] = useState("");
  const [uploadVersion, setUploadVersion] = useState("");

  useEffect(() => {
    loadTemplates();
    loadISOStandards();
  }, []);

  const loadTemplates = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/template-files`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setTemplates(response.data);
    } catch (error) {
      console.error("Failed to load templates:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadISOStandards = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/iso-standards?active_only=true`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setISOStandards(response.data);
    } catch (error) {
      console.error("Failed to load ISO standards:", error);
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) {
      alert("Please select a file");
      return;
    }

    setUploading(true);

    try {
      const token = localStorage.getItem("access_token");
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("description", uploadDescription);
      formData.append("version", uploadVersion);

      await axios.post(`${API_BASE}/api/v1/template-files/upload`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data",
        },
      });

      // Reset form
      setUploadFile(null);
      setUploadDescription("");
      setUploadVersion("");
      setShowUploadModal(false);

      // Reload templates
      loadTemplates();

      alert("Reference document uploaded successfully! Click 'Build' to parse it with AI.");
    } catch (error: any) {
      console.error("Upload failed:", error);
      alert(`Upload failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${API_BASE}/api/v1/template-files/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      loadTemplates();
      alert("Template deleted successfully!");
    } catch (error: any) {
      console.error("Delete failed:", error);
      alert(`Delete failed: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleBuild = async (id: string, filename: string) => {
    // Prevent duplicate clicks
    if (buildingFileId === id) {
      console.log(`Already building file ${id}`);
      return;
    }

    try {
      setBuildingFileId(id); // Mark as building

      const token = localStorage.getItem("access_token");
      const response = await axios.post(
        `${API_BASE}/api/v1/template-files/${id}/build`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Show progress dialog
      setBuildingTaskId(response.data.task_id);
      setBuildingFileName(filename);

      // Show message if task was already in progress
      if (response.data.message) {
        console.log(response.data.message);
      }
    } catch (error: any) {
      console.error("Build failed:", error);
      alert(`Build failed: ${error.response?.data?.detail || error.message}`);
      setBuildingFileId(null); // Clear building state on error
    }
  };

  const handleBuildComplete = () => {
    setBuildingTaskId(null);
    setBuildingFileName("");
    setBuildingFileId(null); // Clear building state
    loadTemplates(); // Refresh to show updated built_templates_count
  };

  const handleBuildError = (error: string) => {
    alert(`Template parsing failed: ${error}`);
    setBuildingTaskId(null);
    setBuildingFileName("");
    setBuildingFileId(null); // Clear building state
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Upload Button */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Reference Documents
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Upload source .docx files, then build templates using AI
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <Upload className="w-4 h-4" />
          <span>Upload Document</span>
        </button>
      </div>

      {/* Templates Table */}
      {templates.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
          <FolderOpen className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No reference documents uploaded yet
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Upload your first .docx file to get started
          </p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Document</span>
          </button>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  File
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Uploaded
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Built Templates
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {templates.map((template) => (
                <tr key={template.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <FileText className="w-5 h-5 text-blue-500" />
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {template.original_filename}
                        </p>
                        {template.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {template.description}
                          </p>
                        )}
                        {template.version && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            v{template.version}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                    {formatFileSize(template.file_size_bytes)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                    {formatDate(template.uploaded_at)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {template.built_templates_count}
                      </span>
                      {template.built_templates_count > 0 && (
                        <Check className="w-4 h-4 text-green-500" />
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end space-x-2">
                      <button
                        onClick={() => handleBuild(template.id, template.original_filename)}
                        disabled={buildingFileId === template.id}
                        title={buildingFileId === template.id ? "Building..." : "Build Template (Parse with AI)"}
                        className={`p-1.5 rounded transition-colors ${
                          buildingFileId === template.id
                            ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                            : 'text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30'
                        }`}
                      >
                        {buildingFileId === template.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Hammer className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDelete(template.id, template.original_filename)}
                        title="Delete"
                        className="p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex justify-between items-center p-6 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                Upload Reference Document
              </h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {/* Info Box */}
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                <p className="text-sm text-blue-900 dark:text-blue-100">
                  <strong>Note:</strong> After uploading, click "Build" to parse the document with AI.
                  You'll assign ISO standards to individual templates in the Template Catalog.
                </p>
              </div>

              {/* File Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Word Document (.docx) *
                </label>
                <input
                  type="file"
                  accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                {uploadFile && (
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    Selected: {uploadFile.name} ({formatFileSize(uploadFile.size)})
                  </p>
                )}
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Description (Optional)
                </label>
                <input
                  type="text"
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  placeholder="e.g., Quality and Security Procedures Manual"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                />
              </div>

              {/* Version */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Version (Optional)
                </label>
                <input
                  type="text"
                  value={uploadVersion}
                  onChange={(e) => setUploadVersion(e.target.value)}
                  placeholder="e.g., v1.0, 2024-Q1"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setShowUploadModal(false)}
                disabled={uploading}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={uploading || !uploadFile}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Uploading...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    <span>Upload</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Build Progress Modal */}
      {buildingTaskId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-2xl">
            <TemplateUploadProgress
              taskId={buildingTaskId}
              onComplete={handleBuildComplete}
              onError={handleBuildError}
              onCancel={() => {
                setBuildingTaskId(null);
                setBuildingFileName("");
                setBuildingFileId(null); // Clear building state
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
