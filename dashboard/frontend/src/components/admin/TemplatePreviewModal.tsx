"use client";

import { X, FileText, Lock, Edit, Tag } from "lucide-react";
import { useState } from "react";

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
  total_fixed_sections: number;
  total_fillable_sections: number;
  semantic_tags: string[];
}

interface TemplatePreviewModalProps {
  template: TemplateDetail;
  onClose: () => void;
}

export default function TemplatePreviewModal({
  template,
  onClose,
}: TemplatePreviewModalProps) {
  const [activeTab, setActiveTab] = useState<"fixed" | "fillable">("fillable");
  const structure = template.template_structure;

  // Safety checks
  const fixedSections = structure?.fixed_sections || [];
  const fillableSections = structure?.fillable_sections || [];
  const metadata = structure?.metadata;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              {structure?.document_title || template.name}
            </h3>
            <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
              <span>Source: {template.source_filename}</span>
              <span className="flex items-center space-x-1">
                <Lock className="w-4 h-4 text-blue-600" />
                <span>{fixedSections.length} fixed sections</span>
              </span>
              <span className="flex items-center space-x-1">
                <Edit className="w-4 h-4 text-green-600" />
                <span>{fillableSections.length} fillable sections</span>
              </span>
            </div>
            {metadata && (
              <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Parsed: {new Date(metadata.parsed_at).toLocaleString()}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setActiveTab("fillable")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === "fillable"
                ? "border-b-2 border-green-600 text-green-600 bg-white dark:bg-gray-800"
                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            }`}
          >
            <div className="flex items-center space-x-2">
              <Edit className="w-4 h-4" />
              <span>Fillable Sections ({fillableSections.length})</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab("fixed")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === "fixed"
                ? "border-b-2 border-blue-600 text-blue-600 bg-white dark:bg-gray-800"
                : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            }`}
          >
            <div className="flex items-center space-x-2">
              <Lock className="w-4 h-4" />
              <span>Fixed Sections ({fixedSections.length})</span>
            </div>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {activeTab === "fillable" ? (
            <div className="space-y-4">
              {fillableSections.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  No fillable sections found
                </div>
              ) : (
                fillableSections.map((section, idx) => (
                  <div
                    key={section.id || idx}
                    className="bg-green-50 dark:bg-green-900/20 rounded-lg border-2 border-green-200 dark:border-green-700 p-5"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                          {section.title}
                        </h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          📍 Location: {section.location}
                        </p>
                      </div>
                      <span className="px-3 py-1 bg-green-600 text-white text-xs font-semibold rounded-full">
                        {section.type}
                      </span>
                    </div>

                    {section.current_content && (
                      <div className="bg-white dark:bg-gray-800 rounded p-3 mb-3">
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Current Content:</p>
                        <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                          {section.current_content}
                        </p>
                      </div>
                    )}

                    {section.placeholder && (
                      <div className="text-sm text-gray-600 dark:text-gray-400 italic mb-3">
                        Placeholder: "{section.placeholder}"
                      </div>
                    )}

                    {section.format && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                        Format: {section.format}
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
                ))
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {fixedSections.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  No fixed sections found
                </div>
              ) : (
                fixedSections.map((section, idx) => (
                  <div
                    key={section.id || idx}
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
                        {section.content.substring(0, 500)}
                        {section.content.length > 500 && "..."}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {activeTab === "fillable" ? (
              <p><strong>Fillable sections</strong> are where customers provide information. Semantic tags enable smart mapping.</p>
            ) : (
              <p><strong>Fixed sections</strong> are policy text that stays the same across all customers.</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
