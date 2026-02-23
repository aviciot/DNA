"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Cpu,
  Zap,
  Edit3,
  Save,
  X,
  Check,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  Info,
  RefreshCw,
  Sliders,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface ProviderInfo {
  provider: string;
  gemini_model: string;
  anthropic_model: string;
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

const KNOWN_MODELS = {
  gemini: [
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
  ],
  anthropic: [
    "claude-opus-4-5",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5",
    "claude-3-5-sonnet-20241022",
  ],
  groq: [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
  ],
};

function ProviderBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
        active
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
          : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
      }`}
    >
      {active ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
      {label}
    </span>
  );
}

function KeyStatus({ hasKey, label }: { hasKey: boolean; label: string }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-700/50">
      <span className="text-sm text-gray-600 dark:text-gray-300">{label}</span>
      <span
        className={`text-xs font-medium px-2 py-0.5 rounded-full ${
          hasKey
            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
            : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
        }`}
      >
        {hasKey ? "✓ Configured" : "⚠ Not set"}
      </span>
    </div>
  );
}

function PromptEditor({
  prompt,
  onSaved,
}: {
  prompt: PromptRow;
  onSaved: (updated: PromptRow) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ ...prompt });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const allModels = [
    ...KNOWN_MODELS.gemini.map((m) => ({ label: `Gemini: ${m}`, value: m })),
    ...KNOWN_MODELS.anthropic.map((m) => ({ label: `Claude: ${m}`, value: m })),
    ...KNOWN_MODELS.groq.map((m) => ({ label: `Groq: ${m}`, value: m })),
  ];

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      const { data } = await axios.put(
        `${API_BASE}/api/v1/admin/ai-config/prompts/${prompt.prompt_key}`,
        {
          model: form.model,
          max_tokens: form.max_tokens,
          temperature: form.temperature,
          is_active: form.is_active,
          prompt_text: form.prompt_text,
          description: form.description,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      onSaved(data);
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setForm({ ...prompt });
    setEditing(false);
  };

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center justify-between px-5 py-4 bg-white dark:bg-gray-800 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
        onClick={() => !editing && setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-900 dark:text-white text-sm">
              {prompt.prompt_key}
            </p>
            {prompt.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {prompt.description}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 dark:text-gray-500 hidden sm:block">
            {prompt.model}
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              prompt.is_active
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                : "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
            }`}
          >
            {prompt.is_active ? "Active" : "Inactive"}
          </span>
          {saved && <CheckCircle className="w-4 h-4 text-emerald-500" />}
          {!editing && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(true);
                setEditing(true);
              }}
              className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
            >
              <Edit3 className="w-4 h-4" />
            </button>
          )}
          {!editing &&
            (expanded ? (
              <ChevronUp className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ))}
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 p-5 space-y-4">
          {/* Model + params row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-1">
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">
                Model
              </label>
              {editing ? (
                <select
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                >
                  {allModels.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                  <option value={form.model}>{form.model}</option>
                </select>
              ) : (
                <p className="text-sm text-gray-900 dark:text-white font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">
                  {prompt.model}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">
                Max Tokens
              </label>
              {editing ? (
                <input
                  type="number"
                  value={form.max_tokens}
                  onChange={(e) =>
                    setForm({ ...form, max_tokens: parseInt(e.target.value) || 0 })
                  }
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                />
              ) : (
                <p className="text-sm text-gray-900 dark:text-white font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">
                  {prompt.max_tokens.toLocaleString()}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">
                Temperature
              </label>
              {editing ? (
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="2"
                  value={form.temperature}
                  onChange={(e) =>
                    setForm({ ...form, temperature: parseFloat(e.target.value) || 0 })
                  }
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                />
              ) : (
                <p className="text-sm text-gray-900 dark:text-white font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">
                  {prompt.temperature}
                </p>
              )}
            </div>
          </div>

          {/* Active toggle */}
          {editing && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => setForm({ ...form, is_active: !form.is_active })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.is_active ? "bg-violet-600" : "bg-gray-300 dark:bg-gray-600"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    form.is_active ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {form.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          )}

          {/* Prompt text */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 uppercase tracking-wide">
              Prompt Template
            </label>
            {editing ? (
              <textarea
                value={form.prompt_text}
                onChange={(e) => setForm({ ...form, prompt_text: e.target.value })}
                rows={16}
                className="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-y"
              />
            ) : (
              <pre className="text-xs font-mono text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                {prompt.prompt_text}
              </pre>
            )}
          </div>

          {/* Updated at */}
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Last updated: {new Date(prompt.updated_at).toLocaleString()}
          </p>

          {/* Actions */}
          {editing && (
            <div className="flex justify-end gap-3 pt-2 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={cancel}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
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

  const load = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const headers = { Authorization: `Bearer ${token}` };
      const [prov, prm] = await Promise.all([
        axios.get(`${API_BASE}/api/v1/admin/ai-config/providers`, { headers }),
        axios.get(`${API_BASE}/api/v1/admin/ai-config/prompts`, { headers }),
      ]);
      setProviderInfo(prov.data);
      setPrompts(prm.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handlePromptSaved = (updated: PromptRow) => {
    setPrompts((prev) => prev.map((p) => (p.prompt_key === updated.prompt_key ? updated : p)));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">AI Configuration</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Manage AI providers, models, and prompt templates
            </p>
          </div>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl w-fit">
        {(["providers", "prompts"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              tab === t
                ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {t === "providers" ? <Sliders className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
            {t === "providers" ? "Providers & Models" : "Prompt Templates"}
          </button>
        ))}
      </div>

      {/* ── Providers tab ── */}
      {tab === "providers" && providerInfo && (
        <div className="space-y-5">
          {/* Active provider banner */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-violet-600 to-purple-700 p-6 text-white shadow-lg">
            <div className="relative z-10">
              <p className="text-sm font-medium text-violet-200 mb-1">Active AI Provider</p>
              <p className="text-3xl font-bold capitalize">{providerInfo.provider}</p>
              <p className="text-sm text-violet-200 mt-1">
                {providerInfo.provider === "gemini"
                  ? providerInfo.gemini_model
                  : providerInfo.provider === "anthropic"
                  ? providerInfo.anthropic_model
                  : "Groq (placeholder)"}
              </p>
            </div>
            <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-white/10" />
            <div className="absolute -right-4 -bottom-10 w-28 h-28 rounded-full bg-white/5" />
          </div>

          {/* Provider cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Gemini */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-400 to-cyan-500 flex items-center justify-center text-white text-xs font-bold">G</div>
                  <span className="font-semibold text-gray-900 dark:text-white">Google Gemini</span>
                </div>
                <ProviderBadge active={providerInfo.provider === "gemini"} label={providerInfo.provider === "gemini" ? "Active" : "Standby"} />
              </div>
              <KeyStatus hasKey={providerInfo.has_gemini_key} label="GOOGLE_API_KEY" />
              <div className="space-y-1">
                <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">Available models</p>
                {KNOWN_MODELS.gemini.map((m) => (
                  <p key={m} className={`text-xs px-2 py-1 rounded font-mono ${m === providerInfo.gemini_model ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" : "text-gray-500 dark:text-gray-400"}`}>
                    {m === providerInfo.gemini_model ? "▶ " : "  "}{m}
                  </p>
                ))}
              </div>
            </div>

            {/* Claude */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-400 to-amber-500 flex items-center justify-center text-white text-xs font-bold">C</div>
                  <span className="font-semibold text-gray-900 dark:text-white">Anthropic Claude</span>
                </div>
                <ProviderBadge active={providerInfo.provider === "anthropic"} label={providerInfo.provider === "anthropic" ? "Active" : "Standby"} />
              </div>
              <KeyStatus hasKey={providerInfo.has_anthropic_key} label="ANTHROPIC_API_KEY" />
              <div className="space-y-1">
                <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">Available models</p>
                {KNOWN_MODELS.anthropic.map((m) => (
                  <p key={m} className={`text-xs px-2 py-1 rounded font-mono ${m === providerInfo.anthropic_model ? "bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300" : "text-gray-500 dark:text-gray-400"}`}>
                    {m === providerInfo.anthropic_model ? "▶ " : "  "}{m}
                  </p>
                ))}
              </div>
            </div>

            {/* Groq */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 space-y-3 opacity-80">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-xs font-bold">Q</div>
                  <span className="font-semibold text-gray-900 dark:text-white">Groq</span>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 font-medium">
                  Coming soon
                </span>
              </div>
              <KeyStatus hasKey={providerInfo.has_groq_key} label="GROQ_API_KEY" />
              <div className="space-y-1">
                <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">Available models</p>
                {KNOWN_MODELS.groq.map((m) => (
                  <p key={m} className="text-xs px-2 py-1 rounded font-mono text-gray-400 dark:text-gray-500">
                    {m}
                  </p>
                ))}
              </div>
            </div>
          </div>

          {/* Worker settings */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-violet-500" />
              Worker Settings
            </h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Concurrency</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {providerInfo.worker_concurrency}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">parallel tasks</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Max cost / task</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  ${providerInfo.max_cost_per_task_usd}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">USD limit</p>
              </div>
            </div>
          </div>

          {/* Info note */}
          <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
            <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Provider selection and API keys are configured via environment variables in the AI service container.
              To switch providers, update <code className="font-mono text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">LLM_PROVIDER</code> and restart the <code className="font-mono text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">dna-ai-service</code> container.
            </p>
          </div>
        </div>
      )}

      {/* ── Prompts tab ── */}
      {tab === "prompts" && (
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl">
            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              Changes take effect on the <strong>next task</strong> — no restart required. Use <code className="font-mono text-xs bg-amber-100 dark:bg-amber-900 px-1 rounded">{"{{ISO_TEXT}}"}</code> as the injection point in ISO build prompts.
            </p>
          </div>

          {prompts.length === 0 ? (
            <div className="text-center py-12 text-gray-400 dark:text-gray-500">
              No prompts found in the database.
            </div>
          ) : (
            prompts.map((p) => (
              <PromptEditor key={p.prompt_key} prompt={p} onSaved={handlePromptSaved} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
