"use client";

import { useEffect, useState } from "react";
import {
  Loader2, Save, Eye, EyeOff, CheckCircle2, XCircle,
  FlaskConical, RefreshCw, KeyRound, Cpu, Plus, X, BarChart2,
} from "lucide-react";
import api from "@/lib/api";

interface LLMProvider {
  name: string;
  display_name: string;
  enabled: boolean;
  has_key: boolean;
  key_source: "db" | "env" | null;
  available_models: string[];
  cost_per_1k_input: number | null;
  cost_per_1k_output: number | null;
}

const PROVIDER_META: Record<string, { color: string; letter: string }> = {
  gemini:  { color: "from-blue-400 to-cyan-500",     letter: "G" },
  claude:  { color: "from-orange-400 to-amber-500",  letter: "C" },
  groq:    { color: "from-emerald-400 to-teal-500",  letter: "Q" },
  openai:  { color: "from-violet-400 to-purple-500", letter: "O" },
};

function KeyStatusBadge({ source }: { source: "db" | "env" | null }) {
  if (source === "db" || source === "env") {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700">
        <CheckCircle2 className="w-3 h-3" /> Key in DB
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700">
      ⚠ No key configured
    </span>
  );
}

function ProviderCard({ provider, onRefresh }: { provider: LLMProvider; onRefresh: () => void }) {
  const meta = PROVIDER_META[provider.name] || { color: "from-slate-400 to-slate-500", letter: "?" };

  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [enabled, setEnabled] = useState(provider.enabled);
  const [models, setModels] = useState<string[]>(provider.available_models);
  const [newModel, setNewModel] = useState("");
  const [costIn, setCostIn] = useState(provider.cost_per_1k_input?.toString() ?? "");
  const [costOut, setCostOut] = useState(provider.cost_per_1k_output?.toString() ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const isDirty =
    apiKey !== "" ||
    enabled !== provider.enabled ||
    JSON.stringify(models) !== JSON.stringify(provider.available_models) ||
    costIn !== (provider.cost_per_1k_input?.toString() ?? "") ||
    costOut !== (provider.cost_per_1k_output?.toString() ?? "");

  const addModel = () => {
    const trimmed = newModel.trim();
    if (trimmed && !models.includes(trimmed)) {
      setModels(m => [...m, trimmed]);
    }
    setNewModel("");
  };

  const removeModel = (m: string) => setModels(prev => prev.filter(x => x !== m));

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = { enabled, available_models: models };
      if (apiKey && apiKey !== "••••••••") payload.api_key = apiKey;
      if (costIn !== "") payload.cost_per_1k_input = parseFloat(costIn);
      if (costOut !== "") payload.cost_per_1k_output = parseFloat(costOut);
      await api.put(`/api/v1/admin/llm-providers/${provider.name}`, payload);
      setSaved(true);
      setApiKey("");
      setTimeout(() => { setSaved(false); onRefresh(); }, 2000);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await api.post(`/api/v1/admin/llm-providers/${provider.name}/test`);
      setTestResult(data);
    } catch (e: any) {
      setTestResult({ ok: false, message: e?.response?.data?.detail || "Request failed" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className={`bg-white border rounded-xl p-5 space-y-4 ${enabled ? "border-slate-200" : "border-slate-100 opacity-60"}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center text-white font-bold text-sm shadow`}>
            {meta.letter}
          </div>
          <div className="space-y-1">
            <p className="font-semibold text-slate-900 text-sm leading-none">{provider.display_name}</p>
            <KeyStatusBadge source={provider.key_source} />
          </div>
        </div>
        <button
          onClick={() => setEnabled(e => !e)}
          className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${enabled ? "bg-emerald-500" : "bg-slate-300"}`}
          title={enabled ? "Disable provider" : "Enable provider"}
        >
          <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${enabled ? "left-5" : "left-0.5"}`} />
        </button>
      </div>

      {/* Available Models */}
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide">Available Models</label>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {models.map(m => (
            <span key={m} className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded-lg">
              {m}
              <button onClick={() => removeModel(m)} className="text-slate-400 hover:text-red-500 transition-colors">
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
          {models.length === 0 && <span className="text-xs text-slate-400 italic">No models listed</span>}
        </div>
        <div className="flex gap-1.5">
          <input
            value={newModel}
            onChange={e => setNewModel(e.target.value)}
            onKeyDown={e => e.key === "Enter" && addModel()}
            placeholder="Add model ID…"
            className="flex-1 px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={addModel}
            disabled={!newModel.trim()}
            className="px-2.5 py-1.5 text-xs bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg disabled:opacity-40 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Cost rates */}
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide">Cost per 1K Tokens (USD)</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Input</label>
            <input
              type="number" step="0.0001" min="0"
              value={costIn}
              onChange={e => setCostIn(e.target.value)}
              placeholder="e.g. 0.0030"
              className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Output</label>
            <input
              type="number" step="0.0001" min="0"
              value={costOut}
              onChange={e => setCostOut(e.target.value)}
              placeholder="e.g. 0.0150"
              className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-1">Used to calculate cost in usage reports.</p>
      </div>

      {/* API Key override */}
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1 uppercase tracking-wide flex items-center gap-1">
          <KeyRound className="w-3 h-3" /> Override API Key
        </label>
        <div className="relative">
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder={
              provider.key_source === "db"
                ? "Leave blank to keep existing key"
                : "Paste API key to store in DB…"
            }
            className="w-full px-3 py-2 pr-9 text-sm border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-slate-400"
          />
          <button onClick={() => setShowKey(v => !v)} className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600">
            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-1">Key is stored encrypted in the database.</p>
      </div>

      {/* Test result */}
      {testResult && (
        <div className={`flex items-start gap-2 text-xs px-3 py-2 rounded-lg ${testResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
          {testResult.ok
            ? <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            : <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />}
          {testResult.message}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleSave}
          disabled={saving || !isDirty}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-40"
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : saved ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
          {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
        <button
          onClick={handleTest}
          disabled={testing || !provider.has_key}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-lg transition-colors disabled:opacity-40"
          title={!provider.has_key ? "Configure a key first" : "Test API connectivity"}
        >
          {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FlaskConical className="w-3.5 h-3.5" />}
          {testing ? "Testing…" : "Test"}
        </button>
      </div>
    </div>
  );
}

// ── Operation type labels ────────────────────────────────────────────────────

const OP_LABEL: Record<string, string> = {
  iso_build:       "Document Generation",
  portal_chat:     "Portal Chat",
  portal_help:     "Help Me Answer",
  email_extraction:"Email Extraction",
  template_parse:  "Template Parse",
};

const OP_COLOR: Record<string, string> = {
  iso_build:       "bg-blue-100 text-blue-700",
  portal_chat:     "bg-violet-100 text-violet-700",
  portal_help:     "bg-amber-100 text-amber-700",
  email_extraction:"bg-emerald-100 text-emerald-700",
  template_parse:  "bg-slate-100 text-slate-600",
};

function fmt(n: number, decimals = 0) {
  return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

interface UsageRow {
  provider: string; model: string; operation_type: string;
  calls: number; tokens_input: number; tokens_output: number;
  tokens_total: number; cost_usd: number;
}
interface UsageData {
  period_days: number;
  rows: UsageRow[];
  totals: { calls: number; tokens_input: number; tokens_output: number; cost_usd: number };
}

function UsageTab() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async (d: number) => {
    setLoading(true);
    try {
      const { data: res } = await api.get(`/api/v1/admin/llm-providers/usage?days=${d}`);
      setData(res);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(days); }, []);

  const handleDays = (d: number) => { setDays(d); load(d); };

  // Group rows by provider for display
  const byProvider: Record<string, UsageRow[]> = {};
  for (const row of data?.rows ?? []) {
    if (!byProvider[row.provider]) byProvider[row.provider] = [];
    byProvider[row.provider].push(row);
  }

  return (
    <div className="space-y-5">
      {/* Period selector */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">Usage by provider, model, and operation type</p>
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
          {[{ label: "7d", v: 7 }, { label: "30d", v: 30 }, { label: "90d", v: 90 }, { label: "All", v: 0 }].map(({ label, v }) => (
            <button key={v} onClick={() => handleDays(v)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${days === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      ) : !data || data.rows.length === 0 ? (
        <div className="text-center py-16 text-slate-400 text-sm">
          No usage recorded{days > 0 ? ` in the last ${days} days` : ""}. Usage is logged automatically once LLM calls are made.
        </div>
      ) : (
        <>
          {/* Totals bar */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Total Calls", value: fmt(data.totals.calls) },
              { label: "Tokens In", value: fmt(data.totals.tokens_input) },
              { label: "Tokens Out", value: fmt(data.totals.tokens_output) },
              { label: "Total Cost", value: `$${Number(data.totals.cost_usd).toFixed(4)}` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white border border-slate-200 rounded-xl p-4">
                <p className="text-xs text-slate-400 mb-1">{label}</p>
                <p className="text-xl font-bold text-slate-900">{value}</p>
              </div>
            ))}
          </div>

          {/* Table */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Provider / Model</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Operation</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Calls</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Tokens In</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Tokens Out</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide text-right">Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(byProvider).map(([provider, rows]) => (
                  rows.map((row, i) => {
                    const meta = PROVIDER_META[provider] || { color: "from-slate-400 to-slate-500", letter: "?" };
                    const opLabel = OP_LABEL[row.operation_type] || row.operation_type;
                    const opColor = OP_COLOR[row.operation_type] || "bg-slate-100 text-slate-600";
                    return (
                      <tr key={`${provider}-${row.model}-${row.operation_type}`}
                        className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3">
                          {i === 0 && (
                            <div className="flex items-center gap-2">
                              <div className={`w-6 h-6 rounded-lg bg-gradient-to-br ${meta.color} flex items-center justify-center text-white font-bold text-xs`}>
                                {meta.letter}
                              </div>
                              <div>
                                <p className="font-medium text-slate-900 capitalize">{provider}</p>
                                <p className="text-xs text-slate-400">{row.model}</p>
                              </div>
                            </div>
                          )}
                          {i > 0 && (
                            <p className="text-xs text-slate-400 pl-8">{row.model}</p>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${opColor}`}>{opLabel}</span>
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700 tabular-nums">{fmt(row.calls)}</td>
                        <td className="px-4 py-3 text-right text-slate-500 tabular-nums text-xs">{fmt(row.tokens_input)}</td>
                        <td className="px-4 py-3 text-right text-slate-500 tabular-nums text-xs">{fmt(row.tokens_output)}</td>
                        <td className="px-4 py-3 text-right font-semibold text-slate-900 tabular-nums">
                          ${Number(row.cost_usd).toFixed(4)}
                        </td>
                      </tr>
                    );
                  })
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-50 border-t-2 border-slate-200">
                  <td className="px-4 py-3 font-semibold text-slate-700" colSpan={2}>Total</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-700 tabular-nums">{fmt(data.totals.calls)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-500 tabular-nums text-xs">{fmt(data.totals.tokens_input)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-500 tabular-nums text-xs">{fmt(data.totals.tokens_output)}</td>
                  <td className="px-4 py-3 text-right font-bold text-slate-900 tabular-nums">${Number(data.totals.cost_usd).toFixed(4)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  );
}


// ── Main component ───────────────────────────────────────────────────────────

export default function LLMProvidersConfig() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"providers" | "usage">("providers");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/v1/admin/llm-providers");
      setProviders(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const configuredCount = providers.filter(p => p.has_key).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">AI Providers</h3>
            <p className="text-sm text-slate-500">
              {configuredCount} of {providers.length} providers have a key configured
            </p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {[
          { id: "providers", label: "Providers", icon: <Cpu className="w-3.5 h-3.5" /> },
          { id: "usage",     label: "Usage & Cost", icon: <BarChart2 className="w-3.5 h-3.5" /> },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id as any)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "providers" ? (
        loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-7 h-7 animate-spin text-slate-400" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {providers.map(p => (
              <ProviderCard key={p.name} provider={p} onRefresh={load} />
            ))}
          </div>
        )
      ) : (
        <UsageTab />
      )}
    </div>
  );
}
