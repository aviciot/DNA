"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { Shield, Plus, Edit2, Trash2, X, Check, Loader2, FileText, Users, AlertCircle, Sparkles, Download } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3010";

interface AIMetadata {
  overview?: string; total_clauses?: number; total_controls?: number;
  key_themes?: string[]; document_count?: number; language?: string;
  built_by_ai?: boolean; model?: string; cost_usd?: number;
}

interface ISOStandard {
  id: string; code: string; name: string; description: string | null;
  requirements_summary: string | null; active: boolean; display_order: number;
  color?: string; ai_metadata?: AIMetadata | null; tags?: string[]; language?: string;
  template_count: number; customer_count: number;
  created_at: string; updated_at: string;
}

const BLANK_ISO = { code: "", name: "", description: "", requirements_summary: "", active: true, display_order: 0, color: "#3b82f6" };
const BLANK_BUILD = { iso_code: "", iso_name: "", iso_description: "", iso_language: "en", iso_color: "#3b82f6", template_format: "legacy" };

const inp = "w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

const PRESET_COLORS = [
  "#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
];

function ColorPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {PRESET_COLORS.map(c => (
        <button key={c} type="button" onClick={() => onChange(c)}
          className={`w-6 h-6 rounded-full transition-all ${
            value === c ? "ring-2 ring-offset-2 ring-slate-400 scale-110" : "hover:scale-110"
          }`}
          style={{ backgroundColor: c }} />
      ))}
      <input type="color" value={value} onChange={e => onChange(e.target.value)}
        className="w-6 h-6 rounded-full cursor-pointer border-0 p-0" title="Custom color" />
    </div>
  );
}

export default function ISOStandards() {
  const [standards, setStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedISO, setExpandedISO] = useState<string | null>(null);
  const [isoTemplates, setISOTemplates] = useState<Record<string, any[]>>({});
  const [editingISO, setEditingISO] = useState<ISOStandard | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newISO, setNewISO] = useState(BLANK_ISO);
  const [isSaving, setIsSaving] = useState(false);
  const [deleteConfirmISO, setDeleteConfirmISO] = useState<ISOStandard | null>(null);
  const [deleteTemplates, setDeleteTemplates] = useState(false);
  const [deleteISOTemplates, setDeleteISOTemplates] = useState<{ id: string; name: string; status: string }[]>([]);
  const [loadingDeleteTemplates, setLoadingDeleteTemplates] = useState(false);
  const [showBuildModal, setShowBuildModal] = useState(false);
  const [buildForm, setBuildForm] = useState(BLANK_BUILD);
  const [buildFile, setBuildFile] = useState<File | null>(null);
  const [buildTaskId, setBuildTaskId] = useState<string | null>(null);
  const [buildStatus, setBuildStatus] = useState<{ status: string; progress: number; current_step: string } | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);

  const [downloadingISO, setDownloadingISO] = useState<string | null>(null);

  useEffect(() => { loadStandards(); }, []);

  const token = () => localStorage.getItem("access_token");
  const headers = () => ({ Authorization: `Bearer ${token()}` });

  const loadStandards = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/iso-standards?active_only=false`, { headers: headers() });
      setStandards(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadTemplatesForISO = async (isoId: string) => {
    if (isoTemplates[isoId]) { setExpandedISO(expandedISO === isoId ? null : isoId); return; }
    try {
      const r = await axios.get(`${API_BASE}/api/v1/catalog-templates?iso_standard_id=${isoId}`, { headers: headers() });
      setISOTemplates({ ...isoTemplates, [isoId]: r.data });
      setExpandedISO(isoId);
    } catch (e) { console.error(e); }
  };

  const handleSaveEdit = async () => {
    if (!editingISO) return;
    setIsSaving(true);
    try {
      await axios.put(`${API_BASE}/api/v1/iso-standards/${editingISO.id}`,
        { code: editingISO.code, name: editingISO.name, description: editingISO.description,
          requirements_summary: editingISO.requirements_summary, active: editingISO.active,
          display_order: editingISO.display_order, color: editingISO.color },
        { headers: headers() });
      await loadStandards();
      setEditingISO(null);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsSaving(false); }
  };

  const handleAddISO = async () => {
    if (!newISO.code || !newISO.name) { alert("Code and Name are required"); return; }
    setIsSaving(true);
    try {
      await axios.post(`${API_BASE}/api/v1/iso-standards`, newISO, { headers: headers() });
      await loadStandards();
      setIsAddModalOpen(false);
      setNewISO(BLANK_ISO);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsSaving(false); }
  };

  const openDeleteModal = async (s: ISOStandard) => {
    setDeleteConfirmISO(s);
    setDeleteTemplates(false);
    setDeleteISOTemplates([]);
    if (s.template_count > 0) {
      setLoadingDeleteTemplates(true);
      try {
        const r = await axios.get(`${API_BASE}/api/v1/iso-standards/${s.id}/templates`, { headers: headers() });
        setDeleteISOTemplates(r.data);
      } catch { }
      finally { setLoadingDeleteTemplates(false); }
    }
  };

  const confirmDelete = async () => {
    if (!deleteConfirmISO) return;
    try {
      await axios.delete(`${API_BASE}/api/v1/iso-standards/${deleteConfirmISO.id}?delete_templates=${deleteTemplates}`, { headers: headers() });
      await loadStandards();
      setDeleteConfirmISO(null);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); setDeleteConfirmISO(null); }
  };

  const handleBuildWithAI = async () => {
    if (!buildFile || !buildForm.iso_code || !buildForm.iso_name) { alert("PDF, code and name required"); return; }
    setIsBuilding(true);
    try {
      const fd = new FormData();
      fd.append("pdf_file", buildFile);
      Object.entries(buildForm).forEach(([k, v]) => fd.append(k, v));
      const r = await axios.post(`${API_BASE}/api/v1/iso-builder/start`, fd,
        { headers: { ...headers(), "Content-Type": "multipart/form-data" } });
      setBuildTaskId(r.data.task_id);
      setBuildStatus({ status: "pending", progress: 0, current_step: "Queued..." });
      const poll = setInterval(async () => {
        try {
          const s = await axios.get(`${API_BASE}/api/v1/iso-builder/tasks/${r.data.task_id}/status`, { headers: headers() });
          setBuildStatus({ status: s.data.status, progress: s.data.progress ?? 0, current_step: s.data.current_step ?? "" });
          if (s.data.status === "completed" || s.data.status === "failed") {
            clearInterval(poll); setIsBuilding(false);
            await loadStandards();
          }
        } catch { clearInterval(poll); setIsBuilding(false); }
      }, 2000);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); setIsBuilding(false); }
  };

  const downloadISOZip = async (s: ISOStandard) => {
    setDownloadingISO(s.id);
    try {
      const res = await fetch(`${API_BASE}/api/v1/iso-standards/${s.id}/export-zip?lang=${s.language || "en"}`,
        { headers: { Authorization: `Bearer ${token()}` } });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${s.code.replace(/[/\\]/g, "-")}.zip`;
      a.click();
    } catch (e: any) { alert(e.message); }
    finally { setDownloadingISO(null); }
  };

  const resetBuild = () => { setShowBuildModal(false); setBuildForm(BLANK_BUILD); setBuildFile(null); setBuildTaskId(null); setBuildStatus(null); setIsBuilding(false); };

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">ISO Standards</h2>
          <p className="text-sm text-slate-500 mt-0.5">{standards.length} standard{standards.length !== 1 ? "s" : ""} in library</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowBuildModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-medium transition-colors shadow-sm">
            <Sparkles className="w-4 h-4" /> Build with AI
          </button>
          <button onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors shadow-sm">
            <Plus className="w-4 h-4" /> Add Standard
          </button>
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 gap-4">
        {standards.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-100 p-16 text-center">
            <Shield className="w-10 h-10 mx-auto text-slate-300 mb-3" />
            <p className="text-slate-500 font-medium">No ISO standards yet</p>
            <p className="text-sm text-slate-400 mt-1">Upload a PDF and build with AI, or add manually</p>
          </div>
        )}
        {standards.map((s) => (
          <div key={s.id} className="bg-white rounded-xl border border-slate-100 overflow-hidden hover:border-slate-200 hover:shadow-sm transition-all">
            <div className="flex">
              {/* Color bar */}
              <div className="w-1 flex-shrink-0 rounded-l-xl" style={{ backgroundColor: s.color || "#3b82f6" }} />
              <div className="flex-1 p-5">
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Top row */}
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-base font-bold text-slate-900">{s.code}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                        s.active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
                      }`}>{s.active ? "Active" : "Inactive"}</span>
                      {s.language && s.language !== "en" && (
                        <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-semibold uppercase">{s.language}</span>
                      )}
                      {s.ai_metadata?.built_by_ai && (
                        <span className="text-xs bg-violet-50 text-violet-600 px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
                          <Sparkles className="w-3 h-3" />AI Built
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-medium text-slate-600 mb-2">{s.name}</p>
                    {s.description && <p className="text-xs text-slate-400 line-clamp-1 mb-3">{s.description}</p>}

                    {/* Stats pills */}
                    <div className="flex flex-wrap items-center gap-2">
                      {s.ai_metadata?.total_clauses != null && (
                        <span className="text-xs bg-blue-50 text-blue-600 px-2.5 py-1 rounded-lg font-medium">
                          {s.ai_metadata.total_clauses} clauses
                        </span>
                      )}
                      {s.ai_metadata?.total_controls != null && (
                        <span className="text-xs bg-violet-50 text-violet-600 px-2.5 py-1 rounded-lg font-medium">
                          {s.ai_metadata.total_controls} controls
                        </span>
                      )}
                      <span className="text-xs bg-slate-50 text-slate-600 px-2.5 py-1 rounded-lg font-medium flex items-center gap-1">
                        <FileText className="w-3 h-3" />{s.template_count} templates
                      </span>
                      <span className="text-xs bg-slate-50 text-slate-600 px-2.5 py-1 rounded-lg font-medium flex items-center gap-1">
                        <Users className="w-3 h-3" />{s.customer_count} customers
                      </span>
                      {s.template_count > 0 && (
                        <button onClick={() => loadTemplatesForISO(s.id)}
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium underline-offset-2 hover:underline">
                          {expandedISO === s.id ? "Hide templates" : "View templates"}
                        </button>
                      )}
                    </div>

                    {/* Expanded templates */}
                    {expandedISO === s.id && isoTemplates[s.id] && (
                      <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 gap-1.5">
                        {isoTemplates[s.id].map((t) => (
                          <div key={t.id} className="flex items-center gap-2 text-xs text-slate-600 bg-slate-50 rounded-lg px-2.5 py-1.5">
                            <FileText className="w-3 h-3 text-blue-400 flex-shrink-0" />
                            <span className="truncate">{t.name}</span>
                            {t.status === "approved" && <Check className="w-3 h-3 text-emerald-500 flex-shrink-0" />}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {s.template_count > 0 && (
                      <button onClick={() => downloadISOZip(s)} disabled={downloadingISO === s.id}
                        title="Download all templates as ZIP"
                        className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors disabled:opacity-50">
                        {downloadingISO === s.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                      </button>
                    )}
                    <button onClick={() => setEditingISO(s)}
                      className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => openDeleteModal(s)}
                      className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Edit Modal */}
      {editingISO && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-lg font-bold text-slate-900">Edit ISO Standard</h3>
              <button onClick={() => setEditingISO(null)} className="p-1.5 hover:bg-slate-100 rounded-lg"><X className="w-4 h-4 text-slate-500" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-xs font-medium text-gray-600 mb-1">ISO Code *</label>
                <input className={inp} value={editingISO.code} onChange={(e) => setEditingISO({ ...editingISO, code: e.target.value })} /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Name *</label>
                <input className={inp} value={editingISO.name} onChange={(e) => setEditingISO({ ...editingISO, name: e.target.value })} /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
                <textarea className={inp} rows={2} value={editingISO.description || ""} onChange={(e) => setEditingISO({ ...editingISO, description: e.target.value })} /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Requirements Summary</label>
                <textarea className={inp} rows={3} value={editingISO.requirements_summary || ""} onChange={(e) => setEditingISO({ ...editingISO, requirements_summary: e.target.value })} /></div>
              <div className="flex items-center gap-6">
                <div><label className="block text-xs font-medium text-gray-600 mb-1">Color</label>
                  <ColorPicker value={editingISO.color || "#3b82f6"} onChange={(v) => setEditingISO({ ...editingISO, color: v })} /></div>
                <label className="flex items-center gap-2 mt-4 cursor-pointer">
                  <input type="checkbox" checked={editingISO.active} onChange={(e) => setEditingISO({ ...editingISO, active: e.target.checked })} className="w-4 h-4" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Active</span>
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-slate-100">
              <button onClick={() => setEditingISO(null)} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
              <button onClick={handleSaveEdit} disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 font-medium">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Save changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteConfirmISO && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-red-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5 text-red-500" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900">Delete {deleteConfirmISO.code}?</h3>
                <p className="text-xs text-slate-500">This cannot be undone</p>
              </div>
            </div>

            {/* Associated templates */}
            {loadingDeleteTemplates ? (
              <div className="flex items-center gap-2 py-3 text-sm text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading associated templates...
              </div>
            ) : deleteISOTemplates.length > 0 && (
              <div className="mb-4">
                <p className="text-sm text-slate-600 mb-2">
                  <span className="font-semibold">{deleteISOTemplates.length}</span> template{deleteISOTemplates.length !== 1 ? "s" : ""} are linked to this ISO plan:
                </p>
                <div className="max-h-40 overflow-y-auto space-y-1 mb-3">
                  {deleteISOTemplates.map(t => (
                    <div key={t.id} className="flex items-center gap-2 text-xs text-slate-600 bg-slate-50 rounded-lg px-2.5 py-1.5">
                      <FileText className="w-3 h-3 text-blue-400 flex-shrink-0" />
                      <span className="truncate flex-1">{t.name}</span>
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                        t.status === 'approved' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'
                      }`}>{t.status}</span>
                    </div>
                  ))}
                </div>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input type="checkbox" checked={deleteTemplates} onChange={e => setDeleteTemplates(e.target.checked)}
                    className="w-4 h-4 accent-red-600" />
                  <span className="text-sm text-slate-700">Also delete these templates</span>
                </label>
                {!deleteTemplates && (
                  <p className="text-xs text-slate-400 mt-1 ml-6">Templates will be kept but unlinked from this ISO plan</p>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2 mt-2">
              <button onClick={() => setDeleteConfirmISO(null)} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
              <button onClick={confirmDelete} className="flex items-center gap-2 px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium">
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Build with AI Modal */}
      {showBuildModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-violet-50 rounded-xl flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-violet-600" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">Build ISO with AI</h3>
                    <p className="text-xs text-slate-500">Upload PDF — AI generates all templates</p>
                  </div>
                </div>
                <button onClick={resetBuild} className="p-1.5 hover:bg-slate-100 rounded-lg"><X className="w-4 h-4 text-slate-500" /></button>
              </div>
              {!buildTaskId ? (
                <div className="space-y-3">
                  <p className="text-sm text-gray-500">Upload the official ISO PDF — AI generates the standard entry and all templates.</p>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">ISO Code *</label>
                    <input className={inp} value={buildForm.iso_code} onChange={(e) => setBuildForm({ ...buildForm, iso_code: e.target.value })} placeholder="e.g. ISO 27001:2022" /></div>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">ISO Name *</label>
                    <input className={inp} value={buildForm.iso_name} onChange={(e) => setBuildForm({ ...buildForm, iso_name: e.target.value })} placeholder="e.g. Information Security Management" /></div>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
                    <input className={inp} value={buildForm.iso_description} onChange={(e) => setBuildForm({ ...buildForm, iso_description: e.target.value })} placeholder="Optional" /></div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="block text-xs font-medium text-gray-600 mb-1">Language</label>
                      <select className={inp} value={buildForm.iso_language} onChange={(e) => setBuildForm({ ...buildForm, iso_language: e.target.value })}>
                        <option value="en">English</option>
                        <option value="he">Hebrew</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                      </select>
                    </div>
                    <div><label className="block text-xs font-medium text-gray-600 mb-1">Template Format</label>
                      <select className={inp} value={buildForm.template_format} onChange={(e) => setBuildForm({ ...buildForm, template_format: e.target.value })}>
                        <option value="legacy">Legacy (topic clusters)</option>
                        <option value="formal">Formal ISMS (numbered sections)</option>
                      </select>
                    </div>
                  </div>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">Color</label>
                    <ColorPicker value={buildForm.iso_color} onChange={(v) => setBuildForm({ ...buildForm, iso_color: v })} /></div>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">ISO Standard PDF *</label>
                    <input type="file" accept=".pdf" onChange={(e) => setBuildFile(e.target.files?.[0] || null)} className={inp} />
                    {buildFile && <p className="mt-1 text-xs text-gray-400">{buildFile.name} ({(buildFile.size / 1024 / 1024).toFixed(1)} MB)</p>}
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button onClick={resetBuild} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
                    <button onClick={handleBuildWithAI} disabled={!buildFile || !buildForm.iso_code || !buildForm.iso_name}
                      className="flex items-center gap-2 px-4 py-2 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg disabled:opacity-50 font-medium shadow-sm">
                      <Sparkles className="w-4 h-4" /> Start AI Build
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4 text-center py-4">
                  {buildStatus?.status === "completed" ? <Check className="w-12 h-12 text-green-500 mx-auto" />
                    : buildStatus?.status === "failed" ? <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
                    : <Loader2 className="w-12 h-12 text-purple-500 animate-spin mx-auto" />}
                  <p className="font-medium text-gray-900 dark:text-white capitalize">{buildStatus?.status}</p>
                  <p className="text-sm text-gray-500">{buildStatus?.current_step}</p>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div className="bg-purple-600 h-2 rounded-full transition-all" style={{ width: `${buildStatus?.progress ?? 0}%` }} />
                  </div>
                  <p className="text-sm text-gray-500">{buildStatus?.progress ?? 0}%</p>
                  {(buildStatus?.status === "completed" || buildStatus?.status === "failed") && (
                    <button onClick={resetBuild} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
                      {buildStatus?.status === "completed" ? "Done" : "Close"}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add ISO Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-lg font-bold text-slate-900">Add ISO Standard</h3>
              <button onClick={() => { setIsAddModalOpen(false); setNewISO(BLANK_ISO); }} className="p-1.5 hover:bg-slate-100 rounded-lg"><X className="w-4 h-4 text-slate-500" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-xs font-medium text-gray-600 mb-1">ISO Code *</label>
                <input className={inp} value={newISO.code} onChange={(e) => setNewISO({ ...newISO, code: e.target.value })} placeholder="ISO 27001:2022" /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Name *</label>
                <input className={inp} value={newISO.name} onChange={(e) => setNewISO({ ...newISO, name: e.target.value })} placeholder="Information Security Management" /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
                <textarea className={inp} rows={2} value={newISO.description} onChange={(e) => setNewISO({ ...newISO, description: e.target.value })} /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Requirements Summary</label>
                <textarea className={inp} rows={3} value={newISO.requirements_summary} onChange={(e) => setNewISO({ ...newISO, requirements_summary: e.target.value })} /></div>
              <div className="flex items-center gap-6">
                <div><label className="block text-xs font-medium text-gray-600 mb-1">Color</label>
                  <ColorPicker value={newISO.color} onChange={(v) => setNewISO({ ...newISO, color: v })} /></div>
                <label className="flex items-center gap-2 mt-4 cursor-pointer">
                  <input type="checkbox" checked={newISO.active} onChange={(e) => setNewISO({ ...newISO, active: e.target.checked })} className="w-4 h-4" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Active</span>
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-slate-100">
              <button onClick={() => { setIsAddModalOpen(false); setNewISO(BLANK_ISO); }} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
              <button onClick={handleAddISO} disabled={isSaving || !newISO.code || !newISO.name}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 font-medium shadow-sm">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create Standard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
