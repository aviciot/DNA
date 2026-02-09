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
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          title="Add new ISO standard (coming soon)"
          disabled
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
                  title="Edit (coming soon)"
                  disabled
                  className="p-1.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  title="Delete (coming soon)"
                  disabled
                  className="p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
          Full CRUD operations for ISO standards will be available in a future update.
        </p>
      </div>
    </div>
  );
}
