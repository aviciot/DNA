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

const inp = "w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

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

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Templates</h2>
          <p className="text-sm text-slate-500 mt-0.5">{templates.length} template{templates.length !== 1 ? "s" : ""} — edit placeholders, questions and automation hooks</p>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-100 p-16 text-center">
          <FileText className="w-10 h-10 mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500 font-medium">No templates yet</p>
          <p className="text-sm text-slate-400 mt-1">Build an ISO standard with AI to generate templates automatically.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-100 hover:border-slate-200 hover:shadow-sm transition-all">
              <div className="p-5">
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Name + status */}
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      <span className="font-semibold text-slate-900">{t.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                        t.status === "approved"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-amber-50 text-amber-700"
                      }`}>
                        {t.status === "approved" ? "Approved" : "Draft"}
                      </span>
                      <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium">v{t.version_number}</span>
                    </div>
                    {t.description && <p className="text-xs text-slate-400 mb-2 line-clamp-1">{t.description}</p>}

                    {/* Stats + ISO */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs bg-slate-50 text-slate-600 px-2.5 py-1 rounded-lg font-medium">{t.total_fixed_sections} sections</span>
                      <span className="text-xs bg-blue-50 text-blue-600 px-2.5 py-1 rounded-lg font-medium">{t.total_fillable_sections} placeholders</span>
                      <span className="text-xs text-slate-400">{fmt(t.updated_at || t.created_at)}</span>
                      <div className="flex items-center gap-1 ml-1">
                        <Shield className="w-3 h-3 text-slate-300" />
                        {t.iso_codes.length > 0
                          ? t.iso_codes.map(c => <span key={c} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-lg font-medium">{c}</span>)
                          : <span className="text-xs text-slate-400">No ISO</span>
                        }
                        <button onClick={() => openISOModal(t)} className="text-xs text-blue-500 hover:text-blue-700 font-medium ml-1">
                          {t.iso_codes.length > 0 ? "Edit" : "Assign"}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={() => editingId === t.id ? setEditingId(null) : startEdit(t)}
                      className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors" title="Edit placeholders">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}
                      className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
                      {expandedId === t.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {t.status === "draft" && (
                      <button onClick={() => handleApprove(t.id)}
                        className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors" title="Approve">
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

              {/* Expanded: editor or read-only view */}
              {expandedId === t.id && (
                <div className="border-t border-slate-100 p-5">
                  {editingId === t.id ? (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold text-slate-700">Editing {editingSections.length} placeholders</span>
                        <div className="flex gap-2">
                          <button onClick={addSection} className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 font-medium">
                            <Plus className="w-3 h-3" /> Add placeholder
                          </button>
                          <button onClick={() => setEditingId(null)} className="text-xs px-3 py-1.5 text-slate-500 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
                          <button onClick={saveEdit} disabled={saving}
                            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
                            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Save
                          </button>
                        </div>
                      </div>

                      {editingSections.map((s, idx) => (
                        <div key={s.id} className="border border-slate-200 rounded-xl p-4 space-y-3 bg-slate-50/50">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono text-violet-600 font-semibold bg-violet-50 px-2 py-0.5 rounded">{s.placeholder || `{{placeholder_${idx + 1}}}`}</span>
                            <button onClick={() => removeSection(idx)} className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>

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
                            <label className="block text-xs font-medium text-slate-500 mb-1">Question shown to customer</label>
                            <textarea className={inp} rows={2} value={s.question} onChange={e => updateSection(idx, "question", e.target.value)} />
                          </div>

                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <label className="block text-xs font-medium text-slate-500 mb-1">Automation source</label>
                              <select className={inp} value={s.automation_source} onChange={e => updateSection(idx, "automation_source", e.target.value)}>
                                {AUTOMATION_SOURCES.map(a => <option key={a} value={a}>{a}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-500 mb-1">Trigger event</label>
                              <select className={inp} value={s.trigger_event} onChange={e => updateSection(idx, "trigger_event", e.target.value)}>
                                {TRIGGER_EVENTS.map(e => <option key={e} value={e}>{e}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-500 mb-1">ISO reference</label>
                              <input className={inp} value={s.iso_reference || ""} onChange={e => updateSection(idx, "iso_reference", e.target.value)} />
                            </div>
                          </div>

                          <div className="flex items-center gap-4">
                            <label className="flex items-center gap-1.5 cursor-pointer">
                              <input type="checkbox" checked={s.is_mandatory} onChange={e => updateSection(idx, "is_mandatory", e.target.checked)} className="w-3.5 h-3.5 accent-blue-600" />
                              <span className="text-xs text-slate-600 font-medium">Mandatory</span>
                            </label>
                            <label className="flex items-center gap-1.5 cursor-pointer">
                              <input type="checkbox" checked={s.auto_fillable} onChange={e => updateSection(idx, "auto_fillable", e.target.checked)} className="w-3.5 h-3.5 accent-blue-600" />
                              <span className="text-xs text-slate-600 font-medium flex items-center gap-1"><Zap className="w-3 h-3 text-amber-500" />Auto-fillable</span>
                            </label>
                            {s.iso_control_title && <span className="text-xs text-slate-400 italic truncate">{s.iso_control_title}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-slate-500">Placeholders ({t.total_fillable_sections})</p>
                      <p className="text-xs text-slate-400">Click <Edit2 className="w-3 h-3 inline" /> to view and edit all placeholder details.</p>
                      {t.semantic_tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {t.semantic_tags.map(tag => (
                            <span key={tag} className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-lg flex items-center gap-1">
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
                  <span className="text-sm text-slate-800 font-medium">{iso.code}</span>
                  <span className="text-xs text-slate-400">{iso.name}</span>
                  {iso.language && iso.language !== "en" && <span className="text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-medium uppercase">{iso.language}</span>}
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
