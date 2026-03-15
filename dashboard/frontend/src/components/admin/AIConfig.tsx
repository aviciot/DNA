"use client";

import { useState, useEffect } from "react";
import {
  Cpu, Zap, Save, X, Check, Loader2, AlertTriangle,
  CheckCircle, Info, RefreshCw, Sliders, ChevronDown, ChevronUp, Edit3,
} from "lucide-react";

import api from "@/lib/api";

interface AIServiceConfig {
  service: string;    // 'iso_builder' | 'extraction'
  provider: string;
  model: string;
  updated_at?: string;
}

interface LLMProvider {
  name: string;
  display_name: string;
  enabled: boolean;
  has_key: boolean;
  available_models: string[];
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

const SERVICE_LABELS: Record<string, { label: string; description: string }> = {
  iso_builder: { label: "ISO Builder",  description: "Builds ISO standards and generates templates from PDFs" },
  extraction:  { label: "Extraction",   description: "Extracts answers from inbound customer emails" },
};

// ──────────────────────────────────────────────────────────────
// ServiceRow — one row in the service config table
// ──────────────────────────────────────────────────────────────

function ServiceRow({
  config,
  providers,
  onSaved,
}: {
  config: AIServiceConfig;
  providers: LLMProvider[];
  onSaved: (updated: AIServiceConfig) => void;
}) {
  const [provider, setProvider] = useState(config.provider);
  const [model, setModel] = useState(config.model);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const enabledProviders = providers.filter(p => p.has_key);
  const selectedProvider = providers.find(p => p.name === provider);
  const availableModels = selectedProvider?.available_models ?? [];

  // When provider changes, reset model to first available
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const prov = providers.find(p => p.name === newProvider);
    const models = prov?.available_models ?? [];
    setModel(models[0] ?? "");
  };

  const isDirty = provider !== config.provider || model !== config.model;

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/api/v1/admin/ai-config/providers", {
        service: config.service,
        provider,
        model,
      });
      const updated = (data as AIServiceConfig[]).find(s => s.service === config.service);
      if (updated) onSaved(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const meta = SERVICE_LABELS[config.service] ?? { label: config.service, description: "" };

  return (
    <div className="flex items-center gap-4 py-4 border-b border-gray-100 dark:border-gray-700 last:border-0">
      {/* Service label */}
      <div className="w-36 flex-shrink-0">
        <p className="text-sm font-semibold text-gray-900 dark:text-white">{meta.label}</p>
        <p className="text-xs text-gray-400 mt-0.5 leading-tight">{meta.description}</p>
      </div>

      {/* Provider dropdown */}
      <div className="w-44 flex-shrink-0">
        <label className="block text-xs text-gray-400 mb-1">Provider</label>
        <select
          value={provider}
          onChange={e => handleProviderChange(e.target.value)}
          className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {enabledProviders.map(p => (
            <option key={p.name} value={p.name}>{p.display_name}</option>
          ))}
          {/* Show current even if not enabled, to avoid losing data */}
          {!enabledProviders.find(p => p.name === provider) && (
            <option value={provider}>{provider} (no key)</option>
          )}
        </select>
      </div>

      {/* Model dropdown */}
      <div className="flex-1 min-w-0">
        <label className="block text-xs text-gray-400 mb-1">Model</label>
        {availableModels.length > 0 ? (
          <select
            value={model}
            onChange={e => setModel(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {availableModels.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        ) : (
          <input
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder="model-id"
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        )}
      </div>

      {/* Save button */}
      <div className="flex-shrink-0">
        <button
          onClick={handleSave}
          disabled={saving || !isDirty}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-40"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// PromptEditor
// ──────────────────────────────────────────────────────────────

function PromptEditor({
  prompt,
  allModels,
  onSaved,
}: {
  prompt: PromptRow;
  allModels: { label: string; value: string }[];
  onSaved: (u: PromptRow) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ ...prompt });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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
                <p className="text-sm font-mono bg-white dark:bg-gray-800 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700">{(prompt.max_tokens ?? 0).toLocaleString()}</p>
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

// ──────────────────────────────────────────────────────────────
// Main component
// ──────────────────────────────────────────────────────────────

export default function AIConfig() {
  const [tab, setTab] = useState<"providers" | "prompts">("providers");
  const [services, setServices] = useState<AIServiceConfig[]>([]);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [prompts, setPrompts] = useState<PromptRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [svcRes, provRes, prmRes] = await Promise.all([
        api.get("/api/v1/admin/ai-config/providers"),
        api.get("/api/v1/admin/llm-providers"),
        api.get("/api/v1/admin/ai-config/prompts"),
      ]);
      setServices(svcRes.data);
      setProviders(provRes.data);
      setPrompts(prmRes.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  // Flatten all available models from all providers for the prompt editor
  const allModels = providers.flatMap(p =>
    (p.available_models ?? []).map(m => ({ label: `${p.display_name}: ${m}`, value: m }))
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
      </div>
    );
  }

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
            <p className="text-sm text-gray-500 dark:text-gray-400">Manage AI service routing and prompt templates</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl w-fit">
        {(["providers", "prompts"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              tab === t ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}>
            {t === "providers" ? <Sliders className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
            {t === "providers" ? "Service Config" : "Prompt Templates"}
          </button>
        ))}
      </div>

      {/* Service Config tab */}
      {tab === "providers" && (
        <div className="space-y-5">
          <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
            <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Each service uses its own provider and model. Configure API keys in the <strong>AI Providers</strong> tab.
              Changes are picked up by the worker on next restart.
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 px-6 py-2">
            {services.length === 0 ? (
              <p className="py-8 text-center text-gray-400 text-sm">No service config found. Run migration 017.</p>
            ) : (
              services.map(svc => (
                <ServiceRow
                  key={svc.service}
                  config={svc}
                  providers={providers}
                  onSaved={updated =>
                    setServices(prev => prev.map(s => s.service === updated.service ? updated : s))
                  }
                />
              ))
            )}
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
            prompts.map((p) => (
              <PromptEditor
                key={p.prompt_key}
                prompt={p}
                allModels={allModels}
                onSaved={(u) => setPrompts((prev) => prev.map((x) => x.prompt_key === u.prompt_key ? u : x))}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
