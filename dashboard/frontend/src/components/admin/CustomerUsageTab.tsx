"use client";

import { useEffect, useState } from "react";
import { Loader2, Zap, TrendingUp, DollarSign, Activity, Pencil, Check, X } from "lucide-react";
import api from "@/lib/api";

const OP_LABEL: Record<string, string> = {
  iso_build:        "Document Generation",
  portal_chat:      "Portal Chat",
  portal_help:      "Help Me Answer",
  email_extraction: "Email Extraction",
  template_parse:   "Template Parse",
};
const OP_COLOR: Record<string, string> = {
  iso_build:        "bg-blue-100 text-blue-700",
  portal_chat:      "bg-violet-100 text-violet-700",
  portal_help:      "bg-amber-100 text-amber-700",
  email_extraction: "bg-emerald-100 text-emerald-700",
  template_parse:   "bg-slate-100 text-slate-600",
};

function fmt(n: number, d = 0) {
  return n.toLocaleString(undefined, { maximumFractionDigits: d });
}

interface UsageData {
  budget: number | null;
  budget_used_pct: number | null;
  this_month: { cost_usd: number; tokens_in: number; tokens_out: number; calls: number };
  all_time:   { cost_usd: number; tokens_in: number; tokens_out: number; calls: number };
  breakdown: { operation_type: string; provider: string; model: string; calls: number; tokens_input: number; tokens_output: number; cost_usd: number }[];
  recent: { operation_type: string; provider: string; model: string; tokens_input: number; tokens_output: number; cost_usd: number; started_at: string }[];
}

export default function CustomerUsageTab({ customerId }: { customerId: number }) {
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [editBudget, setEditBudget] = useState(false);
  const [budgetInput, setBudgetInput] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data: res } = await api.get(`/api/v1/iso-customers/${customerId}/usage`);
      setData(res);
      setBudgetInput(res.budget != null ? String(res.budget) : "");
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [customerId]);

  const saveBudget = async () => {
    setSaving(true);
    try {
      const val = budgetInput.trim() === "" ? null : parseFloat(budgetInput);
      await api.put(`/api/v1/iso-customers/${customerId}/budget`, { monthly_llm_budget_usd: val });
      setEditBudget(false);
      await load();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
    </div>
  );

  if (!data) return (
    <div className="text-center py-16 text-gray-400 text-sm">Failed to load usage data.</div>
  );

  const usedPct = data.budget_used_pct ?? 0;
  const barColor = usedPct >= 90 ? "bg-red-500" : usedPct >= 70 ? "bg-amber-500" : "bg-emerald-500";

  return (
    <div className="space-y-6 p-1">

      {/* ── Budget + this-month summary ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Budget card */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                <DollarSign className="w-4 h-4 text-white" />
              </div>
              <p className="text-sm font-semibold text-gray-900">Monthly Budget</p>
            </div>
            {!editBudget && (
              <button onClick={() => setEditBudget(true)}
                className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
                <Pencil className="w-3 h-3" /> Edit
              </button>
            )}
          </div>

          {editBudget ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">$</span>
              <input type="number" min="0" step="1" value={budgetInput}
                onChange={e => setBudgetInput(e.target.value)}
                placeholder="e.g. 10.00  (blank = no limit)"
                className="flex-1 px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500" />
              <button onClick={saveBudget} disabled={saving}
                className="p-1.5 rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50">
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              </button>
              <button onClick={() => setEditBudget(false)}
                className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <p className="text-2xl font-bold text-gray-900">
              {data.budget != null ? `$${data.budget.toFixed(2)}` : <span className="text-gray-400 text-lg">No limit</span>}
            </p>
          )}

          {data.budget != null && (
            <>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>${data.this_month.cost_usd.toFixed(4)} used</span>
                <span>{usedPct}%</span>
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${barColor}`}
                  style={{ width: `${Math.min(usedPct, 100)}%` }} />
              </div>
              {usedPct >= 90 && (
                <p className="text-xs text-red-600 font-medium">⚠ Approaching budget limit</p>
              )}
            </>
          )}
        </div>

        {/* This month summary */}
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Calls this month", value: fmt(data.this_month.calls), icon: Activity, color: "from-blue-500 to-cyan-500" },
            { label: "Cost this month",  value: `$${data.this_month.cost_usd.toFixed(4)}`, icon: DollarSign, color: "from-violet-500 to-purple-600" },
            { label: "Tokens in",        value: fmt(data.this_month.tokens_in),  icon: Zap,        color: "from-amber-400 to-orange-500" },
            { label: "Tokens out",       value: fmt(data.this_month.tokens_out), icon: TrendingUp, color: "from-emerald-400 to-teal-500" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white border border-gray-200 rounded-xl p-3.5">
              <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center mb-2`}>
                <Icon className="w-3.5 h-3.5 text-white" />
              </div>
              <p className="text-xs text-gray-400 mb-0.5">{label}</p>
              <p className="text-lg font-bold text-gray-900 tabular-nums">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── All-time totals ── */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl px-5 py-3 flex flex-wrap gap-6 text-sm">
        <span className="text-gray-400 font-medium text-xs uppercase tracking-wide self-center">All time</span>
        <span><span className="font-semibold text-gray-900">{fmt(data.all_time.calls)}</span> <span className="text-gray-400">calls</span></span>
        <span><span className="font-semibold text-gray-900">${data.all_time.cost_usd.toFixed(4)}</span> <span className="text-gray-400">total cost</span></span>
        <span><span className="font-semibold text-gray-900">{fmt(data.all_time.tokens_in + data.all_time.tokens_out)}</span> <span className="text-gray-400">total tokens</span></span>
      </div>

      {/* ── This-month breakdown ── */}
      {data.breakdown.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">This Month — by Operation</p>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100 text-left">
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Operation</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Provider / Model</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right">Calls</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right">Tokens</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {data.breakdown.map((row, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${OP_COLOR[row.operation_type] ?? "bg-gray-100 text-gray-600"}`}>
                        {OP_LABEL[row.operation_type] ?? row.operation_type}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="capitalize text-gray-700">{row.provider}</span>
                      <span className="text-gray-400 text-xs ml-1">/ {row.model}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">{fmt(row.calls)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-gray-400 text-xs">{fmt(row.tokens_input + row.tokens_output)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-gray-900">${row.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Recent calls ── */}
      {data.recent.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Recent Calls</p>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100 text-left">
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">When</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Operation</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Provider</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right">Tokens</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {data.recent.map((r, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2 text-xs text-gray-400 tabular-nums whitespace-nowrap">
                      {new Date(r.started_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${OP_COLOR[r.operation_type] ?? "bg-gray-100 text-gray-600"}`}>
                        {OP_LABEL[r.operation_type] ?? r.operation_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 capitalize">{r.provider}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-xs text-gray-400">{fmt(r.tokens_input + r.tokens_output)}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-xs font-medium text-gray-900">${r.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.breakdown.length === 0 && data.recent.length === 0 && (
        <div className="text-center py-12 text-gray-400 text-sm">
          No AI usage recorded for this customer yet.
        </div>
      )}
    </div>
  );
}
