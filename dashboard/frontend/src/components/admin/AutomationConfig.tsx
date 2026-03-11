"use client";
import { useEffect, useState } from "react";
import { Settings2, Mail, Bot, Clock, Save, CheckCircle2, AlertCircle, Loader2, Eye, EyeOff, ChevronDown, ChevronUp, Wifi, WifiOff, FlaskConical, RefreshCw, Inbox, Search, X, Zap, Edit3, Send, Megaphone } from "lucide-react";
import api from "@/lib/api";
import ExtractionReviewPanel from "@/components/shared/ExtractionReviewPanel";
import type { ReviewItem } from "@/components/shared/ExtractionReviewPanel";

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
  attachment_count: number;
  attachment_filenames: string[];
}

interface OutboundTask {
  id: string;
  customer_id: number;
  customer_name: string;
  title: string;
  notification_type: string | null;
  status: string;
  last_error: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  last_execution: {
    attempt_number: number;
    status: string;
    email_address: string | null;
    error_message: string | null;
    attempted_at: string;
  } | null;
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
  // Inbound log UI state
  const [logExpanded, setLogExpanded] = useState(false);
  const [logSearch, setLogSearch] = useState("");
  // Outbound log
  const [outboundExpanded, setOutboundExpanded] = useState(false);
  const [outboundTasks, setOutboundTasks] = useState<OutboundTask[]>([]);
  const [outboundLoading, setOutboundLoading] = useState(false);
  const [broadcastDraft, setBroadcastDraft] = useState("");
  const [broadcastSubject, setBroadcastSubject] = useState("");
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [broadcastResult, setBroadcastResult] = useState<string | null>(null);
  // Extraction prompts
  const [extractionPrompts, setExtractionPrompts] = useState<PromptRow[]>([]);
  const [promptsExpanded, setPromptsExpanded] = useState(false);

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

  const loadExtractionPrompts = async () => {
    try {
      const r = await api.get("/api/v1/admin/ai-config/prompts");
      const automation = (r.data as PromptRow[]).filter(p =>
        p.prompt_key === "email_extraction_system" || p.prompt_key === "email_extraction_user"
      );
      setExtractionPrompts(automation);
    } catch {}
  };

  const loadOutboundTasks = async () => {
    setOutboundLoading(true);
    try {
      const r = await api.get("/api/v1/automation/outbound-tasks?limit=50");
      setOutboundTasks(r.data?.items || []);
    } catch {}
    setOutboundLoading(false);
  };

  const sendBroadcast = async () => {
    if (!broadcastDraft.trim()) return;
    setBroadcastSending(true);
    setBroadcastResult(null);
    try {
      const r = await api.post("/api/v1/automation/broadcast", {
        subject: broadcastSubject || "Announcement from DNA",
        admin_draft: broadcastDraft,
        customer_ids: [],
      });
      setBroadcastResult(`Queued for ${r.data.tasks_created} customer(s)`);
      setBroadcastDraft("");
      setBroadcastSubject("");
      loadOutboundTasks();
    } catch (e: any) {
      setBroadcastResult(`Error: ${e?.response?.data?.detail || "Failed"}`);
    } finally {
      setBroadcastSending(false);
    }
  };

  useEffect(() => {
    api.get("/api/v1/automation/config").then(r => {
      setCfg(r.data);
      setLoading(false);
    }).catch(() => setLoading(false));
    loadReviewQueue();
    loadInboundEmails();
    loadExtractionPrompts();
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
              label: "LLM — AI Provider API",
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

      {/* ── Inbound Email Log (collapsible) ───────────────────── */}
      <section className="border-t border-slate-100 pt-6">
        {/* Header row — always visible, clicking toggles */}
        <button
          onClick={() => {
            if (!logExpanded) loadInboundEmails();
            setLogExpanded(v => !v);
          }}
          className="w-full flex items-center justify-between group"
        >
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Inbox className="w-4 h-4 text-blue-500" />
            Inbound Email Log
            {inboundEmails.length > 0 && (
              <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-xs rounded-full tabular-nums">
                {inboundEmails.length}
              </span>
            )}
          </h3>
          <div className="flex items-center gap-2">
            {logExpanded && (
              <span
                onClick={e => { e.stopPropagation(); loadInboundEmails(); }}
                className="flex items-center gap-1 px-2 py-0.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
              >
                <RefreshCw className={`w-3 h-3 ${emailsLoading ? "animate-spin" : ""}`} />
                Refresh
              </span>
            )}
            {logExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>
        </button>

        {logExpanded && (
          <div className="mt-4 space-y-3">
            {/* Search bar */}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <input
                value={logSearch}
                onChange={e => setLogSearch(e.target.value)}
                placeholder="Search by customer, email, or subject…"
                className="w-full pl-8 pr-8 py-2 text-sm border border-slate-200 rounded-lg bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {logSearch && (
                <button onClick={() => setLogSearch("")} className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
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
            ) : (() => {
              const q = logSearch.toLowerCase();
              const filtered = inboundEmails.filter(e =>
                !q ||
                (e.customer_name || "").toLowerCase().includes(q) ||
                e.from_email.toLowerCase().includes(q) ||
                (e.subject || "").toLowerCase().includes(q)
              );
              return filtered.length === 0 ? (
                <div className="text-center py-6 text-slate-400 text-sm">No results for "{logSearch}"</div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {filtered.map(email => {
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
                          {email.attachment_count > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {email.attachment_filenames.map((fn, i) => (
                                <span key={i} className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded">
                                  📎 {fn}
                                </span>
                              ))}
                            </div>
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
              );
            })()}
          </div>
        )}
      </section>

      {/* ── Outbound Notifications Log (collapsible) ──────────── */}
      <section className="border-t border-slate-100 pt-6">
        <button
          onClick={() => {
            if (!outboundExpanded) loadOutboundTasks();
            setOutboundExpanded(v => !v);
          }}
          className="w-full flex items-center justify-between group"
        >
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Send className="w-4 h-4 text-emerald-500" />
            Outbound Notifications
            {outboundTasks.length > 0 && (
              <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-xs rounded-full tabular-nums">
                {outboundTasks.length}
              </span>
            )}
          </h3>
          <div className="flex items-center gap-2">
            {outboundExpanded && (
              <span
                onClick={e => { e.stopPropagation(); loadOutboundTasks(); }}
                className="flex items-center gap-1 px-2 py-0.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
              >
                <RefreshCw className={`w-3 h-3 ${outboundLoading ? "animate-spin" : ""}`} />
                Refresh
              </span>
            )}
            {outboundExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>
        </button>

        {outboundExpanded && (
          <div className="mt-4 space-y-4">
            {/* Broadcast compose */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <h4 className="text-xs font-semibold text-slate-700 flex items-center gap-2 mb-3">
                <Megaphone className="w-3.5 h-3.5 text-blue-500" />
                Broadcast Announcement
                <span className="font-normal text-slate-400">— sent to all active customers via LLM</span>
              </h4>
              <div className="space-y-2">
                <input
                  value={broadcastSubject}
                  onChange={e => setBroadcastSubject(e.target.value)}
                  placeholder="Subject (optional)"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <textarea
                  value={broadcastDraft}
                  onChange={e => setBroadcastDraft(e.target.value)}
                  placeholder="Write your key message points here…"
                  rows={4}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <div className="flex items-start gap-2 px-3 py-2 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-700">
                  <Zap className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>AI will rewrite your draft into a polished professional email. Each customer receives a personalised version. Tasks queue immediately and send within 5 minutes.</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    One task created per active customer
                  </span>
                  <div className="flex items-center gap-2">
                    {broadcastResult && (
                      <span className={`text-xs font-medium ${broadcastResult.startsWith("Error") ? "text-red-600" : "text-emerald-600"}`}>
                        {broadcastResult}
                      </span>
                    )}
                    <button
                      onClick={sendBroadcast}
                      disabled={broadcastSending || !broadcastDraft.trim()}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      {broadcastSending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                      {broadcastSending ? "Queuing…" : "Send to All"}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Task list */}
            {outboundLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-400 py-4">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading…
              </div>
            ) : outboundTasks.length === 0 ? (
              <div className="text-center py-8 text-slate-400 bg-slate-50 rounded-xl border border-slate-100">
                <Send className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <div className="text-sm font-medium">No outbound notifications yet</div>
                <div className="text-xs mt-1">Welcome emails and announcements will appear here</div>
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {outboundTasks.map(task => {
                  const isPending   = task.status === "pending";
                  const isCompleted = task.status === "completed";
                  const isFailed    = task.status === "failed";
                  const statusColor = isPending
                    ? "bg-amber-100 text-amber-700"
                    : isCompleted
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-red-100 text-red-700";
                  const typeLabel: Record<string, string> = {
                    welcome_customer: "Welcome",
                    welcome_plan: "Plan Welcome",
                    announcement: "Announcement",
                    iso360_reminder: "ISO360 Reminder",
                  };
                  return (
                    <div key={task.id} className="flex items-start gap-3 p-3 rounded-xl border border-slate-100 bg-white hover:bg-slate-50 transition-colors">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-slate-700">{task.customer_name}</span>
                          {task.notification_type && (
                            <span className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">
                              {typeLabel[task.notification_type] ?? task.notification_type}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5 truncate">{task.title}</div>
                        {task.last_execution?.email_address && (
                          <div className="text-xs text-slate-400 mt-0.5">→ {task.last_execution.email_address}</div>
                        )}
                        {isFailed && task.last_error && (
                          <div className="text-xs text-red-500 mt-1 truncate">{task.last_error}</div>
                        )}
                        {task.retry_count > 0 && (
                          <div className="text-xs text-slate-400 mt-0.5">Retries: {task.retry_count}</div>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor}`}>
                          {isPending ? "Pending" : isCompleted ? "Sent" : "Failed"}
                        </span>
                        <span className="text-xs text-slate-400">
                          {new Date(task.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
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

      {/* ── Extraction Prompt Templates (collapsible) ─────────── */}
      <section className="border-t border-slate-100 pt-6">
        <button
          onClick={() => setPromptsExpanded(v => !v)}
          className="w-full flex items-center justify-between"
        >
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Zap className="w-4 h-4 text-violet-500" />
            Extraction Prompt Templates
            <span className="text-xs font-normal text-slate-400">(used by email extraction LLM)</span>
          </h3>
          {promptsExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </button>

        {promptsExpanded && (
          <div className="mt-4 space-y-3">
            <div className="flex items-start gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
              Changes take effect on the next email received — no restart needed.
              Use <code className="font-mono mx-1">{'{'+'questions_block}'}</code>
              <code className="font-mono mx-1">{'{'+'evidence_block}'}</code>
              <code className="font-mono mx-1">{'{'+'body_text}'}</code>
              <code className="font-mono mx-1">{'{'+'attachments_block}'}</code> in the user prompt.
            </div>
            {extractionPrompts.length === 0 ? (
              <div className="text-sm text-slate-400 py-4 text-center">Loading prompts…</div>
            ) : (
              extractionPrompts.map(prompt => (
                <ExtractionPromptEditor
                  key={prompt.prompt_key}
                  prompt={prompt}
                  onSaved={updated => setExtractionPrompts(prev =>
                    prev.map(p => p.prompt_key === updated.prompt_key ? updated : p)
                  )}
                />
              ))
            )}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Inline prompt editor ──────────────────────────────────────
function ExtractionPromptEditor({ prompt, onSaved }: { prompt: PromptRow; onSaved: (u: PromptRow) => void }) {
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

  const label = prompt.prompt_key === "email_extraction_system" ? "System Prompt" : "User Prompt Template";

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-white">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <Zap className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">{label}</p>
            {prompt.description && <p className="text-xs text-slate-400">{prompt.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">{prompt.model}</span>
          {saved && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-violet-600 hover:bg-violet-50 transition-colors"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {editing && (
        <div className="border-t border-slate-100 bg-slate-50 p-4 space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Max Tokens</label>
              <input type="number" value={form.max_tokens}
                onChange={e => setForm({ ...form, max_tokens: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Temperature</label>
              <input type="number" step="0.05" min="0" max="2" value={form.temperature}
                onChange={e => setForm({ ...form, temperature: parseFloat(e.target.value) || 0 })}
                className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
            <div className="flex items-end pb-0.5">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_active}
                  onChange={e => setForm({ ...form, is_active: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500" />
                <span className="text-xs text-slate-600">Active</span>
              </label>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Prompt Text</label>
            <textarea value={form.prompt_text}
              onChange={e => setForm({ ...form, prompt_text: e.target.value })}
              rows={12}
              className="w-full px-3 py-2 text-xs font-mono border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 resize-y" />
          </div>
          <div className="flex justify-end gap-2 pt-1 border-t border-slate-100">
            <button onClick={() => { setForm({ ...prompt }); setEditing(false); }} disabled={saving}
              className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
              Cancel
            </button>
            <button onClick={handleSave} disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors disabled:opacity-50">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
