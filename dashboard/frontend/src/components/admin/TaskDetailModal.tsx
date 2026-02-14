"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  X,
  Edit2,
  Save,
  CheckCircle2,
  Calendar,
  AlertTriangle,
  FileText,
  Clock,
  Loader2,
  Shield,
  Flag,
  PlayCircle,
  XCircle,
  Ban,
  EyeOff,
  Eye,
  AlertCircle as AlertCircleIcon,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

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
}

interface TaskDetailModalProps {
  task: Task;
  onClose: () => void;
  onTaskUpdated: () => void;
}

export default function TaskDetailModal({
  task,
  onClose,
  onTaskUpdated,
}: TaskDetailModalProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    title: task.title,
    description: task.description || "",
    priority: task.priority,
    status: task.status,
    due_date: task.due_date || "",
  });

  const handleUpdate = async () => {
    try {
      setSaving(true);
      const token = localStorage.getItem("access_token");

      await axios.patch(
        `${API_BASE}/api/v1/tasks/${task.id}`,
        formData,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert("✅ Task updated successfully!");
      setIsEditing(false);
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      console.error("Error updating task:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to update task";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setSaving(false);
    }
  };

  const handleComplete = async () => {
    if (!confirm("Mark this task as completed?")) return;

    try {
      setSaving(true);
      const token = localStorage.getItem("access_token");

      await axios.post(
        `${API_BASE}/api/v1/tasks/${task.id}/complete`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert("✅ Task completed successfully!");
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      console.error("Error completing task:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to complete task";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    try {
      setSaving(true);
      const token = localStorage.getItem("access_token");

      await axios.patch(
        `${API_BASE}/api/v1/tasks/${task.id}`,
        { status: newStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert(`✅ Task status changed to ${newStatus}!`);
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      console.error("Error changing status:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to change status";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = async () => {
    const reason = prompt(
      "Why are you cancelling this task?\n(This marks it as no longer relevant)"
    );

    if (reason === null) return; // User clicked cancel

    try {
      setSaving(true);
      const token = localStorage.getItem("access_token");

      await axios.post(
        `${API_BASE}/api/v1/tasks/${task.id}/cancel`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          params: { reason: reason || "Cancelled by user" },
        }
      );

      alert("✅ Task cancelled successfully!");
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      console.error("Error cancelling task:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to cancel task";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setSaving(false);
    }
  };

  const handlePutOnHold = async () => {
    const reason = prompt(
      "Why are you putting this task on hold?\n(Task will remain visible with 'On Hold' status)"
    );

    if (reason === null) return; // User clicked cancel

    try {
      setSaving(true);
      const token = localStorage.getItem("access_token");

      await axios.post(
        `${API_BASE}/api/v1/tasks/${task.id}/hold`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          params: { reason: reason || "On hold" },
        }
      );

      alert("✅ Task put on hold successfully!");
      onTaskUpdated();
      onClose();
    } catch (error: any) {
      console.error("Error putting task on hold:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to put task on hold";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setSaving(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      pending: "bg-gray-100 text-gray-700",
      in_progress: "bg-blue-100 text-blue-700",
      completed: "bg-green-100 text-green-700",
      cancelled: "bg-red-100 text-red-700",
      on_hold: "bg-yellow-100 text-yellow-700",
    };

    return (
      <span
        className={`px-3 py-1 rounded-full text-sm font-semibold ${
          styles[status as keyof typeof styles] || styles.pending
        }`}
      >
        {status.replace("_", " ")}
      </span>
    );
  };

  const getPriorityColor = (priority: string) => {
    const colors = {
      low: "text-gray-600",
      medium: "text-yellow-600",
      high: "text-orange-600",
      critical: "text-red-600",
    };
    return colors[priority as keyof typeof colors] || colors.medium;
  };

  const isOverdue = (dueDate: string | null) => {
    if (!dueDate) return false;
    return new Date(dueDate) < new Date() && task.status !== "completed";
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-white/20 rounded-lg">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Task Details</h2>
              <p className="text-sm text-white/80">
                {task.plan_iso_code} • ID: {task.id.slice(0, 8)}...
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-white/20 p-2 rounded-lg transition-all"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Status & Priority */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {getStatusBadge(task.status)}
              <div className="flex items-center space-x-2">
                <Flag className={`w-5 h-5 ${getPriorityColor(task.priority)}`} />
                <span className={`text-sm font-medium ${getPriorityColor(task.priority)}`}>
                  {task.priority} priority
                </span>
              </div>
            </div>
            {!isEditing && task.status !== "completed" && task.status !== "cancelled" && (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all"
              >
                <Edit2 className="w-4 h-4" />
                <span>Edit</span>
              </button>
            )}
          </div>

          {/* ISO Standard */}
          {task.plan_iso_name && (
            <div className="flex items-center space-x-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <Shield className="w-5 h-5 text-blue-600" />
              <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                {task.plan_iso_name}
              </span>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Title
            </label>
            {isEditing ? (
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              />
            ) : (
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {task.title}
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Description
            </label>
            {isEditing ? (
              <textarea
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                rows={4}
                className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all resize-none"
              />
            ) : (
              <p className="text-gray-700 dark:text-gray-300">
                {task.description || (
                  <span className="italic text-gray-500">No description</span>
                )}
              </p>
            )}
          </div>

          {/* Priority & Status */}
          {isEditing && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Priority
                </label>
                <select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Status
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                >
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="on_hold">On Hold</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
            </div>
          )}

          {/* Due Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Due Date
            </label>
            {isEditing ? (
              <input
                type="date"
                value={formData.due_date}
                onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              />
            ) : task.due_date ? (
              <div className="flex items-center space-x-2">
                <Calendar className="w-5 h-5 text-gray-500" />
                <span
                  className={`text-gray-900 dark:text-white ${
                    isOverdue(task.due_date) ? "text-red-600 font-semibold" : ""
                  }`}
                >
                  {new Date(task.due_date).toLocaleDateString()}
                  {isOverdue(task.due_date) && " (Overdue!)"}
                </span>
              </div>
            ) : (
              <p className="text-gray-500 italic">No due date set</p>
            )}
          </div>

          {/* Evidence Required */}
          {task.requires_evidence && (
            <div className="p-4 bg-orange-50 dark:bg-orange-900/20 rounded-xl border-2 border-orange-200 dark:border-orange-800">
              <div className="flex items-center space-x-2 mb-2">
                <FileText className="w-5 h-5 text-orange-600" />
                <h4 className="text-sm font-semibold text-orange-900 dark:text-orange-100">
                  Evidence Required
                </h4>
              </div>
              <p className="text-sm text-orange-800 dark:text-orange-200">
                {task.evidence_description || "Please upload supporting evidence to complete this task."}
              </p>
            </div>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Created</p>
              <p className="text-sm text-gray-900 dark:text-white">
                {new Date(task.created_at).toLocaleString()}
              </p>
            </div>
            {task.completed_at && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Completed</p>
                <p className="text-sm text-gray-900 dark:text-white">
                  {new Date(task.completed_at).toLocaleString()}
                </p>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          {!isEditing && task.status !== "completed" && task.status !== "cancelled" && (
            <div className="space-y-3 pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Quick Actions
              </p>

              {/* Primary Actions */}
              <div className="grid grid-cols-2 gap-2">
                {task.status === "pending" && (
                  <button
                    onClick={() => handleStatusChange("in_progress")}
                    disabled={saving}
                    className="flex items-center justify-center space-x-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-all disabled:opacity-50"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span className="text-sm font-medium">Start</span>
                  </button>
                )}
                {(task.status === "pending" || task.status === "in_progress" || task.status === "on_hold") && (
                  <button
                    onClick={handleComplete}
                    disabled={saving}
                    className="flex items-center justify-center space-x-2 px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition-all disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="text-sm font-medium">Complete</span>
                  </button>
                )}
              </div>

              {/* Secondary Actions */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                {task.status !== "on_hold" && (
                  <button
                    onClick={handlePutOnHold}
                    disabled={saving}
                    className="flex items-center justify-center space-x-2 px-4 py-2 bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 rounded-lg hover:bg-yellow-200 dark:hover:bg-yellow-900/50 transition-all disabled:opacity-50"
                    title="Put this task on hold temporarily"
                  >
                    <Clock className="w-4 h-4" />
                    <span className="text-sm font-medium">On Hold</span>
                  </button>
                )}
                <button
                  onClick={handleCancel}
                  disabled={saving}
                  className="flex items-center justify-center space-x-2 px-4 py-2 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 transition-all disabled:opacity-50"
                  title="Mark this task as no longer relevant"
                >
                  <Ban className="w-4 h-4" />
                  <span className="text-sm font-medium">Cancel</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 rounded-b-2xl">
          {isEditing ? (
            <>
              <button
                onClick={() => {
                  setIsEditing(false);
                  setFormData({
                    title: task.title,
                    description: task.description || "",
                    priority: task.priority,
                    status: task.status,
                    due_date: task.due_date || "",
                  });
                }}
                disabled={saving}
                className="px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-all disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdate}
                disabled={saving}
                className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-5 h-5" />
                    <span>Save Changes</span>
                  </>
                )}
              </button>
            </>
          ) : (
            <button
              onClick={onClose}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
