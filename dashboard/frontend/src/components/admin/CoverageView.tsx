"use client";

import { useState, useEffect, useCallback } from "react";
import {
  ChevronDown, ChevronRight, FileText, AlertTriangle,
  CheckCircle2, Clock, Circle, Loader2, BarChart3, Shield, CheckCheck,
} from "lucide-react";

import api from "@/lib/api";

interface TemplateRef {
  id: string;
  name: string;
  doc_name?: string | null;
  total_fillable: number;
  doc_status: string | null;
  completion_pct: number | null;
  tasks_total: number;
  tasks_done: number;
}

interface ClauseRef {
  ref: string;
  templates: TemplateRef[];
}

interface ClauseGroup {
  key: string;
  is_annex: boolean;
  total_clauses: number;
  covered_clauses: number;
  completed_docs: number;
  inprogress_docs: number;
  completion_pct: number;
  tasks_total: number;
  tasks_done: number;
  clauses: ClauseRef[];
}

interface CoverageData {
  iso: { id: string; code: string; name: string; color: string };
  mode: "plan" | "customer";
  summary: {
    total_clauses: number;
    covered_clauses: number;
    gap_clauses: number;
    coverage_pct: number;
    total_templates: number;
    tasks_total?: number;
    tasks_done?: number;
  };
  groups: ClauseGroup[];
}

interface Props {
  isoId: string;
  customerId?: number;
  isoColor?: string;
}

const DOC_STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  approved:    { label: "Approved",     color: "#10b981", bg: "#ecfdf5", icon: CheckCircle2 },
  completed:   { label: "Completed",    color: "#10b981", bg: "#ecfdf5", icon: CheckCircle2 },
  in_progress: { label: "In Progress",  color: "#3b82f6", bg: "#eff6ff", icon: Clock },
  draft:       { label: "Draft",        color: "#f59e0b", bg: "#fffbeb", icon: FileText },
  pending:     { label: "Pending",      color: "#6b7280", bg: "#f9fafb", icon: Circle },
};

function docStatusColor(status: string | null, pct: number | null): string {
  if (!status) return "#e5e7eb";
  if (status === "approved" || status === "completed") return "#10b981";
  if (status === "in_progress") return pct && pct > 50 ? "#3b82f6" : "#93c5fd";
  if (status === "draft") return "#f59e0b";
  return "#d1d5db";
}

function planCoverageColor(covered: number, total: number): string {
  if (total === 0) return "#e5e7eb";
  const pct = covered / total;
  if (pct === 1) return "#10b981";
  if (pct >= 0.5) return "#3b82f6";
  if (pct > 0) return "#f59e0b";
  return "#ef4444";
}

function taskRingColor(done: number, total: number): string {
  if (total === 0) return "#e5e7eb";
  if (done === total) return "#10b981";
  if (done / total >= 0.5) return "#3b82f6";
  if (done > 0) return "#f59e0b";
  return "#ef4444";
}

function clauseHeatColor(clause: ClauseRef, isCustomer: boolean): string {
  if (clause.templates.length === 0) return "#fecaca"; // red — gap
  if (!isCustomer) return "#3b82f6"; // plan mode: covered = blue

  // Customer mode: color by task completion, fallback to doc status
  const total = clause.templates.reduce((s, t) => s + (t.tasks_total || 0), 0);
  const done = clause.templates.reduce((s, t) => s + (t.tasks_done || 0), 0);
  if (total > 0) {
    if (done === total) return "#10b981";
    if (done / total >= 0.5) return "#3b82f6";
    if (done > 0) return "#f59e0b";
    return "#fca5a5";
  }
  // Fallback to doc status
  const status = clause.templates[0]?.doc_status;
  if (!status) return "#d1d5db";
  if (status === "completed" || status === "approved") return "#10b981";
  if (status === "in_progress") return "#93c5fd";
  return "#d1d5db";
}

function TaskRing({ done, total, size = 44 }: { done: number; total: number; size?: number }) {
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const pct = total > 0 ? done / total : 0;
  const color = taskRingColor(done, total);
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" style={{ position: "absolute" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#f1f5f9" strokeWidth={5} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${pct * circ} ${circ}`} strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.5s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xs font-bold leading-none" style={{ color }}>{Math.round(pct * 100)}</span>
        <span className="text-slate-400" style={{ fontSize: 8, lineHeight: 1 }}>%</span>
      </div>
    </div>
  );
}

export default function CoverageView({ isoId, customerId, isoColor = "#3b82f6" }: Props) {
  const [data, setData] = useState<CoverageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedClause, setSelectedClause] = useState<ClauseRef | null>(null);
  const [hoveredClause, setHoveredClause] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (customerId) params.customer_id = customerId;
      const r = await api.get(`/api/v1/iso-standards/${isoId}/coverage`, { params });
      setData(r.data);
      if (r.data.groups.length > 0) setExpanded(new Set([r.data.groups[0].key]));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [isoId, customerId]);

  useEffect(() => { load(); }, [load]);

  const toggleGroup = (key: string) => {
    setExpanded(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; });
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
    </div>
  );
  if (!data) return null;

  const { summary, groups, iso, mode } = data;
  const isCustomer = mode === "customer";
  const accentColor = iso.color || isoColor;
  const mainGroups = groups.filter(g => !g.is_annex);
  const annexGroups = groups.filter(g => g.is_annex);

  return (
    <div className="space-y-5">

      {/* ── Summary Bar ── */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: accentColor + "20" }}>
            <Shield className="w-5 h-5" style={{ color: accentColor }} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">{iso.code}</p>
            <p className="text-xs text-slate-500">{iso.name}</p>
          </div>
          <div className="ml-auto flex items-center gap-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">{summary.coverage_pct}%</p>
              <p className="text-xs text-slate-500">Clause Coverage</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-600">
                {summary.covered_clauses}
                <span className="text-sm font-normal text-slate-400">/{summary.total_clauses}</span>
              </p>
              <p className="text-xs text-slate-500">Clauses covered</p>
            </div>
            {summary.gap_clauses > 0 && (
              <div className="text-center">
                <p className="text-2xl font-bold text-red-500">{summary.gap_clauses}</p>
                <p className="text-xs text-slate-500">Gaps</p>
              </div>
            )}
            {isCustomer && (summary.tasks_total ?? 0) > 0 && (
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-600">
                  {summary.tasks_done ?? 0}
                  <span className="text-sm font-normal text-slate-400">/{summary.tasks_total}</span>
                </p>
                <p className="text-xs text-slate-500">Tasks done</p>
                <p className="text-xs text-slate-400">across all docs</p>
              </div>
            )}
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-700">{summary.total_templates}</p>
              <p className="text-xs text-slate-500">Templates</p>
            </div>
          </div>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
          <div className="h-2.5 rounded-full transition-all duration-700"
            style={{ width: `${summary.coverage_pct}%`, backgroundColor: accentColor }} />
        </div>
      </div>

      {/* ── Control Heatmap ── */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-bold text-slate-800">Control Map</p>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            {isCustomer ? (
              <>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block bg-emerald-500" />All tasks done</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block bg-blue-400" />In progress</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#fca5a5" }} />Not started</span>
              </>
            ) : (
              <>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block bg-blue-400" />Covered</span>
              </>
            )}
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block bg-red-200" />Gap</span>
          </div>
        </div>

        {[{ label: "Main Clauses", items: mainGroups }, { label: "Annex A Controls", items: annexGroups }]
          .filter(s => s.items.length > 0)
          .map(section => (
            <div key={section.label} className="mb-4 last:mb-0">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{section.label}</p>
              <div className="flex flex-wrap gap-3">
                {section.items.map(grp => (
                  <div key={grp.key}>
                    <p className="text-xs font-mono text-slate-400 mb-1 text-center">{grp.key}</p>
                    <div className="flex flex-wrap gap-0.5 max-w-[180px]">
                      {grp.clauses.map(clause => {
                        const color = clauseHeatColor(clause, isCustomer);
                        const isActive = selectedClause?.ref === clause.ref;
                        const completedDocs = clause.templates.filter(t => t.doc_status === "completed" || t.doc_status === "approved").length;
                        const inProgressDocs = clause.templates.filter(t => t.doc_status === "in_progress").length;
                        return (
                          <div key={clause.ref} className="relative group">
                            <button
                              onClick={() => { setSelectedClause(isActive ? null : clause); if (!expanded.has(grp.key)) toggleGroup(grp.key); }}
                              onMouseEnter={() => setHoveredClause(clause.ref)}
                              onMouseLeave={() => setHoveredClause(null)}
                              className="w-5 h-5 rounded-sm transition-all hover:scale-125 hover:z-10 ring-offset-1"
                              style={{ backgroundColor: color, outline: isActive ? `2px solid ${color}` : "none", outlineOffset: 2 }}
                            />
                            {/* Tooltip */}
                            {hoveredClause === clause.ref && (
                              <div className="absolute bottom-7 left-1/2 -translate-x-1/2 z-30 pointer-events-none">
                                <div className="bg-slate-800 text-white text-xs px-2 py-1.5 rounded-lg whitespace-nowrap shadow-lg">
                                  <p className="font-mono font-bold">{clause.ref}</p>
                                  {clause.templates.length === 0
                                    ? <p className="text-red-300">No template — gap</p>
                                    : isCustomer
                                      ? <p className="text-slate-300">
                                          {completedDocs > 0 && `✓ ${completedDocs} done`}
                                          {completedDocs > 0 && inProgressDocs > 0 && " · "}
                                          {inProgressDocs > 0 && `◑ ${inProgressDocs} in progress`}
                                          {completedDocs === 0 && inProgressDocs === 0 && `${clause.templates.length} doc${clause.templates.length !== 1 ? "s" : ""} not started`}
                                        </p>
                                      : <p className="text-slate-300">{clause.templates.length} template{clause.templates.length !== 1 ? "s" : ""}</p>
                                  }
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
      </div>

      {/* ── Main layout: clause tree + detail panel ── */}
      <div className="flex gap-5">

        {/* ── Left: Clause Groups ── */}
        <div className="flex-1 min-w-0 space-y-2">
          {[{ label: "Main Clauses", items: mainGroups }, { label: "Annex A Controls", items: annexGroups }]
            .filter(s => s.items.length > 0)
            .map(section => (
              <div key={section.label}>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-1">
                  {section.label}
                </p>
                {section.items.map(grp => {
                  const isOpen = expanded.has(grp.key);
                  // Groups always use clause coverage for their progress bar.
                  // Task completion is a plan-level metric (shown in the summary),
                  // not meaningful per-group because all groups in the same plan
                  // share identical task stats.
                  const clausePct = Math.round((grp.covered_clauses / grp.total_clauses) * 100);
                  const clauseBarColor = planCoverageColor(grp.covered_clauses, grp.total_clauses);
                  const groupLabel = grp.is_annex ? grp.key : `Clause ${grp.key}`;
                  const grpTemplateCnt = grp.clauses.reduce((s, c) => s + c.templates.length, 0);
                  const docsAssigned = grp.completed_docs + grp.inprogress_docs;

                  return (
                    <div key={grp.key} className="bg-white rounded-xl border border-slate-100 overflow-hidden">
                      {/* Group header */}
                      <button onClick={() => toggleGroup(grp.key)}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left">
                        {/* Clause coverage badge */}
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-[10px] font-bold text-white leading-tight text-center"
                          style={{ backgroundColor: clauseBarColor }}>
                          {grp.key}
                        </div>

                        {/* Clause coverage bar */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-semibold text-slate-800">{groupLabel}</span>
                            <span className="text-xs text-slate-400 ml-2 flex-shrink-0">
                              {grp.covered_clauses}/{grp.total_clauses} clauses
                              {grpTemplateCnt > 0 && ` · ${grpTemplateCnt} template${grpTemplateCnt !== 1 ? "s" : ""}`}
                            </span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div className="h-1.5 rounded-full transition-all duration-500"
                              style={{ width: `${clausePct}%`, backgroundColor: clauseBarColor }} />
                          </div>
                          {/* Customer mode: doc completion breakdown */}
                          {isCustomer && docsAssigned > 0 && (
                            <div className="flex items-center gap-3 mt-1">
                              {grp.completed_docs > 0 && (
                                <span className="text-xs text-emerald-600">✓ {grp.completed_docs} completed</span>
                              )}
                              {grp.inprogress_docs > 0 && (
                                <span className="text-xs text-blue-500">◑ {grp.inprogress_docs} in progress</span>
                              )}
                            </div>
                          )}
                        </div>

                        {isOpen
                          ? <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />}
                      </button>

                      {/* Clause rows */}
                      {isOpen && (
                        <div className="border-t border-slate-100 divide-y divide-slate-50">
                          {grp.clauses.map(clause => {
                            const hasTemplates = clause.templates.length > 0;
                            const isSelected = selectedClause?.ref === clause.ref;
                            const dotColor = clauseHeatColor(clause, isCustomer);
                            return (
                              <button key={clause.ref}
                                onClick={() => setSelectedClause(isSelected ? null : clause)}
                                className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                                  isSelected ? "bg-blue-50" : "hover:bg-slate-50"
                                }`}>
                                <div className="w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: dotColor }} />
                                <span className="text-xs font-mono font-semibold text-slate-600 w-16 flex-shrink-0">
                                  {clause.ref}
                                </span>
                                <div className="flex-1 flex items-center gap-1.5 flex-wrap">
                                  {hasTemplates ? (
                                    clause.templates.map(t => {
                                      const cfg = t.doc_status ? DOC_STATUS_CONFIG[t.doc_status] : null;
                                      const label = isCustomer && t.doc_name ? t.doc_name : t.name;
                                      return (
                                        <span key={t.id}
                                          className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
                                          style={cfg
                                            ? { backgroundColor: cfg.bg, color: cfg.color }
                                            : { backgroundColor: "#f1f5f9", color: "#475569" }}
                                          title={label}>
                                          <FileText className="w-2.5 h-2.5" />
                                          {label.length > 32 ? label.slice(0, 32) + "…" : label}
                                          {/* Show % only when in progress — completed/draft don't need it */}
                                          {isCustomer && t.doc_status === "in_progress" && t.completion_pct !== null && (
                                            <span className="opacity-70">{t.completion_pct}%</span>
                                          )}
                                        </span>
                                      );
                                    })
                                  ) : (
                                    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-500 font-medium">
                                      <AlertTriangle className="w-2.5 h-2.5" /> No template
                                    </span>
                                  )}
                                </div>
                                <ChevronRight className={`w-3.5 h-3.5 text-slate-300 flex-shrink-0 transition-transform ${isSelected ? "rotate-90" : ""}`} />
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
        </div>

        {/* ── Right: Detail Panel ── */}
        <div className="w-72 flex-shrink-0">
          <div className="sticky top-0 space-y-3">
            {/* Legend */}
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Legend</p>
              <div className="space-y-2">
                {isCustomer ? (
                  <>
                    {[
                      { color: "#10b981", label: "All tasks done" },
                      { color: "#3b82f6", label: "≥50% tasks done" },
                      { color: "#f59e0b", label: "In progress (<50%)" },
                      { color: "#fca5a5", label: "Not started" },
                      { color: "#e5e7eb", label: "No tasks" },
                    ].map(l => (
                      <div key={l.label} className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: l.color }} />
                        <span className="text-xs text-slate-600">{l.label}</span>
                      </div>
                    ))}
                  </>
                ) : (
                  [
                    { color: "#10b981", label: "Fully covered" },
                    { color: "#3b82f6", label: "Partially covered" },
                    { color: "#f59e0b", label: "Minimal coverage" },
                    { color: "#ef4444", label: "No coverage (gap)" },
                  ].map(l => (
                    <div key={l.label} className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: l.color }} />
                      <span className="text-xs text-slate-600">{l.label}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Clause detail */}
            {selectedClause ? (
              <div className="bg-white rounded-xl border border-slate-100 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                    {selectedClause.ref}
                  </span>
                  <span className="text-xs text-slate-500">
                    {selectedClause.templates.length} template{selectedClause.templates.length !== 1 ? "s" : ""}
                  </span>
                </div>
                {selectedClause.templates.length === 0 ? (
                  <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    <p className="text-xs text-red-600 font-medium">
                      No template covers this clause — this is a gap.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedClause.templates.map(t => {
                      const cfg = t.doc_status ? DOC_STATUS_CONFIG[t.doc_status] : null;
                      const StatusIcon = cfg?.icon ?? FileText;
                      return (
                        <div key={t.id} className="p-3 rounded-lg border border-slate-100">
                          <div className="flex items-start gap-2">
                            <StatusIcon className="w-3.5 h-3.5 mt-0.5 flex-shrink-0"
                              style={{ color: cfg?.color ?? "#94a3b8" }} />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-semibold text-slate-800 leading-tight">
                                {isCustomer && t.doc_name ? t.doc_name : t.name}
                              </p>
                              {isCustomer && t.doc_name && t.doc_name !== t.name && (
                                <p className="text-xs text-slate-400 mt-0.5">{t.name}</p>
                              )}
                              {isCustomer && (
                                <div className="mt-1.5 space-y-1">
                                  <div className="flex justify-between text-xs text-slate-400 mb-0.5">
                                    <span>{cfg?.label ?? "Not started"}</span>
                                    <span>{t.completion_pct ?? 0}%</span>
                                  </div>
                                  <div className="w-full bg-slate-100 rounded-full h-1 overflow-hidden">
                                    <div className="h-1 rounded-full transition-all"
                                      style={{ width: `${t.completion_pct ?? 0}%`, backgroundColor: cfg?.color ?? "#e5e7eb" }} />
                                  </div>
                                  {t.tasks_total > 0 && (
                                    <div className="flex items-center gap-1.5 mt-1">
                                      <CheckCheck className="w-3 h-3 text-slate-400" />
                                      <span className="text-xs text-slate-500">
                                        {t.tasks_done}/{t.tasks_total} tasks done
                                      </span>
                                    </div>
                                  )}
                                </div>
                              )}
                              {!isCustomer && (
                                <p className="text-xs text-slate-400 mt-0.5">
                                  {t.total_fillable} fillable field{t.total_fillable !== 1 ? "s" : ""}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-slate-100 p-4 text-center">
                <BarChart3 className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                <p className="text-xs text-slate-400">Click any clause to see details</p>
              </div>
            )}

            {/* Gap summary */}
            {summary.gap_clauses > 0 && (
              <div className="bg-red-50 rounded-xl border border-red-100 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <p className="text-xs font-semibold text-red-700">
                    {summary.gap_clauses} uncovered clause{summary.gap_clauses !== 1 ? "s" : ""}
                  </p>
                </div>
                <p className="text-xs text-red-500">
                  {isCustomer
                    ? "These clauses have no assigned documents for this customer."
                    : "These clauses have no templates. Build them with AI to close the gaps."}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
