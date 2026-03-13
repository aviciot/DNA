"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Shield, AlertCircle, Clock, CheckCircle2, Loader2,
  ArrowUpRight, RefreshCw, Zap, Search, TrendingUp,
} from "lucide-react";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PlanHealth {
  plan_id: string;
  customer_id: number;
  customer_name: string;
  iso_code: string;
  iso_name: string;
  adjustment_pass_done: boolean;
  total: number;
  on_track: number;
  overdue: number;
  due_soon: number;
  completed_this_year: number;
  event_based: number;
  last_activity_at: string | null;
}

interface HealthResponse {
  plans: PlanHealth[];
  as_of: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function ProgressRing({ value, total, size = 40 }: { value: number; total: number; size?: number }) {
  if (total === 0) return <span className="text-xs text-gray-400">—</span>;
  const pct = Math.round((value / total) * 100);
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const color = pct >= 90 ? "#10b981" : pct >= 70 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={5} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <span className="text-sm font-bold tabular-nums" style={{ color }}>
        {value}/{total}
      </span>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ISO360HealthDashboard() {
  const router = useRouter();
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"customer" | "overdue" | "on_track">("overdue");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/api/v1/iso360/health");
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load ISO360 health data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const plans = useMemo(() => {
    if (!data) return [];
    let list = data.plans;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(p =>
        p.customer_name.toLowerCase().includes(q) ||
        p.iso_code.toLowerCase().includes(q)
      );
    }
    return [...list].sort((a, b) => {
      if (sortBy === "overdue")   return b.overdue - a.overdue;
      if (sortBy === "on_track")  return (b.on_track / Math.max(b.total, 1)) - (a.on_track / Math.max(a.total, 1));
      return a.customer_name.localeCompare(b.customer_name);
    });
  }, [data, search, sortBy]);

  // Summary stats
  const summary = useMemo(() => {
    if (!data) return { customers: 0, plans: 0, totalOverdue: 0, totalDueSoon: 0, avgHealth: 0 };
    const customerIds = new Set(data.plans.map(p => p.customer_id));
    const totalOverdue = data.plans.reduce((s, p) => s + p.overdue, 0);
    const totalDueSoon = data.plans.reduce((s, p) => s + p.due_soon, 0);
    const totalActivities = data.plans.reduce((s, p) => s + p.total, 0);
    const totalOnTrack = data.plans.reduce((s, p) => s + p.on_track, 0);
    const avgHealth = totalActivities > 0 ? Math.round((totalOnTrack / totalActivities) * 100) : 0;
    return { customers: customerIds.size, plans: data.plans.length, totalOverdue, totalDueSoon, avgHealth };
  }, [data]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading ISO360 health data…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{error}</p>
        <button onClick={load} className="text-xs text-indigo-600 hover:underline">Retry</button>
      </div>
    );
  }

  if (!data || data.plans.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <Shield className="w-12 h-12 text-gray-300 dark:text-gray-600" />
        <p className="text-base font-semibold text-gray-600 dark:text-gray-400">No ISO360 plans enabled</p>
        <p className="text-sm text-gray-400">Enable ISO360 on a customer plan to see health data here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Hero */}
      <div className="bg-gradient-to-br from-slate-800 to-indigo-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold">ISO360 Health Dashboard</h2>
              <p className="text-xs text-white/60">As of {formatDate(data.as_of)}</p>
            </div>
          </div>
          <button onClick={load} className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors">
            <RefreshCw className="w-4 h-4 text-white" />
          </button>
        </div>

        {/* Summary chips */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-white/10 rounded-xl px-4 py-3 text-center">
            <p className="text-2xl font-bold">{summary.customers}</p>
            <p className="text-xs text-white/60 mt-0.5">Customers</p>
          </div>
          <div className="bg-white/10 rounded-xl px-4 py-3 text-center">
            <p className="text-2xl font-bold">{summary.plans}</p>
            <p className="text-xs text-white/60 mt-0.5">Active Plans</p>
          </div>
          <div className={`rounded-xl px-4 py-3 text-center ${summary.totalOverdue > 0 ? "bg-red-500/30" : "bg-white/10"}`}>
            <p className="text-2xl font-bold">{summary.totalOverdue}</p>
            <p className="text-xs text-white/60 mt-0.5">Overdue</p>
          </div>
          <div className={`rounded-xl px-4 py-3 text-center ${summary.totalDueSoon > 0 ? "bg-amber-500/20" : "bg-white/10"}`}>
            <p className="text-2xl font-bold">{summary.totalDueSoon}</p>
            <p className="text-xs text-white/60 mt-0.5">Due Soon</p>
          </div>
          <div className={`rounded-xl px-4 py-3 text-center ${summary.avgHealth >= 90 ? "bg-emerald-500/20" : summary.avgHealth >= 70 ? "bg-amber-500/20" : "bg-red-500/20"}`}>
            <p className="text-2xl font-bold">{summary.avgHealth}%</p>
            <p className="text-xs text-white/60 mt-0.5">Avg Health</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-48 border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-2 bg-white dark:bg-gray-800">
          <Search className="w-4 h-4 text-gray-400 flex-shrink-0" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search customer or ISO standard…"
            className="flex-1 bg-transparent text-sm text-gray-900 dark:text-white placeholder:text-gray-400 outline-none"
          />
        </div>
        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-xl p-1">
          {(["overdue", "on_track", "customer"] as const).map(s => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                sortBy === s
                  ? "bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {s === "overdue" ? "Most Overdue" : s === "on_track" ? "Health" : "Customer"}
            </button>
          ))}
        </div>
        <span className="text-xs text-gray-400">{plans.length} plan{plans.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[2fr_1.5fr_1fr_1fr_1fr_1fr_1.2fr_auto] gap-0 px-5 py-3 bg-gray-50 dark:bg-gray-700/50 text-[10px] font-bold uppercase tracking-widest text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
          <span>Customer</span>
          <span>Standard</span>
          <span>On Track</span>
          <span>Overdue</span>
          <span>Due Soon</span>
          <span>Done This Year</span>
          <span>Last Activity</span>
          <span></span>
        </div>

        <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
          {plans.map(plan => {
            const healthPct = plan.total > 0 ? Math.round((plan.on_track / plan.total) * 100) : 100;
            const isHealthy = plan.overdue === 0 && healthPct >= 90;
            const needsAttention = plan.overdue > 0;

            return (
              <div
                key={plan.plan_id}
                className={`grid grid-cols-[2fr_1.5fr_1fr_1fr_1fr_1fr_1.2fr_auto] gap-0 px-5 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors items-center ${
                  needsAttention ? "border-l-4 border-l-red-400" : "border-l-4 border-l-transparent"
                }`}
              >
                {/* Customer */}
                <div className="min-w-0 pr-3">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{plan.customer_name}</p>
                  {!plan.adjustment_pass_done && (
                    <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                      Not personalized
                    </span>
                  )}
                  {plan.adjustment_pass_done && (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-0.5">
                      <CheckCircle2 className="w-3 h-3" /> Personalized
                    </span>
                  )}
                </div>

                {/* Standard */}
                <div className="flex items-center gap-2 pr-3">
                  <Shield className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{plan.iso_code}</p>
                    <p className="text-[10px] text-gray-400 truncate">{plan.iso_name}</p>
                  </div>
                </div>

                {/* On Track */}
                <div>
                  <ProgressRing value={plan.on_track} total={plan.total} size={40} />
                </div>

                {/* Overdue */}
                <div>
                  {plan.overdue > 0 ? (
                    <span className="flex items-center gap-1 text-sm font-bold text-red-600 dark:text-red-400">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {plan.overdue}
                    </span>
                  ) : (
                    <span className="text-sm text-gray-400">—</span>
                  )}
                </div>

                {/* Due Soon */}
                <div>
                  {plan.due_soon > 0 ? (
                    <span className="flex items-center gap-1 text-sm font-semibold text-amber-600 dark:text-amber-400">
                      <Clock className="w-3.5 h-3.5" />
                      {plan.due_soon}
                    </span>
                  ) : (
                    <span className="text-sm text-gray-400">—</span>
                  )}
                </div>

                {/* Completed this year */}
                <div>
                  {plan.completed_this_year > 0 ? (
                    <span className="flex items-center gap-1 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {plan.completed_this_year}
                    </span>
                  ) : (
                    <span className="text-sm text-gray-400">0</span>
                  )}
                </div>

                {/* Last Activity */}
                <div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {formatDate(plan.last_activity_at)}
                  </span>
                </div>

                {/* Link to customer */}
                <div>
                  <button
                    onClick={() => window.open(`/customers/${plan.customer_id}?tab=iso360`, "_blank")}
                    className="p-2 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
                    title="Open customer ISO360 tab"
                  >
                    <ArrowUpRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-gray-400 dark:text-gray-500 px-1">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />≥90% on track</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />70–89%</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-red-500 inline-block" />&lt;70%</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 border-l-4 border-red-400 inline-block" />Row has overdue items</span>
      </div>
    </div>
  );
}
