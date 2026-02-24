"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  FileText, Trash2, Check, X, Loader2, Shield, CheckCircle,
  Plus, Edit2, Save, ChevronDown, ChevronUp, Zap, Tag,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3010";
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

interface ISOStandard { id: string; code: string; name: string; language?: string; }

const inp = "w-full px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm";

export default function TemplateCatalog() {
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingSections, setEditingSections] = useState<FillableSection[]>([]);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showISOModal, setShowISOModal] = useState(false);
  const [isoModalTemplate, setIsoModalTemplate] = useState<CatalogTemplate | null>(null);
  const [selectedISOs, setSelectedISOs] = useState<string[]>([]);

  useEffect(() => { load(); loadISOs(); }, []);

  const load = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/catalog-templates`, { headers: h() });
      setTemplates(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadISOs = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/iso-standards?active_only=false`, { headers: h() });
      setISOStandards(r.data);
    } catch (e) { console.error(e); }
  };

  const startEdit = async (t: CatalogTemplate) => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/catalog-templates/${t.id}`, { headers: h() });
      const sections: FillableSection[] = r.data.template_structure?.fillable_sections || [];
      setEditingSections(JSON.parse(JSON.stringify(sections)));
      setEditingId(t.id);
      setExpandedId(t.id);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const saveEdit = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      await axios.patch(`${API_BASE}/api/v1/catalog-templates/${editingId}/fillable-sections`,
        { fillable_sections: editingSections }, { headers: h() });
      setEditingId(null);
      await load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };

  const handleApprove = async (id: string) => {
    try {
      await axios.put(`${API_BASE}/api/v1/catalog-templates/${id}`, { status: "approved" }, { headers: h() });
      load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await axios.delete(`${API_BASE}/api/v1/catalog-templates/${id}`, { headers: h() });
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
      await axios.patch(`${API_BASE}/api/v1/catalog-templates/${isoModalTemplate.id}/iso-standards`,
        { iso_standard_ids: selectedISOs }, { headers: h() });
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

  const fmt = (d: string | null) => d ? new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }) : null;

  if (loading) return <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Template Catalog</h3>
        <p className="text-sm text-gray-500">AI-generated templates — edit placeholders, questions, and automation hooks</p>
      </div>

      {templates.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
          <FileText className="w-12 h-12 mx-auto text-gray-400 mb-3" />
          <p className="text-gray-500">No templates yet. Build an ISO standard with AI to generate templates.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div key={t.id} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              {/* Card header */}
              <div className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-semibold text-gray-900 dark:text-white text-sm">{t.name}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${t.status === "approved" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                        {t.status === "approved" ? <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3" />Approved</span> : "Draft"}
                      </span>
                      <span className="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 px-1.5 py-0.5 rounded">v{t.version_number}</span>
                    </div>
                    {t.description && <p className="text-xs text-gray-500 mb-2">{t.description}</p>}

                    {/* Stats row */}
                    <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                      <span>{t.total_fixed_sections} fixed sections</span>
                      <span>•</span>
                      <span>{t.total_fillable_sections} placeholders</span>
                      <span>•</span>
                      <span>Created {fmt(t.created_at)}</span>
                      {t.updated_at && t.updated_at !== t.created_at && <><span>•</span><span>Updated {fmt(t.updated_at)}</span></>}
                    </div>

                    {/* ISO badges */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Shield className="w-3.5 h-3.5 text-gray-400" />
                      {t.iso_codes.length > 0
                        ? t.iso_codes.map(c => <span key={c} className="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 px-1.5 py-0.5 rounded">{c}</span>)
                        : <span className="text-xs text-gray-400">No ISOs assigned</span>
                      }
                      <button onClick={() => openISOModal(t)} className="text-xs text-blue-500 hover:underline ml-1">
                        {t.iso_codes.length > 0 ? "Edit" : "Assign"}
                      </button>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 ml-3 shrink-0">
                    <button onClick={() => editingId === t.id ? setEditingId(null) : startEdit(t)}
                      className="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded" title="Edit placeholders">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}
                      className="p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                      {expandedId === t.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {t.status === "draft" && (
                      <button onClick={() => handleApprove(t.id)} className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30 rounded" title="Approve">
                        <Check className="w-4 h-4" />
                      </button>
                    )}
                    <button onClick={() => handleDelete(t.id, t.name)} className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded" title="Delete">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Expanded: editor or read-only view */}
              {expandedId === t.id && (
                <div className="border-t border-gray-100 dark:border-gray-700 p-4">
                  {editingId === t.id ? (
                    /* EDITOR MODE */
                    <div className="space-y-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Editing {editingSections.length} placeholders</span>
                        <div className="flex gap-2">
                          <button onClick={addSection} className="flex items-center gap-1 text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100">
                            <Plus className="w-3 h-3" /> Add placeholder
                          </button>
                          <button onClick={() => setEditingId(null)} className="text-xs px-2 py-1 text-gray-500 hover:bg-gray-100 rounded">Cancel</button>
                          <button onClick={saveEdit} disabled={saving}
                            className="flex items-center gap-1 text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
                            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Save
                          </button>
                        </div>
                      </div>

                      {editingSections.map((s, idx) => (
                        <div key={s.id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono text-purple-600 dark:text-purple-400 font-medium">{s.placeholder || `placeholder_${idx + 1}`}</span>
                            <button onClick={() => removeSection(idx)} className="text-red-400 hover:text-red-600">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-xs text-gray-500 mb-0.5">Title</label>
                              <input className={inp} value={s.title} onChange={e => updateSection(idx, "title", e.target.value)} />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-500 mb-0.5">Placeholder key</label>
                              <input className={inp} value={s.placeholder} onChange={e => updateSection(idx, "placeholder", e.target.value)} placeholder="{{key}}" />
                            </div>
                          </div>

                          <div>
                            <label className="block text-xs text-gray-500 mb-0.5">Question (shown to customer)</label>
                            <textarea className={inp} rows={2} value={s.question} onChange={e => updateSection(idx, "question", e.target.value)} />
                          </div>

                          <div className="grid grid-cols-3 gap-2">
                            <div>
                              <label className="block text-xs text-gray-500 mb-0.5">Automation source</label>
                              <select className={inp} value={s.automation_source} onChange={e => updateSection(idx, "automation_source", e.target.value)}>
                                {AUTOMATION_SOURCES.map(a => <option key={a} value={a}>{a}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs text-gray-500 mb-0.5">Trigger event</label>
                              <select className={inp} value={s.trigger_event} onChange={e => updateSection(idx, "trigger_event", e.target.value)}>
                                {TRIGGER_EVENTS.map(e => <option key={e} value={e}>{e}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs text-gray-500 mb-0.5">ISO reference</label>
                              <input className={inp} value={s.iso_reference || ""} onChange={e => updateSection(idx, "iso_reference", e.target.value)} />
                            </div>
                          </div>

                          <div className="flex items-center gap-4">
                            <label className="flex items-center gap-1.5 cursor-pointer">
                              <input type="checkbox" checked={s.is_mandatory} onChange={e => updateSection(idx, "is_mandatory", e.target.checked)} className="w-3.5 h-3.5" />
                              <span className="text-xs text-gray-600 dark:text-gray-400">Mandatory</span>
                            </label>
                            <label className="flex items-center gap-1.5 cursor-pointer">
                              <input type="checkbox" checked={s.auto_fillable} onChange={e => updateSection(idx, "auto_fillable", e.target.checked)} className="w-3.5 h-3.5" />
                              <span className="text-xs text-gray-600 dark:text-gray-400 flex items-center gap-1"><Zap className="w-3 h-3 text-amber-500" />Auto-fillable</span>
                            </label>
                            {s.iso_control_title && <span className="text-xs text-gray-400 italic truncate">{s.iso_control_title}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    /* READ-ONLY VIEW */
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-gray-500 mb-2">Placeholders ({t.total_fillable_sections})</p>
                      {/* We show a summary — full data loaded on edit */}
                      <p className="text-xs text-gray-400">Click <Edit2 className="w-3 h-3 inline" /> to view and edit all placeholder details.</p>
                      {t.semantic_tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {t.semantic_tags.map(tag => (
                            <span key={tag} className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 px-1.5 py-0.5 rounded flex items-center gap-1">
                              <Tag className="w-2.5 h-2.5" />{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ISO Assignment Modal */}
      {showISOModal && isoModalTemplate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-gray-900 dark:text-white">Assign ISO Standards</h3>
              <button onClick={() => setShowISOModal(false)}><X className="w-5 h-5 text-gray-500" /></button>
            </div>
            <div className="space-y-1 max-h-64 overflow-y-auto mb-4">
              {isoStandards.map(iso => (
                <label key={iso.id} className="flex items-center gap-2 p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded cursor-pointer">
                  <input type="checkbox" checked={selectedISOs.includes(iso.id)}
                    onChange={e => setSelectedISOs(e.target.checked ? [...selectedISOs, iso.id] : selectedISOs.filter(i => i !== iso.id))}
                    className="w-4 h-4" />
                  <span className="text-sm text-gray-900 dark:text-white">{iso.code}{iso.language && iso.language !== "en" ? ` (${iso.language.toUpperCase()})` : ""} — {iso.name}</span>
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowISOModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={saveISOs} className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
