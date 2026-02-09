"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  FileText,
  Eye,
  Edit2,
  Trash2,
  Check,
  X,
  Loader2,
  Shield,
  CheckCircle,
  XCircle,
  Tag,
  Plus,
} from "lucide-react";
import TemplateStudio from "./TemplateStudio";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface CatalogTemplate {
  id: string;
  name: string;
  description: string | null;
  template_file_id: string | null;
  source_filename: string | null;
  status: string;
  version_number: number;
  restored_from_version: number | null;
  total_fixed_sections: number;
  total_fillable_sections: number;
  semantic_tags: string[];
  iso_codes: string[];
  created_at: string;
  approved_at: string | null;
  customer_document_count: number;
}

interface ISOStandard {
  id: string;
  code: string;
  name: string;
  active: boolean;
}

interface TemplateDetail extends CatalogTemplate {
  template_structure: any;
  ai_task_id: string | null;
  created_by_email: string | null;
  approved_by_email: string | null;
}

export default function TemplateCatalog() {
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateDetail | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [showISOModal, setShowISOModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<CatalogTemplate | null>(null);
  const [selectedISOs, setSelectedISOs] = useState<string[]>([]);

  useEffect(() => {
    loadTemplates();
    loadISOStandards();
  }, []);

  const loadTemplates = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/catalog-templates`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setTemplates(response.data);
    } catch (error) {
      console.error("Failed to load catalog templates:", error);
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

  const loadTemplateDetail = async (id: string) => {
    try {
      const token = localStorage.getItem("access_token");
      console.log("Loading template detail for ID:", id);
      const response = await axios.get(`${API_BASE}/api/v1/catalog-templates/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      console.log("Template detail response:", response.data);
      setSelectedTemplate(response.data);
      setShowPreview(true);
    } catch (error: any) {
      console.error("Failed to load template details:", error);
      console.error("Error response:", error.response?.data);
      alert(`Failed to load template details: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      const token = localStorage.getItem("access_token");
      await axios.put(
        `${API_BASE}/api/v1/catalog-templates/${id}`,
        { status: "approved" },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      loadTemplates();
      alert("Template approved!");
    } catch (error: any) {
      console.error("Failed to approve template:", error);
      alert(`Failed to approve: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete template "${name}"?`)) {
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${API_BASE}/api/v1/catalog-templates/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      loadTemplates();
      alert("Template deleted!");
    } catch (error: any) {
      console.error("Failed to delete template:", error);
      alert(`Failed to delete: ${error.response?.data?.detail || error.message}`);
    }
  };

  const openISOModal = (template: CatalogTemplate) => {
    setEditingTemplate(template);
    setSelectedISOs(
      isoStandards
        .filter((iso) => template.iso_codes.includes(iso.code))
        .map((iso) => iso.id)
    );
    setShowISOModal(true);
  };

  const handleUpdateISOs = async () => {
    if (!editingTemplate) return;

    try {
      const token = localStorage.getItem("access_token");
      await axios.patch(
        `${API_BASE}/api/v1/catalog-templates/${editingTemplate.id}/iso-standards`,
        { iso_standard_ids: selectedISOs },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowISOModal(false);
      loadTemplates();
      alert("ISO standards updated!");
    } catch (error: any) {
      console.error("Failed to update ISOs:", error);
      alert(`Failed to update: ${error.response?.data?.detail || error.message}`);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
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
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Template Catalog
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Built templates from AI parsing - assign ISOs and approve for production use
        </p>
      </div>

      {/* Templates Grid */}
      {templates.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
          <FileText className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No templates built yet
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            Go to Reference Documents and click "Build" to parse a document with AI
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {templates.map((template) => (
            <div
              key={template.id}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  {/* Header */}
                  <div className="flex items-center space-x-3 mb-2">
                    <FileText className="w-5 h-5 text-blue-500" />
                    <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {template.name}
                    </h4>
                    {template.status === "approved" ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        Approved
                      </span>
                    ) : template.status === "draft" ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
                        Draft
                      </span>
                    ) : null}
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300">
                      v{template.version_number}
                      {template.restored_from_version && (
                        <span className="ml-1 text-purple-600 dark:text-purple-400">
                          (from v{template.restored_from_version})
                        </span>
                      )}
                    </span>
                  </div>

                  {/* Description */}
                  {template.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      {template.description}
                    </p>
                  )}

                  {/* Source File */}
                  {template.source_filename && (
                    <p className="text-xs text-gray-500 dark:text-gray-500 mb-3">
                      Source: {template.source_filename}
                    </p>
                  )}

                  {/* ISO Standards */}
                  <div className="mb-3">
                    <div className="flex items-center space-x-2 mb-1">
                      <Shield className="w-4 h-4 text-gray-500" />
                      <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                        ISO Standards:
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {template.iso_codes.length > 0 ? (
                        template.iso_codes.map((code) => (
                          <span
                            key={code}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300"
                          >
                            {code}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-gray-500">No ISOs assigned</span>
                      )}
                      <button
                        onClick={() => openISOModal(template)}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                      >
                        <Plus className="w-3 h-3 mr-1" />
                        {template.iso_codes.length > 0 ? "Edit" : "Add ISOs"}
                      </button>
                    </div>
                  </div>

                  {/* Statistics */}
                  <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
                    <span>{template.section_count} sections</span>
                    <span>•</span>
                    <span>
                      {template.field_count} fields ({template.required_field_count} required)
                    </span>
                    {template.estimated_completion_minutes && (
                      <>
                        <span>•</span>
                        <span>~{template.estimated_completion_minutes} min</span>
                      </>
                    )}
                  </div>

                  {/* Dates */}
                  <div className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                    Created: {formatDate(template.created_at)}
                    {template.approved_at && ` • Approved: ${formatDate(template.approved_at)}`}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => loadTemplateDetail(template.id)}
                    title="Template Studio - Edit & Preview"
                    className="p-1.5 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  {template.status === "draft" && (
                    <button
                      onClick={() => handleApprove(template.id)}
                      title="Approve Template"
                      className="p-1.5 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(template.id, template.name)}
                    title="Delete"
                    className="p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Template Studio */}
      {showPreview && selectedTemplate && (
        <TemplateStudio
          template={selectedTemplate}
          onClose={() => setShowPreview(false)}
          onSave={() => {
            loadTemplates();
            setShowPreview(false);
          }}
        />
      )}

      {/* ISO Assignment Modal */}
      {showISOModal && editingTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
            <div className="flex justify-between items-center p-6 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                Assign ISO Standards
              </h3>
              <button
                onClick={() => setShowISOModal(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            <div className="p-6">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Select which ISO standards apply to "{editingTemplate.name}"
              </p>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {isoStandards.map((iso) => (
                  <label key={iso.id} className="flex items-center space-x-2 cursor-pointer p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded">
                    <input
                      type="checkbox"
                      checked={selectedISOs.includes(iso.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedISOs([...selectedISOs, iso.id]);
                        } else {
                          setSelectedISOs(selectedISOs.filter((id) => id !== iso.id));
                        }
                      }}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-900 dark:text-white">
                      {iso.code} - {iso.name}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => setShowISOModal(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateISOs}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                Update
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
