"use client";

import { useState, useEffect } from "react";
import {
  X, Edit2, Save, CheckCircle2, Calendar, FileText, Clock, Loader2,
  Shield, Flag, PlayCircle, Ban, ChevronDown, Mail, Bot, Key, Paperclip,
  UserCheck, Download, Globe,
} from "lucide-react";
import api from "@/lib/api";

interface Task {
  id: string;
  customer_id: number;
  plan_id: string;
  task_type: string;
  task_scope: string;
  section_id: string;
  title: string;
  description: string | null;
  priority: string;
  status: string;
  requires_evidence: boolean;
  evidence_description: string | null;
  auto_generated: boolean;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string | null;
  plan_iso_name: string | null;
  plan_iso_code: string | null;
  is_ignored?: boolean;
  ignored_at?: string | null;
  ignore_reason?: string | null;
  // Automation fields
  placeholder_key?: string | null;
  answered_via?: string | null;
  answer?: string | null;
  answered_at?: string | null;
  notes?: string | null;
  collection_request_id?: string | null;
  needs_human_review?: boolean;
  human_review_reason?: string | null;
  extraction_confidence?: number | null;
  extraction_reasoning?: string | null;
  reviewed_by_human?: boolean;
  evidence_files?: { filename: string; path: string; source: string; confidence?: number; reasoning?: string | null }[];
}

interface TaskDetailModalProps {
  task: Task;
  onClose: () => void;
  onTaskUpdated: () => void;
}

const CANCEL_REASONS = [
  "Not relevant to current scope",
  "Customer requested to skip",
  "Duplicate or covered elsewhere",
  "Other",
];

const HOLD_REASONS = [
  "Waiting for customer response",
  "Missing information",
  "Other",
];

const inp = "w-full px-3 py-2.5 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all text-sm";

export default function TaskDetailModal({ task, onClose, onTaskUpdated }: TaskDetailModalProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  // Edit form
  const [formData, setFormData] = useState({
    title: task.title,
    description: task.description || "",
    priority: task.priority,
    status: task.status,
    due_date: task.due_date || "",
  });

  // Cancel form
  const [showCancelForm, setShowCancelForm] = useState(false);
  const [cancelReason, setCancelReason] = useState(CANCEL_REASONS[0]);
  const [cancelOther, setCancelOther] = useState("");

  // Hold form
  const [showHoldForm, setShowHoldForm] = useState(false);
  const [holdReason, setHoldReason] = useState(HOLD_REASONS[0]);
  const [holdOther, setHoldOther] = useState("");

  // Blob URLs for evidence image previews (auth-aware fetch)
  const [blobUrls, setBlobUrls] = useState<Record<string, string>>({});
  useEffect(() => {
    const imageFiles = (task.evidence_files || []).filter(f =>
      /\.(jpe?g|png|gif|webp|bmp)$/i.test(f.filename)
    );
    if (!imageFiles.length) return;
    let cancelled = false;
    const created: string[] = [];
    (async () => {
      const urls: Record<string, string> = {};
      for (const f of imageFiles) {
        try {
          const resp = await api.get(
            `/api/v1/tasks/${task.id}/evidence/${encodeURIComponent(f.filename)}`,
            { responseType: "blob" }
          );
          const url = URL.createObjectURL(resp.data);
          created.push(url);
          urls[f.filename] = url;
        } catch { /* preview unavailable */ }
      }
      if (!cancelled) setBlobUrls(urls);
    })();
    return () => {
      cancelled = true;
      created.forEach(URL.revokeObjectURL);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task.id]);

  const downloadFile = async (filename: string) => {
    try {
      const resp = await api.get(
        `/api/v1/tasks/${task.id}/evidence/${encodeURIComponent(filename)}`,
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(""), 2500);
  };

  const handleUpdate = async () => {
    try {
      setSaving(true);
      const payload = { ...formData, due_date: formData.due_date || null };
      await api.patch(`/api/v1/tasks/${task.id}`, payload);
      showSuccess("Task updated");
      setIsEditing(false);
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      const msg = error.response?.data?.detail || error.message || "Failed to update task";
      alert(`Error: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  const handleComplete = async () => {
    if (!confirm("Mark this task as completed?")) return;
    try {
      setSaving(true);
      await api.post(`/api/v1/tasks/${task.id}/complete`, {});
      showSuccess("Task completed");
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      alert(error.response?.data?.detail || error.message || "Failed to complete task");
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    try {
      setSaving(true);
      await api.patch(`/api/v1/tasks/${task.id}`, { status: newStatus });
      showSuccess(`Status → ${newStatus.replace("_", " ")}`);
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      alert(error.response?.data?.detail || error.message || "Failed to change status");
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = async () => {
    const reason = cancelReason === "Other" ? (cancelOther.trim() || "Cancelled") : cancelReason;
    try {
      setSaving(true);
      setShowCancelForm(false);
      await api.post(`/api/v1/tasks/${task.id}/cancel`, { reason });
      showSuccess("Task cancelled");
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      alert(error.response?.data?.detail || error.message || "Failed to cancel task");
    } finally {
      setSaving(false);
    }
  };

  const handleHold = async () => {
    const reason = holdReason === "Other" ? (holdOther.trim() || "On hold") : holdReason;
    try {
      setSaving(true);
      setShowHoldForm(false);
      await api.post(`/api/v1/tasks/${task.id}/hold`, { reason });
      showSuccess("Task put on hold");
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      alert(error.response?.data?.detail || error.message || "Failed to put task on hold");
    } finally {
      setSaving(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
      in_progress: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
      completed: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
      cancelled: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
      on_hold: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
      answered: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
    };
    return (
      <span className={`px-3 py-1 rounded-full text-sm font-semibold ${styles[status] || styles.pending}`}>
        {status.replace("_", " ")}
      </span>
    );
  };

  const getPriorityColor = (p: string) =>
    ({ low: "text-gray-600", medium: "text-yellow-600", high: "text-orange-600", critical: "text-red-600" }[p] || "text-yellow-600");

  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== "completed";
  const isDone = task.status === "completed" || task.status === "cancelled";

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 flex items-center justify-between rounded-t-2xl z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-lg"><FileText className="w-5 h-5 text-white" /></div>
            <div>
              <h2 className="text-lg font-bold text-white">Task Details</h2>
              <p className="text-xs text-white/70">{task.plan_iso_code} · {task.id.slice(0, 8)}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white hover:bg-white/20 p-2 rounded-lg transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Success banner */}
        {successMsg && (
          <div className="mx-6 mt-4 px-4 py-2 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg text-sm text-green-700 dark:text-green-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> {successMsg}
          </div>
        )}

        <div className="p-6 space-y-5">
          {/* Status / Priority row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {getStatusBadge(task.status)}
              <div className="flex items-center gap-1.5">
                <Flag className={`w-4 h-4 ${getPriorityColor(task.priority)}`} />
                <span className={`text-sm font-medium ${getPriorityColor(task.priority)}`}>{task.priority} priority</span>
              </div>
            </div>
            {!isEditing && !isDone && (
              <button onClick={() => setIsEditing(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all text-sm">
                <Edit2 className="w-4 h-4" /> Edit
              </button>
            )}
          </div>

          {/* ISO badge */}
          {task.plan_iso_name && (
            <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <Shield className="w-4 h-4 text-blue-600 flex-shrink-0" />
              <span className="text-sm font-medium text-blue-900 dark:text-blue-100">{task.plan_iso_name}</span>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Title</label>
            {isEditing
              ? <input className={inp} value={formData.title} onChange={e => setFormData({ ...formData, title: e.target.value })} />
              : <p className="text-base font-semibold text-gray-900 dark:text-white">{task.title}</p>}
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Description</label>
            {isEditing
              ? <textarea className={inp} rows={3} value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} />
              : <p className="text-sm text-gray-700 dark:text-gray-300">{task.description || <span className="italic text-gray-400">No description</span>}</p>}
          </div>

          {/* Priority + Status when editing */}
          {isEditing && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Priority</label>
                <select className={inp} value={formData.priority} onChange={e => setFormData({ ...formData, priority: e.target.value })}>
                  {["low", "medium", "high", "critical"].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Status</label>
                <select className={inp} value={formData.status} onChange={e => setFormData({ ...formData, status: e.target.value })}>
                  {["pending", "in_progress", "on_hold", "completed"].map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                </select>
              </div>
            </div>
          )}

          {/* Due date */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Due Date</label>
            {isEditing
              ? <input type="date" className={inp} value={formData.due_date} onChange={e => setFormData({ ...formData, due_date: e.target.value })} />
              : task.due_date
                ? <div className="flex items-center gap-2 text-sm">
                    <Calendar className="w-4 h-4 text-gray-500" />
                    <span className={isOverdue ? "text-red-600 font-semibold" : "text-gray-900 dark:text-white"}>
                      {new Date(task.due_date).toLocaleDateString()}{isOverdue && " (Overdue)"}
                    </span>
                  </div>
                : <p className="text-sm text-gray-400 italic">No due date</p>}
          </div>

          {/* Evidence */}
          {task.requires_evidence && (
            <div className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl border border-orange-200 dark:border-orange-800">
              <div className="flex items-center gap-2 mb-1">
                <FileText className="w-4 h-4 text-orange-600" />
                <span className="text-sm font-semibold text-orange-900 dark:text-orange-100">Evidence Required</span>
              </div>
              <p className="text-xs text-orange-800 dark:text-orange-200">{task.evidence_description || "Upload supporting evidence to complete this task."}</p>
              {task.evidence_files && task.evidence_files.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Files received</p>
                  {task.evidence_files.map((f, i) => {
                    const isImage = /\.(jpe?g|png|gif|webp|bmp)$/i.test(f.filename);
                    const previewUrl = blobUrls[f.filename];
                    return (
                      <div key={i} className="rounded-xl border border-orange-200 dark:border-orange-800 overflow-hidden bg-white dark:bg-gray-700">
                        {/* Image preview */}
                        {isImage && previewUrl && (
                          <div className="bg-gray-100 dark:bg-gray-800 flex items-center justify-center max-h-48 overflow-hidden">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={previewUrl} alt={f.filename} className="max-h-48 object-contain" />
                          </div>
                        )}
                        {isImage && !previewUrl && (
                          <div className="bg-gray-100 dark:bg-gray-800 flex items-center justify-center h-16 text-xs text-gray-400">
                            <Loader2 className="w-4 h-4 animate-spin mr-1" /> Loading preview…
                          </div>
                        )}
                        {/* File row */}
                        <div className="flex items-center gap-2 px-2.5 py-1.5 text-xs">
                          <Paperclip className="w-3 h-3 text-slate-400 flex-shrink-0" />
                          <span className="flex-1 truncate font-medium text-gray-800 dark:text-gray-200">{f.filename}</span>
                          {f.confidence != null && (
                            <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded-full font-semibold">
                              {Math.round(f.confidence * 100)}%
                            </span>
                          )}
                          <button onClick={() => downloadFile(f.filename)}
                            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-600 text-gray-500 hover:text-blue-600 transition-colors">
                            <Download className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {/* LLM reasoning */}
                        {f.reasoning && (
                          <div className="px-2.5 pb-2 text-xs text-gray-500 dark:text-gray-400 italic border-t border-orange-100 dark:border-orange-900 pt-1.5">
                            {f.reasoning}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Automation context */}
          {(task.placeholder_key || task.answered_via || task.answer || task.extraction_confidence != null) && (
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700 space-y-3">
              <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5" /> Automation
              </p>

              {/* Channel badge */}
              {task.answered_via && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-28 flex-shrink-0">Answered via</span>
                  {task.answered_via === "email" ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
                      <Mail className="w-3 h-3" /> Email automation
                    </span>
                  ) : task.answered_via === "review_accepted" ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs font-medium">
                      <CheckCircle2 className="w-3 h-3" /> Manual review
                    </span>
                  ) : (task.answered_via === "customer_portal" || task.answered_via === "portal" || task.answered_via === "portal_mcp") ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">
                      <Globe className="w-3 h-3" /> Customer Portal{task.answered_by_name ? ` — ${task.answered_by_name}` : ""}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                      {task.answered_via}
                    </span>
                  )}
                </div>
              )}

              {/* Human review / Auto-applied badge */}
              {task.answered_via && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-28 flex-shrink-0">Verified by</span>
                  {task.reviewed_by_human ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 rounded-full text-xs font-semibold">
                      <UserCheck className="w-3 h-3" /> Human reviewed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300 rounded-full text-xs font-semibold">
                      <Bot className="w-3 h-3" /> Auto-applied
                    </span>
                  )}
                  {task.extraction_confidence != null && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                      task.extraction_confidence >= 0.85 ? "bg-green-100 text-green-700" :
                      task.extraction_confidence >= 0.65 ? "bg-yellow-100 text-yellow-700" :
                      "bg-red-100 text-red-600"
                    }`}>
                      {Math.round(task.extraction_confidence * 100)}% confidence
                    </span>
                  )}
                </div>
              )}

              {/* Placeholder key */}
              {task.placeholder_key && (
                <div className="flex items-start gap-2">
                  <span className="text-xs text-gray-500 w-28 flex-shrink-0 mt-0.5">Data field</span>
                  <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-0.5 rounded">
                    {task.placeholder_key}
                  </span>
                </div>
              )}

              {/* Auto-generated tag */}
              {task.auto_generated && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-28 flex-shrink-0">Origin</span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs font-medium">
                    <Bot className="w-3 h-3" /> AI generated
                  </span>
                </div>
              )}

              {/* Answer text */}
              {task.answer && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Extracted answer</p>
                  <div className="text-sm text-gray-800 dark:text-gray-200 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2 leading-relaxed">
                    {task.answer}
                  </div>
                </div>
              )}

              {/* LLM reasoning */}
              {task.extraction_reasoning && (
                <div>
                  <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <Bot className="w-3 h-3" /> LLM reasoning
                  </p>
                  <div className="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 italic leading-relaxed">
                    {task.extraction_reasoning}
                  </div>
                </div>
              )}

              {/* Notes (cancel/hold reason) */}
              {task.notes && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Notes</p>
                  <p className="text-sm text-gray-700 dark:text-gray-300 italic">{task.notes}</p>
                </div>
              )}
            </div>
          )}

          {/* Metadata — timeline */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Timeline</p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-24 flex-shrink-0">Created</span>
                <span className="text-gray-700 dark:text-gray-300">{new Date(task.created_at).toLocaleString()}</span>
              </div>
              {task.updated_at && task.updated_at !== task.created_at && (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-24 flex-shrink-0">Last updated</span>
                  <span className="text-gray-700 dark:text-gray-300">{new Date(task.updated_at).toLocaleString()}</span>
                </div>
              )}
              {task.answered_at && (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-24 flex-shrink-0">Answered</span>
                  <span className="text-emerald-700 dark:text-emerald-400 font-medium">{new Date(task.answered_at).toLocaleString()}</span>
                </div>
              )}
              {task.completed_at && (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-24 flex-shrink-0">Completed</span>
                  <span className="text-gray-700 dark:text-gray-300">{new Date(task.completed_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          {!isEditing && !isDone && (
            <div className="space-y-3 pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Quick Actions</p>

              {/* Primary */}
              <div className="grid grid-cols-2 gap-2">
                {task.status === "pending" && (
                  <button onClick={() => handleStatusChange("in_progress")} disabled={saving}
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/60 transition-all disabled:opacity-50 text-sm font-medium">
                    <PlayCircle className="w-4 h-4" /> Start
                  </button>
                )}
                <button onClick={handleComplete} disabled={saving}
                  className="flex items-center justify-center gap-2 px-4 py-2 bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 rounded-lg hover:bg-green-200 dark:hover:bg-green-900/60 transition-all disabled:opacity-50 text-sm font-medium">
                  <CheckCircle2 className="w-4 h-4" /> {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Complete"}
                </button>
              </div>

              {/* On Hold */}
              <div>
                {!showHoldForm ? (
                  <button onClick={() => { setShowHoldForm(true); setShowCancelForm(false); }} disabled={saving || task.status === "on_hold"}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 rounded-lg hover:bg-yellow-200 dark:hover:bg-yellow-900/50 transition-all disabled:opacity-50 text-sm font-medium">
                    <Clock className="w-4 h-4" /> Put On Hold
                    <ChevronDown className="w-3.5 h-3.5 ml-auto" />
                  </button>
                ) : (
                  <div className="border border-yellow-200 dark:border-yellow-700 rounded-xl p-3 bg-yellow-50 dark:bg-yellow-900/20 space-y-2">
                    <p className="text-xs font-semibold text-yellow-700 dark:text-yellow-300">Reason for holding:</p>
                    <select className="w-full px-3 py-2 border border-yellow-300 dark:border-yellow-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
                      value={holdReason} onChange={e => setHoldReason(e.target.value)}>
                      {HOLD_REASONS.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                    {holdReason === "Other" && (
                      <input className="w-full px-3 py-2 border border-yellow-300 dark:border-yellow-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
                        placeholder="Describe reason…" value={holdOther} onChange={e => setHoldOther(e.target.value)} />
                    )}
                    <div className="flex gap-2 pt-1">
                      <button onClick={handleHold} disabled={saving}
                        className="flex-1 px-3 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Confirm Hold"}
                      </button>
                      <button onClick={() => setShowHoldForm(false)}
                        className="px-3 py-1.5 text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg text-sm">
                        Back
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Cancel */}
              <div>
                {!showCancelForm ? (
                  <button onClick={() => { setShowCancelForm(true); setShowHoldForm(false); }} disabled={saving}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 transition-all disabled:opacity-50 text-sm font-medium">
                    <Ban className="w-4 h-4" /> Cancel Task
                    <ChevronDown className="w-3.5 h-3.5 ml-auto" />
                  </button>
                ) : (
                  <div className="border border-red-200 dark:border-red-700 rounded-xl p-3 bg-red-50 dark:bg-red-900/20 space-y-2">
                    <p className="text-xs font-semibold text-red-700 dark:text-red-300">Reason for cancelling:</p>
                    <select className="w-full px-3 py-2 border border-red-300 dark:border-red-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
                      value={cancelReason} onChange={e => setCancelReason(e.target.value)}>
                      {CANCEL_REASONS.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                    {cancelReason === "Other" && (
                      <input className="w-full px-3 py-2 border border-red-300 dark:border-red-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
                        placeholder="Describe reason…" value={cancelOther} onChange={e => setCancelOther(e.target.value)} />
                    )}
                    <div className="flex gap-2 pt-1">
                      <button onClick={handleCancel} disabled={saving}
                        className="flex-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Confirm Cancel"}
                      </button>
                      <button onClick={() => setShowCancelForm(false)}
                        className="px-3 py-1.5 text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg text-sm">
                        Back
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-5 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 rounded-b-2xl">
          {isEditing ? (
            <>
              <button onClick={() => { setIsEditing(false); setFormData({ title: task.title, description: task.description || "", priority: task.priority, status: task.status, due_date: task.due_date || "" }); }}
                disabled={saving}
                className="px-5 py-2.5 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-all disabled:opacity-50 text-sm">
                Cancel
              </button>
              <button onClick={handleUpdate} disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all disabled:opacity-50 text-sm">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Changes
              </button>
            </>
          ) : (
            <button onClick={onClose}
              className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all text-sm">
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
