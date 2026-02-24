"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { Shield, Plus, Edit2, Trash2, X, Check, Loader2, FileText, Users, AlertCircle, Sparkles } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3010";

interface AIMetadata {
  overview?: string; total_clauses?: number; total_controls?: number;
  key_themes?: string[]; document_count?: number; language?: string;
  built_by_ai?: boolean; model?: string; cost_usd?: number;
}

interface ISOStandard {
  id: string; code: string; name: string; description: string | null;
  requirements_summary: string | null; active: boolean; display_order: number;
  color?: string; ai_metadata?: AIMetadata | null;
  template_count: number; customer_count: number;
  created_at: string; updated_at: string;
}

const BLANK_ISO = { code: "", name: "", description: "", requirements_summary: "", active: true, display_order: 0, color: "#3b82f6" };
const BLANK_BUILD = { iso_code: "", iso_name: "", iso_description: "", iso_language: "en", iso_color: "#3b82f6" };

const inp = "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm";

function ColorPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <input type="color" value={value} onChange={(e) => onChange(e.target.value)}
        className="w-9 h-9 rounded cursor-pointer border border-gray-300 p-0.5" />
      <span className="text-xs font-mono text-gray-500">{value}</span>
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
  const [showBuildModal, setShowBuildModal] = useState(false);
  const [buildForm, setBuildForm] = useState(BLANK_BUILD);
  const [buildFile, setBuildFile] = useState<File | null>(null);
  const [buildTaskId, setBuildTaskId] = useState<string | null>(null);
  const [buildStatus, setBuildStatus] = useState<{ status: string; progress: number; current_step: string } | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);

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

  const confirmDelete = async () => {
    if (!deleteConfirmISO) return;
    try {
      await axios.delete(`${API_BASE}/api/v1/iso-standards/${deleteConfirmISO.id}`, { headers: headers() });
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
            if (s.data.status === "completed") await loadStandards();
          }
        } catch { clearInterval(poll); setIsBuilding(false); }
      }, 2000);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); setIsBuilding(false); }
  };

  const resetBuild = () => { setShowBuildModal(false); setBuildForm(BLANK_BUILD); setBuildFile(null); setBuildTaskId(null); setBuildStatus(null); setIsBuilding(false); };

  if (loading) return <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">ISO Standards</h3>
          <p className="text-sm text-gray-500">Manage ISO certification standards</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowBuildModal(true)}
            className="flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm transition-colors">
            <Sparkles className="w-4 h-4" /> Build with AI
          </button>
          <button onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors">
            <Plus className="w-4 h-4" /> Add Standard
          </button>
        </div>
      </div>

      {/* Cards */}
      <div className="space-y-3">
        {standards.map((s) => (
          <div key={s.id} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="flex">
              <div className="w-1.5 flex-shrink-0" style={{ backgroundColor: s.color || "#3b82f6" }} />
              <div className="flex-1 p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold text-gray-900 dark:text-white">{s.code}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${s.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                        {s.active ? "Active" : "Inactive"}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">{s.name}</p>
                    {s.description && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{s.description}</p>}
                    {s.ai_metadata && (
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        {s.ai_metadata.total_clauses != null && (
                          <span className="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full">
                            {s.ai_metadata.total_clauses} clauses
                          </span>
                        )}
                        {s.ai_metadata.total_controls != null && (
                          <span className="text-xs bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 px-2 py-0.5 rounded-full">
                            {s.ai_metadata.total_controls} controls
                          </span>
                        )}
                        {s.ai_metadata.language && s.ai_metadata.language !== "en" && (
                          <span className="text-xs bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 px-2 py-0.5 rounded-full uppercase">
                            {s.ai_metadata.language}
                          </span>
                        )}
                        {s.ai_metadata.key_themes?.slice(0, 3).map((t) => (
                          <span key={t} className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-full">{t}</span>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span className="flex items-center gap-1"><FileText className="w-3 h-3" />{s.template_count} templates</span>
                      <span className="flex items-center gap-1"><Users className="w-3 h-3" />{s.customer_count} customers</span>
                      {s.template_count > 0 && (
                        <button onClick={() => loadTemplatesForISO(s.id)} className="text-blue-500 hover:underline">
                          {expandedISO === s.id ? "Hide" : "View"} templates
                        </button>
                      )}
                    </div>
                    {expandedISO === s.id && isoTemplates[s.id] && (
                      <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 space-y-1">
                        {isoTemplates[s.id].map((t) => (
                          <div key={t.id} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                            <FileText className="w-3 h-3 text-blue-400" />
                            <span>{t.name}</span>
                            {t.status === "approved" && <span className="text-green-500">✓</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 ml-3">
                    <button onClick={() => setEditingISO(s)} className="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => s.template_count > 0 ? alert(`Cannot delete: ${s.template_count} template(s) exist`) : setDeleteConfirmISO(s)}
                      className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded">
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Edit ISO Standard</h3>
              <button onClick={() => setEditingISO(null)}><X className="w-5 h-5 text-gray-500" /></button>
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
            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => setEditingISO(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleSaveEdit} disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteConfirmISO && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center gap-3 mb-3">
              <AlertCircle className="w-6 h-6 text-red-500" />
              <h3 className="font-bold text-gray-900 dark:text-white">Delete {deleteConfirmISO.code}?</h3>
            </div>
            <p className="text-sm text-gray-500 mb-4">This action cannot be undone.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteConfirmISO(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={confirmDelete} className="flex items-center gap-2 px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg">
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Build with AI Modal */}
      {showBuildModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-purple-500" />
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">Build ISO with AI</h3>
                </div>
                <button onClick={resetBuild}><X className="w-5 h-5 text-gray-500" /></button>
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
                    <div><label className="block text-xs font-medium text-gray-600 mb-1">Color</label>
                      <ColorPicker value={buildForm.iso_color} onChange={(v) => setBuildForm({ ...buildForm, iso_color: v })} /></div>
                  </div>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">ISO Standard PDF *</label>
                    <input type="file" accept=".pdf" onChange={(e) => setBuildFile(e.target.files?.[0] || null)} className={inp} />
                    {buildFile && <p className="mt-1 text-xs text-gray-400">{buildFile.name} ({(buildFile.size / 1024 / 1024).toFixed(1)} MB)</p>}
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button onClick={resetBuild} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
                    <button onClick={handleBuildWithAI} disabled={!buildFile || !buildForm.iso_code || !buildForm.iso_name}
                      className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50">
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Add New ISO Standard</h3>
              <button onClick={() => { setIsAddModalOpen(false); setNewISO(BLANK_ISO); }}><X className="w-5 h-5 text-gray-500" /></button>
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
            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => { setIsAddModalOpen(false); setNewISO(BLANK_ISO); }} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleAddISO} disabled={isSaving || !newISO.code || !newISO.name}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
