"use client";

import { X, Eye, Edit, History, Lock, AlertTriangle, Tag, Plus, Trash2, Save, ArrowLeft, CheckCircle2, ArrowRight, RefreshCw } from "lucide-react";
import { useState, useEffect } from "react";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface FillableSection {
  id: string;
  title: string;
  location: string;
  type: string;
  semantic_tags: string[];
  current_content?: string;
  placeholder?: string;
  format?: string;
  is_mandatory: boolean;
  mandatory_confidence: number;
}

interface FixedSection {
  id: string;
  title: string;
  content: string;
  section_type: string;
}

interface TemplateStructure {
  document_title: string;
  fixed_sections: FixedSection[];
  fillable_sections: FillableSection[];
  metadata: {
    source_file: string;
    parsed_at: string;
    total_fixed_sections: number;
    total_fillable_sections: number;
    semantic_tags_used: string[];
  };
}

interface TemplateDetail {
  id: string;
  name: string;
  description: string | null;
  source_filename: string | null;
  template_structure: TemplateStructure;
  status: string;
  version_number: number;
  restored_from_version?: number | null;
  total_fixed_sections: number;
  total_fillable_sections: number;
  semantic_tags: string[];
  last_edited_at?: string;
  last_edited_by_email?: string;
}

interface TemplateVersion {
  id: string;
  version_number: number;
  change_summary: string | null;
  notes: string | null;
  created_at: string;
  created_by: number | null;
  created_by_email: string | null;
  restored_from_version: number | null;
}

interface TemplateStudioProps {
  template: TemplateDetail;
  onClose: () => void;
  onSave: () => void;
}

export default function TemplateStudio({
  template,
  onClose,
  onSave,
}: TemplateStudioProps) {
  const [activeTab, setActiveTab] = useState<"preview" | "editor" | "history">("editor");
  const [editedStructure, setEditedStructure] = useState<TemplateStructure>(template.template_structure);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  // Edit modal state
  const [editingSection, setEditingSection] = useState<FillableSection | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);

  // Load version history when history tab is opened
  useEffect(() => {
    if (activeTab === "history" && versions.length === 0) {
      loadVersionHistory();
    }
  }, [activeTab]);

  const loadVersionHistory = async () => {
    setLoadingVersions(true);
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(
        `${API_BASE}/api/v1/catalog-templates/${template.id}/versions`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setVersions(response.data);
    } catch (error) {
      console.error("Failed to load version history:", error);
      alert("Failed to load version history");
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleSaveChanges = async () => {
    if (!hasUnsavedChanges) return;

    if (!confirm("Save changes to template structure? This will create a new version.")) {
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.patch(
        `${API_BASE}/api/v1/catalog-templates/${template.id}/structure`,
        { template_structure: editedStructure },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setHasUnsavedChanges(false);
      alert("✅ Template saved successfully!");
      onSave();
    } catch (error: any) {
      console.error("Failed to save template:", error);
      alert(`Failed to save: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (hasUnsavedChanges) {
      if (!confirm("You have unsaved changes. Are you sure you want to close?")) {
        return;
      }
    }
    onClose();
  };

  const handleEditSection = (section: FillableSection) => {
    setEditingSection({ ...section });
    setShowEditModal(true);
  };

  const handleSaveSection = () => {
    if (!editingSection) return;

    const newStructure = { ...editedStructure };
    const index = newStructure.fillable_sections.findIndex(s => s.id === editingSection.id);
    if (index !== -1) {
      newStructure.fillable_sections[index] = editingSection;
      setEditedStructure(newStructure);
      setHasUnsavedChanges(true);
    }
    setShowEditModal(false);
  };

  const handleDeleteSection = (sectionId: string) => {
    if (!confirm("Delete this fillable section?")) return;

    const newStructure = { ...editedStructure };
    newStructure.fillable_sections = newStructure.fillable_sections.filter(s => s.id !== sectionId);
    newStructure.metadata.total_fillable_sections = newStructure.fillable_sections.length;
    setEditedStructure(newStructure);
    setHasUnsavedChanges(true);
  };

  const handleDeleteFixedSection = (sectionId: string) => {
    if (!confirm("Delete this fixed section? This will permanently remove it.")) return;

    const newStructure = { ...editedStructure };
    newStructure.fixed_sections = newStructure.fixed_sections.filter(s => s.id !== sectionId);
    newStructure.metadata.total_fixed_sections = newStructure.fixed_sections.length;
    setEditedStructure(newStructure);
    setHasUnsavedChanges(true);
  };

  const handleConvertToFillable = (section: FixedSection) => {
    if (!confirm(`Convert "${section.title}" to a fillable section? You'll need to add semantic tags.`)) return;

    const newStructure = { ...editedStructure };

    // Remove from fixed
    newStructure.fixed_sections = newStructure.fixed_sections.filter(s => s.id !== section.id);
    newStructure.metadata.total_fixed_sections = newStructure.fixed_sections.length;

    // Add as fillable
    const newFillable: FillableSection = {
      id: section.id,
      title: section.title,
      location: section.section_type,
      type: "paragraph",
      semantic_tags: [],
      current_content: section.content.substring(0, 500), // Truncate for current_content
      placeholder: `Fill in ${section.title}`,
      format: "Paragraph",
      is_mandatory: false,
      mandatory_confidence: 0,
    };
    newStructure.fillable_sections.push(newFillable);
    newStructure.metadata.total_fillable_sections = newStructure.fillable_sections.length;

    setEditedStructure(newStructure);
    setHasUnsavedChanges(true);
    alert("✅ Converted to fillable! Don't forget to add semantic tags.");
  };

  const handleRestoreVersion = async (versionNumber: number) => {
    if (!confirm(`Restore template to version ${versionNumber}? This will create a new version.`)) {
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      await axios.post(
        `${API_BASE}/api/v1/catalog-templates/${template.id}/versions/${versionNumber}/restore`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert("✅ Version restored successfully!");
      onSave();
      onClose();
    } catch (error: any) {
      console.error("Failed to restore version:", error);
      alert(`Failed to restore: ${error.response?.data?.detail || error.message}`);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-7xl h-[95vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start p-6 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20">
          <div className="flex-1">
            <div className="flex items-center space-x-3 mb-2">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                🎨 Template Studio
              </h2>
              {hasUnsavedChanges && (
                <span className="px-3 py-1 bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-300 text-sm font-semibold rounded-full">
                  Unsaved Changes
                </span>
              )}
            </div>
            <h3 className="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-1">
              {editedStructure.document_title || template.name}
            </h3>
            <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
              <span>
                Version: {template.version_number}
                {template.restored_from_version && (
                  <span className="ml-1 text-purple-600 dark:text-purple-400 font-medium">
                    (restored from v{template.restored_from_version})
                  </span>
                )}
              </span>
              <span>•</span>
              <span>{editedStructure.fillable_sections.length} Fillable</span>
              <span>•</span>
              <span>{editedStructure.fixed_sections.length} Fixed</span>
              {template.last_edited_at && (
                <>
                  <span>•</span>
                  <span>
                    Last edited: {new Date(template.last_edited_at).toLocaleString()}
                    {template.last_edited_by_email && ` by ${template.last_edited_by_email}`}
                  </span>
                </>
              )}
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-white/50 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <button
            onClick={() => setActiveTab("preview")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === "preview"
                ? "border-b-2 border-blue-600 text-blue-600 bg-white dark:bg-gray-800"
                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            }`}
          >
            <div className="flex items-center space-x-2">
              <Eye className="w-4 h-4" />
              <span>Preview</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab("editor")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === "editor"
                ? "border-b-2 border-green-600 text-green-600 bg-white dark:bg-gray-800"
                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            }`}
          >
            <div className="flex items-center space-x-2">
              <Edit className="w-4 h-4" />
              <span>Editor</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === "history"
                ? "border-b-2 border-purple-600 text-purple-600 bg-white dark:bg-gray-800"
                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            }`}
          >
            <div className="flex items-center space-x-2">
              <History className="w-4 h-4" />
              <span>History</span>
            </div>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {activeTab === "preview" && (
            <PreviewTab structure={editedStructure} />
          )}

          {activeTab === "editor" && (
            <EditorTab
              structure={editedStructure}
              onEditSection={handleEditSection}
              onDeleteSection={handleDeleteSection}
              onDeleteFixedSection={handleDeleteFixedSection}
              onConvertToFillable={handleConvertToFillable}
            />
          )}

          {activeTab === "history" && (
            <HistoryTab
              versions={versions}
              loading={loadingVersions}
              currentVersion={template.version_number}
              onRestore={handleRestoreVersion}
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {activeTab === "editor" && (
              <p>
                <strong>Tip:</strong> Click Edit on any fillable section to modify it. Changes are saved when you click Save Changes.
              </p>
            )}
            {activeTab === "preview" && (
              <p>
                <strong>Preview:</strong> Read-only view of your template structure
              </p>
            )}
            {activeTab === "history" && (
              <p>
                <strong>History:</strong> View and restore previous versions
              </p>
            )}
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={handleClose}
              className="px-6 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-lg transition-colors font-medium"
            >
              Close
            </button>
            {activeTab === "editor" && (
              <button
                onClick={handleSaveChanges}
                disabled={!hasUnsavedChanges || saving}
                className={`px-6 py-2 rounded-lg transition-colors font-medium flex items-center space-x-2 ${
                  hasUnsavedChanges && !saving
                    ? "bg-green-600 hover:bg-green-700 text-white"
                    : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-500 cursor-not-allowed"
                }`}
              >
                <Save className="w-4 h-4" />
                <span>{saving ? "Saving..." : "Save Changes"}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Edit Section Modal */}
      {showEditModal && editingSection && (
        <EditSectionModal
          section={editingSection}
          onSave={handleSaveSection}
          onCancel={() => setShowEditModal(false)}
          onChange={setEditingSection}
        />
      )}
    </div>
  );
}

// Preview Tab Component
function PreviewTab({ structure }: { structure: TemplateStructure }) {
  const [viewMode, setViewMode] = useState<"fillable" | "fixed">("fillable");

  return (
    <div className="space-y-4">
      {/* Toggle */}
      <div className="flex space-x-2">
        <button
          onClick={() => setViewMode("fillable")}
          className={`px-4 py-2 rounded-lg font-medium ${
            viewMode === "fillable"
              ? "bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300"
              : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
          }`}
        >
          Fillable ({structure.fillable_sections.length})
        </button>
        <button
          onClick={() => setViewMode("fixed")}
          className={`px-4 py-2 rounded-lg font-medium ${
            viewMode === "fixed"
              ? "bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300"
              : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
          }`}
        >
          Fixed ({structure.fixed_sections.length})
        </button>
      </div>

      {viewMode === "fillable" ? (
        <div className="space-y-4">
          {structure.fillable_sections.map((section, idx) => (
            <div
              key={idx}
              className="bg-green-50 dark:bg-green-900/20 rounded-lg border-2 border-green-200 dark:border-green-700 p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                      {section.title}
                    </h4>
                    {section.is_mandatory && (
                      <span className="px-2 py-0.5 bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-xs font-semibold rounded flex items-center space-x-1">
                        <AlertTriangle className="w-3 h-3" />
                        <span>Mandatory</span>
                        {section.mandatory_confidence > 0 && (
                          <span className="text-xs">({Math.round(section.mandatory_confidence * 100)}%)</span>
                        )}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    📍 {section.location}
                  </p>
                </div>
                <span className="px-3 py-1 bg-green-600 text-white text-xs font-semibold rounded-full">
                  {section.type}
                </span>
              </div>

              {section.current_content && (
                <div className="bg-white dark:bg-gray-800 rounded p-3 mb-3">
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Current Content:</p>
                  <p className="text-sm text-gray-800 dark:text-gray-200">
                    {section.current_content.substring(0, 200)}
                    {section.current_content.length > 200 && "..."}
                  </p>
                </div>
              )}

              {section.semantic_tags && section.semantic_tags.length > 0 && (
                <div className="flex items-start space-x-2">
                  <Tag className="w-4 h-4 text-purple-600 mt-1 flex-shrink-0" />
                  <div className="flex flex-wrap gap-1">
                    {section.semantic_tags.map((tag, tagIdx) => (
                      <span
                        key={tagIdx}
                        className="px-2 py-1 bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-300 text-xs rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {structure.fixed_sections.map((section, idx) => (
            <div
              key={idx}
              className="bg-blue-50 dark:bg-blue-900/20 rounded-lg border-2 border-blue-200 dark:border-blue-700 p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                  {section.title}
                </h4>
                <span className="px-3 py-1 bg-blue-600 text-white text-xs font-semibold rounded-full">
                  {section.section_type}
                </span>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded p-3">
                <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                  {section.content.substring(0, 300)}
                  {section.content.length > 300 && "..."}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Editor Tab Component
function EditorTab({
  structure,
  onEditSection,
  onDeleteSection,
  onDeleteFixedSection,
  onConvertToFillable,
}: {
  structure: TemplateStructure;
  onEditSection: (section: FillableSection) => void;
  onDeleteSection: (id: string) => void;
  onDeleteFixedSection: (id: string) => void;
  onConvertToFillable: (section: FixedSection) => void;
}) {
  return (
    <div className="space-y-6">
      {/* Fillable Sections */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center space-x-2">
          <Edit className="w-5 h-5 text-green-600" />
          <span>Fillable Sections ({structure.fillable_sections.length})</span>
        </h3>
        <div className="space-y-3">
          {structure.fillable_sections.map((section, idx) => (
            <div
              key={idx}
              className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <h4 className="text-base font-semibold text-gray-900 dark:text-white">
                      {section.title}
                    </h4>
                    {section.is_mandatory && (
                      <span className="px-2 py-0.5 bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 text-xs font-semibold rounded flex items-center space-x-1">
                        <AlertTriangle className="w-3 h-3" />
                        <span>Mandatory</span>
                      </span>
                    )}
                    <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded">
                      {section.type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    📍 {section.location}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {section.semantic_tags.map((tag, tagIdx) => (
                      <span
                        key={tagIdx}
                        className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-300 text-xs rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => onEditSection(section)}
                    className="p-2 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-900/60 rounded transition-colors"
                    title="Edit section"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onDeleteSection(section.id)}
                    className="p-2 bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/60 rounded transition-colors"
                    title="Delete section"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Fixed Sections */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center space-x-2">
          <Lock className="w-5 h-5 text-blue-600" />
          <span>Fixed Sections ({structure.fixed_sections.length})</span>
        </h3>
        <div className="space-y-3">
          {structure.fixed_sections.map((section, idx) => (
            <div
              key={idx}
              className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <h4 className="text-base font-semibold text-gray-900 dark:text-white">
                      {section.title}
                    </h4>
                    <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded">
                      {section.section_type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {section.content.substring(0, 100)}...
                  </p>
                </div>
                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => onConvertToFillable(section)}
                    className="p-2 bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/60 rounded transition-colors"
                    title="Convert to fillable section"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onDeleteFixedSection(section.id)}
                    className="p-2 bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/60 rounded transition-colors"
                    title="Delete fixed section"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// History Tab Component
function HistoryTab({
  versions,
  loading,
  currentVersion,
  onRestore,
}: {
  versions: TemplateVersion[];
  loading: boolean;
  currentVersion: number;
  onRestore: (versionNumber: number) => void;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading version history...</div>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No version history available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {versions.map((version) => (
        <div
          key={version.id}
          className={`rounded-lg border-2 p-5 ${
            version.version_number === currentVersion
              ? "border-green-500 bg-green-50 dark:bg-green-900/20"
              : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
          }`}
        >
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2">
                <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                  Version {version.version_number}
                  {version.restored_from_version && (
                    <span className="ml-2 text-purple-600 dark:text-purple-400 font-medium text-base">
                      (from v{version.restored_from_version})
                    </span>
                  )}
                </h4>
                {version.version_number === currentVersion && (
                  <span className="px-3 py-1 bg-green-600 text-white text-xs font-semibold rounded-full flex items-center space-x-1">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Current</span>
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                {version.change_summary || "No summary available"}
              </p>
              {version.notes && (
                <p className="text-sm text-gray-500 dark:text-gray-500 italic">
                  Note: {version.notes}
                </p>
              )}
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                {new Date(version.created_at).toLocaleString()}
                {version.created_by_email && ` by ${version.created_by_email}`}
              </p>
            </div>
            {version.version_number !== currentVersion && (
              <button
                onClick={() => onRestore(version.version_number)}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors font-medium text-sm flex items-center space-x-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Restore</span>
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Edit Section Modal Component
function EditSectionModal({
  section,
  onSave,
  onCancel,
  onChange,
}: {
  section: FillableSection;
  onSave: () => void;
  onCancel: () => void;
  onChange: (section: FillableSection) => void;
}) {
  const [newTag, setNewTag] = useState("");

  const handleAddTag = () => {
    if (newTag.trim() && !section.semantic_tags.includes(newTag.trim())) {
      onChange({
        ...section,
        semantic_tags: [...section.semantic_tags, newTag.trim()],
      });
      setNewTag("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    onChange({
      ...section,
      semantic_tags: section.semantic_tags.filter((t) => t !== tag),
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-xl font-bold text-gray-900 dark:text-white">
            Edit Fillable Section
          </h3>
        </div>

        <div className="p-6 space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Title
            </label>
            <input
              type="text"
              value={section.title}
              onChange={(e) => onChange({ ...section, title: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
            />
          </div>

          {/* Mandatory Toggle */}
          <div>
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={section.is_mandatory}
                onChange={(e) =>
                  onChange({ ...section, is_mandatory: e.target.checked })
                }
                className="w-5 h-5 text-red-600 border-gray-300 rounded focus:ring-red-500"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mark as Mandatory
              </span>
            </label>
            {section.mandatory_confidence > 0 && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-8">
                AI Confidence: {Math.round(section.mandatory_confidence * 100)}%
              </p>
            )}
          </div>

          {/* Placeholder */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Placeholder Text
            </label>
            <textarea
              value={section.placeholder || ""}
              onChange={(e) =>
                onChange({ ...section, placeholder: e.target.value })
              }
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
              placeholder="Help text for customers..."
            />
          </div>

          {/* Semantic Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Semantic Tags
            </label>
            <div className="flex flex-wrap gap-2 mb-3">
              {section.semantic_tags.map((tag, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-300 text-sm rounded-full flex items-center space-x-2"
                >
                  <span>{tag}</span>
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="text-purple-600 dark:text-purple-400 hover:text-purple-800 dark:hover:text-purple-200"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex space-x-2">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleAddTag()}
                placeholder="Add new tag..."
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white text-sm"
              />
              <button
                onClick={handleAddTag}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors text-sm flex items-center space-x-1"
              >
                <Plus className="w-4 h-4" />
                <span>Add</span>
              </button>
            </div>
          </div>

          {/* Location (Read-only) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Location (Read-only)
            </label>
            <p className="text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 p-3 rounded-lg">
              {section.location}
            </p>
          </div>
        </div>

        <div className="flex justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={onCancel}
            className="px-6 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-lg transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors font-medium flex items-center space-x-2"
          >
            <Save className="w-4 h-4" />
            <span>Save Changes</span>
          </button>
        </div>
      </div>
    </div>
  );
}
