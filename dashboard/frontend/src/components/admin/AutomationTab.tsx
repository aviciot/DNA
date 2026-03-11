"use client";
import { useEffect, useRef, useState } from "react";
import {
  Mail, Send, CheckCircle2, Clock, AlertCircle, Loader2,
  MessageSquare, Paperclip,
  RefreshCw, Inbox, ChevronDown, Sparkles,
  MailCheck, ArrowUpRight, ArrowDownLeft,
  Eye, EyeOff, Trash2, X, Ban, Settings, PauseCircle, Shield,
} from "lucide-react";
import api from "@/lib/api";
import ExtractionReviewPanel from "@/components/shared/ExtractionReviewPanel";
import type { ReviewItem } from "@/components/shared/ExtractionReviewPanel";

// ── Types ────────────────────────────────────────────────────

interface AutomationTabProps {
  customerId: number;
  plans: { id: string; iso_code: string; iso_name: string; plan_status: string; iso360_enabled?: boolean }[];
}

interface QuestionItem {
  placeholder_key: string;
  question: string;
  hint?: string;
}

interface EvidenceItem {
  task_id: string;
  title: string;
  description?: string;
}

interface Reply {
  id: string;
  from_email: string;
  subject: string;
  status: string;
  received_at: string;
  extraction_notes?: string;
  body_snippet?: string;
  auto_applied: number;
  pending_review: number;
  total_extracted: number;
}

interface Thread {
  id: string;
  plan_id: string;
  campaign_number: number;
  status: string;
  sent_to: string[];
  subject: string;
  sent_at: string;
  questions_snapshot: QuestionItem[];
  evidence_snapshot: EvidenceItem[];
  iso_code?: string;
  iso_name?: string;
  replies: Reply[];
}

// ReviewItem is imported from ExtractionReviewPanel

interface CustomerConfig {
  customer_id?: number;
  enabled: boolean;
  preferred_language: "en" | "he";
  contact_name?: string | null;
  send_to_emails?: string[] | null;
  max_followups?: number | null;
  followup_delay_days?: number | null;
  send_window_start?: string | null;
  send_window_end?: string | null;
  notes?: string | null;
}

type TimelineItem =
  | { type: "sent"; campaign: Thread }
  | { type: "reply"; reply: Reply };

// ── Helpers ──────────────────────────────────────────────────

function fmt(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function fmtFull(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function groupByPlanId(threads: Thread[]): Map<string, Thread[]> {
  const map = new Map<string, Thread[]>();
  for (const t of threads) {
    const key = t.plan_id || t.id;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(t);
  }
  // Sort each group by sent_at ascending (oldest first = top of timeline)
  for (const [, group] of map) {
    group.sort((a, b) => new Date(a.sent_at).getTime() - new Date(b.sent_at).getTime());
  }
  return map;
}

function buildTimeline(campaigns: Thread[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  for (const c of campaigns) {
    items.push({ type: "sent", campaign: c });
    for (const r of c.replies) {
      items.push({ type: "reply", reply: r });
    }
  }
  return items.sort((a, b) => {
    const ta = a.type === "sent"
      ? new Date(a.campaign.sent_at).getTime()
      : new Date(a.reply.received_at).getTime();
    const tb = b.type === "sent"
      ? new Date(b.campaign.sent_at).getTime()
      : new Date(b.reply.received_at).getTime();
    return ta - tb;
  });
}

function conversationSummary(campaigns: Thread[]): { label: string; color: string } {
  const totalQ = campaigns[0]?.questions_snapshot?.length ?? 0;
  const allReplies = campaigns.flatMap(c => c.replies);
  const totalApplied = allReplies.reduce((s, r) => s + (r.auto_applied || 0), 0);
  const totalPending = allReplies.reduce((s, r) => s + (r.pending_review || 0), 0);
  const hasReplies = allReplies.length > 0;
  const allPending = campaigns.every(c => c.status === "pending");

  if (totalPending > 0)
    return { label: `${totalPending} need review`, color: "text-amber-600 bg-amber-50 border-amber-200" };
  if (!hasReplies && allPending)
    return { label: "Awaiting reply", color: "text-amber-500 bg-amber-50 border-amber-200" };
  if (totalApplied >= totalQ && totalQ > 0)
    return { label: `All ${totalQ} answered`, color: "text-emerald-600 bg-emerald-50 border-emerald-200" };
  if (totalApplied > 0)
    return { label: `${totalApplied}/${totalQ} answered`, color: "text-blue-600 bg-blue-50 border-blue-200" };
  return { label: "No data extracted", color: "text-slate-500 bg-slate-100 border-slate-200" };
}

// ── Customer Config Modal ─────────────────────────────────────

function ConfigModal({
  customerId,
  initialConfig,
  onClose,
  onSaved,
}: {
  customerId: number;
  initialConfig: CustomerConfig;
  onClose: () => void;
  onSaved: (cfg: CustomerConfig) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [form, setForm] = useState<CustomerConfig>({ ...initialConfig });
  const [sendToRaw, setSendToRaw] = useState(
    (initialConfig.send_to_emails || []).join(", ")
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const handleSave = async () => {
    setSaving(true);
    const emails = sendToRaw
      .split(/[,\n]+/)
      .map(s => s.trim())
      .filter(Boolean);
    const payload = {
      ...form,
      send_to_emails: emails.length > 0 ? emails : [],
    };
    try {
      await api.put(`/api/v1/automation/${customerId}/config`, payload);
      setSaved(true);
      onSaved(payload);
      setTimeout(() => { setSaved(false); onClose(); }, 1200);
    } catch {}
    setSaving(false);
  };

  const f = (field: keyof CustomerConfig, value: any) =>
    setForm(prev => ({ ...prev, [field]: value }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        ref={ref}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-800">
              Automation Settings
            </span>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {/* Enabled toggle */}
          <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-slate-50 border border-slate-200">
            <div>
              <div className="text-sm font-medium text-slate-800">Automation enabled</div>
              <div className="text-xs text-slate-400 mt-0.5">
                If disabled, no automated follow-ups will be sent for this customer
              </div>
            </div>
            <button
              onClick={() => f("enabled", !form.enabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                form.enabled ? "bg-emerald-500" : "bg-slate-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  form.enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          {!form.enabled && (
            <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <PauseCircle className="w-3.5 h-3.5 flex-shrink-0" />
              Automated follow-ups are paused for this customer
            </div>
          )}

          {/* Contact name */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Contact name <span className="text-slate-400 font-normal">(overrides customer name in greeting)</span>
            </label>
            <input
              type="text"
              value={form.contact_name || ""}
              onChange={e => f("contact_name", e.target.value || null)}
              placeholder="e.g. John Smith"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Language */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Email language</label>
            <select
              value={form.preferred_language}
              onChange={e => f("preferred_language", e.target.value as "en" | "he")}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="en">English</option>
              <option value="he">Hebrew (עברית)</option>
            </select>
          </div>

          {/* Send to emails */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Override recipient emails <span className="text-slate-400 font-normal">(comma-separated; leave blank to use customer email fields)</span>
            </label>
            <textarea
              value={sendToRaw}
              onChange={e => setSendToRaw(e.target.value)}
              rows={2}
              placeholder="compliance@example.com, cto@example.com"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          {/* Follow-up overrides */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Max follow-ups <span className="text-slate-400 font-normal">(blank = global)</span>
              </label>
              <input
                type="number"
                min={0}
                max={10}
                value={form.max_followups ?? ""}
                onChange={e => f("max_followups", e.target.value ? parseInt(e.target.value) : null)}
                placeholder="3"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Follow-up delay (days)
              </label>
              <input
                type="number"
                min={1}
                max={30}
                value={form.followup_delay_days ?? ""}
                onChange={e => f("followup_delay_days", e.target.value ? parseInt(e.target.value) : null)}
                placeholder="2"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
            <textarea
              value={form.notes || ""}
              onChange={e => f("notes", e.target.value || null)}
              rows={2}
              placeholder="Internal notes about this customer's automation config…"
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : saved ? (
              <CheckCircle2 className="w-3.5 h-3.5" />
            ) : null}
            {saved ? "Saved!" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Questions Modal ───────────────────────────────────────────

function QuestionsModal({ thread, onClose }: { thread: Thread; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const qList = thread.questions_snapshot ?? [];
  const eList = thread.evidence_snapshot ?? [];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        ref={ref}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <ArrowUpRight className="w-4 h-4 text-blue-500 flex-shrink-0" />
              <span className="text-sm font-semibold text-slate-800">
                {thread.subject || "Email sent"}
              </span>
            </div>
            <div className="text-xs text-slate-400">
              {fmtFull(thread.sent_at)} · To: {thread.sent_to?.join(", ")}
            </div>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded ml-3 flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-1">
          {qList.length === 0 && eList.length === 0 && (
            <div className="text-sm text-slate-400 text-center py-6">
              No question data stored for this campaign
            </div>
          )}

          {qList.map((q, i) => (
            <div key={i} className="flex gap-3 py-2.5 border-b border-slate-50 last:border-0">
              <span className="text-xs text-slate-400 font-mono w-6 flex-shrink-0 pt-0.5">
                Q{i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 leading-snug">
                  {q.question || q.placeholder_key}
                </p>
                {q.hint && (
                  <p className="text-xs text-slate-400 mt-0.5 leading-snug">{q.hint}</p>
                )}
              </div>
            </div>
          ))}

          {eList.length > 0 && (
            <>
              <div className="pt-3 pb-1">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                  Evidence Requested
                </span>
              </div>
              {eList.map((ev, i) => (
                <div key={i} className="flex gap-3 py-2.5 border-b border-slate-50 last:border-0">
                  <Paperclip className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-amber-700 leading-snug">{ev.title}</p>
                    {ev.description && (
                      <p className="text-xs text-amber-600/70 mt-0.5 leading-snug">{ev.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 flex justify-between items-center">
          <span className="text-xs text-slate-400">
            {qList.length} question{qList.length !== 1 ? "s" : ""}
            {eList.length > 0 ? ` · ${eList.length} evidence` : ""}
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Reply Row ────────────────────────────────────────────────

function ReplyRow({ reply, isLast }: { reply: Reply; isLast: boolean }) {
  const [showSnippet, setShowSnippet] = useState(false);
  const isApplied = reply.status === "applied" || reply.status === "extracted";
  const isProcessing = reply.status === "processing" || reply.status === "received";

  return (
    <div className="flex gap-3">
      {/* Connector */}
      <div className="flex flex-col items-center flex-shrink-0 pt-1">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center border flex-shrink-0 ${
          isApplied
            ? "bg-emerald-50 border-emerald-200 text-emerald-600"
            : isProcessing
            ? "bg-blue-50 border-blue-200 text-blue-500"
            : "bg-slate-50 border-slate-200 text-slate-400"
        }`}>
          {isApplied
            ? <MailCheck className="w-3.5 h-3.5" />
            : isProcessing
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Mail className="w-3.5 h-3.5" />}
        </div>
        {!isLast && <div className="w-px flex-1 bg-slate-100 min-h-[12px] my-1" />}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${!isLast ? "pb-4" : "pb-1"}`}>
        {/* Direction + meta */}
        <div className="flex items-center gap-2 flex-wrap mb-1.5">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded-full flex-shrink-0">
            <ArrowDownLeft className="w-3 h-3" /> Reply
          </span>
          <span className="text-xs font-medium text-slate-700 truncate max-w-[200px]">
            {reply.from_email}
          </span>
          <span className="text-xs text-slate-400 flex-shrink-0">{fmtFull(reply.received_at)}</span>
          {isProcessing && (
            <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded-full font-medium">
              Processing…
            </span>
          )}
        </div>

        {/* Extraction counts */}
        <div className="flex items-center gap-2 flex-wrap mb-1.5">
          {reply.auto_applied > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
              <CheckCircle2 className="w-3 h-3" /> {reply.auto_applied} auto-applied
            </span>
          )}
          {reply.pending_review > 0 && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
              <AlertCircle className="w-3 h-3" /> {reply.pending_review} pending review
            </span>
          )}
          {isApplied && reply.total_extracted === 0 && (
            <span className="text-xs text-slate-400">No compliance data extracted</span>
          )}
        </div>

        {/* LLM notes — always visible if present */}
        {reply.extraction_notes && (
          <div className="text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2 border border-slate-100 mb-1.5">
            <Sparkles className="w-3 h-3 inline mr-1 text-violet-400 flex-shrink-0" />
            {reply.extraction_notes}
          </div>
        )}

        {/* Body excerpt toggle */}
        {reply.body_snippet && (
          <div>
            <button
              onClick={() => setShowSnippet(v => !v)}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              {showSnippet ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              {showSnippet ? "Hide" : "Show"} email excerpt
            </button>
            {showSnippet && (
              <div className="mt-1.5 text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-2 border border-slate-100 whitespace-pre-wrap break-words max-h-28 overflow-y-auto">
                {reply.body_snippet}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sent Row ──────────────────────────────────────────────────

function SentRow({
  campaign,
  isLast,
  onCancel,
  onViewQuestions,
}: {
  campaign: Thread;
  isLast: boolean;
  onCancel: () => void;
  onViewQuestions: () => void;
}) {
  const [cancelling, setCancelling] = useState(false);
  const isPending = campaign.status === "pending";
  const isCancelled = campaign.status === "cancelled";
  const qCount = campaign.questions_snapshot?.length ?? 0;
  const eCount = campaign.evidence_snapshot?.length ?? 0;

  const handleCancel = async () => {
    setCancelling(true);
    await onCancel();
    setCancelling(false);
  };

  return (
    <div className="flex gap-3">
      {/* Connector */}
      <div className="flex flex-col items-center flex-shrink-0 pt-1">
        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-blue-50 border border-blue-200 text-blue-500 flex-shrink-0">
          <ArrowUpRight className="w-3.5 h-3.5" />
        </div>
        {!isLast && <div className="w-px flex-1 bg-slate-100 min-h-[12px] my-1" />}
      </div>

      {/* Content */}
      <div className={`flex-1 min-w-0 ${!isLast ? "pb-4" : "pb-1"}`}>
        {/* Direction badge + meta */}
        <div className="flex items-start gap-2 flex-wrap mb-1">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded-full flex-shrink-0">
            <ArrowUpRight className="w-3 h-3" />
            {campaign.campaign_number > 1 ? `Follow-up #${campaign.campaign_number}` : "Sent"}
          </span>
          <span className="text-xs text-slate-400 flex-shrink-0">{fmtFull(campaign.sent_at)}</span>
          {isCancelled && (
            <span className="inline-flex items-center gap-1 text-xs text-slate-500 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded-full font-medium flex-shrink-0">
              <Ban className="w-3 h-3" /> Cancelled
            </span>
          )}
        </div>

        {/* Subject */}
        <p className="text-sm font-medium text-slate-700 truncate mb-1">
          {campaign.subject || `ISO ${campaign.iso_code} data collection`}
        </p>

        {/* Recipients + counts */}
        <div className="flex items-center gap-2 flex-wrap text-xs text-slate-400 mb-2">
          <span>To: {campaign.sent_to?.slice(0, 2).join(", ")}{(campaign.sent_to?.length ?? 0) > 2 ? ` +${campaign.sent_to.length - 2}` : ""}</span>
          <span className="text-slate-300">·</span>
          <span>{qCount} question{qCount !== 1 ? "s" : ""}{eCount > 0 ? ` · ${eCount} evidence` : ""}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onViewQuestions}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg transition-colors"
          >
            <Eye className="w-3 h-3" /> View Questions
          </button>
          {isPending && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              title="Stop follow-ups for this campaign"
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-500 hover:text-amber-600 hover:bg-amber-50 border border-slate-200 hover:border-amber-200 rounded-lg transition-colors disabled:opacity-50"
            >
              {cancelling
                ? <Loader2 className="w-3 h-3 animate-spin" />
                : <Ban className="w-3 h-3" />}
              Stop follow-ups
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Conversation Card ─────────────────────────────────────────

function ConversationCard({
  campaigns,
  onDeleteAll,
  onCancelCampaign,
  onViewQuestions,
}: {
  campaigns: Thread[];
  onDeleteAll: () => Promise<void>;
  onCancelCampaign: (id: string) => Promise<void>;
  onViewQuestions: (thread: Thread) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const first = campaigns[0];
  const summary = conversationSummary(campaigns);
  const timeline = buildTimeline(campaigns);
  const lastActivity = [...campaigns.flatMap(c => c.replies), ...campaigns]
    .map(item => ("received_at" in item ? item.received_at : (item as Thread).sent_at))
    .filter(Boolean)
    .sort()
    .at(-1);

  const handleDeleteAll = async () => {
    setDeleting(true);
    await onDeleteAll();
    setDeleting(false);
    setConfirmDelete(false);
  };

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors">
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-3 flex-1 min-w-0 text-left"
        >
          <ChevronDown className={`w-4 h-4 text-slate-400 flex-shrink-0 transition-transform ${expanded ? "" : "-rotate-90"}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-slate-800 text-sm">{first?.iso_code}</span>
              <span className="text-xs text-slate-400 truncate hidden sm:block">{first?.iso_name}</span>
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              {campaigns.length} campaign{campaigns.length !== 1 ? "s" : ""}
              {lastActivity ? ` · Last activity ${fmt(lastActivity)}` : ""}
            </div>
          </div>
        </button>

        {/* Summary badge + delete */}
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${summary.color}`}>
            {summary.label}
          </span>
          {!confirmDelete ? (
            <button
              title="Delete conversation"
              onClick={() => setConfirmDelete(true)}
              className="p-1.5 rounded hover:bg-red-50 text-slate-300 hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-red-600 font-medium">Delete all?</span>
              <button
                disabled={deleting}
                onClick={handleDeleteAll}
                className="px-2 py-0.5 bg-red-600 text-white text-xs rounded font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : "Yes"}
              </button>
              <button onClick={() => setConfirmDelete(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Timeline */}
      {expanded && (
        <div className="border-t border-slate-100 px-4 pt-4 pb-3">
          {timeline.length === 0 ? (
            <div className="flex items-center gap-2 text-xs text-slate-400 py-2">
              <Clock className="w-3.5 h-3.5" /> No activity yet
            </div>
          ) : (
            <div>
              {timeline.map((item, i) =>
                item.type === "sent" ? (
                  <SentRow
                    key={item.campaign.id}
                    campaign={item.campaign}
                    isLast={i === timeline.length - 1}
                    onCancel={() => onCancelCampaign(item.campaign.id)}
                    onViewQuestions={() => onViewQuestions(item.campaign)}
                  />
                ) : (
                  <ReplyRow
                    key={item.reply.id}
                    reply={item.reply}
                    isLast={i === timeline.length - 1}
                  />
                )
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────

const DEFAULT_CONFIG: CustomerConfig = { enabled: true, preferred_language: "en" };

export default function AutomationTab({ customerId, plans }: AutomationTabProps) {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState(plans[0]?.id || "");
  const [refreshing, setRefreshing] = useState(false);
  const [pollingInbox, setPollingInbox] = useState(false);
  const [sendSuccess, setSendSuccess] = useState(false);
  const [questionsModal, setQuestionsModal] = useState<Thread | null>(null);
  const [configModal, setConfigModal] = useState(false);
  const [customerConfig, setCustomerConfig] = useState<CustomerConfig>(DEFAULT_CONFIG);
  const [orphanOpen, setOrphanOpen] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [notifTasks, setNotifTasks] = useState<any[]>([]);
  const [notifLoading, setNotifLoading] = useState(false);

  const load = async (quiet = false) => {
    if (!quiet) setLoading(true);
    else setRefreshing(true);
    try {
      const [statusRes, cfgRes] = await Promise.all([
        api.get(`/api/v1/automation/${customerId}/status`),
        api.get(`/api/v1/automation/${customerId}/config`),
      ]);
      setStatus(statusRes.data);
      setCustomerConfig(cfgRes.data || DEFAULT_CONFIG);
    } catch {}
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => { load(); }, [customerId]);

  const sendCampaign = async (force = false) => {
    const plan = plans.find(p => p.id === selectedPlan);
    if (!plan) return;

    // Recency guard: warn if last send was within the configured follow-up delay
    if (!force) {
      const planThreads = ((status?.threads || []) as Thread[]).filter(
        (t: Thread) => t.plan_id === selectedPlan && t.sent_at,
      );
      if (planThreads.length > 0) {
        const mostRecentMs = planThreads.reduce(
          (max: number, t: Thread) => Math.max(max, new Date(t.sent_at).getTime()),
          0,
        );
        const delayMs = (customerConfig.followup_delay_days ?? 2) * 24 * 60 * 60 * 1000;
        if (Date.now() - mostRecentMs < delayMs) {
          setPendingConfirm(true);
          return;
        }
      }
    }

    setPendingConfirm(false);
    setSending(selectedPlan);
    try {
      await api.post(`/api/v1/automation/${customerId}/send-collection`, {
        plan_id: selectedPlan, iso_code: plan.iso_code, iso_name: plan.iso_name,
      });
      // Optimistically inject a thread so the recency guard works immediately on next click
      setStatus((prev: any) => ({
        ...prev,
        threads: [
          { plan_id: selectedPlan, sent_at: new Date().toISOString(), id: "optimistic", replies: [] },
          ...(prev?.threads || []),
        ],
      }));
      setSendSuccess(true);
      setTimeout(() => { setSendSuccess(false); load(true); }, 3000);
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Failed to send campaign");
    } finally {
      setSending(null);
    }
  };

  const deleteConversation = async (campaignIds: string[]) => {
    for (const id of campaignIds) {
      try { await api.delete(`/api/v1/automation/threads/${id}`); } catch {}
    }
    await load(true);
  };

  const cancelCampaign = async (campaignId: string) => {
    try {
      await api.post(`/api/v1/automation/threads/${campaignId}/cancel`, {});
      await load(true);
    } catch (e: any) {
      alert(e?.response?.data?.detail || "Failed to cancel");
    }
  };

  const triggerPoll = async () => {
    setPollingInbox(true);
    try {
      await api.post(`/api/v1/automation/trigger-imap-poll`, {});
      setTimeout(() => { load(true); setPollingInbox(false); }, 5000);
    } catch { setPollingInbox(false); }
  };

  const loadNotifTasks = async () => {
    setNotifLoading(true);
    try {
      const r = await api.get(`/api/v1/automation/outbound-tasks?limit=20`);
      const all = r.data?.items || [];
      setNotifTasks(all.filter((t: any) => t.customer_id === customerId));
    } catch {}
    setNotifLoading(false);
  };

  // Load notification tasks once on mount
  useEffect(() => { loadNotifTasks(); }, [customerId]);

  if (loading) return (
    <div className="flex items-center justify-center py-16 text-slate-400">
      <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading automation status…
    </div>
  );

  const threads: Thread[] = status?.threads || [];
  const orphanReplies: Reply[] = status?.orphan_replies || [];
  const reviewQueue: ReviewItem[] = status?.review_queue || [];
  const conversations = groupByPlanId(threads);
  const { total_campaigns = 0, total_replies = 0, auto_applied = 0, pending_review = 0 } =
    status?.summary || {};

  const statCards = [
    { label: "Campaigns Sent",   value: total_campaigns, icon: <Send className="w-4 h-4" />,         color: "blue" },
    { label: "Replies Received", value: total_replies,   icon: <Mail className="w-4 h-4" />,         color: "violet" },
    { label: "Auto-Applied",     value: auto_applied,    icon: <CheckCircle2 className="w-4 h-4" />, color: "emerald" },
    { label: "Pending Review",   value: pending_review,  icon: <AlertCircle className="w-4 h-4" />,  color: pending_review > 0 ? "amber" : "slate" },
  ];

  return (
    <div className="space-y-5 p-1">
      {/* Config modal */}
      {configModal && (
        <ConfigModal
          customerId={customerId}
          initialConfig={customerConfig}
          onClose={() => setConfigModal(false)}
          onSaved={cfg => setCustomerConfig(cfg)}
        />
      )}

      {/* Questions modal */}
      {questionsModal && (
        <QuestionsModal thread={questionsModal} onClose={() => setQuestionsModal(null)} />
      )}

      {/* Automation paused banner */}
      {!customerConfig.enabled && (
        <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
          <PauseCircle className="w-4 h-4 flex-shrink-0" />
          <span>Automated follow-ups are <strong>paused</strong> for this customer.</span>
          <button
            onClick={() => setConfigModal(true)}
            className="ml-auto text-xs text-amber-600 underline hover:no-underline"
          >
            Configure
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {statCards.map(s => (
          <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
            <div className={`text-${s.color}-500 mb-1.5`}>{s.icon}</div>
            <div className="text-2xl font-bold text-slate-900 tabular-nums">{s.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Send campaign */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <Send className="w-4 h-4 text-blue-500" /> Send Collection Campaign
          </h3>
          <button
            onClick={() => setConfigModal(true)}
            title="Customer automation settings"
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            {customerConfig.preferred_language === "he" ? "HE" : "EN"}
            {!customerConfig.enabled && <PauseCircle className="w-3 h-3 text-amber-500" />}
          </button>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={selectedPlan}
            onChange={e => { setSelectedPlan(e.target.value); setPendingConfirm(false); }}
            className="flex-1 min-w-[180px] px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            {plans.map(p => (
              <option key={p.id} value={p.id}>{p.iso_code} — {p.iso_name}</option>
            ))}
          </select>
          <button
            onClick={() => sendCampaign()}
            disabled={!!sending || !selectedPlan}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {sending === selectedPlan ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            Send Email
          </button>
          <button
            onClick={triggerPoll}
            disabled={pollingInbox}
            title="Trigger one immediate IMAP poll"
            className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            {pollingInbox ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Inbox className="w-3.5 h-3.5" />}
            {pollingInbox ? "Checking…" : "Check Inbox"}
          </button>
          <button onClick={() => load(true)} disabled={refreshing} className="p-2 hover:bg-slate-100 rounded-lg" title="Refresh">
            <RefreshCw className={`w-4 h-4 text-slate-400 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
        {sendSuccess ? (
          <div className="mt-2 flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">
            <CheckCircle2 className="w-4 h-4" /> Campaign queued — email will be sent within a few seconds.
          </div>
        ) : pendingConfirm ? (
          <div className="mt-2 flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span className="text-xs text-amber-700 flex-1">
              An email was sent recently (within the {customerConfig.followup_delay_days ?? 2}-day follow-up window). Send another?
            </span>
            <button
              onClick={() => sendCampaign(true)}
              disabled={!!sending}
              className="px-3 py-1 text-xs font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              Send anyway
            </button>
            <button
              onClick={() => setPendingConfirm(false)}
              className="px-3 py-1 text-xs text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <p className="text-xs text-slate-400 mt-2">
            Collects all pending compliance questions and evidence requests, then sends a formatted email.
            Use <strong>Check Inbox</strong> to poll immediately.
          </p>
        )}
      </div>

      {/* Review queue */}
      <ExtractionReviewPanel
        items={reviewQueue}
        onReviewed={() => load(true)}
      />

      {/* Conversations */}
      {conversations.size > 0 ? (
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2 flex items-center gap-2">
            <MessageSquare className="w-3.5 h-3.5" /> Conversations
          </h3>
          <div className="space-y-3">
            {[...conversations.entries()].map(([planId, campaigns]) => (
              <ConversationCard
                key={planId}
                campaigns={campaigns}
                onDeleteAll={() => deleteConversation(campaigns.map(c => c.id))}
                onCancelCampaign={cancelCampaign}
                onViewQuestions={setQuestionsModal}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-slate-400">
          <Mail className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <div className="text-sm font-medium">No automation activity yet</div>
          <div className="text-xs mt-1">Send a collection campaign to get started</div>
        </div>
      )}

      {/* ISO360 service status */}
      {plans.some(p => p.iso360_enabled) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-amber-600" />
            <span className="text-sm font-semibold text-amber-800">ISO360 Premium Active</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {plans.filter(p => p.iso360_enabled).map(p => (
              <span key={p.id} className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-100 text-amber-700 border border-amber-300 rounded-full text-xs font-bold">
                <Shield className="w-3 h-3" /> {p.iso_code}
              </span>
            ))}
          </div>
          <p className="text-xs text-amber-700 mt-2">
            Annual review reminders are scheduled. Evidence tasks will be auto-created on the configured annual date.
          </p>
        </div>
      )}

      {/* Notification emails sent to this customer */}
      {notifTasks.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
              <MailCheck className="w-3.5 h-3.5" /> Notification Emails
            </h3>
            <button onClick={loadNotifTasks} disabled={notifLoading}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50">
              <RefreshCw className={`w-3 h-3 ${notifLoading ? "animate-spin" : ""}`} />
            </button>
          </div>
          <div className="space-y-1.5">
            {notifTasks.map(t => {
              const typeLabel: Record<string, string> = {
                welcome_customer: "Welcome", welcome_plan: "Plan Welcome",
                announcement: "Announcement", iso360_reminder: "ISO360 Reminder",
              };
              const statusColor = t.status === "completed" ? "bg-emerald-100 text-emerald-700"
                : t.status === "failed" ? "bg-red-100 text-red-600"
                : "bg-amber-100 text-amber-700";
              return (
                <div key={t.id} className="flex items-center gap-3 px-3 py-2 bg-white border border-slate-100 rounded-lg text-xs">
                  <span className="text-slate-400 font-mono">{new Date(t.created_at).toLocaleDateString()}</span>
                  <span className="flex-1 text-slate-600 truncate">{typeLabel[t.notification_type] ?? t.notification_type ?? "—"}</span>
                  {t.last_execution?.email_address && (
                    <span className="text-slate-400 truncate max-w-[160px]">{t.last_execution.email_address}</span>
                  )}
                  <span className={`px-1.5 py-0.5 rounded-full font-semibold ${statusColor}`}>
                    {t.status === "completed" ? "Sent" : t.status === "failed" ? "Failed" : "Pending"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Orphan replies — received without a campaign token (matched by sender email or reference code) */}
      {orphanReplies.length > 0 && (
        <div className="mt-4">
          <button
            onClick={() => setOrphanOpen(v => !v)}
            className="w-full flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2 hover:text-slate-600 transition-colors group"
          >
            <span className="flex items-center gap-2">
              <Inbox className="w-3.5 h-3.5" />
              Direct Replies
              <span className="normal-case font-normal bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">
                {orphanReplies.length}
              </span>
            </span>
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${orphanOpen ? "rotate-180" : ""}`} />
          </button>
          {orphanOpen && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 space-y-3">
              <p className="text-xs text-amber-700">
                These replies arrived without a matching campaign link — the customer replied from a new
                thread or the tracking address was stripped. They were matched by sender email or reference
                code and extraction ran against all pending tasks.
              </p>
              {orphanReplies.map((reply, i) => (
                <ReplyRow key={reply.id} reply={reply} isLast={i === orphanReplies.length - 1} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
