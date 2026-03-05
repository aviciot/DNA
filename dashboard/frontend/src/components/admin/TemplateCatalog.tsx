"use client";

import { useState, useEffect } from "react";
import {
  FileText, Trash2, Check, X, Loader2, Shield,
  Edit2, Search, Filter, Eye, Printer, Download,
} from "lucide-react";

import api from "@/lib/api";
import TemplateEditorModal, { PlaceholderEntry } from "@/components/shared/TemplateEditorModal";

interface CatalogTemplate {
  id: string; name: string; description: string | null;
  iso_standard: string | null; status: string;
  version_number: number; total_fixed_sections: number;
  total_fillable_sections: number; semantic_tags: string[];
  iso_codes: string[]; iso_standard_ids?: string[]; created_at: string;
  updated_at: string | null; approved_at: string | null;
}

interface ISOStandard { id: string; code: string; name: string; language?: string; color?: string; }


export default function TemplateCatalog() {
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterISO, setFilterISO] = useState("");

  // Edit modal state
  const [editingTemplate, setEditingTemplate] = useState<CatalogTemplate | null>(null);
  const [editIsoStandardId, setEditIsoStandardId] = useState<string | null>(null);
  const [editDictionary, setEditDictionary] = useState<PlaceholderEntry[]>([]);
  const [editStructure, setEditStructure] = useState<Record<string, any>>({});

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

  const syncAll = async () => {
    try {
      await api.post("/api/v1/catalog-templates/sync-all-placeholders");
      await load();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
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
      const structure = r.data.template_structure || {};
      const isoIds: string[] = r.data.iso_standard_ids || [];

      let dictionary: PlaceholderEntry[] = [];
      const isoId = isoIds[0] || null;
      if (isoId) {
        const dr = await api.get(`/api/v1/iso-standards/${isoId}/placeholder-dictionary`);
        dictionary = dr.data || [];
      }

      setEditIsoStandardId(isoId);
      setEditDictionary(JSON.parse(JSON.stringify(dictionary)));
      setEditStructure(structure);
      setEditingTemplate(t);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
  };

  const handleEditorSave = async (updatedStructure: Record<string, any>, updatedDict: PlaceholderEntry[]) => {
    if (!editingTemplate) return;
    const sectionsKey = updatedStructure.sections ? "sections" : "fixed_sections";
    await api.patch(`/api/v1/catalog-templates/${editingTemplate.id}/sections`, {
      sections: updatedStructure[sectionsKey] ?? [],
      sections_key: sectionsKey,
    });
    if (editIsoStandardId) {
      await api.patch(`/api/v1/iso-standards/${editIsoStandardId}/placeholder-dictionary`, {
        placeholder_dictionary: updatedDict,
      });
    }
    setEditingTemplate(null);
    await load();
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
        <TemplateEditorModal
          title={editingTemplate.name}
          subtitle={`${editDictionary.length} placeholders · v${editingTemplate.version_number}`}
          warning={editIsoStandardId
            ? "Placeholder changes apply to all templates in this ISO standard"
            : undefined}
          structure={editStructure}
          dictionary={editDictionary}
          onSave={handleEditorSave}
          onClose={() => setEditingTemplate(null)}
        />
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
