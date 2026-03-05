"use client";

/**
 * TemplateEditorModal — reusable template content + placeholder editor.
 *
 * Workflow:
 *  1. Content tab  → read/edit document text, use {{key}} to mark data fields
 *  2. Placeholders → define question/label/category for each {{key}}
 *  3. Save         → updates template structure + ISO standard placeholder dictionary
 *
 * Reused in:
 *  - Admin > Template Catalog (master templates)
 *  - Customer document view   (customer-level copy, future)
 */

import { useState, useMemo, useCallback } from "react";
import {
  X, Save, Loader2, Plus, Trash2, ChevronDown, ChevronUp,
  AlertTriangle, BookOpen, Hash, ArrowRight, Info,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PlaceholderEntry {
  key: string;
  question: string;
  label: string;
  category: string;
  hint?: string;
  data_type: string;
  is_required: boolean;
  automation_source?: string;
  auto_fillable?: boolean;
  trigger_event?: string;
}

interface EditableSection {
  id: string;
  number?: string;
  title: string;
  content: string;
  iso_reference?: string;
  type?: string;
  isSpecial: boolean;
  depth: number;
  parentId?: string;
}

interface Props {
  title: string;
  subtitle?: string;
  warning?: string;
  structure: Record<string, any>;
  dictionary: PlaceholderEntry[];
  onSave: (updatedStructure: Record<string, any>, updatedDictionary: PlaceholderEntry[]) => Promise<void>;
  onClose: () => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES = [
  "Company Info", "People & Roles", "Security Controls", "Risk Management",
  "Asset Management", "Incident Management", "Audit & Compliance",
  "Third Parties", "Legal & Regulatory", "Document Control", "General",
];

const SPECIAL_TYPES = new Set(["document_control_table", "approval_table"]);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function flattenSections(structure: Record<string, any>): EditableSection[] {
  const rawSections: any[] = structure.sections ?? structure.fixed_sections ?? [];
  const result: EditableSection[] = [];

  for (const s of rawSections) {
    const isSpecial = SPECIAL_TYPES.has(s.type ?? "");
    result.push({
      id: s.id ?? Math.random().toString(36).slice(2),
      number: s.number,
      title: s.title || s.id || "Section",
      content: s.content ?? "",
      iso_reference: s.iso_reference,
      type: s.type,
      isSpecial,
      depth: 0,
    });
    if (Array.isArray(s.subsections)) {
      for (const sub of s.subsections) {
        result.push({
          id: sub.id ?? Math.random().toString(36).slice(2),
          number: sub.number,
          title: sub.title || sub.id,
          content: sub.content ?? "",
          iso_reference: sub.iso_reference,
          type: sub.type,
          isSpecial: false,
          depth: 1,
          parentId: s.id,
        });
      }
    }
  }
  return result;
}

function rebuildStructure(
  original: Record<string, any>,
  edited: EditableSection[]
): Record<string, any> {
  const contentById: Record<string, string> = {};
  for (const s of edited) contentById[s.id] = s.content;

  const sectionsKey = original.sections ? "sections" : "fixed_sections";
  const rawSections: any[] = original[sectionsKey] ?? [];

  const rebuilt = rawSections.map((s: any) => {
    const out = { ...s };
    if (contentById[s.id] !== undefined && !SPECIAL_TYPES.has(s.type ?? "")) {
      out.content = contentById[s.id];
    }
    if (Array.isArray(s.subsections)) {
      out.subsections = s.subsections.map((sub: any) => ({
        ...sub,
        content: contentById[sub.id] ?? sub.content,
      }));
    }
    return out;
  });

  return { ...original, [sectionsKey]: rebuilt };
}

function extractKeysFromText(text: string): string[] {
  const matches = text.matchAll(/\{\{([^}]+)\}\}/g);
  return [...new Set([...matches].map(m => m[1].trim()))];
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function TemplateEditorModal({
  title, subtitle, warning, structure, dictionary, onSave, onClose,
}: Props) {
  const [tab, setTab] = useState<"content" | "placeholders">("content");
  const [sections, setSections] = useState<EditableSection[]>(() => flattenSections(structure));
  const [dict, setDict] = useState<PlaceholderEntry[]>(() => JSON.parse(JSON.stringify(dictionary)));
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const s = flattenSections(structure);
    // Start with non-empty, non-special sections expanded
    return new Set(s.filter(x => !x.isSpecial && x.content.trim()).map(x => x.id));
  });

  // ── Derived ──────────────────────────────────────────────────────────────────

  // All {{keys}} found across all editable section content
  const allKeysInContent = useMemo(() => {
    const allText = sections.filter(s => !s.isSpecial).map(s => s.content).join(" ");
    return new Set(extractKeysFromText(allText));
  }, [sections]);

  // Per-section key lookup: sectionId → keys used in that section
  const keysBySectionId = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const s of sections) {
      if (!s.isSpecial) map[s.id] = extractKeysFromText(s.content);
    }
    return map;
  }, [sections]);

  const keysInDict = useMemo(() => new Set(dict.map(d => d.key)), [dict]);

  // Keys used in content but not yet defined in dictionary
  const missingFromDict = useMemo(
    () => [...allKeysInContent].filter(k => !keysInDict.has(k)).sort(),
    [allKeysInContent, keysInDict]
  );

  // Dict entries not referenced in any section content
  const unusedInContent = useMemo(
    () => dict.filter(d => !allKeysInContent.has(d.key)),
    [dict, allKeysInContent]
  );

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const toggleExpand = (id: string) =>
    setExpanded(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const updateContent = useCallback((id: string, val: string) =>
    setSections(prev => prev.map(s => s.id === id ? { ...s, content: val } : s)), []);

  const updateDictEntry = useCallback((idx: number, patch: Partial<PlaceholderEntry>) =>
    setDict(prev => prev.map((d, i) => i === idx ? { ...d, ...patch } : d)), []);

  const addToDict = (key: string) => {
    if (keysInDict.has(key)) return;
    setDict(prev => [...prev, {
      key,
      question: "",
      label: key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
      category: "General",
      data_type: "text",
      is_required: true,
    }]);
  };

  const addAllMissing = () => {
    for (const k of missingFromDict) addToDict(k);
    setTab("placeholders");
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(rebuildStructure(structure, sections), dict);
    } finally {
      setSaving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────────

  const contentSections = sections.filter(s => !s.isSpecial);
  const specialSections = sections.filter(s => s.isSpecial);

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 flex-shrink-0">
          <div>
            <h3 className="font-bold text-slate-900 text-sm">{title}</h3>
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose}
              className="text-xs px-3 py-1.5 text-slate-500 hover:bg-slate-100 rounded-lg font-medium transition-colors">
              Cancel
            </button>
            <button onClick={handleSave} disabled={saving}
              className="flex items-center gap-1.5 text-xs px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium transition-colors">
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              Save
            </button>
            <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg ml-1">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>

        {/* ── How it works strip ── */}
        <div className="flex items-center gap-3 px-6 py-2.5 bg-blue-50 border-b border-blue-100 text-xs text-blue-700 flex-shrink-0">
          <Info className="w-3.5 h-3.5 flex-shrink-0 text-blue-400" />
          <span className="font-medium">How to edit:</span>
          <span className="flex items-center gap-1.5">
            <span className="bg-white border border-blue-200 rounded px-1.5 py-0.5 font-medium">1. Content</span>
            <ArrowRight className="w-3 h-3" />
            Edit document text. Write <code className="bg-blue-100 px-1 rounded font-mono">{`{{field_name}}`}</code> to add a data field.
          </span>
          <span className="flex items-center gap-1.5 ml-2">
            <span className="bg-white border border-blue-200 rounded px-1.5 py-0.5 font-medium">2. Placeholders</span>
            <ArrowRight className="w-3 h-3" />
            Set the question asked to the customer for each field.
          </span>
        </div>

        {/* ── Tabs ── */}
        <div className="flex gap-1 px-6 pt-3 border-b border-slate-100 flex-shrink-0">
          <button
            onClick={() => setTab("content")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-t-lg border-b-2 transition-colors ${
              tab === "content"
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            Document Content
            <span className="bg-slate-100 text-slate-500 text-xs px-1.5 py-0.5 rounded-full ml-0.5">
              {contentSections.length} sections
            </span>
          </button>
          <button
            onClick={() => setTab("placeholders")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-t-lg border-b-2 transition-colors ${
              tab === "placeholders"
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            <Hash className="w-3.5 h-3.5" />
            Placeholders
            {missingFromDict.length > 0 ? (
              <span className="bg-red-100 text-red-600 text-xs px-1.5 py-0.5 rounded-full ml-0.5 font-bold">
                {missingFromDict.length} undefined
              </span>
            ) : (
              <span className="bg-slate-100 text-slate-500 text-xs px-1.5 py-0.5 rounded-full ml-0.5">
                {dict.length}
              </span>
            )}
          </button>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 overflow-y-auto p-6">

          {/* ════ CONTENT TAB ════ */}
          {tab === "content" && (
            <div className="space-y-3">

              {/* System section pills */}
              {specialSections.length > 0 && (
                <div className="flex flex-wrap gap-2 pb-2">
                  <span className="text-xs text-slate-400 self-center">Auto-generated sections (not editable):</span>
                  {specialSections.map(s => (
                    <span key={s.id}
                      className="text-xs bg-slate-50 text-slate-400 border border-slate-100 px-2.5 py-1 rounded-lg">
                      {s.title}
                    </span>
                  ))}
                </div>
              )}

              {contentSections.length === 0 && (
                <div className="text-center py-16 text-slate-400">
                  <BookOpen className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No editable sections in this template.</p>
                </div>
              )}

              {contentSections.map((sec) => {
                const isOpen = expanded.has(sec.id);
                const keysHere = keysBySectionId[sec.id] ?? [];
                const hasContent = sec.content.trim().length > 0;

                return (
                  <div key={sec.id}
                    className={`rounded-xl border transition-all ${
                      sec.depth === 1
                        ? "ml-6 border-slate-100 bg-slate-50/40"
                        : "border-slate-200 bg-white shadow-sm"
                    }`}
                  >
                    {/* Clickable header */}
                    <button
                      onClick={() => toggleExpand(sec.id)}
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-50/80 rounded-xl transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        {sec.number && (
                          <span className="font-mono font-bold text-slate-400 flex-shrink-0 text-xs w-8">
                            {sec.number}
                          </span>
                        )}
                        <span className={`font-semibold truncate ${sec.depth === 1 ? "text-xs text-slate-600" : "text-sm text-slate-800"}`}>
                          {sec.title}
                        </span>
                        {/* Keys used in this section */}
                        {keysHere.length > 0 && (
                          <div className="flex items-center gap-1 flex-wrap ml-1">
                            {keysHere.slice(0, 4).map(k => (
                              <span key={k}
                                className="text-xs bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded font-mono border border-violet-100">
                                {`{{${k}}}`}
                              </span>
                            ))}
                            {keysHere.length > 4 && (
                              <span className="text-xs text-slate-400">+{keysHere.length - 4}</span>
                            )}
                          </div>
                        )}
                        {!hasContent && !isOpen && (
                          <span className="text-xs text-slate-300 italic">empty</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                        {sec.iso_reference && (
                          <span className="text-xs text-slate-300 font-mono hidden sm:block">{sec.iso_reference}</span>
                        )}
                        <span className="text-xs text-slate-400">
                          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </span>
                      </div>
                    </button>

                    {/* Expanded content */}
                    {isOpen && (
                      <div className="px-4 pb-4 space-y-2">
                        <p className="text-xs text-slate-400">
                          Edit the document text below. Use{" "}
                          <code className="bg-slate-100 text-violet-600 px-1 rounded font-mono">{"{{field_name}}"}</code>{" "}
                          anywhere in the text to mark a customer data field.
                        </p>
                        <textarea
                          className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-800 leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                          rows={Math.max(4, sec.content.split("\n").length + 1)}
                          value={sec.content}
                          onChange={e => updateContent(sec.id, e.target.value)}
                          spellCheck={false}
                          placeholder="Write the section content here. Use {{field_name}} for customer-specific values."
                        />
                        {keysHere.length > 0 && (
                          <p className="text-xs text-slate-400">
                            Fields in this section:{" "}
                            {keysHere.map(k => (
                              <button
                                key={k}
                                onClick={() => { addToDict(k); setTab("placeholders"); }}
                                className="inline-block font-mono text-violet-600 hover:text-violet-800 mr-1.5"
                                title="Click to define this field's question in the Placeholders tab"
                              >
                                {`{{${k}}}`}
                              </button>
                            ))}
                            <span className="text-slate-300">· click a field to define its question</span>
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ════ PLACEHOLDERS TAB ════ */}
          {tab === "placeholders" && (
            <div className="space-y-4">

              {/* ISO-level warning */}
              {warning && (
                <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                  {warning}
                </div>
              )}

              {/* What this tab does */}
              <div className="bg-slate-50 rounded-xl border border-slate-100 px-4 py-3 text-xs text-slate-600 space-y-1">
                <p className="font-semibold text-slate-700">What this tab does:</p>
                <p>
                  For every <code className="bg-white border border-slate-200 px-1 rounded font-mono text-violet-600">{"{{field}}"}</code>{" "}
                  used in the document, define the <strong>question</strong> that will be asked to the customer during data collection.
                </p>
                <p className="text-slate-400">
                  Example: <code className="font-mono">{"{{organization_name}}"}</code> → <em>"What is the full legal name of your organization?"</em>
                </p>
              </div>

              {/* Missing keys — need to be defined */}
              {missingFromDict.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-red-700 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {missingFromDict.length} field{missingFromDict.length > 1 ? "s" : ""} used in the document but not defined yet:
                    </p>
                    <button
                      onClick={addAllMissing}
                      className="text-xs px-2.5 py-1 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium transition-colors"
                    >
                      Define all
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {missingFromDict.map(k => (
                      <button key={k}
                        onClick={() => addToDict(k)}
                        className="flex items-center gap-1 text-xs bg-white border border-red-200 text-red-600 px-2.5 py-1.5 rounded-lg hover:bg-red-50 font-mono transition-colors"
                        title="Click to add this field to the dictionary and define its question"
                      >
                        <Plus className="w-3 h-3" />
                        {k}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="flex items-center gap-4 text-xs text-slate-500 px-1">
                <span>
                  <span className="font-semibold text-slate-700">{allKeysInContent.size}</span> fields in document
                </span>
                <span>
                  <span className="font-semibold text-slate-700">{dict.length}</span> defined
                </span>
                {unusedInContent.length > 0 && (
                  <span className="text-slate-400">
                    {unusedInContent.length} defined but not used in this template
                  </span>
                )}
              </div>

              {/* Dictionary entries */}
              {dict.length === 0 ? (
                <div className="text-center py-12 border-2 border-dashed border-slate-100 rounded-xl">
                  <Hash className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                  <p className="text-sm text-slate-400">No placeholders defined yet.</p>
                  <p className="text-xs text-slate-300 mt-1">
                    Go to the Content tab and add <code className="font-mono">{"{{field_name}}"}</code> to the document text, then come back here.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {dict.map((entry, idx) => {
                    const usedHere = allKeysInContent.has(entry.key);
                    // Which sections use this key?
                    const sectionsUsing = sections.filter(s =>
                      !s.isSpecial && (keysBySectionId[s.id] ?? []).includes(entry.key)
                    );

                    return (
                      <div key={idx}
                        className={`rounded-xl border p-4 transition-all ${
                          !usedHere ? "border-slate-100 bg-slate-50/40 opacity-60" : "border-slate-200 bg-white"
                        }`}
                      >
                        <div className="flex items-start gap-3">

                          {/* Left: key + where used */}
                          <div className="w-40 flex-shrink-0">
                            <div className="font-mono text-xs font-semibold px-2 py-1.5 rounded-lg mb-1.5 inline-block max-w-full truncate"
                              style={{
                                background: usedHere ? "#f5f3ff" : "#f8fafc",
                                color: usedHere ? "#7c3aed" : "#94a3b8",
                              }}
                            >
                              {`{{${entry.key || "…"}}}`}
                            </div>
                            {sectionsUsing.length > 0 && (
                              <p className="text-xs text-slate-400 leading-tight">
                                Used in: {sectionsUsing.map(s => s.number ? `§${s.number}` : s.title).join(", ")}
                              </p>
                            )}
                            {!usedHere && (
                              <p className="text-xs text-slate-400 italic">not in this template</p>
                            )}
                            {/* Editable key name */}
                            <input
                              className="mt-1.5 w-full text-xs px-2 py-1 border border-slate-100 rounded-lg bg-slate-50 text-slate-500 font-mono focus:outline-none focus:ring-1 focus:ring-blue-300"
                              placeholder="field_key"
                              value={entry.key}
                              onChange={e => updateDictEntry(idx, { key: e.target.value.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "") })}
                            />
                          </div>

                          {/* Center: question */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <label className="text-xs font-medium text-slate-500">
                                Question asked to customer <span className="text-red-400">*</span>
                              </label>
                              {entry.question
                                ? <span className="text-xs bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-medium">AI generated</span>
                                : <span className="text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-medium">needs question</span>
                              }
                            </div>
                            <textarea
                              className={`w-full px-3 py-2 border rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent ${
                                entry.question
                                  ? "border-slate-200 text-slate-800 bg-white"
                                  : "border-amber-200 bg-amber-50/30 text-slate-800"
                              }`}
                              rows={2}
                              placeholder={`e.g. "What is your organization's ${(entry.label || entry.key).toLowerCase()}?"`}
                              value={entry.question}
                              onChange={e => updateDictEntry(idx, { question: e.target.value })}
                            />
                            {entry.hint !== undefined && (
                              <input
                                className="mt-1 w-full px-2 py-1 border border-slate-100 rounded-lg text-xs text-slate-500 bg-slate-50 focus:outline-none focus:ring-1 focus:ring-blue-300"
                                placeholder="Hint / helper text for the customer (optional)"
                                value={entry.hint ?? ""}
                                onChange={e => updateDictEntry(idx, { hint: e.target.value })}
                              />
                            )}
                          </div>

                          {/* Right: label + category + required */}
                          <div className="w-36 flex-shrink-0 space-y-2">
                            <div>
                              <label className="text-xs text-slate-400 mb-0.5 block">Label</label>
                              <input
                                className="w-full px-2 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-300"
                                placeholder="Display label"
                                value={entry.label}
                                onChange={e => updateDictEntry(idx, { label: e.target.value })}
                              />
                            </div>
                            <div>
                              <label className="text-xs text-slate-400 mb-0.5 block">Category</label>
                              <select
                                className="w-full px-2 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-800 bg-white focus:outline-none focus:ring-1 focus:ring-blue-300"
                                value={entry.category}
                                onChange={e => updateDictEntry(idx, { category: e.target.value })}
                              >
                                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                              </select>
                            </div>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={entry.is_required}
                                onChange={e => updateDictEntry(idx, { is_required: e.target.checked })}
                                className="w-3.5 h-3.5 accent-blue-600"
                              />
                              <span className="text-xs text-slate-600">Required</span>
                            </label>
                          </div>

                          {/* Delete */}
                          <button
                            onClick={() => setDict(prev => prev.filter((_, i) => i !== idx))}
                            className="p-1.5 text-slate-300 hover:text-red-500 rounded-lg transition-colors flex-shrink-0 mt-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Add placeholder manually */}
              <button
                onClick={() => setDict(prev => [...prev, {
                  key: "", question: "", label: "", category: "General",
                  data_type: "text", is_required: true,
                }])}
                className="flex items-center gap-1.5 text-xs px-3 py-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 font-medium transition-colors"
              >
                <Plus className="w-3 h-3" /> Add placeholder manually
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
