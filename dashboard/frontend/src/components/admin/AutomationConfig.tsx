"use client";
import { useEffect, useState } from "react";
import { Settings2, Mail, Bot, Clock, Save, CheckCircle2, AlertCircle, Loader2, Eye, EyeOff, ChevronDown, Wifi, WifiOff, FlaskConical, RefreshCw, Inbox } from "lucide-react";
import api from "@/lib/api";
import ExtractionReviewPanel from "@/components/shared/ExtractionReviewPanel";
import type { ReviewItem } from "@/components/shared/ExtractionReviewPanel";

interface InboundEmail {
  id: string;
  customer_id: number | null;
  customer_name: string | null;
  from_email: string;
  subject: string | null;
  status: string;
  received_at: string;
  total_items: number;
  auto_applied: number;
  pending_review: number;
  accepted: number;
  llm_notes: string | null;
}

interface AutomationCfg {
  enabled: boolean;
  email_provider: string;
  sendgrid_api_key: string;
  sendgrid_from_email: string;
  sendgrid_from_name: string;
  gmail_address: string;
  gmail_app_password: string;
  imap_host: string;
  imap_port: number;
  imap_poll_interval_seconds: number;
  extraction_provider: string;
  extraction_model: string;
  auto_apply_threshold: number;
  confidence_floor: number;
  review_mode: string;
  followup_delay_days: number;
  max_followups: number;
  send_window_start: string;
  send_window_end: string;
  timezone: string;
  send_extraction_reply: boolean;
}

const PROVIDERS = [
  { value: "gemini",    label: "Google Gemini" },
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "groq",      label: "Groq (LLaMA)" },
];

const MODELS: Record<string, { value: string; label: string }[]> = {
  gemini:    [{ value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" }, { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" }],
  anthropic: [{ value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" }, { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" }],
  groq:      [{ value: "llama-3.3-70b-versatile", label: "LLaMA 3.3 70B" }, { value: "llama-3.1-8b-instant", label: "LLaMA 3.1 8B" }],
};

export default function AutomationConfig() {
  const [cfg, setCfg] = useState<Partial<AutomationCfg>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [showSgKey, setShowSgKey] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string } | null>>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [inboundEmails, setInboundEmails] = useState<InboundEmail[]>([]);
  const [emailsLoading, setEmailsLoading] = useState(false);

  const loadReviewQueue = async () => {
    setReviewLoading(true);
    try {
      const r = await api.get("/api/v1/automation/review-queue?limit=50");
      setReviewQueue(r.data || []);
    } catch {}
    setReviewLoading(false);
  };

  const loadInboundEmails = async () => {
    setEmailsLoading(true);
    try {
      const r = await api.get("/api/v1/automation/inbound-emails?limit=30");
      setInboundEmails(r.data || []);
    } catch {}
    setEmailsLoading(false);
  };

  useEffect(() => {
    api.get("/api/v1/automation/config").then(r => {
      setCfg(r.data);
      setLoading(false);
    }).catch(() => setLoading(false));
    loadReviewQueue();
    loadInboundEmails();
  }, []);

  const set = (k: keyof AutomationCfg, v: unknown) => setCfg(p => ({ ...p, [k]: v }));

  const runTest = async (testType: string) => {
    setTesting(testType);
    setTestResults(p => ({ ...p, [testType]: null }));
    try {
      const r = await api.post("/api/v1/automation/test", {
        test_type: testType,
        email_provider: cfg.email_provider,
        gmail_address: cfg.gmail_address,
        gmail_app_password: cfg.gmail_app_password,
        sendgrid_api_key: cfg.sendgrid_api_key,
        imap_host: cfg.imap_host,
        imap_port: cfg.imap_port,
        extraction_provider: cfg.extraction_provider,
      });
      setTestResults(p => ({ ...p, [testType]: r.data }));
    } catch (e: any) {
      setTestResults(p => ({ ...p, [testType]: { ok: false, message: e?.response?.data?.detail || "Request failed" } }));
    } finally {
      setTesting(null);
    }
  };

  const save = async () => {
    setSaving(true); setError("");
    try {
      // Don't send masked password fields
      const payload = { ...cfg };
      if (payload.gmail_app_password === "••••••••") delete payload.gmail_app_password;
      if (payload.sendgrid_api_key === "••••••••") delete payload.sendgrid_api_key;
      await api.put("/api/v1/automation/config", payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex items-center gap-2 p-6 text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;

  const modelOptions = MODELS[cfg.extraction_provider || "gemini"] || [];

  return (
    <div className="space-y-6">
      {/* Enable toggle */}
      <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200">
        <div>
          <div className="font-semibold text-slate-900 flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${cfg.enabled ? "bg-emerald-500" : "bg-slate-300"}`} />
            Email Automation {cfg.enabled ? "Enabled" : "Disabled"}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">When enabled, the automation service polls for inbound emails and sends follow-ups</p>
        </div>
        <button
          onClick={() => set("enabled", !cfg.enabled)}
          className={`relative w-12 h-6 rounded-full transition-colors ${cfg.enabled ? "bg-emerald-500" : "bg-slate-300"}`}
        >
          <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all ${cfg.enabled ? "left-7" : "left-1"}`} />
        </button>
      </div>

      {/* Email Provider */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3">
          <Mail className="w-4 h-4 text-blue-500" /> Email Provider
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {["gmail", "sendgrid"].map(p => (
            <button key={p} onClick={() => set("email_provider", p)}
              className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${cfg.email_provider === p ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>
              {p === "gmail" ? "📧 Gmail SMTP" : "📤 SendGrid"}
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Gmail Address</label>
            <input value={cfg.gmail_address || ""} onChange={e => set("gmail_address", e.target.value)}
              placeholder="you@gmail.com"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Gmail App Password</label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                value={cfg.gmail_app_password || ""}
                onChange={e => set("gmail_app_password", e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx"
                className="w-full px-3 py-2 pr-10 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button onClick={() => setShowPass(p => !p)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-1">Google Account → Security → App Passwords → create "DNA Automation"</p>
          </div>

          {cfg.email_provider === "sendgrid" && (<>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">SendGrid API Key</label>
              <div className="relative">
                <input
                  type={showSgKey ? "text" : "password"}
                  value={cfg.sendgrid_api_key || ""}
                  onChange={e => set("sendgrid_api_key", e.target.value)}
                  placeholder="SG.xxxxx"
                  className="w-full px-3 py-2 pr-10 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button onClick={() => setShowSgKey(p => !p)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                  {showSgKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">From Email</label>
                <input value={cfg.sendgrid_from_email || ""} onChange={e => set("sendgrid_from_email", e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">From Name</label>
                <input value={cfg.sendgrid_from_name || "DNA Compliance"} onChange={e => set("sendgrid_from_name", e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
          </>)}

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1">IMAP Host</label>
              <input value={cfg.imap_host || "imap.gmail.com"} onChange={e => set("imap_host", e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Port</label>
              <input type="number" value={cfg.imap_port || 993} onChange={e => set("imap_port", parseInt(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Poll Interval (seconds)</label>
            <input type="number" min={30} max={3600} value={cfg.imap_poll_interval_seconds || 60}
              onChange={e => set("imap_poll_interval_seconds", parseInt(e.target.value))}
              className="w-40 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
      </section>

      {/* AI Extraction */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3">
          <Bot className="w-4 h-4 text-violet-500" /> AI Extraction
        </h3>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">LLM Provider</label>
              <select value={cfg.extraction_provider || "gemini"} onChange={e => { set("extraction_provider", e.target.value); set("extraction_model", ""); }}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Model</label>
              <select value={cfg.extraction_model || ""} onChange={e => set("extraction_model", e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Default</option>
                {modelOptions.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-2">
              Review Mode
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "hybrid",      label: "Hybrid", desc: "Auto high confidence, queue rest" },
                { value: "human_first", label: "Human First", desc: "All items go to review queue" },
                { value: "autonomous",  label: "Autonomous", desc: "Auto-apply everything above floor" },
              ].map(opt => (
                <button key={opt.value} onClick={() => set("review_mode", opt.value)}
                  className={`p-2.5 rounded-lg border-2 text-left transition-all ${cfg.review_mode === opt.value ? "border-violet-500 bg-violet-50" : "border-slate-200 hover:border-slate-300"}`}>
                  <div className="text-xs font-semibold text-slate-800">{opt.label}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Auto-Apply Threshold <span className="text-slate-400">(confidence ≥ this → auto-apply)</span>
              </label>
              <div className="flex items-center gap-2">
                <input type="range" min={0.5} max={1.0} step={0.05} value={cfg.auto_apply_threshold || 0.85}
                  onChange={e => set("auto_apply_threshold", parseFloat(e.target.value))}
                  className="flex-1" />
                <span className="text-sm font-mono font-semibold text-slate-700 w-10">
                  {((cfg.auto_apply_threshold || 0.85) * 100).toFixed(0)}%
                </span>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Confidence Floor <span className="text-slate-400">(below this → discard)</span>
              </label>
              <div className="flex items-center gap-2">
                <input type="range" min={0.0} max={0.8} step={0.05} value={cfg.confidence_floor || 0.60}
                  onChange={e => set("confidence_floor", parseFloat(e.target.value))}
                  className="flex-1" />
                <span className="text-sm font-mono font-semibold text-slate-700 w-10">
                  {((cfg.confidence_floor || 0.60) * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
          <label className="flex items-center gap-3 pt-1">
            <input
              type="checkbox"
              checked={cfg.send_extraction_reply ?? true}
              onChange={e => set("send_extraction_reply", e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
            />
            <span className="text-sm text-slate-700 dark:text-slate-300">
              Send automated reply email to customer after extraction
            </span>
          </label>
        </div>
      </section>

      {/* Scheduling */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-amber-500" /> Follow-up Schedule
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Follow-up delay (days)</label>
            <input type="number" min={1} max={14} value={cfg.followup_delay_days || 2}
              onChange={e => set("followup_delay_days", parseInt(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Max follow-ups</label>
            <input type="number" min={1} max={5} value={cfg.max_followups || 3}
              onChange={e => set("max_followups", parseInt(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Send window start</label>
            <input type="time" value={cfg.send_window_start || "09:00"}
              onChange={e => set("send_window_start", e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Send window end</label>
            <input type="time" value={cfg.send_window_end || "17:00"}
              onChange={e => set("send_window_end", e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-600 mb-1">Timezone</label>
            <input value={cfg.timezone || "UTC"} onChange={e => set("timezone", e.target.value)}
              placeholder="UTC, Asia/Jerusalem, America/New_York…"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
      </section>

      {/* Connection Tests */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3">
          <FlaskConical className="w-4 h-4 text-emerald-500" /> Connection Tests
        </h3>
        <p className="text-xs text-slate-500 mb-3">
          Test each connection using the values currently entered above (save is not required first).
        </p>
        <div className="space-y-2">
          {[
            {
              key: "smtp",
              label: cfg.email_provider === "sendgrid" ? "SendGrid — API Key" : "Gmail SMTP — Outbound Send",
              description: cfg.email_provider === "sendgrid"
                ? "Validates your SendGrid API key against the SendGrid account API"
                : "Connects to smtp.gmail.com:465 and authenticates with your App Password",
              icon: <Mail className="w-4 h-4" />,
            },
            {
              key: "imap",
              label: "IMAP — Inbox Receive",
              description: `Connects to ${cfg.imap_host || "imap.gmail.com"}:${cfg.imap_port || 993} and logs in to read emails`,
              icon: <Wifi className="w-4 h-4" />,
            },
            {
              key: "llm",
              label: `LLM — ${cfg.extraction_provider === "anthropic" ? "Anthropic Claude" : cfg.extraction_provider === "groq" ? "Groq" : "Google Gemini"} API`,
              description: "Validates the API key is set and reachable by listing available models",
              icon: <Bot className="w-4 h-4" />,
            },
          ].map(({ key, label, description, icon }) => {
            const result = testResults[key];
            const isRunning = testing === key;
            return (
              <div key={key} className="flex items-start gap-3 p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="text-slate-500 mt-0.5">{icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-slate-800">{label}</span>
                    {result && (
                      <span className={`flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${result.ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                        {result.ok ? <CheckCircle2 className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                        {result.ok ? "Connected" : "Failed"}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{description}</p>
                  {result && (
                    <p className={`text-xs mt-1 ${result.ok ? "text-emerald-700" : "text-red-600"}`}>
                      {result.message}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => runTest(key)}
                  disabled={!!testing}
                  className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-slate-300 rounded-lg text-slate-600 hover:bg-white hover:border-slate-400 transition-colors disabled:opacity-50"
                >
                  {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <FlaskConical className="w-3 h-3" />}
                  {isRunning ? "Testing…" : "Test"}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* Save */}
      <div className="flex items-center gap-3 pt-2">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Configuration
        </button>
        {saved && <span className="flex items-center gap-1 text-sm text-emerald-600"><CheckCircle2 className="w-4 h-4" /> Saved</span>}
        {error && <span className="flex items-center gap-1 text-sm text-red-600"><AlertCircle className="w-4 h-4" /> {error}</span>}
      </div>

      {/* ── Inbound Email Log ─────────────────────────────────── */}
      <section className="border-t border-slate-100 pt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Inbox className="w-4 h-4 text-blue-500" />
            Inbound Email Log
            {inboundEmails.length > 0 && (
              <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-xs rounded-full tabular-nums">
                {inboundEmails.length}
              </span>
            )}
          </h3>
          <button
            onClick={loadInboundEmails}
            disabled={emailsLoading}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${emailsLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {emailsLoading ? (
          <div className="flex items-center gap-2 text-sm text-slate-400 py-4">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        ) : inboundEmails.length === 0 ? (
          <div className="text-center py-8 text-slate-400 bg-slate-50 rounded-xl border border-slate-100">
            <Inbox className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <div className="text-sm font-medium">No emails received yet</div>
          </div>
        ) : (
          <div className="space-y-2">
            {inboundEmails.map(email => {
              const noMatch = email.total_items === 0;
              const hasReview = email.pending_review > 0;
              const allApplied = email.auto_applied > 0 && email.pending_review === 0;
              const statusColor = noMatch
                ? "bg-slate-100 text-slate-500"
                : hasReview
                ? "bg-amber-100 text-amber-700"
                : allApplied
                ? "bg-emerald-100 text-emerald-700"
                : "bg-blue-100 text-blue-700";
              const statusLabel = noMatch
                ? "No match"
                : hasReview
                ? `${email.pending_review} for review`
                : `${email.auto_applied} applied`;
              return (
                <div key={email.id} className="flex items-start gap-3 p-3 rounded-xl border border-slate-100 bg-white hover:bg-slate-50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {email.customer_name ? (
                        <span className="text-xs font-semibold text-slate-700">{email.customer_name}</span>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Unknown sender</span>
                      )}
                      <span className="text-xs text-slate-400 truncate">{email.from_email}</span>
                    </div>
                    {email.subject && (
                      <div className="text-xs text-slate-500 mt-0.5 truncate">{email.subject}</div>
                    )}
                    {noMatch && email.llm_notes && (
                      <div className="text-xs text-slate-400 mt-1 italic truncate">{email.llm_notes}</div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor}`}>
                      {statusLabel}
                    </span>
                    <span className="text-xs text-slate-400">
                      {new Date(email.received_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ── Global Extraction Review Queue ────────────────────── */}
      <section className="border-t border-slate-100 pt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Bot className="w-4 h-4 text-amber-500" />
            Global Review Queue
            {reviewQueue.length > 0 && (
              <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-full tabular-nums">
                {reviewQueue.length}
              </span>
            )}
          </h3>
          <button
            onClick={loadReviewQueue}
            disabled={reviewLoading}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${reviewLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {reviewLoading ? (
          <div className="flex items-center gap-2 text-sm text-slate-400 py-4">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading review queue…
          </div>
        ) : reviewQueue.length === 0 ? (
          <div className="text-center py-8 text-slate-400 bg-slate-50 rounded-xl border border-slate-100">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <div className="text-sm font-medium">No items pending review</div>
            <div className="text-xs mt-1">All extractions have been processed</div>
          </div>
        ) : (
          <ExtractionReviewPanel
            items={reviewQueue}
            onReviewed={loadReviewQueue}
            title="All Customers — Pending Review"
          />
        )}
      </section>
    </div>
  );
}
