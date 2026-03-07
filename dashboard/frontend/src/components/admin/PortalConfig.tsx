"use client";

import { useEffect, useState } from "react";
import {
  Globe, MessageSquare, FileText, Settings, BarChart2,
  Save, Loader2, CheckCircle2, AlertCircle, Cpu, Zap,
  RefreshCw, ChevronDown, ChevronUp, Edit3, X, Check, Sparkles,
} from "lucide-react";
import api from "@/lib/api";

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
  is_active: boolean;
  prompt_text: string;
  updated_at: string;
}

interface PortalConfigData {
  chat_defaults: { language: string; chat_tone: string; max_context_messages: number; max_tokens: number };
  portal_settings: { token_expiry_days: number; require_av_scan: boolean; max_upload_mb: number };
  llm: { provider: string; model: string };
  system_prompt: PromptRow | null;
  help_defaults: { language: string; provider: string; model: string };
}

interface Stats {
  active_tokens: number;
  portal_logins: number;
  answers_submitted: number;
  mcp_chat_calls: number;
  mcp_chat_cost_usd: number;
}

// ── LLM Provider row (reuses same pattern as AIConfig ServiceRow) ──────────

function LLMRow({ provider, model, providers, onSaved }: {
  provider: string; model: string;
  providers: LLMProvider[];
  onSaved: (p: string, m: string) => void;
}) {
  const [prov, setProv] = useState(provider);
  const [mod, setMod] = useState(model);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const enabledProviders = providers.filter(p => p.has_key);
  const selectedProvider = providers.find(p => p.name === prov);
  const availableModels = selectedProvider?.available_models ?? [];
  const isDirty = prov !== provider || mod !== model;

  const handleProviderChange = (v: string) => {
    setProv(v);
    const p = providers.find(x => x.name === v);
    setMod(p?.available_models[0] ?? "");
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put("/api/v1/admin/ai-config/providers", { service: "portal_chat", provider: prov, model: mod });
      onSaved(prov, mod);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  return (
    <div className="flex items-center gap-4 py-4">
      <div className="w-36 flex-shrink-0">
        <p className="text-sm font-semibold text-gray-900">Portal Chat</p>
        <p className="text-xs text-gray-400 mt-0.5 leading-tight">LLM used for customer AI chat sessions</p>
      </div>
      <div className="w-44 flex-shrink-0">
        <label className="block text-xs text-gray-400 mb-1">Provider</label>
        <select value={prov} onChange={e => handleProviderChange(e.target.value)}
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent">
          {enabledProviders.map(p => <option key={p.name} value={p.name}>{p.display_name}</option>)}
          {!enabledProviders.find(p => p.name === prov) && <option value={prov}>{prov} (no key)</option>}
        </select>
      </div>
      <div className="flex-1 min-w-0">
        <label className="block text-xs text-gray-400 mb-1">Model</label>
        {availableModels.length > 0 ? (
          <select value={mod} onChange={e => setMod(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent">
            {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        ) : (
          <input value={mod} onChange={e => setMod(e.target.value)} placeholder="model-id"
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500" />
        )}
      </div>
      <div className="flex-shrink-0">
        <button onClick={handleSave} disabled={saving || !isDirty}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-40">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ── Inline prompt editor ──────────────────────────────────────

function PromptEditor({ prompt, onSaved }: {
  prompt: PromptRow;
  onSaved: (u: PromptRow) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ prompt_text: prompt.prompt_text, is_active: prompt.is_active, description: prompt.description });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put(`/api/v1/admin/ai-config/prompts/${prompt.prompt_key}`, {
        is_active: form.is_active, prompt_text: form.prompt_text, description: form.description,
      });
      onSaved(data);
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 bg-white cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => !editing && setExpanded(!expanded)}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-900 text-sm">{prompt.prompt_key}</p>
            {prompt.description && <p className="text-xs text-gray-500 mt-0.5">{prompt.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${prompt.is_active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
            {prompt.is_active ? "Active" : "Inactive"}
          </span>
          {saved && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
          {!editing && (
            <button onClick={e => { e.stopPropagation(); setExpanded(true); setEditing(true); }}
              className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors">
              <Edit3 className="w-4 h-4" />
            </button>
          )}
          {!editing && (expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />)}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-200 bg-gray-50 p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide">Prompt Template</label>
            {editing ? (
              <textarea value={form.prompt_text} onChange={e => setForm({ ...form, prompt_text: e.target.value })} rows={16}
                className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-violet-500 resize-y" />
            ) : (
              <pre className="text-xs font-mono text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-auto max-h-64 whitespace-pre-wrap">
                {prompt.prompt_text}
              </pre>
            )}
          </div>

          <p className="text-xs text-gray-400">Last updated: {new Date(prompt.updated_at).toLocaleString()}</p>

          {editing && (
            <div className="flex justify-end gap-3 pt-2 border-t border-gray-200">
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

// ── Main component ────────────────────────────────────────────

export default function PortalConfig() {
  const [data, setData] = useState<PortalConfigData | null>(null);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  const [chatForm, setChatForm] = useState({ language: "en", chat_tone: "friendly", max_context_messages: 20, max_tokens: 8192 });
  const [settingsForm, setSettingsForm] = useState({ token_expiry_days: 30, require_av_scan: true, max_upload_mb: 10 });
  const [helpForm, setHelpForm] = useState({ language: "en", provider: "", model: "" });

  const [savingChat, setSavingChat] = useState(false);
  const [savedChat, setSavedChat] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savedSettings, setSavedSettings] = useState(false);
  const [savingHelp, setSavingHelp] = useState(false);
  const [savedHelp, setSavedHelp] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [cfgRes, provRes, statsRes] = await Promise.all([
        api.get("/api/v1/admin/portal-config"),
        api.get("/api/v1/admin/llm-providers"),
        api.get("/api/v1/admin/portal-config/stats"),
      ]);
      const cfg = cfgRes.data as PortalConfigData;
      setData(cfg);
      setProviders(provRes.data);
      setStats(statsRes.data);
      setChatForm(cfg.chat_defaults);
      setSettingsForm(cfg.portal_settings);
      if (cfg.help_defaults) setHelpForm(cfg.help_defaults);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const saveChat = async () => {
    setSavingChat(true); setError("");
    try {
      await api.put("/api/v1/admin/portal-config/chat-defaults", chatForm);
      setSavedChat(true);
      setTimeout(() => setSavedChat(false), 2500);
    } catch (e: any) { setError(e?.response?.data?.detail || "Save failed"); }
    finally { setSavingChat(false); }
  };

  const saveHelp = async () => {
    setSavingHelp(true); setError("");
    try {
      await api.put("/api/v1/admin/portal-config/help-defaults", helpForm);
      setSavedHelp(true);
      setTimeout(() => setSavedHelp(false), 2500);
    } catch (e: any) { setError(e?.response?.data?.detail || "Save failed"); }
    finally { setSavingHelp(false); }
  };

  const saveSettings = async () => {
    setSavingSettings(true); setError("");
    try {
      await api.put("/api/v1/admin/portal-config/settings", settingsForm);
      setSavedSettings(true);
      setTimeout(() => setSavedSettings(false), 2500);
    } catch (e: any) { setError(e?.response?.data?.detail || "Save failed"); }
    finally { setSavingSettings(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
    </div>
  );

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
            <Globe className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">Customer Portal</h3>
            <p className="text-sm text-gray-500">Configure the customer-facing portal and AI chat</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* ── 1. Chat LLM Provider ─────────────────────────────── */}
      <section>
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
          <Cpu className="w-4 h-4 text-blue-500" /> Chat LLM Provider
        </h4>
        <div className="bg-white rounded-xl border border-gray-200 px-6 py-2">
          {data && (
            <LLMRow
              provider={data.llm.provider}
              model={data.llm.model}
              providers={providers}
              onSaved={(p, m) => setData(prev => prev ? { ...prev, llm: { provider: p, model: m } } : prev)}
            />
          )}
        </div>
      </section>

      {/* ── 2. Chat Defaults ─────────────────────────────────── */}
      <section>
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
          <MessageSquare className="w-4 h-4 text-violet-500" /> Chat Defaults
        </h4>
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Language</label>
              <select value={chatForm.language} onChange={e => setChatForm({ ...chatForm, language: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500">
                <option value="en">English</option>
                <option value="he">Hebrew</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Chat Tone</label>
              <select value={chatForm.chat_tone} onChange={e => setChatForm({ ...chatForm, chat_tone: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500">
                <option value="friendly">Friendly</option>
                <option value="formal">Formal</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Max Context Messages</label>
              <input type="number" min={5} max={100} value={chatForm.max_context_messages}
                onChange={e => setChatForm({ ...chatForm, max_context_messages: parseInt(e.target.value) || 20 })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Max Tokens</label>
              <input type="number" min={1024} max={32768} step={1024} value={chatForm.max_tokens}
                onChange={e => setChatForm({ ...chatForm, max_tokens: parseInt(e.target.value) || 8192 })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <div className="flex items-center gap-3 pt-1">
            <button onClick={saveChat} disabled={savingChat}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
              {savingChat ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Defaults
            </button>
            {savedChat && <span className="flex items-center gap-1 text-sm text-emerald-600"><CheckCircle2 className="w-4 h-4" /> Saved</span>}
          </div>
        </div>
      </section>

      {/* ── 3. System Prompt ─────────────────────────────────── */}
      <section>
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
          <FileText className="w-4 h-4 text-amber-500" /> System Prompt
        </h4>
        {data?.system_prompt ? (
          <PromptEditor
            prompt={data.system_prompt}
            onSaved={u => setData(prev => prev ? { ...prev, system_prompt: u } : prev)}
          />
        ) : (
          <div className="text-sm text-gray-400 p-4 bg-gray-50 rounded-xl border border-gray-200">
            No system prompt found. Run migration 005 to seed <code className="font-mono text-xs">portal_mcp_system</code>.
          </div>
        )}
      </section>

      {/* ── 4. Help Me Answer ────────────────────────────────── */}
      <section>
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-violet-500" /> Help Me Answer
        </h4>
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <p className="text-xs text-gray-400">
            AI explanation shown inline when a customer clicks "Help me answer" on a task.
            Leave Provider blank to use the same model as Portal Chat.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Language</label>
              <select value={helpForm.language} onChange={e => setHelpForm({ ...helpForm, language: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-violet-500">
                <option value="en">English</option>
                <option value="he">Hebrew</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="es">Spanish</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Provider (optional override)</label>
              <select value={helpForm.provider} onChange={e => {
                const p = providers.find(x => x.name === e.target.value);
                setHelpForm({ ...helpForm, provider: e.target.value, model: p?.available_models[0] ?? "" });
              }}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-violet-500">
                <option value="">— Same as Chat —</option>
                {providers.filter(p => p.has_key).map(p => <option key={p.name} value={p.name}>{p.display_name}</option>)}
              </select>
            </div>
            {helpForm.provider && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Model</label>
                {(() => {
                  const models = providers.find(p => p.name === helpForm.provider)?.available_models ?? [];
                  return models.length > 0 ? (
                    <select value={helpForm.model} onChange={e => setHelpForm({ ...helpForm, model: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-violet-500">
                      {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  ) : (
                    <input value={helpForm.model} onChange={e => setHelpForm({ ...helpForm, model: e.target.value })}
                      placeholder="model-id"
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-violet-500" />
                  );
                })()}
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 pt-1">
            <button onClick={saveHelp} disabled={savingHelp}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors disabled:opacity-50">
              {savingHelp ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Help Settings
            </button>
            {savedHelp && <span className="flex items-center gap-1 text-sm text-emerald-600"><CheckCircle2 className="w-4 h-4" /> Saved</span>}
          </div>
        </div>
      </section>

      {/* ── 5. Portal Settings ───────────────────────────────── */}
      <section>
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
          <Settings className="w-4 h-4 text-gray-500" /> Portal Settings
        </h4>
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Token Expiry (days)</label>
              <input type="number" min={1} max={365} value={settingsForm.token_expiry_days}
                onChange={e => setSettingsForm({ ...settingsForm, token_expiry_days: parseInt(e.target.value) || 30 })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Max Upload Size (MB)</label>
              <input type="number" min={1} max={100} value={settingsForm.max_upload_mb}
                onChange={e => setSettingsForm({ ...settingsForm, max_upload_mb: parseInt(e.target.value) || 10 })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <label className="flex items-center gap-3">
            <input type="checkbox" checked={settingsForm.require_av_scan}
              onChange={e => setSettingsForm({ ...settingsForm, require_av_scan: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            <span className="text-sm text-gray-700">Require antivirus scan on uploaded files</span>
          </label>
          <div className="flex items-center gap-3 pt-1">
            <button onClick={saveSettings} disabled={savingSettings}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
              {savingSettings ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Settings
            </button>
            {savedSettings && <span className="flex items-center gap-1 text-sm text-emerald-600"><CheckCircle2 className="w-4 h-4" /> Saved</span>}
          </div>
        </div>
      </section>

      {/* ── 5. Activity Stats ────────────────────────────────── */}
      <section>
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
          <BarChart2 className="w-4 h-4 text-emerald-500" /> Activity Stats
        </h4>
        {stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { label: "Active Tokens", value: stats.active_tokens },
              { label: "Portal Logins", value: stats.portal_logins },
              { label: "Answers Submitted", value: stats.answers_submitted },
              { label: "MCP Chat Calls", value: stats.mcp_chat_calls },
              { label: "MCP Chat Cost", value: `$${stats.mcp_chat_cost_usd.toFixed(4)}` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-400 mb-1">{label}</p>
                <p className="text-2xl font-bold text-gray-900">{value}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-gray-400 p-4">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading stats…
          </div>
        )}
      </section>
    </div>
  );
}
