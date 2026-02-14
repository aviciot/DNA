"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import axios from "axios";
import {
  ArrowLeft,
  Users,
  ClipboardList,
  FileText,
  TrendingUp,
  Mail,
  Phone,
  Calendar,
  CheckCircle2,
  Clock,
  AlertCircle,
  Upload,
  Download,
  Eye,
  Sparkles,
  Target,
  ChevronRight,
} from "lucide-react";
import TaskDetailModal from "@/components/admin/TaskDetailModal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
  email: string;
  phone?: string;
  address?: string;
  created_at: string;
}

interface Task {
  id: string;
  title: string;
  description?: string;
  status: string;
  priority: string;
  due_date?: string;
  completed_at?: string;
  requires_evidence: boolean;
  evidence_description?: string;
  plan_iso_name?: string;
  plan_iso_code?: string;
  document_id?: string;
  document_name?: string;
  template_name?: string;
  created_at: string;
}

interface Plan {
  id: string;
  customer_id: number;
  iso_standard_id: string;
  iso_code: string;
  iso_name: string;
  plan_name: string | null;
  plan_status: string;
  target_completion_date: string | null;
  created_at: string;
  total_templates: number;
  completed_templates: number;
  total_tasks: number;
  completed_tasks: number;
  progress_percentage: number;
}

interface PlanTemplate {
  id: string; // template_id
  plan_id: string;
  template_name: string;
  template_description?: string;
  iso_code?: string;
  total_tasks: number;
  completed_tasks: number;
}

export default function CustomerWorkspacePage() {
  const router = useRouter();
  const params = useParams();
  const customerId = params?.id as string;
  const { user, isAuthenticated, isLoading, fetchUser } = useAuthStore();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [planTemplates, setPlanTemplates] = useState<PlanTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"tasks" | "documents" | "template" | "progress">("documents");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Filters
  const [taskStatusFilter, setTaskStatusFilter] = useState<string>("all");
  const [taskPriorityFilter, setTaskPriorityFilter] = useState<string>("all");

  // Expandable templates
  const [expandedTemplates, setExpandedTemplates] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    } else if (!isLoading && isAuthenticated && customerId) {
      loadCustomerData();
    }
  }, [isLoading, isAuthenticated, customerId, router]);

  const loadCustomerData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const headers = { Authorization: `Bearer ${token}` };

      // Load customer details
      const customerRes = await axios.get(`${API_BASE}/api/v1/customers/${customerId}`, {
        headers,
      });
      setCustomer(customerRes.data);

      // Load tasks
      const tasksRes = await axios.get(
        `${API_BASE}/api/v1/customers/${customerId}/tasks`,
        {
          headers,
          params: { include_ignored: false },
        }
      );
      setTasks(tasksRes.data || []);

      // Load plans
      const plansRes = await axios.get(
        `${API_BASE}/api/v1/customers/${customerId}/plans`,
        { headers }
      );
      const plansData = plansRes.data?.plans || plansRes.data || [];
      setPlans(plansData);

      // Load plan templates (ISO → Templates with task stats)
      const templatesRes = await axios.get(
        `${API_BASE}/api/v1/customers/${customerId}/plan-templates`,
        { headers }
      );
      setPlanTemplates(templatesRes.data || []);
    } catch (error) {
      console.error("Failed to load customer data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task);
    setShowTaskModal(true);
  };

  const handleTaskUpdated = () => {
    loadCustomerData();
  };

  // Calculate stats
  const calculateStats = () => {
    const active = tasks.filter(
      (t) => t.status !== "completed" && t.status !== "cancelled"
    ).length;
    const completed = tasks.filter((t) => t.status === "completed").length;
    const overdue = tasks.filter(
      (t) =>
        t.due_date &&
        new Date(t.due_date) < new Date() &&
        t.status !== "completed"
    ).length;
    const progress = tasks.length > 0 ? Math.round((completed / tasks.length) * 100) : 0;

    return { active, completed, overdue, total: tasks.length, progress };
  };

  const stats = calculateStats();

  // Filter tasks
  const filteredTasks = tasks.filter((task) => {
    if (taskStatusFilter !== "all" && task.status !== taskStatusFilter) return false;
    if (taskPriorityFilter !== "all" && task.priority !== taskPriorityFilter) return false;
    return true;
  });

  const getStatusColor = (status: string) => {
    const colors: { [key: string]: string } = {
      pending: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
      in_progress: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
      on_hold: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
      completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
      cancelled: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    };
    return colors[status] || colors.pending;
  };

  const getPriorityColor = (priority: string) => {
    const colors: { [key: string]: string } = {
      low: "bg-gray-100 text-gray-600",
      medium: "bg-blue-100 text-blue-600",
      high: "bg-orange-100 text-orange-600",
      critical: "bg-red-100 text-red-600",
    };
    return colors[priority] || colors.medium;
  };

  if (isLoading || loading || !customer) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-900 dark:to-gray-800">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading workspace...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-900 dark:to-gray-800">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Back Button */}
          <button
            onClick={() => router.push("/customers")}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Customers</span>
          </button>

          {/* Customer Header */}
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center flex-shrink-0">
                <Users className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                  {customer.name}
                </h1>
                <div className="mt-2 flex flex-col gap-1 text-sm text-gray-600 dark:text-gray-400">
                  {customer.email && (
                    <div className="flex items-center gap-2">
                      <Mail className="w-4 h-4" />
                      <span>{customer.email}</span>
                    </div>
                  )}
                  {customer.phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="w-4 h-4" />
                      <span>{customer.phone}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Stats */}
            <div className="flex gap-4">
              <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                <Clock className="w-6 h-6 text-blue-600 dark:text-blue-400 mx-auto mb-1" />
                <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {stats.active}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Active</p>
              </div>
              <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-xl">
                <CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400 mx-auto mb-1" />
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {stats.completed}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Completed</p>
              </div>
              <div className="text-center p-4 bg-red-50 dark:bg-red-900/20 rounded-xl">
                <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400 mx-auto mb-1" />
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {stats.overdue}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Overdue</p>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Overall Progress
              </span>
              <span className="text-sm font-bold text-gray-900 dark:text-white">
                {stats.progress}%
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  stats.progress >= 75
                    ? "bg-gradient-to-r from-green-500 to-emerald-600"
                    : stats.progress >= 50
                    ? "bg-gradient-to-r from-blue-500 to-cyan-600"
                    : stats.progress >= 25
                    ? "bg-gradient-to-r from-yellow-500 to-orange-600"
                    : "bg-gradient-to-r from-red-500 to-rose-600"
                }`}
                style={{ width: `${stats.progress}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
          {/* Tab Navigation */}
          <div className="border-b border-gray-200 dark:border-gray-700">
            <nav className="flex">
              <button
                onClick={() => setActiveTab("documents")}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === "documents"
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                <FileText className="w-5 h-5" />
                <span>Documents</span>
              </button>
              <button
                onClick={() => setActiveTab("tasks")}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === "tasks"
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                <ClipboardList className="w-5 h-5" />
                <span>Tasks ({tasks.length})</span>
              </button>
              <button
                onClick={() => setActiveTab("template")}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === "template"
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                <Target className="w-5 h-5" />
                <span>Template ({plans.length})</span>
              </button>
              <button
                onClick={() => setActiveTab("progress")}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === "progress"
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                <TrendingUp className="w-5 h-5" />
                <span>Progress</span>
              </button>
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {/* Tasks Tab */}
            {activeTab === "tasks" && (
              <div>
                {/* Filters */}
                <div className="flex gap-4 mb-6">
                  <select
                    value={taskStatusFilter}
                    onChange={(e) => setTaskStatusFilter(e.target.value)}
                    className="px-4 py-2 border-2 border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="all">All Status</option>
                    <option value="pending">Pending</option>
                    <option value="in_progress">In Progress</option>
                    <option value="on_hold">On Hold</option>
                    <option value="completed">Completed</option>
                  </select>

                  <select
                    value={taskPriorityFilter}
                    onChange={(e) => setTaskPriorityFilter(e.target.value)}
                    className="px-4 py-2 border-2 border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="all">All Priority</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                {/* Tasks List */}
                {filteredTasks.length === 0 ? (
                  <div className="text-center py-12">
                    <Sparkles className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <p className="text-xl text-gray-600 dark:text-gray-400">
                      No tasks found
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
                      {taskStatusFilter !== "all" || taskPriorityFilter !== "all"
                        ? "Try adjusting your filters"
                        : "All tasks are completed!"}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredTasks.map((task) => (
                      <div
                        key={task.id}
                        onClick={() => handleTaskClick(task)}
                        className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-md transition-all cursor-pointer"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                              {task.title}
                            </h3>
                            {task.description && (
                              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                                {task.description}
                              </p>
                            )}
                            <div className="flex items-center gap-2 flex-wrap">
                              <span
                                className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(
                                  task.status
                                )}`}
                              >
                                {task.status.replace("_", " ")}
                              </span>
                              <span
                                className={`px-3 py-1 rounded-full text-xs font-medium ${getPriorityColor(
                                  task.priority
                                )}`}
                              >
                                {task.priority}
                              </span>
                              {task.plan_iso_code && (
                                <span className="px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300">
                                  {task.plan_iso_code}
                                </span>
                              )}
                              {task.due_date && (
                                <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                                  <Calendar className="w-3 h-3" />
                                  {new Date(task.due_date).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          </div>
                          {task.requires_evidence && (
                            <div className="ml-4">
                              <Upload className="w-5 h-5 text-orange-500" />
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Documents Tab */}
            {activeTab === "documents" && (
              <div>
                {plans.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <p className="text-xl text-gray-600 dark:text-gray-400">
                      No ISO plans assigned
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
                      No documents to display yet
                    </p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {plans.map((plan) => {
                      // Get templates for this plan
                      const templates = planTemplates.filter(
                        (tmpl) => tmpl.plan_id === plan.id
                      );

                      return (
                        <div
                          key={plan.id}
                          className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-xl border-2 border-blue-200 dark:border-blue-700 p-6"
                        >
                          {/* ISO Header */}
                          <div className="flex items-center gap-4 mb-6 pb-4 border-b border-blue-200 dark:border-blue-700">
                            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center flex-shrink-0">
                              <FileText className="w-7 h-7 text-white" />
                            </div>
                            <div className="flex-1">
                              <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                                {plan.iso_name}
                              </h3>
                              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                {plan.iso_code} • {templates.length} {templates.length === 1 ? "Template" : "Templates"}
                              </p>
                            </div>
                          </div>

                          {/* Templates */}
                          {templates.length === 0 ? (
                            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                              <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50" />
                              <p className="text-sm">No templates assigned to this ISO standard yet</p>
                            </div>
                          ) : (
                            <div className="space-y-3">
                              {templates.map((template) => {
                                const isExpanded = expandedTemplates.has(template.id);
                                // Get tasks for this plan (all tasks since they're not linked to specific templates)
                                const templateTasks = tasks.filter(t => t.plan_iso_code === plan.iso_code);

                                return (
                                  <div
                                    key={template.id}
                                    className="bg-white dark:bg-gray-800 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-600 transition-all overflow-hidden"
                                  >
                                    {/* Template Header - Clickable */}
                                    <div
                                      onClick={() => {
                                        const newExpanded = new Set(expandedTemplates);
                                        if (isExpanded) {
                                          newExpanded.delete(template.id);
                                        } else {
                                          newExpanded.add(template.id);
                                        }
                                        setExpandedTemplates(newExpanded);
                                      }}
                                      className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                                    >
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3 flex-1">
                                          <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                                            <FileText className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                                          </div>
                                          <div className="flex-1 min-w-0">
                                            <h4 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                                              {template.template_name}
                                            </h4>
                                            {template.template_description && (
                                              <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                                                {template.template_description}
                                              </p>
                                            )}
                                          </div>
                                        </div>
                                        <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                                          <div className="text-right">
                                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                              {template.total_tasks} {template.total_tasks === 1 ? "Task" : "Tasks"}
                                            </p>
                                            <p className="text-xs text-green-600 dark:text-green-400">
                                              {template.completed_tasks} completed
                                            </p>
                                          </div>
                                          <div className={`transform transition-transform ${isExpanded ? "rotate-180" : ""}`}>
                                            <ChevronRight className="w-5 h-5 text-gray-400 rotate-90" />
                                          </div>
                                        </div>
                                      </div>
                                    </div>

                                    {/* Expanded Tasks */}
                                    {isExpanded && (
                                      <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4">
                                        <div className="space-y-2">
                                          {templateTasks.map((task) => (
                                            <div
                                              key={task.id}
                                              onClick={() => handleTaskClick(task)}
                                              className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-md transition-all cursor-pointer group"
                                            >
                                              <div className="flex items-start justify-between">
                                                <div className="flex-1">
                                                  <div className="flex items-center gap-2 mb-2">
                                                    <h5 className="font-semibold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                                      {task.title}
                                                    </h5>
                                                    {task.requires_evidence && (
                                                      <div className="flex items-center gap-1 px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 rounded">
                                                        <Upload className="w-3 h-3 text-orange-600 dark:text-orange-400" />
                                                        <span className="text-xs font-medium text-orange-600 dark:text-orange-400">
                                                          Evidence
                                                        </span>
                                                      </div>
                                                    )}
                                                  </div>

                                                  {task.description && (
                                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-1">
                                                      {task.description}
                                                    </p>
                                                  )}

                                                  <div className="flex items-center gap-2 flex-wrap">
                                                    <span
                                                      className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(
                                                        task.status
                                                      )}`}
                                                    >
                                                      {task.status.replace("_", " ")}
                                                    </span>
                                                    <span
                                                      className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(
                                                        task.priority
                                                      )}`}
                                                    >
                                                      {task.priority}
                                                    </span>
                                                    {task.due_date && (
                                                      <span className="flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded-full text-xs text-gray-600 dark:text-gray-400">
                                                        <Calendar className="w-3 h-3" />
                                                        {new Date(task.due_date).toLocaleDateString()}
                                                      </span>
                                                    )}
                                                  </div>
                                                </div>

                                                {/* Task Status Icon */}
                                                <div className="ml-4 flex-shrink-0">
                                                  {task.status === "completed" ? (
                                                    <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                                                  ) : task.status === "in_progress" ? (
                                                    <Clock className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                                  ) : (
                                                    <AlertCircle className="w-5 h-5 text-gray-400" />
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Template Tab */}
            {activeTab === "template" && (
              <div>
                {plans.length === 0 ? (
                  <div className="text-center py-12">
                    <Target className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <p className="text-xl text-gray-600 dark:text-gray-400">
                      No ISO plans assigned
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
                      Contact admin to assign ISO standards
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {plans.map((plan) => (
                      <div
                        key={plan.id}
                        className="p-6 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-400 dark:hover:border-blue-600 transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                              {plan.iso_name}
                            </h3>
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                              {plan.iso_code}
                            </p>
                          </div>
                          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                            Open Template
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Progress Tab */}
            {activeTab === "progress" && (
              <div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                  <div className="p-6 bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 rounded-xl border border-blue-200 dark:border-blue-700">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                      Task Progress
                    </h3>
                    <div className="space-y-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Total Tasks</span>
                        <span className="font-bold text-gray-900 dark:text-white">
                          {stats.total}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Completed</span>
                        <span className="font-bold text-green-600 dark:text-green-400">
                          {stats.completed}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">In Progress</span>
                        <span className="font-bold text-blue-600 dark:text-blue-400">
                          {stats.active}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Overdue</span>
                        <span className="font-bold text-red-600 dark:text-red-400">
                          {stats.overdue}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="p-6 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-xl border border-purple-200 dark:border-purple-700">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                      ISO Plans
                    </h3>
                    <div className="space-y-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Active Plans</span>
                        <span className="font-bold text-gray-900 dark:text-white">
                          {plans.length}
                        </span>
                      </div>
                      {plans.map((plan) => (
                        <div key={plan.id} className="flex justify-between text-sm">
                          <span className="text-gray-600 dark:text-gray-400">
                            {plan.iso_code}
                          </span>
                          <span className="font-medium text-gray-900 dark:text-white">
                            {plan.plan_status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Timeline */}
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    Recent Activity
                  </h3>
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    Activity timeline coming soon
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Task Detail Modal */}
      {showTaskModal && selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => {
            setShowTaskModal(false);
            setSelectedTask(null);
          }}
          onTaskUpdated={handleTaskUpdated}
        />
      )}
    </div>
  );
}
