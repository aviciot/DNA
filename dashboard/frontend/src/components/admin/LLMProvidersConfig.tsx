"use client";

import { useEffect, useState } from "react";
import {
  Loader2, Save, Eye, EyeOff, CheckCircle2, XCircle,
  FlaskConical, RefreshCw, KeyRound, Cpu, Plus, X,
} from "lucide-react";
import api from "@/lib/api";

interface LLMProvider {
  name: string;
  display_name: string;
  enabled: boolean;
  has_key: boolean;
  key_source: "db" | "env" | null;
  available_models: string[];
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
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const isDirty =
    apiKey !== "" ||
    enabled !== provider.enabled ||
    JSON.stringify(models) !== JSON.stringify(provider.available_models);

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

export default function LLMProvidersConfig() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-7 h-7 animate-spin text-slate-400" />
      </div>
    );
  }

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

      {/* Provider cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {providers.map(p => (
          <ProviderCard key={p.name} provider={p} onRefresh={load} />
        ))}
      </div>
    </div>
  );
}
