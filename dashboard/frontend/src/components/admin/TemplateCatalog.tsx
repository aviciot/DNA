"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  FileText, Trash2, Check, X, Loader2, Shield,
  Plus, Edit2, Save, ChevronDown, ChevronUp, Zap, Tag, Search, Filter, Eye, Printer, Download,
} from "lucide-react";

import api from "@/lib/api";
const h = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });

const AUTOMATION_SOURCES = ["manual", "hr_system", "asset_inventory", "risk_register", "ad_directory", "scan_tool", "ticketing_system"];
const TRIGGER_EVENTS = ["annual_review", "employee_onboarding", "system_change", "incident", "audit"];

interface FillableSection {
  id: string; title: string; placeholder: string; question: string;
  is_mandatory: boolean; is_required: boolean; auto_fillable: boolean;
  automation_source: string; trigger_event: string;
  semantic_tags: string[]; iso_reference?: string; iso_control_title?: string;
  location?: string; type?: string;
}

interface CatalogTemplate {
  id: string; name: string; description: string | null;
  iso_standard: string | null; status: string;
  version_number: number; total_fixed_sections: number;
  total_fillable_sections: number; semantic_tags: string[];
  iso_codes: string[]; created_at: string;
  updated_at: string | null; approved_at: string | null;
}

interface ISOStandard { id: string; code: string; name: string; language?: string; color?: string; }

const inp = "w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

export default function TemplateCatalog() {
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterISO, setFilterISO] = useState("");

  // Edit modal state
  const [editingTemplate, setEditingTemplate] = useState<CatalogTemplate | null>(null);
  const [editingSections, setEditingSections] = useState<FillableSection[]>([]);
  const [saving, setSaving] = useState(false);
  const [automationExpanded, setAutomationExpanded] = useState<Record<number, boolean>>({});

  // ISO assign modal
  const [showISOModal, setShowISOModal] = useState(false);
  const [isoModalTemplate, setIsoModalTemplate] = useState<CatalogTemplate | null>(null);
  const [selectedISOs, setSelectedISOs] = useState<string[]>([]);

  // Preview modal
  const [previewTemplate, setPreviewTemplate] = useState<CatalogTemplate | null>(null);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [previewLang, setPreviewLang] = useState("en");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");

  useEffect(() => { load(); loadISOs(); }, []);

  const load = async () => {
    try {
      const r = await api.get("/api/v1/catalog-templates");
      setTemplates(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadISOs = async () => {
    try {
      const r = await api.get("/api/v1/iso-standards?active_only=false");
      setISOStandards(r.data);
    } catch (e) { console.error(e); }
  };

  const startEdit = async (t: CatalogTemplate) => {
    try {
      const r = await api.get(`/api/v1/catalog-templates/${t.id}`);
      const sections: FillableSection[] = r.data.template_structure?.fillable_sections || [];
      setEditingSections(JSON.parse(JSON.stringify(sections)));
      setEditingTemplate(t);
      setAutomationExpanded({});
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const saveEdit = async () => {
    if (!editingTemplate) return;
    setSaving(true);
    try {
      await api.patch(`/api/v1/catalog-templates/${editingTemplate.id}/fillable-sections`,
        { fillable_sections: editingSections });
      setEditingTemplate(null);
      await load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };

  const handleApprove = async (id: string) => {
    try {
      await api.put(`/api/v1/catalog-templates/${id}`, { status: "approved" });
      load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await api.delete(`/api/v1/catalog-templates/${id}`);
      load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const openISOModal = (t: CatalogTemplate) => {
    setIsoModalTemplate(t);
    setSelectedISOs(isoStandards.filter(iso => t.iso_codes.includes(iso.code)).map(iso => iso.id));
    setShowISOModal(true);
  };

  const saveISOs = async () => {
    if (!isoModalTemplate) return;
    try {
      await api.patch(`/api/v1/catalog-templates/${isoModalTemplate.id}/iso-standards`,
        { iso_standard_ids: selectedISOs });
      setShowISOModal(false);
      load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const updateSection = (idx: number, field: keyof FillableSection, value: any) => {
    setEditingSections(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  const addSection = () => {
    setEditingSections(prev => [...prev, {
      id: `field_${Date.now()}`, title: "", placeholder: "", question: "",
      is_mandatory: false, is_required: false, auto_fillable: false,
      automation_source: "manual", trigger_event: "annual_review", semantic_tags: [],
    }]);
  };

  const removeSection = (idx: number) => {
    setEditingSections(prev => prev.filter((_, i) => i !== idx));
  };

  const openPreview = async (t: CatalogTemplate, lang = "en") => {
    setPreviewTemplate(t);
    setPreviewLang(lang);
    setPreviewLoading(true);
    setPreviewHtml("");
    try {
      const token = localStorage.getItem("access_token");
      const r = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/document-design/preview/template/${t.id}?lang=${lang}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const html = await r.text();
      setPreviewHtml(html);
    } catch (e) { console.error(e); }
    finally { setPreviewLoading(false); }
  };

  const switchPreviewLang = (lang: string) => {
    if (previewTemplate) openPreview(previewTemplate, lang);
  };

  const fmt = (d: string | null) => d ? new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : null;

  // Get ISO color for a template
  const getISOColor = (t: CatalogTemplate) => {
    if (t.iso_codes.length === 0) return "#94a3b8";
    const iso = isoStandards.find(i => t.iso_codes.includes(i.code));
    return iso?.color || "#3b82f6";
  };

  // Filter templates
  const filtered = templates.filter(t => {
    const matchSearch = !search || t.name.toLowerCase().includes(search.toLowerCase());
    const matchISO = !filterISO || t.iso_codes.includes(filterISO);
    return matchSearch && matchISO;
  });

  // Unique ISO codes across all templates for filter
  const allIsoCodes = [...new Set(templates.flatMap(t => t.iso_codes))].sort();

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Templates</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {filtered.length} of {templates.length} templates
            {" · "}
            <span className="text-slate-400">Approve = make available for customer assignment</span>
          </p>
        </div>
      </div>

      {/* Search + filter */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Search templates..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <select
            className="pl-9 pr-8 py-2 border border-slate-200 rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none"
            value={filterISO}
            onChange={e => setFilterISO(e.target.value)}
          >
            <option value="">All ISO standards</option>
            {allIsoCodes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-100 p-16 text-center">
          <FileText className="w-10 h-10 mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500 font-medium">{search || filterISO ? "No templates match" : "No templates yet"}</p>
          <p className="text-sm text-slate-400 mt-1">Build an ISO standard with AI to generate templates automatically.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((t) => {
            const isoColor = getISOColor(t);
            return (
              <div key={t.id} className="bg-white rounded-xl border border-slate-100 hover:border-slate-200 hover:shadow-sm transition-all flex overflow-hidden">
                {/* ISO color bar */}
                <div className="w-1 flex-shrink-0" style={{ backgroundColor: isoColor }} />
                <div className="flex-1 p-4">
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-semibold text-slate-900 text-sm">{t.name}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                          t.status === "approved" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                        }`}>
                          {t.status === "approved" ? "Approved" : "Draft"}
                        </span>
                        <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium">v{t.version_number}</span>
                      </div>

                      <div className="flex items-center gap-2 flex-wrap mt-1.5">
                        <span className="text-xs bg-slate-50 text-slate-600 px-2 py-0.5 rounded-lg font-medium">{t.total_fixed_sections} sections</span>
                        <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-lg font-medium">{t.total_fillable_sections} placeholders</span>
                        <span className="text-xs text-slate-400">{fmt(t.updated_at || t.created_at)}</span>
                        <div className="flex items-center gap-1">
                          <Shield className="w-3 h-3 text-slate-300" />
                          {t.iso_codes.length > 0
                            ? t.iso_codes.map(c => (
                                <span key={c} className="text-xs px-2 py-0.5 rounded-lg font-medium text-white"
                                  style={{ backgroundColor: isoColor }}>{c}</span>
                              ))
                            : <span className="text-xs text-slate-400">No ISO</span>
                          }
                          <button onClick={() => openISOModal(t)} className="text-xs text-blue-500 hover:text-blue-700 font-medium ml-1">
                            {t.iso_codes.length > 0 ? "Edit" : "Assign"}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button onClick={() => openPreview(t)}
                        className="p-2 text-slate-400 hover:text-violet-600 hover:bg-violet-50 rounded-lg transition-colors" title="Preview document">
                        <Eye className="w-4 h-4" />
                      </button>
                      <button onClick={() => startEdit(t)}
                        className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors" title="Edit placeholders">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      {t.status === "draft" && (
                        <button onClick={() => handleApprove(t.id)}
                          className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                          title="Approve — makes this template available for customer assignment">
                          <Check className="w-4 h-4" />
                        </button>
                      )}
                      <button onClick={() => handleDelete(t.id, t.name)}
                        className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Delete">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit Modal */}
      {editingTemplate && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 flex-shrink-0">
              <div>
                <h3 className="font-bold text-slate-900">{editingTemplate.name}</h3>
                <p className="text-xs text-slate-500 mt-0.5">Editing {editingSections.length} placeholders</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={addSection}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 font-medium">
                  <Plus className="w-3 h-3" /> Add
                </button>
                <button onClick={() => setEditingTemplate(null)}
                  className="text-xs px-3 py-1.5 text-slate-500 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
                <button onClick={saveEdit} disabled={saving}
                  className="flex items-center gap-1.5 text-xs px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
                  {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Save
                </button>
                <button onClick={() => setEditingTemplate(null)} className="p-1.5 hover:bg-slate-100 rounded-lg ml-1">
                  <X className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            </div>

            {/* Scrollable sections */}
            <div className="overflow-y-auto flex-1 p-6 space-y-4">
              {editingSections.map((s, idx) => (
                <div key={s.id} className="border border-slate-200 rounded-xl overflow-hidden">
                  {/* Section header */}
                  <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
                    <span className="text-xs font-mono text-violet-600 font-semibold bg-violet-50 px-2 py-0.5 rounded">
                      {s.placeholder || `{{placeholder_${idx + 1}}}`}
                    </span>
                    <button onClick={() => removeSection(idx)}
                      className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="p-4 space-y-3">
                    {/* Core fields */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-slate-500 mb-1">Title</label>
                        <input className={inp} value={s.title} onChange={e => updateSection(idx, "title", e.target.value)} />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-500 mb-1">Placeholder key</label>
                        <input className={inp} value={s.placeholder} onChange={e => updateSection(idx, "placeholder", e.target.value)} placeholder="{{key}}" />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-500 mb-1">
                        Question <span className="text-slate-400 font-normal">— shown to customer during interview</span>
                      </label>
                      <textarea className={inp} rows={2} value={s.question} onChange={e => updateSection(idx, "question", e.target.value)} />
                    </div>

                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={s.is_mandatory} onChange={e => updateSection(idx, "is_mandatory", e.target.checked)} className="w-3.5 h-3.5 accent-blue-600" />
                        <span className="text-xs text-slate-600 font-medium">Mandatory</span>
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={s.auto_fillable} onChange={e => updateSection(idx, "auto_fillable", e.target.checked)} className="w-3.5 h-3.5 accent-blue-600" />
                        <span className="text-xs text-slate-600 font-medium flex items-center gap-1">
                          <Zap className="w-3 h-3 text-amber-500" />Auto-fillable
                          <span className="text-slate-400 font-normal">(can be filled from integrations)</span>
                        </span>
                      </label>
                    </div>

                    {/* Automation hooks — collapsed by default */}
                    <div className="border border-slate-100 rounded-lg overflow-hidden">
                      <button
                        onClick={() => setAutomationExpanded(prev => ({ ...prev, [idx]: !prev[idx] }))}
                        className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 transition-colors text-left">
                        <span className="text-xs font-medium text-slate-500 flex items-center gap-1.5">
                          <Zap className="w-3 h-3 text-amber-400" />
                          Automation hooks
                          <span className="text-slate-400 font-normal">— for future integrations</span>
                        </span>
                        {automationExpanded[idx] ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                      </button>
                      {automationExpanded[idx] && (
                        <div className="p-3 grid grid-cols-3 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">
                              Automation source
                              <span className="block text-slate-400 font-normal">Which system fills this</span>
                            </label>
                            <select className={inp} value={s.automation_source} onChange={e => updateSection(idx, "automation_source", e.target.value)}>
                              {AUTOMATION_SOURCES.map(a => <option key={a} value={a}>{a}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">
                              Trigger event
                              <span className="block text-slate-400 font-normal">When to auto-fill</span>
                            </label>
                            <select className={inp} value={s.trigger_event} onChange={e => updateSection(idx, "trigger_event", e.target.value)}>
                              {TRIGGER_EVENTS.map(e => <option key={e} value={e}>{e}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">
                              ISO reference
                              <span className="block text-slate-400 font-normal">Clause or control ID</span>
                            </label>
                            <input className={inp} value={s.iso_reference || ""} onChange={e => updateSection(idx, "iso_reference", e.target.value)} />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {previewTemplate && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl flex flex-col" style={{width: '95vw', height: '95vh'}}>
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 flex-shrink-0">
              <div className="flex items-center gap-3">
                <Eye className="w-5 h-5 text-violet-500" />
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">{previewTemplate.name}</h3>
                  <p className="text-xs text-slate-400">Document preview</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    const iframe = document.querySelector<HTMLIFrameElement>('iframe[title="Template preview"]');
                    iframe?.contentWindow?.print();
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  <Printer className="w-3.5 h-3.5" /> Print
                </button>
                <div className="relative">
                  <button
                    onClick={() => setShowDownloadMenu(v => !v)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" /> Download
                  </button>
                  {showDownloadMenu && (
                    <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-10 min-w-[130px]">
                      <button
                        onClick={() => {
                          const blob = new Blob([previewHtml], { type: 'text/html' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `${previewTemplate.name.replace(/[^a-z0-9]/gi, '_')}_${previewLang}.html`;
                          a.click();
                          URL.revokeObjectURL(url);
                          setShowDownloadMenu(false);
                        }}
                        className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 rounded-t-lg"
                      >
                        Save as HTML
                      </button>
                      <button
                        onClick={async () => {
                          const token2 = localStorage.getItem('access_token');
                          const r = await fetch(
                            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/document-design/preview/template/${previewTemplate.id}/pdf?lang=${previewLang}`,
                            { headers: { Authorization: `Bearer ${token2}` } }
                          );
                          const blob = await r.blob();
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          const date = new Date().toISOString().slice(0,10);
                          a.download = `${previewTemplate.name}_${date}.pdf`;
                          a.click();
                          URL.revokeObjectURL(url);
                          setShowDownloadMenu(false);
                        }}
                        className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 rounded-b-lg"
                      >
                        Save as PDF
                      </button>
                    </div>
                  )}
                </div>
                {/* Language selector */}
                <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                  {["en", "he"].map(lang => (
                    <button
                      key={lang}
                      onClick={() => switchPreviewLang(lang)}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                        previewLang === lang
                          ? "bg-white text-slate-900 shadow-sm"
                          : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      {lang === "en" ? "English" : "עברית"}
                    </button>
                  ))}
                </div>
                <button onClick={() => { setPreviewTemplate(null); setShowDownloadMenu(false); }} className="p-1.5 hover:bg-slate-100 rounded-lg">
                  <X className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            </div>

            {/* Preview content */}
            <div className="flex-1 overflow-hidden relative" style={{minHeight: 0}}>
              {previewLoading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
                </div>
              ) : previewHtml ? (
                <iframe
                  srcDoc={previewHtml}
                  className="w-full h-full border-0"
                  title="Template preview"
                  sandbox="allow-same-origin"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                  Failed to load preview
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ISO Assignment Modal */}
      {showISOModal && isoModalTemplate && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-slate-900">Assign ISO Standards</h3>
              <button onClick={() => setShowISOModal(false)} className="p-1.5 hover:bg-slate-100 rounded-lg"><X className="w-4 h-4 text-slate-500" /></button>
            </div>
            <div className="space-y-1 max-h-64 overflow-y-auto mb-4">
              {isoStandards.map(iso => (
                <label key={iso.id} className="flex items-center gap-2.5 p-2.5 hover:bg-slate-50 rounded-lg cursor-pointer">
                  <input type="checkbox" checked={selectedISOs.includes(iso.id)}
                    onChange={e => setSelectedISOs(e.target.checked ? [...selectedISOs, iso.id] : selectedISOs.filter(i => i !== iso.id))}
                    className="w-4 h-4 accent-blue-600" />
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: iso.color || "#3b82f6" }} />
                  <span className="text-sm text-slate-800 font-medium">{iso.code}</span>
                  <span className="text-xs text-slate-400 truncate">{iso.name}</span>
                  {iso.language && iso.language !== "en" && <span className="text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-medium uppercase flex-shrink-0">{iso.language}</span>}
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowISOModal(false)} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
              <button onClick={saveISOs} className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium shadow-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
