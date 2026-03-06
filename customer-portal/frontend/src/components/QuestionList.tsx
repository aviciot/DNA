"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, CheckCircle2, Upload, AlertCircle } from "lucide-react";
import type { Question } from "./PortalClient";

interface Props {
  questions: Question[];
  onAnswered: (taskId: string, value: string) => void;
  onUploaded: (taskId: string) => void;
  dark?: boolean;
}

export default function QuestionList({ questions, onAnswered, onUploaded, dark = true }: Props) {
  const pending = questions.filter((q) => q.status === "pending");
  const done = questions.filter((q) => ["answered", "completed"].includes(q.status));

  if (questions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32" style={{ color: "var(--muted)" }}>
        <CheckCircle2 size={40} className="mb-3 opacity-30" />
        <p className="text-sm">No tasks found for this plan.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {pending.length > 0 && (
        <section>
          <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
            Pending · {pending.length}
          </div>
          <div className="space-y-2">
            {pending.map((q, i) => (
              <motion.div key={q.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                <TaskCard question={q} onAnswered={onAnswered} onUploaded={onUploaded} />
              </motion.div>
            ))}
          </div>
        </section>
      )}
      {done.length > 0 && (
        <section>
          <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
            Completed · {done.length}
          </div>
          <div className="space-y-2">
            {done.map((q) => (
              <TaskCard key={q.id} question={q} onAnswered={onAnswered} onUploaded={onUploaded} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const priorityAccent: Record<string, string> = {
  urgent: "#ef4444",
  high: "#f59e0b",
  medium: "#6366f1",
  low: "#5a5a72",
};

function TaskCard({ question: q, onAnswered, onUploaded }: {
  question: Question;
  onAnswered: (id: string, val: string) => void;
  onUploaded: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(q.status === "pending");
  const [value, setValue] = useState(q.answer || "");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const isDone = ["answered", "completed"].includes(q.status);
  const accent = priorityAccent[q.priority] || priorityAccent.medium;

  async function handleSave() {
    if (!value.trim()) return;
    setSaving(true); setError("");
    try {
      const res = await fetch("/api/portal/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: q.id, placeholder_key: q.placeholder_key || "", value }),
      });
      if (!res.ok) throw new Error("Failed");
      onAnswered(q.id, value);
      setExpanded(false);
    } catch { setError("Failed to save. Try again."); }
    finally { setSaving(false); }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`/api/portal/upload/${q.id}`, { method: "POST", body: form });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || "Upload failed"); }
      onUploaded(q.id);
      setExpanded(false);
    } catch (err: any) { setError(err.message || "Upload failed"); }
    finally { setUploading(false); }
  }

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-white/[0.02]">
        <div className="w-1 h-8 rounded-full flex-shrink-0" style={{ background: isDone ? "var(--green)" : accent }} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate" style={{ color: isDone ? "var(--muted)" : "var(--text)" }}>
            {q.title}
          </div>
          {q.requires_evidence && (
            <div className="text-xs mt-0.5 flex items-center gap-1" style={{ color: "var(--muted)" }}>
              <Upload size={10} />
              {q.evidence_uploaded ? "File uploaded" : "File required"}
            </div>
          )}
        </div>
        {isDone && <CheckCircle2 size={16} style={{ color: "var(--green)", flexShrink: 0 }} />}
        <ChevronDown size={14} style={{ color: "var(--muted)", flexShrink: 0, transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
            <div className="px-4 pb-4 pt-1 border-t space-y-3" style={{ borderColor: "var(--border)" }}>
              {q.description && <p className="text-sm" style={{ color: "var(--muted)" }}>{q.description}</p>}

              {q.requires_evidence ? (
                <div>
                  {q.evidence_description && <p className="text-xs mb-2" style={{ color: "var(--muted)" }}>{q.evidence_description}</p>}
                  {q.evidence_uploaded ? (
                    <div className="flex items-center gap-2 text-sm" style={{ color: "var(--green)" }}>
                      <CheckCircle2 size={14} /> File uploaded
                    </div>
                  ) : (
                    <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-all hover:opacity-90"
                      style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.25)" }}>
                      <Upload size={14} />
                      {uploading ? "Uploading..." : "Upload File"}
                      <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
                    </label>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <textarea value={value} onChange={(e) => setValue(e.target.value)}
                    placeholder="Type your answer here..."
                    rows={3} disabled={isDone}
                    className="w-full px-3 py-2.5 rounded-lg text-sm resize-none focus:outline-none transition-colors"
                    style={{ background: "var(--surface2)", border: "1px solid var(--border)", color: "var(--text)" }}
                  />
                  {!isDone && (
                    <button onClick={handleSave} disabled={saving || !value.trim()}
                      className="px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-40"
                      style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.3)" }}>
                      {saving ? "Saving..." : "Save Answer"}
                    </button>
                  )}
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 text-xs" style={{ color: "var(--red)" }}>
                  <AlertCircle size={12} /> {error}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
