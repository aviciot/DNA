"use client";
import { useState } from "react";
import {
  ThumbsUp, ThumbsDown, Edit3, Loader2, Sparkles, Bot,
  CheckCircle2, X, RotateCcw, PauseCircle, Paperclip,
} from "lucide-react";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────

export interface ReviewItem {
  id: string;
  item_type: "answer" | "evidence";
  placeholder_key?: string;
  task_id?: string;
  extracted_value: string;
  confidence: number;
  reasoning?: string;
  status: string;
  created_at: string;
  task_title?: string;
  customer_name?: string;  // global admin view
  customer_id?: number;    // global admin view
  iso_code?: string;       // global admin view
  plan_id?: string;
}

const CONFIDENCE_COLOR = (c: number) =>
  c >= 0.85 ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
  c >= 0.60 ? "text-amber-600 bg-amber-50 border-amber-200" :
              "text-red-600 bg-red-50 border-red-200";

const REJECT_ACTIONS = [
  {
    value: "pending" as const,
    label: "Return to pending",
    icon: RotateCcw,
    desc: "Reset this task — customer will be asked again next campaign",
    color: "text-blue-700 border-blue-200 bg-blue-50",
  },
  {
    value: "on_hold" as const,
    label: "Put on hold",
    icon: PauseCircle,
    desc: "Pause this task until manually resumed",
    color: "text-amber-700 border-amber-200 bg-amber-50",
  },
  {
    value: "rejected" as const,
    label: "Mark incorrect",
    icon: X,
    desc: "Extraction is wrong — task keeps its current status",
    color: "text-red-700 border-red-200 bg-red-50",
  },
];

// ── Single Item Card ──────────────────────────────────────────

function ReviewCard({ item, onReviewed }: { item: ReviewItem; onReviewed: () => void }) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(item.extracted_value);
  const [rejecting, setRejecting] = useState(false);
  const [rejectAction, setRejectAction] = useState<"pending" | "on_hold" | "rejected">("pending");
  const [rejectReason, setRejectReason] = useState("");
  const [rephrased, setRephrased] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"accepted" | "rejected" | null>(null);

  if (done) {
    return (
      <div className={`mx-4 my-3 p-3 rounded-xl border text-sm flex items-center gap-2 ${
        done === "accepted"
          ? "bg-emerald-50 border-emerald-200 text-emerald-700"
          : "bg-slate-50 border-slate-200 text-slate-500"
      }`}>
        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
        {done === "accepted"
          ? (item.item_type === "evidence" ? "Evidence file applied" : "Answer accepted and applied")
          : "Extraction rejected"}
      </div>
    );
  }

  const handleAccept = async () => {
    setBusy(true);
    try {
      await api.post(`/api/v1/automation/review-item/${item.id}/accept`, {
        edited_value: editing ? editValue : null,
      });
      setDone("accepted");
      setTimeout(onReviewed, 800);
    } catch {}
    setBusy(false);
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await api.post(`/api/v1/automation/review-item/${item.id}/reject`, {
        action: rejectAction,
        reason: rejectReason || null,
        rephrased_question: rejectAction === "pending" ? (rephrased || null) : null,
      });
      setDone("rejected");
      setTimeout(onReviewed, 500);
    } catch {}
    setBusy(false);
  };

  return (
    <div className="p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start gap-3">
        {/* Type badge */}
        <div className={`px-2 py-0.5 rounded-full text-xs font-semibold mt-0.5 flex-shrink-0 ${
          item.item_type === "answer" ? "bg-blue-100 text-blue-700" : "bg-orange-100 text-orange-700"
        }`}>
          {item.item_type === "answer" ? "Answer" : "Evidence"}
        </div>

        <div className="flex-1 min-w-0">
          {/* Customer context (global admin view) */}
          {item.customer_name && (
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-xs font-semibold text-slate-700">{item.customer_name}</span>
              {item.iso_code && (
                <span className="text-xs text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded font-mono">
                  {item.iso_code}
                </span>
              )}
            </div>
          )}

          {/* Task title / question */}
          {item.task_title && (
            <p className="text-xs font-medium text-slate-600 mb-1 leading-snug">
              {item.task_title}
            </p>
          )}

          {/* Placeholder key */}
          <div className="font-mono text-xs text-slate-400 mb-2">
            {item.placeholder_key || item.task_id}
          </div>

          {/* Extracted value */}
          {item.item_type === "evidence" ? (
            <div className="flex items-center gap-2 text-sm bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <Paperclip className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
              <span className="font-medium text-amber-800 truncate">{item.extracted_value}</span>
            </div>
          ) : editing ? (
            <input
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              className="w-full px-2.5 py-1.5 text-sm border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
          ) : (
            <div className="text-sm text-slate-800 bg-slate-50 rounded-lg px-3 py-2 border border-slate-100 leading-snug">
              {item.extracted_value}
            </div>
          )}

          {/* LLM reasoning */}
          {item.reasoning && (
            <div className="text-xs text-slate-400 mt-1.5 italic flex gap-1 leading-snug">
              <Sparkles className="w-3 h-3 flex-shrink-0 mt-0.5 text-violet-400" />
              {item.reasoning}
            </div>
          )}
        </div>

        {/* Confidence badge */}
        <div className={`px-2 py-0.5 rounded-full text-xs font-bold border flex-shrink-0 ${CONFIDENCE_COLOR(item.confidence)}`}>
          {(item.confidence * 100).toFixed(0)}%
        </div>
      </div>

      {/* Inline reject form */}
      {rejecting && (
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-3 space-y-2.5">
          <div className="text-xs font-semibold text-slate-600 mb-1.5">
            What should happen to this task?
          </div>

          {/* Action radio buttons */}
          <div className="space-y-1.5">
            {REJECT_ACTIONS.map(({ value, label, icon: Icon, desc, color }) => (
              <label
                key={value}
                className={`flex items-start gap-2.5 cursor-pointer p-2.5 rounded-lg border transition-colors ${
                  rejectAction === value
                    ? color
                    : "border-transparent hover:bg-white hover:border-slate-200"
                }`}
              >
                <input
                  type="radio"
                  name={`reject-action-${item.id}`}
                  value={value}
                  checked={rejectAction === value}
                  onChange={() => setRejectAction(value)}
                  className="mt-0.5 accent-slate-700 flex-shrink-0"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 text-xs font-medium">
                    <Icon className="w-3 h-3 flex-shrink-0" />
                    {label}
                  </div>
                  <div className="text-xs opacity-70 mt-0.5">{desc}</div>
                </div>
              </label>
            ))}
          </div>

          {/* Rephrased question — only when "Return to pending" */}
          {rejectAction === "pending" && (
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Rephrased question{" "}
                <span className="text-slate-400 font-normal">
                  (optional — stored in task notes for the next campaign)
                </span>
              </label>
              <textarea
                value={rephrased}
                onChange={e => setRephrased(e.target.value)}
                rows={2}
                placeholder="Make the question clearer, add context or an example…"
                className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-400 resize-none"
              />
            </div>
          )}

          {/* Reason (all actions) */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Reason <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
              placeholder="e.g. Value is incorrect, answer is incomplete…"
              className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
          </div>

          {/* Confirm row */}
          <div className="flex items-center gap-2 pt-0.5">
            <button
              onClick={handleReject}
              disabled={busy}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 disabled:opacity-50"
            >
              {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsDown className="w-3 h-3" />}
              Confirm Reject
            </button>
            <button
              onClick={() => setRejecting(false)}
              className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Normal action row */}
      {!rejecting && (
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleAccept}
            disabled={busy}
            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsUp className="w-3 h-3" />}
            {editing ? "Accept Edited" : "Accept"}
          </button>

          {item.item_type !== "evidence" && (
            !editing ? (
              <button
                onClick={() => { setEditing(true); setEditValue(item.extracted_value); }}
                className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 text-slate-600 rounded-lg text-xs font-medium hover:bg-slate-50 transition-colors"
              >
                <Edit3 className="w-3 h-3" /> Edit
              </button>
            ) : (
              <button
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 border border-slate-200 text-slate-500 rounded-lg text-xs hover:bg-slate-50"
              >
                Cancel
              </button>
            )
          )}

          <button
            onClick={() => { setRejecting(true); setEditing(false); }}
            disabled={busy}
            className="flex items-center gap-1 px-3 py-1.5 border border-red-200 text-red-600 rounded-lg text-xs font-medium hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            <ThumbsDown className="w-3 h-3" /> Reject
          </button>
        </div>
      )}
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────

interface ExtractionReviewPanelProps {
  items: ReviewItem[];
  onReviewed: () => void;
  title?: string;
}

export default function ExtractionReviewPanel({
  items,
  onReviewed,
  title = "AI Extraction — Pending Review",
}: ExtractionReviewPanelProps) {
  if (items.length === 0) return null;

  return (
    <div className="bg-white border border-amber-200 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-amber-50 border-b border-amber-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-amber-800 flex items-center gap-2">
          <Bot className="w-4 h-4" />
          {title}
          <span className="px-1.5 py-0.5 bg-amber-200 text-amber-800 text-xs rounded-full font-bold tabular-nums">
            {items.length}
          </span>
        </h3>
        <p className="text-xs text-amber-600">
          Review each extraction and decide whether to accept, edit, or reject it
        </p>
      </div>

      {/* Items */}
      <div className="divide-y divide-slate-100">
        {items.map(item => (
          <ReviewCard key={item.id} item={item} onReviewed={onReviewed} />
        ))}
      </div>
    </div>
  );
}
