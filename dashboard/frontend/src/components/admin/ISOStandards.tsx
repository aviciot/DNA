"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Shield,
  Plus,
  Edit2,
  Trash2,
  X,
  Check,
  Loader2,
  FileText,
  Users,
  AlertCircle,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface ISOStandard {
  id: string;
  code: string;
  name: string;
  description: string | null;
  requirements_summary: string | null;
  active: boolean;
  display_order: number;
  template_count: number;
  customer_count: number;
  created_at: string;
  updated_at: string;
}

interface CatalogTemplate {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
}

export default function ISOStandards() {
  const [standards, setStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedISO, setExpandedISO] = useState<string | null>(null);
  const [isoTemplates, setISOTemplates] = useState<Record<string, CatalogTemplate[]>>({});
  const [loadingTemplates, setLoadingTemplates] = useState<Record<string, boolean>>({});
  const [editingISO, setEditingISO] = useState<ISOStandard | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newISO, setNewISO] = useState({ code: "", name: "", description: "", requirements_summary: "", active: true, display_order: 0 });
  const [isSaving, setIsSaving] = useState(false);
  const [deleteConfirmISO, setDeleteConfirmISO] = useState<ISOStandard | null>(null);

  useEffect(() => {
    loadStandards();
  }, []);

  const loadStandards = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/iso-standards?active_only=false`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setStandards(response.data);
    } catch (error) {
      console.error("Failed to load ISO standards:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplatesForISO = async (isoId: string) => {
    if (isoTemplates[isoId]) {
      // Already loaded, just toggle
      setExpandedISO(expandedISO === isoId ? null : isoId);
      return;
    }

    setLoadingTemplates({ ...loadingTemplates, [isoId]: true });
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(
        `${API_BASE}/api/v1/catalog-templates?iso_standard_id=${isoId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setISOTemplates({ ...isoTemplates, [isoId]: response.data });
      setExpandedISO(isoId);
    } catch (error) {
      console.error("Failed to load templates for ISO:", error);
    } finally {
      setLoadingTemplates({ ...loadingTemplates, [isoId]: false });
    }
  };

  const handleEdit = (standard: ISOStandard) => {
    setEditingISO(standard);
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingISO) return;

    setIsSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.put(
        `${API_BASE}/api/v1/iso-standards/${editingISO.id}`,
        {
          code: editingISO.code,
          name: editingISO.name,
          description: editingISO.description,
          requirements_summary: editingISO.requirements_summary,
          active: editingISO.active,
          display_order: editingISO.display_order,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Refresh the list
      await loadStandards();

      // Close modal
      setIsEditModalOpen(false);
      setEditingISO(null);
    } catch (error: any) {
      console.error("Failed to update ISO standard:", error);
      alert(
        `Failed to update ISO standard: ${
          error.response?.data?.detail || error.message
        }`
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (standard: ISOStandard) => {
    if (standard.template_count > 0) {
      alert(
        `Cannot delete ${standard.code}: ${standard.template_count} template(s) are using it. Consider marking it as inactive instead.`
      );
      return;
    }

    setDeleteConfirmISO(standard);
  };

  const confirmDelete = async () => {
    if (!deleteConfirmISO) return;

    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${API_BASE}/api/v1/iso-standards/${deleteConfirmISO.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      // Refresh the list
      await loadStandards();

      setDeleteConfirmISO(null);
    } catch (error: any) {
      console.error("Failed to delete ISO standard:", error);
      alert(
        `Failed to delete ISO standard: ${
          error.response?.data?.detail || error.message
        }`
      );
      setDeleteConfirmISO(null);
    }
  };

  const handleAddISO = async () => {
    if (!newISO.code || !newISO.name) {
      alert("Code and Name are required");
      return;
    }

    setIsSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.post(
        `${API_BASE}/api/v1/iso-standards`,
        newISO,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Refresh the list
      await loadStandards();

      // Close modal and reset form
      setIsAddModalOpen(false);
      setNewISO({ code: "", name: "", description: "", requirements_summary: "", active: true, display_order: 0 });
    } catch (error: any) {
      console.error("Failed to create ISO standard:", error);
      alert(
        `Failed to create ISO standard: ${
          error.response?.data?.detail || error.message
        }`
      );
    } finally {
      setIsSaving(false);
    }
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
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            ISO Standards
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Manage ISO certification standards available in the system
          </p>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          title="Add new ISO standard"
        >
          <Plus className="w-4 h-4" />
          <span>Add ISO Standard</span>
        </button>
      </div>

      {/* Standards Grid */}
      <div className="grid grid-cols-1 gap-4">
        {standards.map((standard) => (
          <div
            key={standard.id}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                {/* Header */}
                <div className="flex items-center space-x-3 mb-2">
                  <Shield className="w-5 h-5 text-blue-500" />
                  <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {standard.code}
                  </h4>
                  {standard.active ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-900/30 text-gray-800 dark:text-gray-300">
                      Inactive
                    </span>
                  )}
                </div>

                {/* Name */}
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {standard.name}
                </p>

                {/* Description */}
                {standard.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                    {standard.description}
                  </p>
                )}

                {/* Requirements Summary */}
                {standard.requirements_summary && (
                  <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-3">
                    <p className="text-xs font-medium text-blue-900 dark:text-blue-100 mb-1">
                      Key Requirements:
                    </p>
                    <p className="text-xs text-blue-800 dark:text-blue-200">
                      {standard.requirements_summary}
                    </p>
                  </div>
                )}

                {/* Stats */}
                <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400 mb-3">
                  <div className="flex items-center space-x-1">
                    <FileText className="w-4 h-4" />
                    <span>{standard.template_count} template(s)</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Users className="w-4 h-4" />
                    <span>{standard.customer_count} customer(s)</span>
                  </div>
                </div>

                {/* View Templates Button */}
                {standard.template_count > 0 && (
                  <button
                    onClick={() => loadTemplatesForISO(standard.id)}
                    className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center space-x-1"
                  >
                    <FileText className="w-4 h-4" />
                    <span>
                      {expandedISO === standard.id ? "Hide" : "View"} templates
                    </span>
                  </button>
                )}

                {/* Expanded Template List */}
                {expandedISO === standard.id && (
                  <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                    {loadingTemplates[standard.id] ? (
                      <div className="flex items-center space-x-2 text-sm text-gray-500">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Loading templates...</span>
                      </div>
                    ) : isoTemplates[standard.id]?.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">
                          Built Templates:
                        </p>
                        {isoTemplates[standard.id].map((template) => (
                          <div
                            key={template.id}
                            className="bg-gray-50 dark:bg-gray-900/50 rounded p-2 text-sm"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2">
                                <FileText className="w-4 h-4 text-blue-500" />
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {template.name}
                                </span>
                                <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                                  v{template.version_number}
                                </span>
                              </div>
                              {template.status === "approved" && (
                                <span className="text-xs text-green-600 dark:text-green-400">
                                  ✓ Approved
                                </span>
                              )}
                            </div>
                            {template.description && (
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                                {template.description}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        No templates found for this ISO standard
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleEdit(standard)}
                  title="Edit ISO standard"
                  className="p-1.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(standard)}
                  title="Delete ISO standard"
                  className="p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Info Note */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <p className="text-sm text-blue-900 dark:text-blue-100">
          <strong>Note:</strong> ISO standards are seeded during database initialization.
          You can now edit and delete standards using the action buttons.
        </p>
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && editingISO && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Modal Header */}
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                    Edit ISO Standard
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Update the details of this ISO standard
                  </p>
                </div>
                <button
                  onClick={() => {
                    setIsEditModalOpen(false);
                    setEditingISO(null);
                  }}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              {/* Form */}
              <div className="space-y-4">
                {/* Code */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    ISO Code *
                  </label>
                  <input
                    type="text"
                    value={editingISO.code}
                    onChange={(e) =>
                      setEditingISO({ ...editingISO, code: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="e.g., ISO 9001:2015"
                  />
                </div>

                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    value={editingISO.name}
                    onChange={(e) =>
                      setEditingISO({ ...editingISO, name: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="e.g., Quality Management Systems"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={editingISO.description || ""}
                    onChange={(e) =>
                      setEditingISO({ ...editingISO, description: e.target.value })
                    }
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Full description of the standard"
                  />
                </div>

                {/* Requirements Summary */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Requirements Summary
                  </label>
                  <textarea
                    value={editingISO.requirements_summary || ""}
                    onChange={(e) =>
                      setEditingISO({
                        ...editingISO,
                        requirements_summary: e.target.value,
                      })
                    }
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Key requirements overview"
                  />
                </div>

                {/* Active Status */}
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="active"
                    checked={editingISO.active}
                    onChange={(e) =>
                      setEditingISO({ ...editingISO, active: e.target.checked })
                    }
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label
                    htmlFor="active"
                    className="text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Active
                  </label>
                </div>

                {/* Display Order */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Display Order
                  </label>
                  <input
                    type="number"
                    value={editingISO.display_order}
                    onChange={(e) =>
                      setEditingISO({
                        ...editingISO,
                        display_order: parseInt(e.target.value) || 0,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => {
                    setIsEditModalOpen(false);
                    setEditingISO(null);
                  }}
                  disabled={isSaving}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={isSaving || !editingISO.code || !editingISO.name}
                  className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      <span>Save Changes</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmISO && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6">
              <div className="flex items-center space-x-3 mb-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Delete ISO Standard?
                </h3>
              </div>

              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Are you sure you want to delete <strong>{deleteConfirmISO.code}</strong>?
                This action cannot be undone.
              </p>

              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setDeleteConfirmISO(null)}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmDelete}
                  className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add ISO Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                  Add New ISO Standard
                </h3>
                <button
                  onClick={() => {
                    setIsAddModalOpen(false);
                    setNewISO({ code: "", name: "", description: "", requirements_summary: "", active: true, display_order: 0 });
                  }}
                  className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    ISO Code <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newISO.code}
                    onChange={(e) => setNewISO({ ...newISO, code: e.target.value })}
                    placeholder="ISO 27001:2022"
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newISO.name}
                    onChange={(e) => setNewISO({ ...newISO, name: e.target.value })}
                    placeholder="Information Security Management"
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  <textarea
                    value={newISO.description}
                    onChange={(e) => setNewISO({ ...newISO, description: e.target.value })}
                    placeholder="Brief description of the standard..."
                    rows={3}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Requirements Summary
                  </label>
                  <textarea
                    value={newISO.requirements_summary}
                    onChange={(e) => setNewISO({ ...newISO, requirements_summary: e.target.value })}
                    placeholder="Key requirements and clauses..."
                    rows={4}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Display Order
                  </label>
                  <input
                    type="number"
                    value={newISO.display_order}
                    onChange={(e) => setNewISO({ ...newISO, display_order: parseInt(e.target.value) || 0 })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    checked={newISO.active}
                    onChange={(e) => setNewISO({ ...newISO, active: e.target.checked })}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                  />
                  <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                    Active (visible to users)
                  </label>
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => {
                    setIsAddModalOpen(false);
                    setNewISO({ code: "", name: "", description: "", requirements_summary: "", active: true, display_order: 0 });
                  }}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddISO}
                  disabled={isSaving || !newISO.code || !newISO.name}
                  className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      <span>Create ISO Standard</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
