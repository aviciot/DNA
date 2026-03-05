"use client";

import { useState, useEffect } from "react";
import { X, Save, Eye, Edit2, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import api from "@/lib/api";

interface FillableSection {
  id: string;
  title: string;
  placeholder: string;
  question: string;
  is_mandatory: boolean;
  type?: string;
  content?: string | null;
}

interface FixedSection {
  title?: string;
  content?: string;
  section_type?: string;
}

interface Props {
  customerId: string;
  docId: string;
  docName: string;
  templateId: string;
  onClose: () => void;
}

const inp = "w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

export default function DocumentCustomizePanel({ customerId, docId, docName, templateId, onClose }: Props) {
  const [tab, setTab] = useState<"edit" | "preview">("edit");
  const [fillable, setFillable] = useState<FillableSection[]>([]);
  const [fixed, setFixed] = useState<FixedSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedFixed, setExpandedFixed] = useState<Set<number>>(new Set());
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    loadContent();
  }, [docId]);

  const loadContent = async () => {
    try {
      setLoading(true);
      // Fetch the document content via the plan documents endpoint — we already have it
      // but we need the full content JSONB. Use the template endpoint as fallback for structure.
      // Actually fetch from a dedicated endpoint — we'll use the existing template detail
      // and overlay with customer doc content.
      const r = await api.get(`/api/v1/iso-customers/${customerId}/documents/${docId}/content`);
      setFillable(r.data.fillable_sections || []);
      setFixed(r.data.fixed_sections || []);
    } catch {
      // fallback: load from template structure
      try {
        const r = await api.get(`/api/v1/catalog-templates/${templateId}`);
        const structure = r.data.template_structure || {};
        setFillable(structure.fillable_sections || []);
        setFixed(structure.fixed_sections || []);
      } catch (e) {
        console.error("Failed to load document content", e);
      }
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/api/v1/iso-customers/${customerId}/documents/${docId}/content`, {
        fillable_sections: fillable,
        fixed_sections: fixed,
      });
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    } finally {
      setSaving(false);
    }
  };

  const loadPreview = async () => {
    setPreviewLoading(true);
    setPreviewHtml("");
    try {
      const token = localStorage.getItem("access_token");
      const r = await fetch(
        `/api/document-preview?docId=${docId}&lang=en`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPreviewHtml(await r.text());
    } catch (e) {
      console.error(e);
    } finally {
      setPreviewLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "preview") loadPreview();
  }, [tab]);

  const updateFillable = (idx: number, field: keyof FillableSection, value: any) => {
    setFillable(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  const updateFixed = (idx: number, field: keyof FixedSection, value: string) => {
    setFixed(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="w-full max-w-2xl bg-white shadow-2xl flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 flex-shrink-0">
          <div>
            <h3 className="font-bold text-slate-900 text-sm truncate max-w-xs">{docName}</h3>
            <p className="text-xs text-slate-400 mt-0.5">Customize document</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={save}
              disabled={saving || tab === "preview"}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 font-medium"
            >
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              Save
            </button>
            <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100 flex-shrink-0">
          {(["edit", "preview"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex items-center gap-1.5 px-5 py-3 text-xs font-semibold border-b-2 transition-colors ${
                tab === t
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-slate-400 hover:text-slate-600"
              }`}
            >
              {t === "edit" ? <Edit2 className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              {t === "edit" ? "Edit" : "Preview"}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
            </div>
          ) : tab === "edit" ? (
            <div className="p-6 space-y-6">
              {/* Fixed sections */}
              {fixed.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Fixed Sections</p>
                  <div className="space-y-2">
                    {fixed.map((sec, idx) => {
                      const isOpen = expandedFixed.has(idx);
                      return (
                        <div key={idx} className="border border-slate-200 rounded-xl overflow-hidden">
                          <button
                            onClick={() => {
                              const next = new Set(expandedFixed);
                              isOpen ? next.delete(idx) : next.add(idx);
                              setExpandedFixed(next);
                            }}
                            className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
                          >
                            <span className="text-xs font-medium text-slate-700 truncate">
                              {sec.title || sec.section_type || `Section ${idx + 1}`}
                            </span>
                            {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />}
                          </button>
                          {isOpen && (
                            <div className="p-4 space-y-3">
                              {sec.title !== undefined && (
                                <div>
                                  <label className="block text-xs font-medium text-slate-500 mb-1">Title</label>
                                  <input className={inp} value={sec.title} onChange={e => updateFixed(idx, "title", e.target.value)} />
                                </div>
                              )}
                              <div>
                                <label className="block text-xs font-medium text-slate-500 mb-1">Content</label>
                                <textarea className={inp} rows={4} value={sec.content || ""} onChange={e => updateFixed(idx, "content", e.target.value)} />
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Fillable sections */}
              {fillable.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Fillable Sections</p>
                  <div className="space-y-3">
                    {fillable.map((s, idx) => (
                      <div key={s.id || idx} className="border border-slate-200 rounded-xl overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
                          <span className="text-xs font-mono text-violet-600 font-semibold bg-violet-50 px-2 py-0.5 rounded">
                            {s.placeholder || `{{field_${idx + 1}}}`}
                          </span>
                          {s.is_mandatory && (
                            <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded font-medium">Required</span>
                          )}
                        </div>
                        <div className="p-4 space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="block text-xs font-medium text-slate-500 mb-1">Title / Label</label>
                              <input className={inp} value={s.title} onChange={e => updateFillable(idx, "title", e.target.value)} />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-500 mb-1">Placeholder key</label>
                              <input className={inp} value={s.placeholder} onChange={e => updateFillable(idx, "placeholder", e.target.value)} />
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">
                              Question <span className="text-slate-400 font-normal">— shown during interview</span>
                            </label>
                            <textarea className={inp} rows={2} value={s.question} onChange={e => updateFillable(idx, "question", e.target.value)} />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {fillable.length === 0 && fixed.length === 0 && (
                <div className="text-center py-12 text-slate-400 text-sm">No sections found</div>
              )}
            </div>
          ) : (
            <div className="h-full" style={{ minHeight: "600px" }}>
              {previewLoading ? (
                <div className="flex items-center justify-center h-40">
                  <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
                </div>
              ) : previewHtml ? (
                <iframe
                  srcDoc={previewHtml}
                  className="w-full h-full border-0"
                  title="Document preview"
                  sandbox="allow-same-origin"
                  style={{ minHeight: "600px" }}
                />
              ) : (
                <div className="flex items-center justify-center h-40 text-slate-400 text-sm">
                  Failed to load preview
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
