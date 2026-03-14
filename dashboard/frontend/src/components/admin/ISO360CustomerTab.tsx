"use client";

import { useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  Shield,
  Search,
  Settings,
  ClipboardList,
  ChevronRight,
  X,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  Zap,
  Filter,
  EyeOff,
  Eye,
  MessageSquare,
  Play,
  RefreshCw,
} from "lucide-react";
import api from "@/lib/api";

const MermaidGraph = dynamic(() => import("@/components/shared/MermaidGraph"), { ssr: false });

// ── Types ─────────────────────────────────────────────────────────────────────

interface StepItem {
  order: number;
  instruction: string;
}

interface EvidenceField {
  field_name: string;
  field_type: string;
  required: boolean;
}

interface ISO360Activity {
  doc_id: string;
  plan_id: string;
  placeholder_key: string;
  title: string;
  type: string;
  update_frequency: string;
  responsible_role: string | null;
  iso_clause: string | null;
  status: string;
  next_due_date: string | null;
  last_completed_at: string | null;
  steps: StepItem[];
  evidence_fields: EvidenceField[];
  completion_status: string;
  excluded: boolean;
}

interface ISO360PlanStats {
  total: number;
  completed_this_year: number;
  due_soon: number;
  overdue: number;
  event_based: number;
}

interface ISO360Plan {
  plan_id: string;
  iso_code: string;
  iso_name: string;
  iso360_enabled: boolean;
  adjustment_pass_done: boolean;
  onboarding_threshold_pct: number;
  activities: ISO360Activity[];
  stats: ISO360PlanStats;
}

interface ISO360CustomerResponse {
  plans: ISO360Plan[];
}

interface ISO360CustomerTabProps {
  customerId: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getTypeIcon(type: string) {
  switch (type) {
    case "review":
      return <Search className="w-4 h-4 text-blue-500" />;
    case "operational_activity":
      return <Settings className="w-4 h-4 text-violet-500" />;
    case "record":
      return <ClipboardList className="w-4 h-4 text-emerald-500" />;
    default:
      return <ClipboardList className="w-4 h-4 text-gray-400" />;
  }
}

function getTypeLabel(type: string): string {
  switch (type) {
    case "review": return "Review";
    case "operational_activity": return "Operations";
    case "record": return "Record";
    default: return type;
  }
}

function getTypeColor(type: string): string {
  switch (type) {
    case "review": return "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300";
    case "operational_activity": return "bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300";
    case "record": return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
    default: return "bg-gray-50 text-gray-600 dark:bg-gray-700 dark:text-gray-400";
  }
}

function getFreqBadge(freq: string): string {
  switch (freq) {
    case "monthly": return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300";
    case "quarterly": return "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300";
    case "yearly": return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
    case "event_based": return "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400";
    default: return "bg-gray-100 text-gray-600";
  }
}

function getFreqLabel(freq: string): string {
  switch (freq) {
    case "monthly": return "Monthly";
    case "quarterly": return "Quarterly";
    case "yearly": return "Yearly";
    case "event_based": return "Event-based";
    default: return freq;
  }
}

function getCompletionBadgeClass(cs: string): string {
  switch (cs) {
    case "overdue": return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
    case "due_soon": return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
    case "completed": return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
    case "event_based": return "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400";
    default: return "bg-gray-50 text-gray-400 dark:bg-gray-800 dark:text-gray-500";
  }
}

function getCompletionLabel(cs: string): string {
  switch (cs) {
    case "overdue": return "Overdue";
    case "due_soon": return "Due Soon";
    case "completed": return "Completed";
    case "event_based": return "On Demand";
    case "upcoming": return "Upcoming";
    default: return cs;
  }
}

function getRowBorder(cs: string): string {
  switch (cs) {
    case "overdue": return "border-l-4 border-l-red-400";
    case "due_soon": return "border-l-4 border-l-amber-400";
    case "completed": return "border-l-4 border-l-emerald-400";
    default: return "border-l-4 border-l-transparent";
  }
}

function getAttentionCardBorder(cs: string): string {
  if (cs === "overdue") return "border-red-200 dark:border-red-700 bg-red-50 dark:bg-red-900/20";
  return "border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20";
}

// ── Activity Detail Modal ─────────────────────────────────────────────────────

function ActivityDetailModal({
  activity,
  onClose,
}: {
  activity: ISO360Activity;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col overflow-hidden">
        {/* Gradient header */}
        <div className="bg-gradient-to-br from-slate-800 to-indigo-900 px-6 py-5 flex items-start justify-between flex-shrink-0">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center flex-shrink-0">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold text-white/70 uppercase tracking-widest mb-0.5">
                ISO360 Activity
              </p>
              <h2 className="text-lg font-bold text-white leading-snug max-w-lg">
                {activity.title}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 bg-white/20 hover:bg-white/30 rounded-lg flex items-center justify-center transition-colors flex-shrink-0 ml-3 mt-0.5"
          >
            <X className="w-4 h-4 text-white" />
          </button>
        </div>

        {/* Badges row */}
        <div className="flex flex-wrap gap-2 px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex-shrink-0">
          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${getFreqBadge(activity.update_frequency)}`}>
            {getFreqLabel(activity.update_frequency)}
          </span>
          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${getTypeColor(activity.type)}`}>
            {getTypeLabel(activity.type)}
          </span>
          {activity.iso_clause && (
            <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
              Clause {activity.iso_clause}
            </span>
          )}
          {activity.responsible_role && (
            <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
              {activity.responsible_role}
            </span>
          )}
          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${getCompletionBadgeClass(activity.completion_status)}`}>
            {getCompletionLabel(activity.completion_status)}
          </span>
        </div>

        {/* Dates */}
        <div className="flex gap-6 px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-amber-500 flex-shrink-0" />
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Next Due</p>
              <p className={`text-sm font-bold ${
                activity.completion_status === "overdue"
                  ? "text-red-600 dark:text-red-400"
                  : activity.completion_status === "due_soon"
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-gray-900 dark:text-white"
              }`}>
                {activity.update_frequency === "event_based" && !activity.next_due_date
                  ? "On demand"
                  : formatDate(activity.next_due_date)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Last Completed</p>
              <p className="text-sm font-bold text-gray-900 dark:text-white">
                {activity.last_completed_at ? formatDate(activity.last_completed_at) : "Never"}
              </p>
            </div>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          {/* Steps */}
          {activity.steps && activity.steps.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest mb-3">
                Steps
              </h4>
              <div className="space-y-2">
                {activity.steps.map((step, idx) => (
                  <div key={idx} className="flex gap-3">
                    <div className="w-6 h-6 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                      {step.order ?? idx + 1}
                    </div>
                    <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                      {step.instruction}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence fields */}
          {activity.evidence_fields && activity.evidence_fields.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest mb-3">
                Evidence Required
              </h4>
              <div className="space-y-1.5">
                {activity.evidence_fields.map((ef, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-3 px-3 py-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-xl"
                  >
                    <div className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
                    <span className="text-sm font-medium text-gray-800 dark:text-gray-200 flex-1">
                      {ef.field_name}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 font-mono">
                      {ef.field_type}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      ef.required
                        ? "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400"
                        : "bg-gray-100 text-gray-400 dark:bg-gray-700 dark:text-gray-500"
                    }`}>
                      {ef.required ? "required" : "optional"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No steps or evidence */}
          {(!activity.steps || activity.steps.length === 0) &&
            (!activity.evidence_fields || activity.evidence_fields.length === 0) && (
            <div className="text-center py-8 text-gray-400 dark:text-gray-500">
              <ClipboardList className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No detailed steps or evidence fields defined.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function ISO360CustomerTab({ customerId }: ISO360CustomerTabProps) {
  const [data, setData] = useState<ISO360CustomerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedActivity, setSelectedActivity] = useState<ISO360Activity | null>(null);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);

  // Trigger state
  const [triggering, setTriggering] = useState<string | null>(null);
  const [triggerMsg, setTriggerMsg] = useState<{ docId: string; ok: boolean; text: string } | null>(null);

  // Exclude state — optimistic: doc_id → excluded bool override
  const [excludedMap, setExcludedMap] = useState<Record<string, boolean>>({});

  // Complete state
  const [completingDoc, setCompletingDoc] = useState<string | null>(null);

  // KYC state
  interface KYCSummaryOrgProfile { size?: string; industry?: string; cloud?: string[]; key_tools?: string[]; dev_stack?: string[] }
  interface KYCSummary { org_profile?: KYCSummaryOrgProfile; existing_controls?: string[]; identified_gaps?: string[]; compliance_maturity?: string; key_risks?: string[] }
  interface KYCStatus { batch_id?: string; status?: string; total_questions: number; answered_count: number; has_active_batch: boolean; error_message?: string; kyc_summary?: KYCSummary; kyc_summary_graph?: string }
  const [kycStatus, setKycStatus] = useState<KYCStatus | null>(null);
  const [kycLoading, setKycLoading] = useState(false);
  const [kycTriggering, setKycTriggering] = useState(false);
  const [kycError, setKycError] = useState<string | null>(null);
  const [planLanguage, setPlanLanguage] = useState<string>("en");
  const [langUpdating, setLangUpdating] = useState(false);

  const loadKycStatus = async (planId: string) => {
    try {
      const res = await api.get(`/api/v1/customers/${customerId}/iso360/kyc/status?plan_id=${planId}`);
      setKycStatus(res.data);
    } catch { /* ignore */ }
  };

  const triggerKyc = async (planId: string) => {
    setKycTriggering(true);
    setKycError(null);
    try {
      await api.post(`/api/v1/customers/${customerId}/iso360/kyc/trigger?plan_id=${planId}`);
      await loadKycStatus(planId);
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 409) {
        setKycError("KYC questionnaire is already active for this plan.");
        await loadKycStatus(planId);
      } else {
        setKycError(err.response?.data?.detail || "Failed to start KYC");
      }
    } finally {
      setKycTriggering(false);
    }
  };

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [freqFilter, setFreqFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await api.get(`/api/v1/customers/${customerId}/iso360`);
        setData(res.data);
        if (res.data.plans?.length > 0) {
          setActivePlanId(res.data.plans[0].plan_id);
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load ISO360 data");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  // Load KYC status whenever active plan changes and adjustment hasn't run yet
  useEffect(() => {
    if (!activePlanId || !data) return;
    const plan = data.plans.find(p => p.plan_id === activePlanId);
    if (plan && !plan.adjustment_pass_done) {
      loadKycStatus(activePlanId);
      setPlanLanguage("en"); // reset; will be overridden once we fetch plan language
    }
  }, [activePlanId, data]);

  const updatePlanLanguage = async (planId: string, lang: string) => {
    setLangUpdating(true);
    try {
      await api.patch(`/api/v1/customers/${customerId}/iso360/plans/${planId}/language?language=${lang}`);
      setPlanLanguage(lang);
    } catch { /* ignore — non-critical */ }
    finally { setLangUpdating(false); }
  };

  const triggerActivity = async (docId: string, title: string) => {
    setTriggering(docId);
    setTriggerMsg(null);
    try {
      await api.post(`/api/v1/customers/${customerId}/iso360/activities/${docId}/trigger`);
      setTriggerMsg({ docId, ok: true, text: "Task created — visible in Tasks tab" });
    } catch (err: any) {
      const detail = err.response?.data?.detail || "Failed to trigger activity";
      const isConflict = err.response?.status === 409;
      setTriggerMsg({ docId, ok: false, text: isConflict ? "Task already open" : detail });
    } finally {
      setTriggering(null);
      setTimeout(() => setTriggerMsg(null), 4000);
    }
  };

  const toggleExclude = async (a: ISO360Activity) => {
    const current = a.doc_id in excludedMap ? excludedMap[a.doc_id] : a.excluded;
    const next = !current;
    setExcludedMap((m) => ({ ...m, [a.doc_id]: next })); // optimistic
    try {
      await api.patch(
        `/api/v1/customers/${customerId}/iso360/activities/${a.doc_id}/exclude?excluded=${next}`
      );
    } catch {
      setExcludedMap((m) => ({ ...m, [a.doc_id]: current })); // revert on error
    }
  };

  async function handleMarkComplete(docId: string) {
    if (completingDoc) return;
    setCompletingDoc(docId);
    try {
      const res = await fetch(`/api/v1/customers/${customerId}/iso360/activities/${docId}/complete`, { method: "POST" });
      if (res.ok) {
        const reload = async () => {
          try {
            const r = await api.get(`/api/v1/customers/${customerId}/iso360`);
            setData(r.data);
          } catch { /* ignore */ }
        };
        await reload();
      }
    } catch (e) { console.error(e); }
    finally { setCompletingDoc(null); }
  }

  const activePlan = useMemo(() => {
    if (!data || !activePlanId) return data?.plans[0] ?? null;
    return data.plans.find((p) => p.plan_id === activePlanId) ?? data.plans[0] ?? null;
  }, [data, activePlanId]);

  const filteredActivities = useMemo(() => {
    if (!activePlan) return [];
    return activePlan.activities.filter((a) => {
      if (typeFilter !== "all" && a.type !== typeFilter) return false;
      if (freqFilter !== "all" && a.update_frequency !== freqFilter) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        if (
          !a.title.toLowerCase().includes(q) &&
          !a.placeholder_key.toLowerCase().includes(q) &&
          !(a.iso_clause || "").toLowerCase().includes(q)
        ) return false;
      }
      return true;
    });
  }, [activePlan, typeFilter, freqFilter, search]);

  const attentionActivities = useMemo(() => {
    if (!activePlan) return [];
    return activePlan.activities.filter(
      (a) => a.completion_status === "overdue" || a.completion_status === "due_soon"
    );
  }, [activePlan]);

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading ISO360 data…</p>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{error}</p>
      </div>
    );
  }

  // ── Empty state: no ISO360 enabled plans ──────────────────────────────────
  if (!data || data.plans.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-5 text-center px-8">
        <div className="w-20 h-20 bg-amber-100 dark:bg-amber-900/30 rounded-3xl flex items-center justify-center">
          <Shield className="w-10 h-10 text-amber-500" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            ISO360 Not Active
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm leading-relaxed">
            Enable ISO360 in the Documents tab to activate year-round compliance
            management for this customer.
          </p>
        </div>
        <p className="text-xs italic text-amber-600 dark:text-amber-400 font-medium">
          "Keep customers certified, year-round."
        </p>
      </div>
    );
  }

  // ── Waiting for adjustment pass — show KYC panel ─────────────────────────
  if (activePlan && !activePlan.adjustment_pass_done) {
    const kyc = kycStatus;
    const kycPending   = kyc?.status === "pending";
    const kycGenerating = kyc?.status === "generating";
    const kycCompleted  = kyc?.status === "completed" || kyc?.status === "adjustment_triggered";
    const kycFailed     = kyc?.status === "failed";
    const kycProgress   = kyc && kyc.total_questions > 0
      ? Math.round((kyc.answered_count / kyc.total_questions) * 100)
      : 0;

    return (
      <div className="space-y-4">
        {/* Plan selector if multiple plans */}
        {data.plans.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            {data.plans.map((p) => (
              <button
                key={p.plan_id}
                onClick={() => setActivePlanId(p.plan_id)}
                className={`px-4 py-2 rounded-xl text-sm font-semibold border-2 transition-colors ${
                  activePlanId === p.plan_id
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
                    : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-indigo-300"
                }`}
              >
                {p.iso_code}
              </button>
            ))}
          </div>
        )}

        {/* KYC panel */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-br from-slate-800 to-indigo-900 px-6 py-5 flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center flex-shrink-0">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-white/60">ISO360 KYC</p>
              <h3 className="text-base font-bold text-white">Onboarding Questionnaire</h3>
            </div>
            <div className="ml-auto text-right">
              <p className="text-xs font-semibold text-white/70 uppercase tracking-wide">{activePlan.iso_code}</p>
              <p className="text-[10px] text-white/50">{activePlan.iso_name}</p>
            </div>
            {/* Per-plan language toggle */}
            <div className="flex items-center gap-1 ml-3">
              {(["en", "he"] as const).map((lang) => (
                <button
                  key={lang}
                  onClick={() => updatePlanLanguage(activePlan.plan_id, lang)}
                  disabled={langUpdating}
                  className={`text-xs px-2 py-0.5 rounded font-semibold border transition-colors ${
                    planLanguage === lang
                      ? "bg-white text-indigo-700 border-white"
                      : "bg-white/20 text-white/70 border-white/30 hover:bg-white/30"
                  }`}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="p-6 space-y-5">
            {/* Explanation */}
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              Before personalising the {activePlan.iso_code} activity schedule, generate a short
              onboarding questionnaire. The AI uses customer answers to tailor compliance steps,
              responsible roles, and evidence requirements to this customer's real environment.
            </p>

            {/* Status card */}
            {!kyc || !kyc.has_active_batch ? (
              /* Not started */
              <div className="flex flex-col items-center gap-4 py-6">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center">
                  <MessageSquare className="w-7 h-7 text-indigo-500" />
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">No questionnaire yet</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-xs">
                    AI will generate ~10 compliance questions tailored to this customer's industry and ISO standard.
                  </p>
                </div>
                {kycError && (
                  <p className="text-xs text-red-500 text-center">{kycError}</p>
                )}
                <button
                  onClick={() => triggerKyc(activePlan.plan_id)}
                  disabled={kycTriggering}
                  className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-50"
                >
                  {kycTriggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  Start KYC Questionnaire
                </button>
              </div>
            ) : kycGenerating ? (
              /* Generating */
              <div className="flex flex-col items-center gap-3 py-6">
                <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">AI is generating questions…</p>
                <p className="text-xs text-gray-400">This usually takes 10–20 seconds</p>
                <button onClick={() => loadKycStatus(activePlan.plan_id)} className="text-xs text-indigo-600 hover:underline flex items-center gap-1 mt-2">
                  <RefreshCw className="w-3 h-3" /> Refresh
                </button>
              </div>
            ) : kycCompleted ? (
              /* Completed / adjustment triggered */
              <div className="space-y-5">
                <div className="flex flex-col items-center gap-3 py-4">
                  <div className="w-12 h-12 rounded-2xl bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center">
                    <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                  </div>
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                    {kyc?.status === "adjustment_triggered" ? "Personalisation running…" : "All questions answered"}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 text-center max-w-xs">
                    {kyc?.status === "adjustment_triggered"
                      ? "The AI is now personalising activities. Reload the page in a few minutes."
                      : "Waiting for the AI to start the adjustment pass."}
                  </p>
                </div>

                {/* KYC Summary panel — shown once summary is generated */}
                {kyc?.kyc_summary && (
                  <div className="border border-indigo-100 dark:border-indigo-800 rounded-xl overflow-hidden">
                    <div className="bg-indigo-50 dark:bg-indigo-900/20 px-4 py-3 flex items-center gap-2">
                      <Shield className="w-4 h-4 text-indigo-500" />
                      <p className="text-xs font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-wide">
                        Customer Compliance Profile
                      </p>
                      {kyc.kyc_summary.compliance_maturity && (
                        <span className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-full ${
                          kyc.kyc_summary.compliance_maturity === "advanced"
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                            : kyc.kyc_summary.compliance_maturity === "intermediate"
                            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                            : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                        }`}>
                          {kyc.kyc_summary.compliance_maturity}
                        </span>
                      )}
                    </div>
                    <div className="p-4 grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs">
                      {/* Org profile */}
                      {kyc.kyc_summary.org_profile && (
                        <div>
                          <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">Organisation</p>
                          <div className="space-y-1 text-gray-700 dark:text-gray-300">
                            {kyc.kyc_summary.org_profile.industry && <p>🏢 {kyc.kyc_summary.org_profile.industry}</p>}
                            {kyc.kyc_summary.org_profile.size && <p>👥 {kyc.kyc_summary.org_profile.size}</p>}
                            {kyc.kyc_summary.org_profile.cloud?.length ? <p>☁️ {kyc.kyc_summary.org_profile.cloud.join(", ")}</p> : null}
                            {kyc.kyc_summary.org_profile.key_tools?.length ? <p>🔧 {kyc.kyc_summary.org_profile.key_tools.join(", ")}</p> : null}
                          </div>
                        </div>
                      )}
                      {/* Controls + gaps */}
                      <div className="space-y-3">
                        {kyc.kyc_summary.existing_controls?.length ? (
                          <div>
                            <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Existing Controls</p>
                            <ul className="space-y-0.5">
                              {kyc.kyc_summary.existing_controls.map((c, i) => (
                                <li key={i} className="text-emerald-700 dark:text-emerald-400">✅ {c}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {kyc.kyc_summary.identified_gaps?.length ? (
                          <div>
                            <p className="font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Identified Gaps</p>
                            <ul className="space-y-0.5">
                              {kyc.kyc_summary.identified_gaps.map((g, i) => (
                                <li key={i} className="text-amber-700 dark:text-amber-400">⚠️ {g}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )}

                {/* Mermaid compliance posture graph */}
                {kyc?.kyc_summary_graph && (
                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 dark:bg-gray-800/50 px-4 py-3">
                      <p className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                        Compliance Posture Diagram
                      </p>
                    </div>
                    <div className="p-4 bg-white dark:bg-gray-900">
                      <MermaidGraph chart={kyc.kyc_summary_graph} />
                    </div>
                  </div>
                )}
              </div>
            ) : kycFailed ? (
              /* Failed */
              <div className="flex flex-col items-center gap-3 py-6">
                <AlertCircle className="w-8 h-8 text-red-400" />
                <p className="text-sm font-semibold text-red-600 dark:text-red-400">Generation failed</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center">{kyc?.error_message}</p>
                <button
                  onClick={() => triggerKyc(activePlan.plan_id)}
                  disabled={kycTriggering}
                  className="flex items-center gap-2 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 text-sm font-semibold rounded-xl transition-colors disabled:opacity-50"
                >
                  {kycTriggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  Retry
                </button>
              </div>
            ) : kycPending ? (
              /* Pending — questions created, waiting for answers */
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                    Questionnaire sent — awaiting answers
                  </p>
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-2.5 py-1 rounded-lg">
                    {kyc.answered_count}/{kyc.total_questions} answered
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 transition-all duration-500"
                    style={{ width: `${kycProgress}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  The regular task scheduler will send these questions to the customer.
                  Once all are answered, personalisation starts automatically.
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  // ── Main view ─────────────────────────────────────────────────────────────
  const stats = activePlan!.stats;

  return (
    <div className="space-y-5">
      {/* Plan selector tabs (if multiple plans) */}
      {data.plans.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {data.plans.map((p) => (
            <button
              key={p.plan_id}
              onClick={() => { setActivePlanId(p.plan_id); setTypeFilter("all"); setFreqFilter("all"); setSearch(""); }}
              className={`px-4 py-2 rounded-xl text-sm font-semibold border-2 transition-colors ${
                activePlanId === p.plan_id
                  ? "border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                  : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-amber-300"
              }`}
            >
              {p.iso_code}
            </button>
          ))}
        </div>
      )}

      {/* ── Hero / Status Header ─────────────────────────────────────────── */}
      <div className="bg-gradient-to-br from-slate-800 to-indigo-900 rounded-2xl p-5 text-white shadow-lg">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-widest text-white/70">
                  ISO360 ACTIVE
                </span>
                <span className="w-2 h-2 bg-green-300 rounded-full animate-pulse" />
              </div>
              <p className="text-white/80 text-sm mt-0.5">Year-round compliance management</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs font-semibold text-white/70 uppercase tracking-wide">
              {activePlan!.iso_code}
            </p>
            <p className="text-xs text-white/60">{activePlan!.iso_name}</p>
          </div>
        </div>

        {/* Stats chips */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Activities", value: stats.total, icon: ClipboardList, accent: "bg-white/20" },
            { label: "Due Soon", value: stats.due_soon, icon: Clock, accent: stats.due_soon > 0 ? "bg-yellow-300/30" : "bg-white/20" },
            { label: "Overdue", value: stats.overdue, icon: AlertCircle, accent: stats.overdue > 0 ? "bg-red-300/30" : "bg-white/20" },
            { label: "Done This Year", value: stats.completed_this_year, icon: CheckCircle2, accent: "bg-green-300/20" },
          ].map(({ label, value, icon: Icon, accent }) => (
            <div key={label} className={`${accent} rounded-xl p-3 text-center`}>
              <Icon className="w-4 h-4 mx-auto mb-1 text-white/80" />
              <p className="text-xl font-bold text-white">{value}</p>
              <p className="text-xs text-white/70">{label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Attention Strip ──────────────────────────────────────────────── */}
      {attentionActivities.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-amber-500" />
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">
              Requires Attention
            </h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 font-medium">
              {attentionActivities.length}
            </span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {attentionActivities.map((a) => (
              <button
                key={a.doc_id}
                onClick={() => setSelectedActivity(a)}
                className={`flex-shrink-0 w-64 rounded-xl border-2 p-3 text-left hover:shadow-md transition-shadow ${getAttentionCardBorder(a.completion_status)}`}
              >
                <div className="flex items-start justify-between mb-1.5">
                  <span className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                    a.completion_status === "overdue"
                      ? "bg-red-200 text-red-700 dark:bg-red-800/50 dark:text-red-300"
                      : "bg-amber-200 text-amber-700 dark:bg-amber-800/50 dark:text-amber-300"
                  }`}>
                    {a.completion_status === "overdue" ? "OVERDUE" : "DUE THIS MONTH"}
                  </span>
                  <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                </div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white line-clamp-2 leading-snug mb-2">
                  {a.title}
                </p>
                <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                  <span>{getFreqLabel(a.update_frequency)}</span>
                  {a.iso_clause && (
                    <>
                      <span>·</span>
                      <span>{a.iso_clause}</span>
                    </>
                  )}
                </div>
                {a.next_due_date && (
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mt-1">
                    Due: {formatDateShort(a.next_due_date)}
                  </p>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Full Activity List ────────────────────────────────────────────── */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        {/* List header + filters */}
        <div className="p-4 border-b border-gray-100 dark:border-gray-700">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              All Activities
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 font-medium">
                {filteredActivities.length}
              </span>
            </h3>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search…"
                  className="pl-8 pr-3 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-amber-500 focus:outline-none w-36"
                />
              </div>
              {/* Type filter */}
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-amber-500 focus:outline-none"
              >
                <option value="all">All Types</option>
                <option value="review">Review</option>
                <option value="operational_activity">Operations</option>
                <option value="record">Record</option>
              </select>
              {/* Frequency filter */}
              <select
                value={freqFilter}
                onChange={(e) => setFreqFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-amber-500 focus:outline-none"
              >
                <option value="all">All Frequencies</option>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="yearly">Yearly</option>
                <option value="event_based">Event-based</option>
              </select>
              {(typeFilter !== "all" || freqFilter !== "all" || search) && (
                <button
                  onClick={() => { setTypeFilter("all"); setFreqFilter("all"); setSearch(""); }}
                  className="text-xs text-amber-600 hover:underline"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Table header */}
        <div className="grid grid-cols-[2fr_3fr_1fr_1.5fr_7rem] gap-0 px-4 py-2 bg-gray-50 dark:bg-gray-700/50 text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
          <span>Type</span>
          <span>Activity</span>
          <span>Frequency</span>
          <span>Next Due</span>
          <span>Action</span>
        </div>

        {/* Rows */}
        {filteredActivities.length === 0 ? (
          <div className="text-center py-12 text-gray-400 dark:text-gray-500">
            <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No activities match the current filters.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {filteredActivities.map((a) => {
              const isExcluded = a.doc_id in excludedMap ? excludedMap[a.doc_id] : a.excluded;
              return (
              <div
                key={a.doc_id}
                className={`w-full grid grid-cols-[2fr_3fr_1fr_1.5fr_7rem] gap-0 px-4 py-3 hover:bg-amber-50/50 dark:hover:bg-amber-900/10 transition-colors group ${getRowBorder(isExcluded ? "" : a.completion_status)} ${isExcluded ? "opacity-40" : ""}`}
              >
                {/* Type */}
                <div
                  className="flex items-center gap-2 min-w-0 pr-2 cursor-pointer"
                  onClick={() => setSelectedActivity(a)}
                >
                  {getTypeIcon(a.type)}
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-lg ${getTypeColor(a.type)}`}>
                    {getTypeLabel(a.type)}
                  </span>
                </div>

                {/* Title */}
                <div
                  className="flex items-center min-w-0 pr-2 cursor-pointer"
                  onClick={() => setSelectedActivity(a)}
                >
                  <span className="text-sm font-medium text-gray-900 dark:text-white truncate group-hover:text-amber-700 dark:group-hover:text-amber-300 transition-colors">
                    {a.title}
                  </span>
                  {a.iso_clause && (
                    <span className="ml-2 text-[10px] text-gray-400 dark:text-gray-500 flex-shrink-0">
                      {a.iso_clause}
                    </span>
                  )}
                </div>

                {/* Frequency */}
                <div
                  className="flex items-center cursor-pointer"
                  onClick={() => setSelectedActivity(a)}
                >
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-lg ${getFreqBadge(a.update_frequency)}`}>
                    {getFreqLabel(a.update_frequency)}
                  </span>
                </div>

                {/* Next due */}
                <div
                  className="flex items-center gap-1.5 cursor-pointer"
                  onClick={() => setSelectedActivity(a)}
                >
                  {a.completion_status === "event_based" ? (
                    <span className="text-xs text-gray-400 dark:text-gray-500 italic">on-demand</span>
                  ) : a.completion_status === "completed" ? (
                    <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Done
                    </span>
                  ) : (
                    <span className={`text-xs font-medium ${
                      a.completion_status === "overdue"
                        ? "text-red-600 dark:text-red-400"
                        : a.completion_status === "due_soon"
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-gray-500 dark:text-gray-400"
                    }`}>
                      {formatDateShort(a.next_due_date)}
                    </span>
                  )}
                  <ChevronRight className="w-3.5 h-3.5 text-gray-300 dark:text-gray-600 group-hover:text-amber-400 transition-colors ml-auto" />
                </div>

                {/* Action — Trigger (event_based) + Complete + Exclude toggle */}
                <div className="flex items-center gap-2 pl-1">
                  {a.update_frequency === "event_based" && (
                    triggerMsg?.docId === a.doc_id ? (
                      <span className={`text-[11px] font-medium ${
                        triggerMsg.ok
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-red-500 dark:text-red-400"
                      }`}>
                        {triggerMsg.text}
                      </span>
                    ) : (
                      <button
                        onClick={() => triggerActivity(a.doc_id, a.title)}
                        disabled={triggering === a.doc_id || isExcluded}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-xs font-semibold transition-colors shadow-sm"
                      >
                        {triggering === a.doc_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Zap className="w-3.5 h-3.5" />
                        )}
                        Trigger
                      </button>
                    )
                  )}
                  {a.completion_status !== "completed" && a.update_frequency !== "event_based" && (
                    <button
                      onClick={() => handleMarkComplete(a.doc_id)}
                      disabled={completingDoc === a.doc_id}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                      title="Mark as complete"
                      style={{ background: "rgba(16,185,129,0.1)", color: "#10b981", border: "1px solid rgba(16,185,129,0.25)" }}>
                      {completingDoc === a.doc_id
                        ? <Loader2 size={11} className="animate-spin" />
                        : <CheckCircle2 size={11} />
                      }
                      Complete
                    </button>
                  )}
                  <button
                    title={isExcluded ? "Re-enable activity" : "Exclude activity"}
                    onClick={() => toggleExclude(a)}
                    className={`p-1.5 rounded-lg transition-colors ${
                      isExcluded
                        ? "text-red-400 hover:text-red-600 bg-red-50 dark:bg-red-900/20"
                        : "text-gray-300 hover:text-gray-500 dark:text-gray-600 dark:hover:text-gray-400"
                    }`}
                  >
                    {isExcluded ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Activity Detail Modal ─────────────────────────────────────────── */}
      {selectedActivity && (
        <ActivityDetailModal
          activity={selectedActivity}
          onClose={() => setSelectedActivity(null)}
        />
      )}
    </div>
  );
}
