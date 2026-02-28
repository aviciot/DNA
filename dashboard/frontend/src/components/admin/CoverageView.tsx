"use client";

import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  ChevronDown, ChevronRight, FileText, AlertTriangle,
  CheckCircle2, Clock, Circle, Loader2, BarChart3, Shield
} from "lucide-react";

import api from "@/lib/api";

interface TemplateRef {
  id: string;
  name: string;
  total_fillable: number;
  doc_status: string | null;
  completion_pct: number | null;
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
  if (!status) return "#e5e7eb"; // no doc — gap
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

function RadialScore({ pct, color, size = 64 }: { pct: number; color: string; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={6} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }} />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        className="rotate-90" style={{ fontSize: size * 0.22, fontWeight: 700, fill: "#111827", transform: `rotate(90deg) translate(0, -${size}px)` }} />
    </svg>
  );
}

export default function CoverageView({ isoId, customerId, isoColor = "#3b82f6" }: Props) {
  const [data, setData] = useState<CoverageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedClause, setSelectedClause] = useState<ClauseRef | null>(null);

  const token = () => localStorage.getItem("access_token");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (customerId) params.customer_id = customerId;
      const r = await api.get(
        `/api/v1/iso-standards/${isoId}/coverage`,
        { params }
      );
      setData(r.data);
      // Auto-expand first group
      if (r.data.groups.length > 0) setExpanded(new Set([r.data.groups[0].key]));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [isoId, customerId]);

  useEffect(() => { load(); }, [load]);

  const toggleGroup = (key: string) => {
    setExpanded(prev => {
      const n = new Set(prev);
      n.has(key) ? n.delete(key) : n.add(key);
      return n;
    });
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

  // Split groups: main clauses vs annex
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
              <p className="text-xs text-slate-500">{isCustomer ? "Completion" : "Coverage"}</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-600">{summary.covered_clauses}</p>
              <p className="text-xs text-slate-500">Covered</p>
            </div>
            {summary.gap_clauses > 0 && (
              <div className="text-center">
                <p className="text-2xl font-bold text-red-500">{summary.gap_clauses}</p>
                <p className="text-xs text-slate-500">Gaps</p>
              </div>
            )}
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-700">{summary.total_templates}</p>
              <p className="text-xs text-slate-500">Templates</p>
            </div>
          </div>
        </div>
        {/* Overall progress bar */}
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
          <div className="h-2.5 rounded-full transition-all duration-700"
            style={{ width: `${summary.coverage_pct}%`, backgroundColor: accentColor }} />
        </div>
      </div>

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
                  const barColor = isCustomer
                    ? docStatusColor(grp.completion_pct === 100 ? "approved" : grp.completion_pct ? "in_progress" : null, grp.completion_pct)
                    : planCoverageColor(grp.covered_clauses, grp.total_clauses);
                  const pct = isCustomer
                    ? grp.completion_pct
                    : Math.round((grp.covered_clauses / grp.total_clauses) * 100);

                  return (
                    <div key={grp.key} className="bg-white rounded-xl border border-slate-100 overflow-hidden">
                      {/* Group header */}
                      <button onClick={() => toggleGroup(grp.key)}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left">
                        <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold text-white"
                          style={{ backgroundColor: barColor }}>
                          {grp.key}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-semibold text-slate-800">
                              {isCustomer
                                ? `${grp.completion_pct}% complete`
                                : `${grp.covered_clauses}/${grp.total_clauses} clauses covered`}
                            </span>
                            <span className="text-xs text-slate-400 ml-2 flex-shrink-0">
                              {grp.clauses.length} clause{grp.clauses.length !== 1 ? "s" : ""}
                            </span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div className="h-1.5 rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: barColor }} />
                          </div>
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
                            const dotColor = isCustomer
                              ? docStatusColor(
                                  clause.templates[0]?.doc_status ?? null,
                                  clause.templates[0]?.completion_pct ?? null
                                )
                              : planCoverageColor(hasTemplates ? 1 : 0, 1);

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
                                      return (
                                        <span key={t.id}
                                          className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
                                          style={cfg
                                            ? { backgroundColor: cfg.bg, color: cfg.color }
                                            : { backgroundColor: "#f1f5f9", color: "#475569" }}>
                                          <FileText className="w-2.5 h-2.5" />
                                          {t.name.length > 28 ? t.name.slice(0, 28) + "…" : t.name}
                                          {isCustomer && t.completion_pct != null && (
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
                  Object.entries(DOC_STATUS_CONFIG).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: v.color }} />
                      <span className="text-xs text-slate-600">{v.label}</span>
                    </div>
                  ))
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
                              <p className="text-xs font-semibold text-slate-800 leading-tight">{t.name}</p>
                              {isCustomer && (
                                <div className="mt-1.5">
                                  <div className="flex justify-between text-xs text-slate-400 mb-0.5">
                                    <span>{cfg?.label ?? "Not started"}</span>
                                    <span>{t.completion_pct ?? 0}%</span>
                                  </div>
                                  <div className="w-full bg-slate-100 rounded-full h-1 overflow-hidden">
                                    <div className="h-1 rounded-full transition-all"
                                      style={{ width: `${t.completion_pct ?? 0}%`, backgroundColor: cfg?.color ?? "#e5e7eb" }} />
                                  </div>
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
