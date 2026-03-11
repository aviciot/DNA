"use client";

import { useState, useEffect, useRef } from "react";
import {
  Loader2, Sparkles, RefreshCw, CheckCircle2, Clock, AlertTriangle,
  ChevronDown, ChevronRight, Edit2, Check, X, Copy, Info,
  AlertCircle, Link2,
} from "lucide-react";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────

interface ActivityEntry {
  key: string;
  title?: string;
  label?: string;
  category?: string;
  iso_clause?: string;
  description?: string;
  type?: string;
  lifecycle?: "static" | "recurring";
  update_frequency?: string | null;
  template_name?: string | null;
  template_id_source?: string | null;
  source?: "template" | "iso_level" | "placeholder_fallback";
  // iso360_template fields
  template_status?: "not_generated" | "generated" | "needs_review" | "approved";
  iso360_template_id?: string | null;
  iso360_template_title?: string | null;
  used_by_standards_count?: number;
  template_updated_at?: string | null;
}

interface PanelData {
  iso_standard_id: string;
  iso_code: string;
  iso_name: string;
  has_metadata: boolean;
  has_recurring_activities: boolean;
  activities: ActivityEntry[];
  stats: {
    total: number;
    recurring: number;
    generated: number;
    not_generated: number;
  };
}

interface JobStatus {
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  total: number;
  done: number;
  current_key?: string | null;
  created?: number;
  skipped?: number;
  iso_code?: string;
  message?: string;
  error?: string;
}

interface Props {
  isoId: string;
  isoCode: string;
  isoColor: string;
}

// ── Helpers ───────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  policy:               "bg-blue-50 text-blue-700",
  procedure:            "bg-indigo-50 text-indigo-700",
  operational_activity: "bg-amber-50 text-amber-700",
  review:               "bg-violet-50 text-violet-700",
  record:               "bg-emerald-50 text-emerald-700",
};

const FREQ_COLORS: Record<string, string> = {
  monthly:     "bg-rose-50 text-rose-600",
  quarterly:   "bg-orange-50 text-orange-600",
  yearly:      "bg-sky-50 text-sky-600",
  event_based: "bg-slate-100 text-slate-500",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  not_generated: <Clock className="w-3.5 h-3.5 text-slate-400" />,
  generated:     <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />,
  needs_review:  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />,
  approved:      <CheckCircle2 className="w-3.5 h-3.5 text-blue-500" />,
};

const STATUS_LABELS: Record<string, string> = {
  not_generated: "Not generated",
  generated:     "Generated",
  needs_review:  "Needs review",
  approved:      "Approved",
};

function Badge({ children, className }: { children: React.ReactNode; className: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${className}`}>
      {children}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────

export default function ISO360TemplatesPanel({ isoId, isoCode, isoColor }: Props) {
  const [data, setData] = useState<PanelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadData();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [isoId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/api/v1/iso360-templates/standard/${isoId}`);
      setData(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const startGeneration = async () => {
    setGenerating(true);
    setJobStatus({ status: "queued", progress: 0, total: 0, done: 0 });
    try {
      const r = await api.post(`/api/v1/iso360-templates/standard/${isoId}/generate`);
      const jobId = r.data.job_id;
      pollRef.current = setInterval(async () => {
        try {
          const s = await api.get(`/api/v1/iso360-templates/jobs/${jobId}/status`);
          setJobStatus(s.data);
          if (s.data.status === "completed" || s.data.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setGenerating(false);
            if (s.data.status === "completed") await loadData();
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
          setGenerating(false);
        }
      }, 2000);
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
      setGenerating(false);
      setJobStatus(null);
    }
  };

  const toggleExpand = (key: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!data) return null;

  const noMetadata = !data.has_metadata && data.activities.length > 0;
  const needsRebuild = !data.has_recurring_activities && data.has_metadata;

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-2 h-8 rounded-full flex-shrink-0"
            style={{ backgroundColor: isoColor }}
          />
          <div>
            <h3 className="text-sm font-bold text-slate-900">ISO360 Templates — ISO {isoCode}</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {data.stats.recurring} recurring · {data.stats.generated}/{data.stats.recurring} generated
            </p>
          </div>
        </div>

        <button
          onClick={startGeneration}
          disabled={generating || noMetadata}
          title={noMetadata ? "Rebuild the ISO standard first to populate metadata" : ""}
          className="flex items-center gap-2 px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white
                     rounded-lg text-xs font-medium transition-colors disabled:opacity-50 shadow-sm"
        >
          {generating
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Sparkles className="w-3.5 h-3.5" />}
          {generating ? "Generating…" : "Generate ISO360 Templates"}
        </button>
      </div>

      {/* Rebuild recommended warning (has metadata but no recurring_activities yet) */}
      {needsRebuild && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm">
          <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-800">Rebuild recommended</p>
            <p className="text-amber-700 mt-0.5">
              This standard was built before ISO360 activity generation was available.
              Rebuild with AI to get clause-linked recurring activities per template.
              Currently showing placeholder-based fallback data.
            </p>
          </div>
        </div>
      )}

      {/* No metadata at all warning */}
      {!data.has_metadata && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm">
          <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-800">Rebuild required</p>
            <p className="text-amber-700 mt-0.5">
              This standard has not been built with AI yet. Use &quot;Build with AI&quot; in the ISO Standards tab first.
            </p>
          </div>
        </div>
      )}

      {/* Generation progress */}
      {jobStatus && (
        <div className={`rounded-xl border p-3 text-xs ${
          jobStatus.status === "failed" ? "bg-red-50 border-red-200" :
          jobStatus.status === "completed" ? "bg-emerald-50 border-emerald-200" :
          "bg-slate-50 border-slate-200"
        }`}>
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium text-slate-700 capitalize">
              {jobStatus.status === "queued"    && "Queued — waiting for worker…"}
              {jobStatus.status === "running"   && `Generating: ${jobStatus.current_key || "…"}`}
              {jobStatus.status === "completed" && `Done — ${jobStatus.created ?? 0} created, ${jobStatus.skipped ?? 0} reused`}
              {jobStatus.status === "failed"    && `Failed: ${jobStatus.error}`}
            </span>
            <span className="text-slate-400">{jobStatus.done}/{jobStatus.total}</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all ${
                jobStatus.status === "failed" ? "bg-red-500" :
                jobStatus.status === "completed" ? "bg-emerald-500" : "bg-violet-500"
              }`}
              style={{ width: `${jobStatus.progress}%` }}
            />
          </div>
          {jobStatus.message && (
            <p className="mt-1.5 text-slate-500">{jobStatus.message}</p>
          )}
        </div>
      )}

      {/* Stats pills */}
      <div className="flex gap-2 flex-wrap">
        <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-lg font-medium">
          {data.stats.total} total activities
        </span>
        <span className="text-xs bg-violet-50 text-violet-700 px-2.5 py-1 rounded-lg font-medium">
          {data.stats.recurring} recurring
        </span>
        <span className="text-xs bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded-lg font-medium">
          {data.stats.generated} generated
        </span>
        {data.stats.not_generated > 0 && (
          <span className="text-xs bg-amber-50 text-amber-600 px-2.5 py-1 rounded-lg font-medium">
            {data.stats.not_generated} not yet generated
          </span>
        )}
      </div>

      {/* Activity rows */}
      {data.activities.length > 0 && (
        <section className="space-y-1">
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide px-0.5">
            Recurring Activities ({data.activities.length})
          </h4>
          {data.activities.map(activity => (
            <ActivityRow
              key={activity.key}
              entry={activity}
              expanded={expandedKeys.has(activity.key)}
              onToggle={() => toggleExpand(activity.key)}
              onUpdated={loadData}
            />
          ))}
        </section>
      )}

      {data.activities.length === 0 && (
        <div className="text-center py-8 text-slate-400 text-sm">
          No activities found. Build this ISO standard with AI first.
        </div>
      )}
    </div>
  );
}

// ── Activity Row ───────────────────────────────────────────

interface RowProps {
  entry: ActivityEntry;
  expanded: boolean;
  onToggle: () => void;
  onUpdated: () => void;
}

function ActivityRow({ entry, expanded, onToggle, onUpdated }: RowProps) {
  const [template, setTemplate] = useState<any>(null);
  const [loadingTmpl, setLoadingTmpl] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  const hasTemplate = entry.template_status !== "not_generated" && entry.iso360_template_id;
  const displayTitle = entry.title || entry.label || entry.key;

  const handleExpand = async () => {
    onToggle();
    if (!expanded && hasTemplate && !template) {
      setLoadingTmpl(true);
      try {
        const r = await api.get(`/api/v1/iso360-templates/${entry.iso360_template_id}`);
        setTemplate(r.data);
      } catch (e) { console.error(e); }
      finally { setLoadingTmpl(false); }
    }
  };

  const startEdit = () => {
    if (!template) return;
    setEditData({
      title:            template.title,
      responsible_role: template.responsible_role,
      steps:            JSON.stringify(template.steps, null, 2),
      evidence_fields:  JSON.stringify(template.evidence_fields, null, 2),
    });
    setEditing(true);
  };

  const handleSave = async () => {
    if (!entry.iso360_template_id || !editData) return;
    setSaving(true);
    try {
      let steps, evidence_fields;
      try { steps = JSON.parse(editData.steps); } catch { alert("Invalid JSON in steps"); setSaving(false); return; }
      try { evidence_fields = JSON.parse(editData.evidence_fields); } catch { alert("Invalid JSON in evidence fields"); setSaving(false); return; }

      await api.put(`/api/v1/iso360-templates/${entry.iso360_template_id}`, {
        title:            editData.title,
        responsible_role: editData.responsible_role,
        steps,
        evidence_fields,
        status:           "needs_review",
      });
      const r = await api.get(`/api/v1/iso360-templates/${entry.iso360_template_id}`);
      setTemplate(r.data);
      setEditing(false);
      onUpdated();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };

  return (
    <div className="border border-slate-100 rounded-xl overflow-hidden hover:border-slate-200 transition-colors">
      {/* Row header */}
      <button
        onClick={handleExpand}
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
      >
        {expanded
          ? <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
          : <ChevronRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />}

        <span className="text-xs font-mono text-slate-500 flex-shrink-0 w-48 truncate">
          {entry.key}
        </span>

        <div className="flex-1 min-w-0">
          <span className="text-xs text-slate-700 font-medium block truncate">
            {displayTitle}
          </span>
          {entry.description && (
            <span className="text-xs text-slate-400 block truncate mt-0.5">
              {entry.description}
            </span>
          )}
          {entry.template_name && entry.source === "template" && (
            <span className="inline-flex items-center gap-1 text-xs text-sky-600 mt-0.5">
              <Link2 className="w-3 h-3" />
              {entry.template_name}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          {entry.iso_clause && (
            <Badge className="bg-slate-100 text-slate-500">
              {entry.iso_clause}
            </Badge>
          )}
          {entry.type && (
            <Badge className={TYPE_COLORS[entry.type] || "bg-slate-100 text-slate-500"}>
              {entry.type?.replace("_", " ")}
            </Badge>
          )}
          {entry.update_frequency && (
            <Badge className={FREQ_COLORS[entry.update_frequency] || "bg-slate-100 text-slate-500"}>
              {entry.update_frequency?.replace("_", " ")}
            </Badge>
          )}
          {entry.source === "iso_level" && (
            <Badge className="bg-purple-50 text-purple-600">cross-cutting</Badge>
          )}
          <span className="flex items-center gap-1 text-xs text-slate-400">
            {STATUS_ICONS[entry.template_status || "not_generated"]}
            {STATUS_LABELS[entry.template_status || "not_generated"]}
          </span>
          {(entry.used_by_standards_count || 0) > 1 && (
            <span className="flex items-center gap-0.5 text-xs text-sky-600 bg-sky-50 px-1.5 py-0.5 rounded-full">
              <Copy className="w-3 h-3" /> {entry.used_by_standards_count}
            </span>
          )}
        </div>
      </button>

      {/* Expanded template details */}
      {expanded && (
        <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-3">
          {loadingTmpl && (
            <div className="flex items-center gap-2 text-xs text-slate-400 py-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading template…
            </div>
          )}

          {!hasTemplate && !loadingTmpl && (
            <p className="text-xs text-slate-400 italic">
              No template generated yet. Click &quot;Generate ISO360 Templates&quot; above.
            </p>
          )}

          {hasTemplate && template && !editing && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">{template.title}</p>
                  {template.responsible_role && (
                    <p className="text-xs text-slate-500 mt-0.5">
                      Responsible: {template.responsible_role}
                    </p>
                  )}
                </div>
                <button
                  onClick={startEdit}
                  className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-blue-600
                             hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors"
                >
                  <Edit2 className="w-3.5 h-3.5" /> Edit
                </button>
              </div>

              {template.steps?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 mb-1.5">Steps</p>
                  <ol className="space-y-1">
                    {template.steps.map((s: any) => (
                      <li key={s.order} className="flex gap-2 text-xs text-slate-600">
                        <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-500
                                         flex items-center justify-center flex-shrink-0 text-[10px] font-medium">
                          {s.order}
                        </span>
                        {s.instruction}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {template.evidence_fields?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 mb-1.5">Evidence Fields</p>
                  <div className="flex flex-wrap gap-1.5">
                    {template.evidence_fields.map((f: any) => (
                      <span key={f.field_name}
                        className="text-xs bg-white border border-slate-200 rounded-lg px-2 py-0.5 text-slate-600">
                        {f.field_name}
                        <span className="text-slate-400 ml-1">({f.field_type})</span>
                        {f.required && <span className="text-red-400 ml-0.5">*</span>}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {hasTemplate && editing && editData && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Title</label>
                  <input
                    className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg
                               focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                    value={editData.title}
                    onChange={e => setEditData({ ...editData, title: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Responsible Role</label>
                  <input
                    className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg
                               focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                    value={editData.responsible_role}
                    onChange={e => setEditData({ ...editData, responsible_role: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  Steps (JSON array)
                </label>
                <textarea
                  rows={6}
                  className="w-full px-3 py-2 text-xs font-mono border border-slate-200 rounded-lg
                             focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                  value={editData.steps}
                  onChange={e => setEditData({ ...editData, steps: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  Evidence Fields (JSON array)
                </label>
                <textarea
                  rows={4}
                  className="w-full px-3 py-2 text-xs font-mono border border-slate-200 rounded-lg
                             focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                  value={editData.evidence_fields}
                  onChange={e => setEditData({ ...editData, evidence_fields: e.target.value })}
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setEditing(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg font-medium">
                  Cancel
                </button>
                <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700
                             text-white rounded-lg font-medium disabled:opacity-50">
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Save
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
