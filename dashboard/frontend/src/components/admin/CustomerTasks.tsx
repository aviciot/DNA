"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  X,
  ListChecks,
  Filter,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Search,
  ChevronDown,
  FileText,
  Shield,
  EyeOff,
} from "lucide-react";
import TaskDetailModal from "./TaskDetailModal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
}

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

interface CustomerTasksProps {
  customer: Customer;
  onClose: () => void;
  onTaskUpdate?: () => void;
}

export default function CustomerTasks({
  customer,
  onClose,
  onTaskUpdate,
}: CustomerTasksProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filteredTasks, setFilteredTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [showTaskDetail, setShowTaskDetail] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showArchived, setShowArchived] = useState(false);

  useEffect(() => {
    loadTasks();
  }, [customer.id]);

  useEffect(() => {
    filterTasks();
  }, [tasks, statusFilter, priorityFilter, searchQuery, showArchived]);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const res = await axios.get(
        `${API_BASE}/api/v1/customers/${customer.id}/tasks`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      console.log("Tasks loaded:", res.data);
      setTasks(res.data || []);
    } catch (error) {
      console.error("Error loading tasks:", error);
      alert("Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

  const filterTasks = () => {
    let filtered = [...tasks];

    // Exclude ignored/archived tasks by default
    if (!showArchived) {
      filtered = filtered.filter((t) => !t.is_ignored);
    }

    // Status filter
    if (statusFilter !== "all") {
      filtered = filtered.filter((t) => t.status === statusFilter);
    }

    // Priority filter
    if (priorityFilter !== "all") {
      filtered = filtered.filter((t) => t.priority === priorityFilter);
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          t.title.toLowerCase().includes(query) ||
          t.description?.toLowerCase().includes(query) ||
          t.plan_iso_name?.toLowerCase().includes(query)
      );
    }

    setFilteredTasks(filtered);
  };

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task);
    setShowTaskDetail(true);
  };

  const handleTaskUpdated = () => {
    loadTasks();
    if (onTaskUpdate) onTaskUpdate();
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      pending: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
      in_progress: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
      on_hold: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
      completed: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
      cancelled: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
    };

    const icons = {
      pending: Clock,
      in_progress: Loader2,
      on_hold: Clock,
      completed: CheckCircle2,
      cancelled: X,
    };

    const Icon = icons[status as keyof typeof icons] || Clock;
    const style = styles[status as keyof typeof styles] || styles.pending;

    return (
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}
      >
        <Icon className="w-3 h-3 mr-1" />
        {status.replace("_", " ")}
      </span>
    );
  };

  const getPriorityBadge = (priority: string) => {
    const styles = {
      low: "bg-gray-100 text-gray-600",
      medium: "bg-yellow-100 text-yellow-700",
      high: "bg-orange-100 text-orange-700",
      critical: "bg-red-100 text-red-700",
    };

    return (
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium ${
          styles[priority as keyof typeof styles] || styles.medium
        }`}
      >
        {priority}
      </span>
    );
  };

  const isOverdue = (dueDate: string | null) => {
    if (!dueDate) return false;
    return new Date(dueDate) < new Date();
  };

  // Calculate stats dynamically for all statuses
  const calculateStats = () => {
    const statusCounts: { [key: string]: number } = {};
    const activeStatuses = new Set<string>();

    tasks.forEach((t) => {
      if (!t.is_ignored) {
        activeStatuses.add(t.status);
        statusCounts[t.status] = (statusCounts[t.status] || 0) + 1;
      }
    });

    const overdue = tasks.filter(
      (t) => !t.is_ignored && isOverdue(t.due_date) && t.status !== "completed"
    ).length;

    const ignored = tasks.filter((t) => t.is_ignored).length;

    return { statusCounts, overdue, ignored, total: tasks.filter(t => !t.is_ignored).length };
  };

  const stats = calculateStats();

  return (
    <>
      {showTaskDetail && selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => {
            setShowTaskDetail(false);
            setSelectedTask(null);
          }}
          onTaskUpdated={handleTaskUpdated}
        />
      )}

      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <ListChecks className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Tasks</h2>
                <p className="text-sm text-white/80">{customer.name}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:bg-white/20 p-2 rounded-lg transition-all"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Stats Bar - Dynamic for all statuses */}
          <div className="p-6 bg-gray-50 dark:bg-gray-900/50 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center flex-wrap gap-4">
              {/* Total */}
              <div className="text-center px-4">
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {stats.total}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Total Active</p>
              </div>

              <div className="h-10 w-px bg-gray-300 dark:bg-gray-600" />

              {/* Dynamic Status Counts */}
              {Object.entries(stats.statusCounts).map(([status, count]) => {
                const colors: { [key: string]: string } = {
                  pending: "text-gray-600",
                  in_progress: "text-blue-600",
                  on_hold: "text-yellow-600",
                  completed: "text-green-600",
                  cancelled: "text-red-600",
                  failed: "text-red-700",
                  succeeded: "text-green-700",
                };

                return (
                  <div key={status} className="text-center px-3">
                    <p className={`text-2xl font-bold ${colors[status] || "text-gray-600"}`}>
                      {count}
                    </p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 capitalize">
                      {status.replace("_", " ")}
                    </p>
                  </div>
                );
              })}

              {stats.overdue > 0 && (
                <>
                  <div className="h-10 w-px bg-gray-300 dark:bg-gray-600" />
                  <div className="text-center px-3">
                    <p className="text-2xl font-bold text-red-600">{stats.overdue}</p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Overdue</p>
                  </div>
                </>
              )}

              {stats.ignored > 0 && (
                <>
                  <div className="h-10 w-px bg-gray-300 dark:bg-gray-600" />
                  <div className="text-center px-3">
                    <p className="text-2xl font-bold text-orange-600">{stats.ignored}</p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Archived</p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Filters */}
          <div className="p-6 border-b border-gray-200 dark:border-gray-700 space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tasks..."
                className="w-full pl-10 pr-4 py-2 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              />
            </div>

            {/* Filters */}
            <div className="flex items-center space-x-4">
              <Filter className="w-5 h-5 text-gray-500" />

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 border-2 border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="on_hold">On Hold</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="px-4 py-2 border-2 border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              >
                <option value="all">All Priority</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>

              <span className="text-sm text-gray-600 dark:text-gray-400">
                {filteredTasks.length} of {tasks.length} tasks
              </span>

              {stats.ignored > 0 && (
                <label className="flex items-center space-x-2 ml-auto cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showArchived}
                    onChange={(e) => setShowArchived(e.target.checked)}
                    className="w-4 h-4 text-orange-600 rounded focus:ring-2 focus:ring-orange-500"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Show archived ({stats.ignored})
                  </span>
                </label>
              )}
            </div>
          </div>

          {/* Task List */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="text-center py-12">
                <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-blue-600" />
                <p className="text-gray-600 dark:text-gray-400">Loading tasks...</p>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="text-center py-12">
                <ListChecks className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                <p className="text-gray-600 dark:text-gray-400">
                  {tasks.length === 0
                    ? "No tasks yet"
                    : "No tasks match your filters"}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredTasks.map((task) => (
                  <div
                    key={task.id}
                    onClick={() => handleTaskClick(task)}
                    className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-md transition-all cursor-pointer bg-white dark:bg-gray-800/50"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-1">
                          {task.title}
                        </h3>
                        {task.description && (
                          <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-1">
                            {task.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2 ml-4">
                        {getStatusBadge(task.status)}
                        {getPriorityBadge(task.priority)}
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400">
                      <div className="flex items-center space-x-4">
                        {task.plan_iso_name && (
                          <span className="flex items-center">
                            <Shield className="w-3.5 h-3.5 mr-1 text-blue-500" />
                            {task.plan_iso_code}
                          </span>
                        )}
                        {task.due_date && (
                          <span
                            className={`flex items-center ${
                              isOverdue(task.due_date) && task.status !== "completed"
                                ? "text-red-600 font-semibold"
                                : ""
                            }`}
                          >
                            <Calendar className="w-3.5 h-3.5 mr-1" />
                            Due: {new Date(task.due_date).toLocaleDateString()}
                            {isOverdue(task.due_date) && task.status !== "completed" && (
                              <span className="ml-1">(Overdue)</span>
                            )}
                          </span>
                        )}
                        {task.requires_evidence && (
                          <span className="flex items-center text-orange-600">
                            <FileText className="w-3.5 h-3.5 mr-1" />
                            Evidence Required
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
            <button
              onClick={onClose}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
