"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Cpu, Zap, Save, X, Check, Loader2, AlertTriangle,
  CheckCircle, Info, RefreshCw, Sliders, ChevronDown, ChevronUp, Edit3,
} from "lucide-react";

import api from "@/lib/api";

interface ProviderInfo {
  provider: string;
  gemini_model: string;
  anthropic_model: string;
  groq_model: string;
  has_gemini_key: boolean;
  has_anthropic_key: boolean;
  has_groq_key: boolean;
  worker_concurrency: number;
  max_cost_per_task_usd: number;
}

interface PromptRow {
  id: string;
  prompt_key: string;
  description: string | null;
  model: string;
  max_tokens: number;
  temperature: number;
  is_active: boolean;
  prompt_text: string;
  updated_at: string;
}

// Best models per provider — chosen for large context + best value
const PROVIDER_MODELS: Record<string, { value: string; label: string; note: string }[]> = {
  gemini: [
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash", note: "Best value · 1M ctx" },
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro", note: "Highest quality · 1M ctx" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash", note: "Fast · 1M ctx" },
  ],
  anthropic: [
    { value: "claude-sonnet-4-5-20250929", label: "Claude Sonnet 4.5", note: "Best value · 200K ctx" },
    { value: "claude-opus-4-5", label: "Claude Opus 4.5", note: "Highest quality · 200K ctx" },
    { value: "claude-haiku-4-5", label: "Claude Haiku 4.5", note: "Fastest · 200K ctx" },
  ],
  groq: [
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B", note: "Best value · 128K ctx" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant", note: "Ultra-fast · 128K ctx" },
    { value: "moonshotai/kimi-k2-instruct", label: "Kimi K2", note: "Large context · 128K ctx" },
  ],
};

const PROVIDER_META: Record<string, { name: string; color: string; bg: string; letter: string }> = {
  gemini:    { name: "Google Gemini",    color: "from-blue-400 to-cyan-500",    bg: "bg-blue-50 dark:bg-blue-900/20",    letter: "G" },
  anthropic: { name: "Anthropic Claude", color: "from-orange-400 to-amber-500", bg: "bg-orange-50 dark:bg-orange-900/20", letter: "C" },
  groq:      { name: "Groq",             color: "from-emerald-400 to-teal-500", bg: "bg-emerald-50 dark:bg-emerald-900/20", letter: "Q" },
};

function ProviderCard({
  id,
  info,
  activeProvider,
  activeModel,
  onSelect,
  saving,
}: {
  id: string;
  info: ProviderInfo;
  activeProvider: string;
  activeModel: string;
  onSelect: (provider: string, model: string) => void;
  saving: boolean;
}) {
  const meta = PROVIDER_META[id];
  const models = PROVIDER_MODELS[id];
  const isActive = activeProvider === id;
  const hasKey = id === "gemini" ? info.has_gemini_key : id === "anthropic" ? info.has_anthropic_key : info.has_groq_key;
  const currentModel = isActive ? activeModel : (
    id === "gemini" ? info.gemini_model : id === "anthropic" ? info.anthropic_model : info.groq_model
  );
  const [selectedModel, setSelectedModel] = useState(currentModel);

  return (
    <div className={`relative rounded-2xl border-2 transition-all ${
      isActive
        ? "border-blue-500 shadow-lg shadow-blue-100 dark:shadow-blue-900/20"
        : "border-gray-200 dark:border-gray-700"
    } bg-white dark:bg-gray-800 p-5 space-y-4`}>
      {isActive && (
        <div className="absolute -top-3 left-4 px-2 py-0.5 bg-blue-500 text-white text-xs font-semibold rounded-full">
          Active
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${meta.color} flex items-center justify-center text-white font-bold text-sm shadow`}>
            {meta.letter}
          </div>
          <div>
            <p className="font-semibold text-gray-900 dark:text-white">{meta.name}</p>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              hasKey
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
            }`}>
              {hasKey ? "✓ Key configured" : "⚠ Key not set"}
            </span>
          </div>
        </div>
      </div>

      {/* Model selector */}
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">
          Model
        </label>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          disabled={!hasKey}
          className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
        >
          {models.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label} — {m.note}
            </option>
          ))}
        </select>
      </div>

      {/* Activate button */}
      <button
        onClick={() => onSelect(id, selectedModel)}
        disabled={!hasKey || saving || (isActive && selectedModel === activeModel)}
        className={`w-full py-2 rounded-xl text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
          isActive && selectedModel === activeModel
            ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-default"
            : "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
        }`}
      >
        {saving && isActive ? (
          <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Saving…</span>
        ) : isActive && selectedModel === activeModel ? (
          <span className="flex items-center justify-center gap-2"><CheckCircle className="w-4 h-4 text-emerald-500" /> Currently active</span>
        ) : (
          `Use ${meta.name}`
        )}
      </button>
    </div>
  );
}

function PromptEditor({ prompt, onSaved }: { prompt: PromptRow; onSaved: (u: PromptRow) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ ...prompt });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const allModels = [
    ...PROVIDER_MODELS.gemini.map((m) => ({ label: `Gemini: ${m.label}`, value: m.value })),
    ...PROVIDER_MODELS.anthropic.map((m) => ({ label: `Claude: ${m.label}`, value: m.value })),
    ...PROVIDER_MODELS.groq.map((m) => ({ label: `Groq: ${m.label}`, value: m.value })),
  ];

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put(
        `/api/v1/admin/ai-config/prompts/${prompt.prompt_key}`,
        { model: form.model, max_tokens: form.max_tokens, temperature: form.temperature, is_active: form.is_active, prompt_text: form.prompt_text, description: form.description }
      );
      onSaved(data);
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
      <div
        className="flex items-center justify-between px-5 py-4 bg-white dark:bg-gray-800 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
        onClick={() => !editing && setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-900 dark:text-white text-sm">{prompt.prompt_key}</p>
            {prompt.description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{prompt.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 hidden sm:block">{prompt.model}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${prompt.is_active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
            {prompt.is_active ? "Active" : "Inactive"}
          </span>
          {saved && <CheckCircle className="w-4 h-4 text-emerald-500" />}
          {!editing && (
            <button onClick={(e) => { e.stopPropagation(); setExpanded(true); setEditing(true); }} className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors">
              <Edit3 className="w-4 h-4" />
            </button>
          )}
          {!editing && (expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />)}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-1">
              <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide">Model</label>
              {editing ? (
                <select value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500">
                  {allModels.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              ) : (
                <p className="text-sm font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">{prompt.model}</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide">Max Tokens</label>
              {editing ? (
                <input type="number" value={form.max_tokens} onChange={(e) => setForm({ ...form, max_tokens: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-violet-500" />
              ) : (
                <p className="text-sm font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">{prompt.max_tokens.toLocaleString()}</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide">Temperature</label>
              {editing ? (
                <input type="number" step="0.05" min="0" max="2" value={form.temperature} onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-violet-500" />
              ) : (
                <p className="text-sm font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">{prompt.temperature}</p>
              )}
            </div>
          </div>

          {editing && (
            <div className="flex items-center gap-3">
              <button onClick={() => setForm({ ...form, is_active: !form.is_active })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${form.is_active ? "bg-violet-600" : "bg-gray-300"}`}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${form.is_active ? "translate-x-6" : "translate-x-1"}`} />
              </button>
              <span className="text-sm text-gray-700 dark:text-gray-300">{form.is_active ? "Active" : "Inactive"}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide">Prompt Template</label>
            {editing ? (
              <textarea value={form.prompt_text} onChange={(e) => setForm({ ...form, prompt_text: e.target.value })} rows={16}
                className="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-violet-500 resize-y" />
            ) : (
              <pre className="text-xs font-mono text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                {prompt.prompt_text}
              </pre>
            )}
          </div>

          <p className="text-xs text-gray-400">Last updated: {new Date(prompt.updated_at).toLocaleString()}</p>

          {editing && (
            <div className="flex justify-end gap-3 pt-2 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => { setForm({ ...prompt }); setEditing(false); }} disabled={saving}
                className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                <X className="w-4 h-4" /> Cancel
              </button>
              <button onClick={handleSave} disabled={saving}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors disabled:opacity-50">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {saving ? "Saving…" : "Save Changes"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AIConfig() {
  const [tab, setTab] = useState<"providers" | "prompts">("providers");
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null);
  const [prompts, setPrompts] = useState<PromptRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [prov, prm] = await Promise.all([
        api.get("/api/v1/admin/ai-config/providers"),
        api.get("/api/v1/admin/ai-config/prompts"),
      ]);
      setProviderInfo(prov.data);
      setPrompts(prm.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSelectProvider = async (provider: string, model: string) => {
    setSaving(true);
    try {
      const { data } = await api.put(
        `/api/v1/admin/ai-config/providers`,
        { provider, model }
      );
      setProviderInfo(data);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
      </div>
    );
  }

  const activeModel = providerInfo
    ? providerInfo.provider === "gemini" ? providerInfo.gemini_model
    : providerInfo.provider === "anthropic" ? providerInfo.anthropic_model
    : providerInfo.groq_model
    : "";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">AI Configuration</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">Manage AI providers, models, and prompt templates</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {saveSuccess && (
            <span className="flex items-center gap-1.5 text-sm text-emerald-600 font-medium">
              <CheckCircle className="w-4 h-4" /> Saved — restart ai-service to apply
            </span>
          )}
          <button onClick={load} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl w-fit">
        {(["providers", "prompts"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              tab === t ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}>
            {t === "providers" ? <Sliders className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
            {t === "providers" ? "Providers & Models" : "Prompt Templates"}
          </button>
        ))}
      </div>

      {/* Providers tab */}
      {tab === "providers" && providerInfo && (
        <div className="space-y-5">
          {/* Info banner */}
          <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
            <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Provider selection is saved to the database and picked up by the <code className="font-mono text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">dna-ai-service</code> worker on next restart.
              API keys are configured via environment variables in <code className="font-mono text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">docker-compose.yml</code>.
            </p>
          </div>

          {/* Provider cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {(["gemini", "anthropic", "groq"] as const).map((id) => (
              <ProviderCard
                key={id}
                id={id}
                info={providerInfo}
                activeProvider={providerInfo.provider}
                activeModel={activeModel}
                onSelect={handleSelectProvider}
                saving={saving}
              />
            ))}
          </div>

          {/* Worker settings */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-violet-500" /> Worker Settings
              <span className="text-xs font-normal text-gray-400 ml-1">(set via env vars in docker-compose)</span>
            </h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">Concurrency</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{providerInfo.worker_concurrency}</p>
                <p className="text-xs text-gray-400 mt-0.5">parallel tasks</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">Max cost / task</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">${providerInfo.max_cost_per_task_usd}</p>
                <p className="text-xs text-gray-400 mt-0.5">USD limit</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Prompts tab */}
      {tab === "prompts" && (
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl">
            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              Changes take effect on the <strong>next task</strong> — no restart required. Use <code className="font-mono text-xs bg-amber-100 dark:bg-amber-900 px-1 rounded">{"{{ISO_TEXT}}"}</code> as the injection point in ISO build prompts.
            </p>
          </div>
          {prompts.length === 0 ? (
            <div className="text-center py-12 text-gray-400">No prompts found in the database.</div>
          ) : (
            prompts.map((p) => <PromptEditor key={p.prompt_key} prompt={p} onSaved={(u) => setPrompts((prev) => prev.map((x) => x.prompt_key === u.prompt_key ? u : x))} />)
          )}
        </div>
      )}
    </div>
  );
}
