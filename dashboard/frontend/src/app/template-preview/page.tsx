"use client";

import { useState } from "react";
import { Upload, FileText, Eye, Download, Loader2, CheckCircle, XCircle, AlertCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Field {
  name: string;
  label: string;
  type: string;
  required: boolean;
  evidence: boolean;
  evidence_filename?: string;
  locations: string[];
}

interface UploadResponse {
  template_id: string;
  filename: string;
  total_placeholders: number;
  fields: Field[];
}

interface PreviewResponse {
  preview_id: string;
  pdf_url: string;
  docx_url: string;
  success: boolean;
  error?: string;
}

export default function TemplatePreviewPage() {
  // State
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Template data
  const [templateId, setTemplateId] = useState<string>("");
  const [templateFilename, setTemplateFilename] = useState<string>("");
  const [fields, setFields] = useState<Field[]>([]);

  // Form data
  const [formData, setFormData] = useState<Record<string, any>>({});

  // Preview data
  const [previewId, setPreviewId] = useState<string>("");
  const [pdfUrl, setPdfUrl] = useState<string>("");
  const [docxUrl, setDocxUrl] = useState<string>("");

  // Error handling
  const [error, setError] = useState<string>("");

  // Get auth token
  const getAuthHeaders = () => {
    const token = localStorage.getItem("access_token");
    return {
      "Authorization": token ? `Bearer ${token}` : "",
    };
  };

  // Handle file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.docx')) {
      setError("Please upload a .docx file");
      return;
    }

    setError("");
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/api/v1/template-preview/upload-template`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data: UploadResponse = await response.json();

      setTemplateId(data.template_id);
      setTemplateFilename(data.filename);
      setFields(data.fields);
      setStep(2);

    } catch (err: any) {
      setError(err.message || "Failed to upload template");
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
    }
  };

  // Handle form field change
  const handleFieldChange = (fieldName: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));
  };

  // Handle image upload
  const handleImageUpload = async (fieldName: string, file: File) => {
    // For now, store the file path/name
    // In production, you'd upload to server and get URL
    setFormData(prev => ({
      ...prev,
      [fieldName]: file.name
    }));
  };

  // Generate preview
  const handleGeneratePreview = async () => {
    setError("");
    setGenerating(true);

    try {
      const response = await fetch(`${API_BASE}/api/v1/template-preview/generate-preview`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          template_id: templateId,
          filled_data: formData,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Preview generation failed");
      }

      const data: PreviewResponse = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Preview generation failed");
      }

      setPreviewId(data.preview_id);
      setPdfUrl(`${API_BASE}${data.pdf_url}`);
      setDocxUrl(`${API_BASE}${data.docx_url}`);
      setStep(3);

    } catch (err: any) {
      setError(err.message || "Failed to generate preview");
      console.error("Generation error:", err);
    } finally {
      setGenerating(false);
    }
  };

  // Reset and start over
  const handleReset = () => {
    setStep(1);
    setTemplateId("");
    setTemplateFilename("");
    setFields([]);
    setFormData({});
    setPreviewId("");
    setPdfUrl("");
    setDocxUrl("");
    setError("");
  };

  // Render field input based on type
  const renderFieldInput = (field: Field) => {
    const value = formData[field.name] || "";

    switch (field.type) {
      case "textarea":
        return (
          <textarea
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={4}
            placeholder={`Enter ${field.label.toLowerCase()}`}
            required={field.required}
          />
        );

      case "date":
        return (
          <input
            type="date"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required={field.required}
          />
        );

      case "email":
        return (
          <input
            type="email"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder={`Enter ${field.label.toLowerCase()}`}
            required={field.required}
          />
        );

      case "image":
        return (
          <div className="space-y-2">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleImageUpload(field.name, file);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required={field.required}
            />
            {value && (
              <p className="text-sm text-gray-600">Selected: {value}</p>
            )}
          </div>
        );

      default:
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder={`Enter ${field.label.toLowerCase()}`}
            required={field.required}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Template Preview System
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Phase 1: Proof of Concept - Upload template, fill data, preview output
          </p>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-between max-w-2xl mx-auto">
            {[
              { num: 1, label: "Upload Template" },
              { num: 2, label: "Fill Data" },
              { num: 3, label: "Preview" },
            ].map((s, idx) => (
              <div key={s.num} className="flex items-center">
                <div
                  className={`flex items-center justify-center w-10 h-10 rounded-full font-bold ${
                    step >= s.num
                      ? "bg-blue-600 text-white"
                      : "bg-gray-300 text-gray-600"
                  }`}
                >
                  {s.num}
                </div>
                <span className={`ml-2 ${step >= s.num ? "text-blue-600 font-semibold" : "text-gray-500"}`}>
                  {s.label}
                </span>
                {idx < 2 && (
                  <div className={`w-24 h-1 mx-4 ${step > s.num ? "bg-blue-600" : "bg-gray-300"}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <div className="flex items-center">
              <XCircle className="w-5 h-5 text-red-600 mr-2" />
              <p className="text-red-800 dark:text-red-200">{error}</p>
            </div>
          </div>
        )}

        {/* Step 1: Upload Template */}
        {step === 1 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
            <div className="flex flex-col items-center justify-center space-y-4">
              <Upload className="w-16 h-16 text-blue-600" />
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                Upload Template Document
              </h2>
              <p className="text-gray-600 dark:text-gray-400 text-center max-w-md">
                Upload a DOCX file with placeholders in the format: <code className="bg-gray-100 px-2 py-1 rounded">{"{{field_name}}"}</code>
              </p>

              <div className="w-full max-w-md">
                <label className="flex flex-col items-center justify-center w-full h-64 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    <Upload className="w-12 h-12 text-gray-400 mb-3" />
                    <p className="mb-2 text-sm text-gray-500 dark:text-gray-400">
                      <span className="font-semibold">Click to upload</span> or drag and drop
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">DOCX files only</p>
                  </div>
                  <input
                    type="file"
                    className="hidden"
                    accept=".docx"
                    onChange={handleFileUpload}
                    disabled={uploading}
                  />
                </label>
              </div>

              {uploading && (
                <div className="flex items-center space-x-2 text-blue-600">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Uploading and analyzing template...</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 2: Fill Data */}
        {step === 2 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Form */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                    Fill Template Data
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {templateFilename}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {fields.length} fields detected
                  </p>
                </div>
              </div>

              <div className="space-y-6 max-h-[600px] overflow-y-auto pr-4">
                {fields.map((field) => (
                  <div key={field.name}>
                    <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                      {field.label}
                      {field.required && <span className="text-red-500 ml-1">*</span>}
                      {field.evidence && (
                        <span className="ml-2 text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                          Evidence Required
                        </span>
                      )}
                    </label>
                    {renderFieldInput(field)}
                    <p className="text-xs text-gray-500 mt-1">
                      Type: {field.type} • Used in {field.locations.length} location(s)
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex space-x-4">
                <button
                  onClick={handleReset}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Start Over
                </button>
                <button
                  onClick={handleGeneratePreview}
                  disabled={generating}
                  className="flex-1 flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Generating Preview...
                    </>
                  ) : (
                    <>
                      <Eye className="w-5 h-5 mr-2" />
                      Generate Preview
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Right: Instructions */}
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-6">
              <div className="flex items-start">
                <AlertCircle className="w-6 h-6 text-blue-600 mr-3 flex-shrink-0 mt-1" />
                <div>
                  <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">
                    Instructions
                  </h3>
                  <ul className="space-y-2 text-sm text-blue-800 dark:text-blue-200">
                    <li>• Fill in all required fields (marked with *)</li>
                    <li>• Fields marked "Evidence Required" need file uploads</li>
                    <li>• For image fields, upload PNG or JPG files</li>
                    <li>• Date fields will be formatted automatically</li>
                    <li>• Click "Generate Preview" to see the filled document</li>
                  </ul>
                </div>
              </div>

              <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg p-4">
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Sample Data
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  Quick fill for testing:
                </p>
                <button
                  onClick={() => {
                    const sampleData: Record<string, any> = {};
                    fields.forEach(field => {
                      if (field.type === "date") {
                        sampleData[field.name] = "2026-02-11";
                      } else if (field.type === "email") {
                        sampleData[field.name] = "test@example.com";
                      } else if (field.type === "image") {
                        sampleData[field.name] = "sample_logo.png";
                      } else if (field.type === "textarea") {
                        sampleData[field.name] = "Sample text content for " + field.label;
                      } else {
                        sampleData[field.name] = "Sample " + field.label;
                      }
                    });
                    setFormData(sampleData);
                  }}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  Fill with sample data →
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Preview */}
        {step === 3 && (
          <div className="space-y-6">
            {/* Success Message */}
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
              <div className="flex items-center">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                <p className="text-green-800 dark:text-green-200 font-semibold">
                  Document generated successfully!
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4">
              <div className="flex items-center space-x-4">
                <FileText className="w-6 h-6 text-gray-600" />
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">
                    {templateFilename}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Preview ID: {previewId.substring(0, 8)}...
                  </p>
                </div>
              </div>
              <div className="flex space-x-3">
                <a
                  href={docxUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download DOCX
                </a>
                <a
                  href={pdfUrl}
                  download
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download PDF
                </a>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  New Template
                </button>
              </div>
            </div>

            {/* PDF Preview */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
                Preview (PDF)
              </h3>
              <iframe
                src={pdfUrl}
                className="w-full h-[800px] border border-gray-300 rounded-lg"
                title="PDF Preview"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
