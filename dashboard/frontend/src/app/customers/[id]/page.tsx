"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import axios from "axios";
import {
  ArrowLeft, Users, ClipboardList, FileText, TrendingUp,
  Mail, Phone, Calendar, CheckCircle2, Clock, AlertCircle,
  Upload, Sparkles, ChevronRight, BarChart3,
  MessageSquare, ChevronDown, ThumbsUp, ShieldCheck, Pencil, Settings2, FileDown, Loader2, Plus, X, Trash2, TriangleAlert, Search, Eye,
  UserCheck, Bot,
} from "lucide-react";
import TaskDetailModal from "@/components/admin/TaskDetailModal";
import CoverageView from "@/components/admin/CoverageView";
import AutomationTab from "@/components/admin/AutomationTab";
import TemplateEditorModal, { PlaceholderEntry } from "@/components/shared/TemplateEditorModal";

import api from "@/lib/api";

/** Animates a number from 0 up to `target` over `duration` ms. Re-runs when `active` flips to true. */
function useCountUp(target: number, duration = 700, active = true): number {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!active || target === 0) { setVal(target); return; }
    setVal(0);
    let start: number | null = null;
    const raf = (ts: number) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      // Ease-out quad
      setVal(Math.round((1 - (1 - p) * (1 - p)) * target));
      if (p < 1) requestAnimationFrame(raf);
    };
    const id = requestAnimationFrame(raf);
    return () => cancelAnimationFrame(id);
  }, [target, active]);
  return val;
}

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
  updated_at?: string;
  requires_evidence: boolean;
  evidence_description?: string;
  plan_id?: string;
  plan_iso_name?: string;
  plan_iso_code?: string;
  template_id?: string;
  document_id?: string;
  document_name?: string;
  template_name?: string;
  auto_generated?: boolean;
  created_at: string;
  updated_at?: string;
  placeholder_key?: string;
  answered_via?: string;
  answer?: string;
  answered_at?: string;
  notes?: string;
  needs_human_review?: boolean;
  human_review_reason?: string;
  extraction_confidence?: number | null;
  extraction_reasoning?: string | null;
  reviewed_by_human?: boolean;
  evidence_files?: { filename: string; path: string; source: string; confidence?: number; reasoning?: string | null }[];
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
  answered_tasks: number;
  progress_percentage: number;
}

interface PlanTemplate {
  id: string;
  doc_id?: string;
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
  const { isAuthenticated, isLoading } = useAuthStore();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [planTemplates, setPlanTemplates] = useState<PlanTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [sentPlaceholderKeys, setSentPlaceholderKeys] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<"tasks" | "documents" | "progress" | "coverage" | "interview" | "automation">("documents");

  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<any>(null);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const debounceTimers = useState<Record<string, ReturnType<typeof setTimeout>>>(() => ({}))[0];
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [customizeModal, setCustomizeModal] = useState<{
    docId: string; docName: string;
    structure: Record<string, any>; dictionary: PlaceholderEntry[];
  } | null>(null);

  const [deleteDocConfirm, setDeleteDocConfirm] = useState<{
    docId: string;
    docName: string;
    totalTasks: number;
    pendingCount: number;
    nonPendingTasks: Array<{ id: string; title: string; status: string; priority: string; requires_evidence: boolean }>;
  } | null>(null);
  const [deletingDoc, setDeletingDoc] = useState(false);

  const [generatingPdf, setGeneratingPdf] = useState<string | null>(null);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const [downloadingZip, setDownloadingZip] = useState<string | null>(null);
  const [taskStatusFilter, setTaskStatusFilter] = useState<string>("all");
  const [taskPriorityFilter, setTaskPriorityFilter] = useState<string>("all");
  const [taskPlanFilter, setTaskPlanFilter] = useState<string>("all");
  const [expandedTemplates, setExpandedTemplates] = useState<Set<string>>(new Set());
  const [showAddTask, setShowAddTask] = useState(false);
  const [addingTask, setAddingTask] = useState(false);
  const [newTask, setNewTask] = useState({
    title: "", description: "", priority: "medium",
    requires_evidence: false, evidence_description: "", plan_id: "",
  });
  const [taskSearch, setTaskSearch] = useState("");
  const [excludeCancelled, setExcludeCancelled] = useState(true);
  const [interviewSearch, setInterviewSearch] = useState("");
  const [showCancelledInInterview, setShowCancelledInInterview] = useState(false);
  const [unansweredOnly, setUnansweredOnly] = useState(false);
  const [clearingReview, setClearingReview] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === "interview" && selectedPlanId && selectedPlanId !== "null") {
      loadQuestions(selectedPlanId);
    }
  }, [activeTab, selectedPlanId]);

  useEffect(() => {
    if (plans.length > 0 && !selectedPlanId) setSelectedPlanId(plans[0].id);
  }, [plans]);

  useEffect(() => {
    if (!isLoading && isAuthenticated && customerId) {
      loadCustomerData();
    }
  }, [isLoading, isAuthenticated, customerId]);

  useEffect(() => {
    if (!customerId || !isAuthenticated) return;
    const interval = setInterval(() => loadCustomerData(true), 10000);
    return () => clearInterval(interval);
  }, [customerId, isAuthenticated]);

  const loadCustomerData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const customerRes = await api.get(`/api/v1/iso-customers/${customerId}`);
      setCustomer(customerRes.data);

      const tasksRes = await api.get(`/api/v1/tasks`, { params: { customer_id: customerId, include_ignored: false } });
      setTasks(tasksRes.data || []);

      // Fetch automation sent-keys to display badge on tasks (non-blocking)
      api.get(`/api/v1/automation/${customerId}/sent-keys`).then(r => {
        setSentPlaceholderKeys(new Set(r.data?.sent_placeholder_keys || []));
      }).catch(() => {});

      const plansRes = await api.get(`/api/v1/iso-plans/customer/${customerId}`);
      const plansData = plansRes.data?.plans || plansRes.data || [];
      setPlans(plansData);

      if (plansData.length > 0) {
        const allDocs: PlanTemplate[] = [];
        await Promise.all(plansData.map(async (plan: Plan) => {
          const docsRes = await api.get(`/api/v1/iso-plans/${plan.id}/documents`).catch(() => ({ data: [] }));
          for (const d of (docsRes.data || [])) {
            allDocs.push({
              id: d.template_id,
              doc_id: d.id,
              plan_id: d.plan_id,
              template_name: d.document_name || d.template_name || "Untitled",
              template_description: d.template_description,
              total_tasks: d.total_tasks || 0,
              completed_tasks: d.completed_tasks || 0,
            });
          }
        }));
        setPlanTemplates(allDocs);
      } else {
        setPlanTemplates([]);
      }
    } catch (error) {
      console.error("Failed to load customer data:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadQuestions = async (planId: string) => {
    try {
      setQuestionsLoading(true);
      const res = await api.get(`/api/v1/customers/${customerId}/plans/${planId}/questions`);
      setQuestions(res.data);
      const vals: Record<string, string> = {};
      for (const cat of res.data.categories || []) {
        for (const q of cat.questions) {
          if (q.field_value != null) vals[q.placeholder_key] = q.field_value;
        }
      }
      setEditValues(vals);
      setExpandedCategories(new Set(res.data.categories.map((c: any) => c.category)));
    } catch (e) {
      console.error("Failed to load questions", e);
    } finally {
      setQuestionsLoading(false);
    }
  };

  const saveAnswer = async (fieldKey: string, value: string, planId: string) => {
    try {
      await api.put(`/api/v1/customers/${customerId}/profile`, {
        answers: [{ field_key: fieldKey, value }],
        plan_id: planId,
      });
      setSavedKeys(s => new Set(s).add(fieldKey));
      setTimeout(() => setSavedKeys(s => { const n = new Set(s); n.delete(fieldKey); return n; }), 2000);
      const res = await api.get(`/api/v1/customers/${customerId}/plans/${planId}/questions`);
      setQuestions(res.data);
    } catch (e) {
      console.error("Failed to save answer", e);
    }
  };

  const handleAnswerChange = (fieldKey: string, value: string, planId: string) => {
    setEditValues(v => ({ ...v, [fieldKey]: value }));
    if (debounceTimers[fieldKey]) clearTimeout(debounceTimers[fieldKey]);
    debounceTimers[fieldKey] = setTimeout(() => saveAnswer(fieldKey, value, planId), 800);
  };

  const uploadEvidence = async (taskId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    try {
      await api.post(`/api/v1/customers/${customerId}/tasks/${taskId}/evidence`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (selectedPlanId) await loadQuestions(selectedPlanId);
    } catch (e) {
      console.error("Evidence upload failed", e);
    }
  };

  const approveTask = async (taskId: string) => {
    try {
      await api.post(`/api/v1/customers/${customerId}/tasks/${taskId}/approve`);
      if (selectedPlanId) await loadQuestions(selectedPlanId);
      await loadCustomerData(true);
    } catch (e) {
      console.error("Approve failed", e);
    }
  };

  const reopenTask = async (taskId: string) => {
    try {
      await api.post(`/api/v1/customers/${customerId}/tasks/${taskId}/reopen`);
      if (selectedPlanId) await loadQuestions(selectedPlanId);
      await loadCustomerData(true);
    } catch (e) {
      console.error("Reopen failed", e);
    }
  };

  const clearHumanReview = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setClearingReview(taskId);
    try {
      await api.post(`/api/v1/tasks/${taskId}/toggle-human-review`, { needs_human_review: false });
      await loadCustomerData(true);
    } catch (err) {
      console.error("Failed to clear human review flag", err);
    } finally {
      setClearingReview(null);
    }
  };

  const generatePdf = async (docId: string, docName: string) => {
    setGeneratingPdf(docId);
    try {
      const token = localStorage.getItem("access_token");
      const r = await fetch(`/api/document-pdf?docId=${docId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(await r.text());
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${docName.replace(/\s+/g, "_")}_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("PDF generation failed", e);
    } finally {
      setGeneratingPdf(null);
    }
  };

  const downloadPlanZip = async (planId: string, isoCode: string) => {
    setDownloadingZip(planId);
    try {
      const token = localStorage.getItem("access_token");
      const r = await fetch(`/api/v1/iso-plans/${planId}/export-zip?lang=en`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(await r.text());
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${isoCode}_documents_${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("ZIP download failed", e);
    } finally {
      setDownloadingZip(null);
    }
  };

  const startCustomize = async (docId: string, docName: string) => {
    try {
      const [structureRes, dictRes] = await Promise.all([
        api.get(`/api/v1/iso-customers/${customerId}/documents/${docId}/content`),
        api.get(`/api/v1/iso-customers/${customerId}/documents/${docId}/placeholder-dictionary`),
      ]);
      setCustomizeModal({
        docId,
        docName,
        structure: structureRes.data || {},
        dictionary: dictRes.data || [],
      });
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    }
  };

  const handleCustomizeSave = async (updatedStructure: Record<string, any>, updatedDict: PlaceholderEntry[]) => {
    if (!customizeModal) return;
    const isFormal = updatedStructure.template_format === "formal" || Array.isArray(updatedStructure.sections);
    const sectionsKey = isFormal ? "sections" : "fixed_sections";
    const sectionsData = isFormal
      ? (updatedStructure.sections || [])
      : (updatedStructure.fixed_sections || []);

    await api.patch(
      `/api/v1/iso-customers/${customerId}/documents/${customizeModal.docId}/content`,
      {
        [sectionsKey]: sectionsData,
        sections_key: sectionsKey,
        placeholder_dictionary: updatedDict,
      }
    );
    setCustomizeModal(null);
    loadCustomerData(true);
  };

  const startDeleteDoc = async (docId: string, docName: string) => {
    try {
      const r = await api.get(`/api/v1/iso-customers/${customerId}/documents/${docId}/task-impact`);
      setDeleteDocConfirm({
        docId,
        docName,
        totalTasks: r.data.total_tasks,
        pendingCount: r.data.pending_count,
        nonPendingTasks: r.data.non_pending_tasks || [],
      });
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    }
  };

  const confirmDeleteDoc = async () => {
    if (!deleteDocConfirm) return;
    setDeletingDoc(true);
    try {
      await api.delete(`/api/v1/iso-customers/${customerId}/documents/${deleteDocConfirm.docId}`);
      setDeleteDocConfirm(null);
      loadCustomerData(true);
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    } finally {
      setDeletingDoc(false);
    }
  };

  const createTask = async () => {
    if (!newTask.title.trim()) return;
    setAddingTask(true);
    try {
      await api.post(`/api/v1/tasks`, {
        customer_id: parseInt(customerId),
        plan_id: newTask.plan_id || (plans[0]?.id ?? null),
        task_type: newTask.requires_evidence ? "evidence_required" : "custom",
        task_scope: "customer",
        title: newTask.title.trim(),
        description: newTask.description.trim() || null,
        priority: newTask.priority,
        requires_evidence: newTask.requires_evidence,
        evidence_description: newTask.requires_evidence ? (newTask.evidence_description || null) : null,
      });
      setNewTask({ title: "", description: "", priority: "medium", requires_evidence: false, evidence_description: "", plan_id: "" });
      setShowAddTask(false);
      loadCustomerData(true);
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    } finally {
      setAddingTask(false);
    }
  };

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task);
    setShowTaskModal(true);
  };

  const handleTaskUpdated = () => { loadCustomerData(); };

  const calculateStats = () => {
    const active = tasks.filter(t => t.status !== "completed" && t.status !== "cancelled").length;
    const completed = tasks.filter(t => t.status === "completed").length;
    const overdue = tasks.filter(t => t.due_date && new Date(t.due_date) < new Date() && t.status !== "completed").length;
    const progress = tasks.length > 0 ? Math.round((completed / tasks.length) * 100) : 0;
    return { active, completed, overdue, total: tasks.length, progress };
  };

  const stats = calculateStats();
  // answeredCount and animated values must be at component top level (Rules of Hooks)
  const answeredCount = tasks.filter(t => t.status === "answered").length;
  const animPct       = useCountUp(stats.progress, 900);
  const animCompleted = useCountUp(stats.completed, 700);
  const animAnswered  = useCountUp(answeredCount, 750);
  const animActive    = useCountUp(Math.max(0, stats.active - answeredCount), 800);
  const animOverdue   = useCountUp(stats.overdue, 600);

  const filteredTasks = tasks.filter(task => {
    if (taskStatusFilter !== "all") {
      if (task.status !== taskStatusFilter) return false;
    } else if (excludeCancelled && task.status === "cancelled") {
      return false;
    }
    if (taskPriorityFilter !== "all" && task.priority !== taskPriorityFilter) return false;
    if (taskPlanFilter !== "all" && task.plan_id !== taskPlanFilter) return false;
    if (taskSearch.trim()) {
      const q = taskSearch.toLowerCase();
      if (!task.title.toLowerCase().includes(q) && !(task.description || "").toLowerCase().includes(q)) return false;
    }
    return true;
  });
  const activeTaskCount = tasks.filter(t => t.status !== "cancelled").length;

  const getTaskRowBg = (status: string) => {
    const colors: Record<string, string> = {
      pending:     "bg-slate-50 dark:bg-slate-800/40",
      in_progress: "bg-blue-50/60 dark:bg-blue-900/20",
      on_hold:     "bg-amber-50/60 dark:bg-amber-900/20",
      completed:   "bg-emerald-50/60 dark:bg-emerald-900/20",
      cancelled:   "bg-red-50/40 dark:bg-red-900/10",
      answered:    "bg-violet-50/60 dark:bg-violet-900/20",
    };
    return colors[status] || colors.pending;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending:     "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
      in_progress: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
      on_hold:     "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
      completed:   "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
      cancelled:   "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    };
    return colors[status] || colors.pending;
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      low:      "bg-gray-100 text-gray-600",
      medium:   "bg-blue-100 text-blue-600",
      high:     "bg-orange-100 text-orange-600",
      critical: "bg-red-100 text-red-600",
    };
    return colors[priority] || colors.medium;
  };

  if (loading || !customer) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Customer Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="px-6 py-5">
          <button onClick={() => router.push("/customers")}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 mb-4 transition-colors">
            <ArrowLeft className="w-4 h-4" /> Back to Customers
          </button>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center flex-shrink-0">
                <Users className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{customer.name}</h1>
                <div className="mt-1 flex gap-3 text-sm text-gray-500">
                  {customer.email && <span className="flex items-center gap-1"><Mail className="w-3.5 h-3.5" />{customer.email}</span>}
                  {customer.phone && <span className="flex items-center gap-1"><Phone className="w-3.5 h-3.5" />{customer.phone}</span>}
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              {[{icon: Clock, val: stats.active, label: "Active", color: "blue"}, {icon: CheckCircle2, val: stats.completed, label: "Done", color: "green"}, {icon: AlertCircle, val: stats.overdue, label: "Overdue", color: "red"}].map(({icon: Icon, val, label, color}) => (
                <div key={label} className={`text-center p-3 bg-${color}-50 dark:bg-${color}-900/20 rounded-lg`}>
                  <Icon className={`w-4 h-4 text-${color}-500 mx-auto mb-0.5`} />
                  <p className={`text-xl font-bold text-${color}-600`}>{val}</p>
                  <p className="text-xs text-gray-500">{label}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-500 mb-1"><span>Progress</span><span className="font-bold text-gray-900 dark:text-white">{stats.progress}%</span></div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all" style={{ width: `${stats.progress}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-6 py-5">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
          <div className="border-b border-gray-200 dark:border-gray-700">
            <nav className="flex">
              {([
                { id: "documents", icon: FileText, label: "Documents" },
                { id: "tasks", icon: ClipboardList, label: `Tasks (${activeTaskCount})` },
                { id: "progress", icon: TrendingUp, label: "Progress" },
                { id: "coverage", icon: BarChart3, label: "Coverage" },
                { id: "interview", icon: MessageSquare, label: "Interview" },
                { id: "automation", icon: Mail, label: "Automation" },
              ] as const).map(({ id, icon: Icon, label }) => (
                <button key={id} onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === id
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                  }`}>
                  <Icon className="w-5 h-5" /><span>{label}</span>
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {/* Tasks Tab */}
            {activeTab === "tasks" && (
              <div>
                {/* Filter bar + Add button */}
                <div className="flex flex-col gap-3 mb-5">
                  <div className="flex items-center gap-3">
                    {/* Search */}
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text" value={taskSearch} onChange={e => setTaskSearch(e.target.value)}
                        placeholder="Search tasks by title or description..."
                        className="w-full pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white focus:border-blue-500 focus:outline-none"
                      />
                    </div>
                    <button
                      onClick={() => { setShowAddTask(v => !v); }}
                      className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors flex-shrink-0"
                    >
                      <Plus className="w-4 h-4" /> Add Task
                    </button>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <select value={taskStatusFilter} onChange={e => setTaskStatusFilter(e.target.value)}
                      className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white focus:border-blue-500">
                      <option value="all">All Status</option>
                      <option value="pending">Pending</option>
                      <option value="in_progress">In Progress</option>
                      <option value="on_hold">On Hold</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                    <select value={taskPriorityFilter} onChange={e => setTaskPriorityFilter(e.target.value)}
                      className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white focus:border-blue-500">
                      <option value="all">All Priority</option>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                    {plans.length > 1 && (
                      <select value={taskPlanFilter} onChange={e => setTaskPlanFilter(e.target.value)}
                        className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white focus:border-blue-500">
                        <option value="all">All ISO Plans</option>
                        {plans.map(p => (
                          <option key={p.id} value={p.id}>{p.iso_code} — {p.iso_name}</option>
                        ))}
                      </select>
                    )}
                    <label className="flex items-center gap-2 cursor-pointer select-none ml-1">
                      <input
                        type="checkbox" checked={excludeCancelled}
                        onChange={e => setExcludeCancelled(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-600 dark:text-gray-400">Exclude cancelled</span>
                    </label>
                    {(taskSearch || taskStatusFilter !== "all" || taskPriorityFilter !== "all" || taskPlanFilter !== "all") && (
                      <button onClick={() => { setTaskSearch(""); setTaskStatusFilter("all"); setTaskPriorityFilter("all"); setTaskPlanFilter("all"); }}
                        className="text-xs text-blue-600 hover:underline">
                        Clear filters
                      </button>
                    )}
                    <span className="ml-auto text-xs text-gray-400">{filteredTasks.length} task{filteredTasks.length !== 1 ? "s" : ""}</span>
                  </div>
                </div>

                {/* Inline Add Task form */}
                {showAddTask && (
                  <div className="bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-200 dark:border-blue-700 rounded-xl p-5 mb-5">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-sm font-semibold text-slate-800 dark:text-white">New Manual Task</h4>
                      <button onClick={() => setShowAddTask(false)} className="p-1 hover:bg-white/50 rounded-lg">
                        <X className="w-4 h-4 text-slate-400" />
                      </button>
                    </div>
                    <div className="space-y-3">
                      <input
                        placeholder="Task title *"
                        value={newTask.title}
                        onChange={e => setNewTask(v => ({ ...v, title: e.target.value }))}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <textarea
                        placeholder="Description (optional)"
                        value={newTask.description}
                        onChange={e => setNewTask(v => ({ ...v, description: e.target.value }))}
                        rows={2}
                        className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      />
                      <div className="flex gap-3">
                        <div className="flex-1">
                          <label className="block text-xs font-medium text-slate-500 mb-1">Priority</label>
                          <select
                            value={newTask.priority}
                            onChange={e => setNewTask(v => ({ ...v, priority: e.target.value }))}
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="urgent">Urgent</option>
                          </select>
                        </div>
                        {plans.length > 1 && (
                          <div className="flex-1">
                            <label className="block text-xs font-medium text-slate-500 mb-1">Plan</label>
                            <select
                              value={newTask.plan_id || plans[0]?.id}
                              onChange={e => setNewTask(v => ({ ...v, plan_id: e.target.value }))}
                              className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                              {plans.map(p => <option key={p.id} value={p.id}>{p.iso_code}</option>)}
                            </select>
                          </div>
                        )}
                      </div>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={newTask.requires_evidence}
                          onChange={e => setNewTask(v => ({ ...v, requires_evidence: e.target.checked }))}
                          className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-slate-700">Requires evidence upload</span>
                      </label>
                      {newTask.requires_evidence && (
                        <input
                          placeholder="Evidence description (e.g. 'Upload signed policy document')"
                          value={newTask.evidence_description}
                          onChange={e => setNewTask(v => ({ ...v, evidence_description: e.target.value }))}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      )}
                    </div>
                    <div className="flex justify-end gap-2 mt-4">
                      <button onClick={() => setShowAddTask(false)}
                        className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
                        Cancel
                      </button>
                      <button
                        onClick={createTask}
                        disabled={addingTask || !newTask.title.trim()}
                        className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
                      >
                        {addingTask ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                        Create Task
                      </button>
                    </div>
                  </div>
                )}

                {filteredTasks.length === 0 ? (
                  <div className="text-center py-12">
                    <Sparkles className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <p className="text-xl text-gray-600 dark:text-gray-400">No tasks found</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredTasks.map(task => (
                      <div key={task.id} onClick={() => handleTaskClick(task)}
                        className={`p-4 border rounded-xl hover:border-blue-400 hover:shadow-md transition-all cursor-pointer ${task.needs_human_review ? "border-orange-300 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/10" : `border-gray-200 dark:border-gray-700 ${getTaskRowBg(task.status)}`}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{task.title}</h3>
                              {task.needs_human_review && (
                                <span className="text-[10px] px-1.5 py-0.5 bg-orange-100 text-orange-600 dark:bg-orange-900/40 dark:text-orange-400 rounded-full font-medium">
                                  Needs review
                                </span>
                              )}
                            </div>
                            {task.needs_human_review && task.human_review_reason && (
                              <p className="text-xs text-orange-600 dark:text-orange-400 mb-1">{task.human_review_reason}</p>
                            )}
                            {task.description && <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{task.description}</p>}
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>{task.status.replace("_", " ")}</span>
                              <span className={`px-3 py-1 rounded-full text-xs font-medium ${getPriorityColor(task.priority)}`}>{task.priority}</span>
                              {task.plan_iso_code && <span className="px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-600">{task.plan_iso_code}</span>}
                              {task.due_date && <span className="flex items-center gap-1 text-xs text-gray-500"><Calendar className="w-3 h-3" />{new Date(task.due_date).toLocaleDateString()}</span>}
                              {task.answered_via === "email" && <span className="flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium"><Mail className="w-3 h-3" />Via Email</span>}
                              {task.answered_via !== "email" && task.placeholder_key && sentPlaceholderKeys.has(task.placeholder_key) && task.status === "pending" && <span className="flex items-center gap-1 px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs font-medium"><Mail className="w-3 h-3" />Sent</span>}
                              {task.reviewed_by_human && <span title="Human reviewed" className="flex items-center gap-1 px-2 py-0.5 bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 rounded-full text-xs font-semibold"><UserCheck className="w-3 h-3" />Reviewed</span>}
                              {!task.reviewed_by_human && task.answered_via === "email" && task.status !== "pending" && <span title="Auto-applied by AI" className="flex items-center gap-1 px-2 py-0.5 bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300 rounded-full text-xs font-semibold"><Bot className="w-3 h-3" />Auto</span>}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                            {task.needs_human_review && (
                              <button
                                onClick={(e) => clearHumanReview(task.id, e)}
                                disabled={clearingReview === task.id}
                                title="Clear review flag — return to normal extraction"
                                className="p-1.5 rounded-lg text-orange-500 hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors disabled:opacity-50"
                              >
                                {clearingReview === task.id
                                  ? <Loader2 className="w-4 h-4 animate-spin" />
                                  : <X className="w-4 h-4" />}
                              </button>
                            )}
                            {task.requires_evidence && <Upload className="w-5 h-5 text-orange-500" />}
                          </div>
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
                    <p className="text-xl text-gray-600 dark:text-gray-400">No ISO plans assigned</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {plans.map(plan => {
                      const templates = planTemplates.filter(t => t.plan_id === plan.id);
                      return (
                        <div key={plan.id} className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-xl border-2 border-blue-200 dark:border-blue-700 p-6">
                          <div className="flex items-center gap-4 mb-6 pb-4 border-b border-blue-200 dark:border-blue-700">
                            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center flex-shrink-0">
                              <FileText className="w-7 h-7 text-white" />
                            </div>
                            <div className="flex-1">
                              <h3 className="text-2xl font-bold text-gray-900 dark:text-white">{plan.iso_name}</h3>
                              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{plan.iso_code} • {templates.length} {templates.length === 1 ? "Template" : "Templates"}</p>
                            </div>
                            {templates.length > 0 && (
                              <button
                                onClick={() => downloadPlanZip(plan.id, plan.iso_code)}
                                disabled={downloadingZip === plan.id}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 rounded-lg transition-colors disabled:opacity-50 flex-shrink-0"
                              >
                                {downloadingZip === plan.id
                                  ? <Loader2 className="w-4 h-4 animate-spin" />
                                  : <FileDown className="w-4 h-4" />}
                                Download All
                              </button>
                            )}
                          </div>
                          {templates.length === 0 ? (
                            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                              <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50" />
                              <p className="text-sm">No templates assigned yet</p>
                            </div>
                          ) : (
                            <div className="space-y-3">
                              {templates.map(template => {
                                const isExpanded = expandedTemplates.has(template.id);
                                const templateTasks = tasks.filter(t =>
                                  template.doc_id ? t.document_id === template.doc_id : t.template_id === template.id
                                );
                                return (
                                  <div key={template.id} className="bg-white dark:bg-gray-800 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-blue-400 transition-all overflow-hidden">
                                    {/* Template Header */}
                                    <div className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                                      <div className="flex items-center justify-between">
                                        <div
                                          onClick={() => { const n = new Set(expandedTemplates); if (isExpanded) n.delete(template.id); else n.add(template.id); setExpandedTemplates(n); }}
                                          className="flex items-center gap-3 flex-1 cursor-pointer"
                                        >
                                          <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                                            <FileText className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                                          </div>
                                          <div className="flex-1 min-w-0">
                                            <h4 className="text-lg font-semibold text-gray-900 dark:text-white truncate">{template.template_name}</h4>
                                            {template.template_description && <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{template.template_description}</p>}
                                          </div>
                                        </div>
                                        <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                                          {template.doc_id && (
                                            <button
                                              onClick={e => { e.stopPropagation(); startCustomize(template.doc_id!, template.template_name); }}
                                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-violet-50 text-violet-600 hover:bg-violet-100 rounded-lg transition-colors"
                                            >
                                              <Settings2 className="w-3.5 h-3.5" /> Customize
                                            </button>
                                          )}
                                          {template.doc_id && (
                                            <button
                                              onClick={e => { e.stopPropagation(); generatePdf(template.doc_id!, template.template_name); }}
                                              disabled={generatingPdf === template.doc_id}
                                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-50 text-emerald-600 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-50"
                                            >
                                              {generatingPdf === template.doc_id
                                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                : <FileDown className="w-3.5 h-3.5" />}
                                              PDF
                                            </button>
                                          )}
                                          {template.doc_id && (
                                            <button
                                              onClick={e => { e.stopPropagation(); setPreviewDocId(template.doc_id!); }}
                                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 rounded-lg transition-colors"
                                            >
                                              <Eye className="w-3.5 h-3.5" /> Preview
                                            </button>
                                          )}
                                          {template.doc_id && (
                                            <button
                                              onClick={e => { e.stopPropagation(); startDeleteDoc(template.doc_id!, template.template_name); }}
                                              className="flex items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-red-400 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors"
                                              title="Delete this document"
                                            >
                                              <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                          )}
                                          <div className="text-right">
                                            <p className="text-sm font-semibold text-gray-900 dark:text-white">{template.total_tasks} {template.total_tasks === 1 ? "Task" : "Tasks"}</p>
                                            <p className="text-xs text-green-600 dark:text-green-400">{template.completed_tasks} completed</p>
                                          </div>
                                          <div
                                            onClick={() => { const n = new Set(expandedTemplates); if (isExpanded) n.delete(template.id); else n.add(template.id); setExpandedTemplates(n); }}
                                            className={`transform transition-transform cursor-pointer ${isExpanded ? "rotate-180" : ""}`}
                                          >
                                            <ChevronRight className="w-5 h-5 text-gray-400 rotate-90" />
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                    {/* Expanded Tasks */}
                                    {isExpanded && (
                                      <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4">
                                        <div className="space-y-2">
                                          {templateTasks.map(task => (
                                            <div key={task.id} onClick={() => handleTaskClick(task)}
                                              className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-400 hover:shadow-md transition-all cursor-pointer group">
                                              <div className="flex items-start justify-between">
                                                <div className="flex-1">
                                                  <div className="flex items-center gap-2 mb-2">
                                                    <h5 className="font-semibold text-gray-900 dark:text-white group-hover:text-blue-600 transition-colors">{task.title}</h5>
                                                    {task.requires_evidence && (
                                                      <div className="flex items-center gap-1 px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 rounded">
                                                        <Upload className="w-3 h-3 text-orange-600" />
                                                        <span className="text-xs font-medium text-orange-600">Evidence</span>
                                                      </div>
                                                    )}
                                                  </div>
                                                  {task.description && <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-1">{task.description}</p>}
                                                  <div className="flex items-center gap-2 flex-wrap">
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>{task.status.replace("_", " ")}</span>
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(task.priority)}`}>{task.priority}</span>
                                                    {task.due_date && <span className="flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded-full text-xs text-gray-600"><Calendar className="w-3 h-3" />{new Date(task.due_date).toLocaleDateString()}</span>}
                                                    {task.answered_via === "email" && <span className="flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium"><Mail className="w-3 h-3" />Via Email</span>}
                                                    {task.answered_via !== "email" && task.placeholder_key && sentPlaceholderKeys.has(task.placeholder_key) && task.status === "pending" && <span className="flex items-center gap-1 px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs font-medium"><Mail className="w-3 h-3" />Sent</span>}
                                                  </div>
                                                </div>
                                                <div className="ml-4 flex-shrink-0">
                                                  {task.status === "completed" ? <CheckCircle2 className="w-5 h-5 text-green-600" /> : task.status === "in_progress" ? <Clock className="w-5 h-5 text-blue-600" /> : <AlertCircle className="w-5 h-5 text-gray-400" />}
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


            {/* Progress Tab */}
            {activeTab === "progress" && (
              <div>
                {/* ── Hero stats ── */}
                {(() => {
                  const r = 64, circ = 2 * Math.PI * r;
                  const donePct = stats.total > 0 ? stats.completed / stats.total : 0;
                  const answeredPct = stats.total > 0 ? answeredCount / stats.total : 0;
                  const activePct = stats.total > 0 ? Math.max(0, stats.active - answeredCount) / stats.total : 0;

                  // Multi-segment donut offsets (rotate-90 origin = top)
                  const doneOffset = 0;
                  const answeredOffset = donePct * circ;
                  const activeOffset = (donePct + answeredPct) * circ;

                  return (
                    <div className="bg-white rounded-2xl border border-slate-100 p-6 mb-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row items-center gap-8">

                        {/* Big completion ring — animates via CSS transition on stroke-dasharray */}
                        <div className="relative flex-shrink-0" style={{ width: 152, height: 152 }}>
                          <svg width="152" height="152" className="-rotate-90" style={{ position: "absolute" }}>
                            <circle cx="76" cy="76" r={r} fill="none" stroke="#f1f5f9" strokeWidth="13" />
                            {donePct > 0 && (
                              <circle cx="76" cy="76" r={r} fill="none" stroke="#10b981" strokeWidth="13"
                                strokeDasharray={`${donePct * circ} ${circ}`}
                                strokeDashoffset={-doneOffset}
                                strokeLinecap="butt" style={{ transition: "stroke-dasharray 1s ease" }} />
                            )}
                            {answeredPct > 0 && (
                              <circle cx="76" cy="76" r={r} fill="none" stroke="#8b5cf6" strokeWidth="13"
                                strokeDasharray={`${answeredPct * circ} ${circ}`}
                                strokeDashoffset={-answeredOffset}
                                strokeLinecap="butt" style={{ transition: "stroke-dasharray 1s ease" }} />
                            )}
                            {activePct > 0 && (
                              <circle cx="76" cy="76" r={r} fill="none" stroke="#3b82f6" strokeWidth="13"
                                strokeDasharray={`${activePct * circ} ${circ}`}
                                strokeDashoffset={-activeOffset}
                                strokeLinecap="butt" style={{ transition: "stroke-dasharray 1s ease" }} />
                            )}
                          </svg>
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-4xl font-black text-slate-900 leading-none">{animPct}</span>
                            <span className="text-sm font-semibold text-slate-400 mt-0.5">%</span>
                            <span className="text-xs text-slate-400 mt-1">done</span>
                          </div>
                        </div>

                        {/* Stat chips — numbers count up on load */}
                        <div className="grid grid-cols-2 gap-3 flex-1 w-full">
                          {([
                            { label: "Completed", value: animCompleted, raw: stats.completed, color: "#10b981", bg: "#ecfdf5", Icon: CheckCircle2 },
                            { label: "Answered", value: animAnswered, raw: answeredCount, color: "#8b5cf6", bg: "#f5f3ff", Icon: Sparkles, sub: "awaiting review" },
                            { label: "In Progress", value: animActive, raw: Math.max(0, stats.active - answeredCount), color: "#3b82f6", bg: "#eff6ff", Icon: Clock },
                            { label: "Overdue", value: animOverdue, raw: stats.overdue, color: "#ef4444", bg: "#fef2f2", Icon: AlertCircle },
                          ] as { label: string; value: number; raw: number; color: string; bg: string; Icon: any; sub?: string }[]).map(({ label, value, raw, color, bg, Icon, sub }) => (
                            <div key={label} className="rounded-xl p-4" style={{ backgroundColor: bg }}>
                              <div className="flex items-center gap-1.5 mb-2">
                                <Icon className="w-3.5 h-3.5" style={{ color }} />
                                <span className="text-xs font-semibold text-slate-500">{label}</span>
                              </div>
                              <p className="text-3xl font-black leading-none mb-2" style={{ color }}>{value}</p>
                              <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: color + "25" }}>
                                <div className="h-1.5 rounded-full transition-all duration-700"
                                  style={{ width: `${stats.total > 0 ? Math.min(100, Math.round(raw / stats.total * 100)) : 0}%`, backgroundColor: color }} />
                              </div>
                              {sub && <p className="text-xs mt-1.5" style={{ color }}>{sub}</p>}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Segmented bar footer */}
                      <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between gap-4">
                        <span className="text-sm text-slate-400">{stats.total} tasks total</span>
                        {stats.total > 0 && (
                          <div className="flex items-center gap-3 flex-1 max-w-xs">
                            <div className="flex-1 h-2 rounded-full overflow-hidden bg-slate-100 flex">
                              <div style={{ width: `${stats.completed / stats.total * 100}%`, backgroundColor: "#10b981", transition: "width 0.8s" }} />
                              <div style={{ width: `${answeredCount / stats.total * 100}%`, backgroundColor: "#8b5cf6", transition: "width 0.8s" }} />
                              <div style={{ width: `${Math.max(0, stats.active - answeredCount) / stats.total * 100}%`, backgroundColor: "#3b82f6", transition: "width 0.8s" }} />
                            </div>
                            <span className="text-xs text-slate-400 flex-shrink-0">{stats.completed + answeredCount}/{stats.total}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* ── Per-plan cards (data comes from plan's own task stats) ── */}
                {plans.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                    {plans.map(plan => {
                      // Use plan-level task stats computed by backend (not filtered from task array)
                      const planDone = plan.completed_tasks ?? 0;
                      const planAnswered = plan.answered_tasks ?? 0;
                      const planTotal = plan.total_tasks ?? 0;
                      const planPct = plan.progress_percentage ?? 0;
                      const sColors: Record<string, string> = { active: "#3b82f6", completed: "#10b981", paused: "#f59e0b", pending: "#94a3b8", in_progress: "#3b82f6" };
                      const sColor = sColors[plan.plan_status] ?? "#94a3b8";
                      const shortCode = plan.iso_code.replace("ISO/IEC ", "").replace("ISO ", "");
                      const r = 28, circ = 2 * Math.PI * r;
                      const donePct = planTotal > 0 ? planDone / planTotal : 0;
                      const answeredPct = planTotal > 0 ? planAnswered / planTotal : 0;
                      return (
                        <div key={plan.id} className="bg-white rounded-xl border border-slate-100 p-5 shadow-sm">
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0"
                                style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
                                {shortCode.slice(0, 6)}
                              </div>
                              <div>
                                <p className="text-sm font-bold text-slate-900">{plan.iso_code}</p>
                                <p className="text-xs text-slate-400 leading-tight">{plan.iso_name}</p>
                              </div>
                            </div>
                            <span className="text-xs font-semibold px-2 py-0.5 rounded-full capitalize flex-shrink-0"
                              style={{ color: sColor, backgroundColor: sColor + "18" }}>
                              {plan.plan_status.replace("_", " ")}
                            </span>
                          </div>

                          <div className="flex items-center gap-5">
                            {/* Mini donut ring */}
                            <div className="relative flex-shrink-0" style={{ width: 68, height: 68 }}>
                              <svg width="68" height="68" className="-rotate-90" style={{ position: "absolute" }}>
                                <circle cx="34" cy="34" r={r} fill="none" stroke="#f1f5f9" strokeWidth="6" />
                                {donePct > 0 && (
                                  <circle cx="34" cy="34" r={r} fill="none" stroke="#10b981" strokeWidth="6"
                                    strokeDasharray={`${donePct * circ} ${circ}`}
                                    strokeLinecap="butt" style={{ transition: "stroke-dasharray 1.2s ease" }} />
                                )}
                                {answeredPct > 0 && (
                                  <circle cx="34" cy="34" r={r} fill="none" stroke="#8b5cf6" strokeWidth="6"
                                    strokeDasharray={`${answeredPct * circ} ${circ}`}
                                    strokeDashoffset={-(donePct * circ)}
                                    strokeLinecap="butt" style={{ transition: "stroke-dasharray 1.2s ease" }} />
                                )}
                              </svg>
                              <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-base font-black text-slate-900 leading-none">{planPct}</span>
                                <span className="text-[9px] text-slate-400">%</span>
                              </div>
                            </div>

                            {/* Stats */}
                            <div className="flex-1">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-slate-400">{planDone + planAnswered} / {planTotal} tasks</span>
                              </div>
                              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden flex">
                                <div style={{ width: `${planTotal > 0 ? planDone / planTotal * 100 : 0}%`, backgroundColor: "#10b981", transition: "width 1.2s ease" }} />
                                <div style={{ width: `${planTotal > 0 ? planAnswered / planTotal * 100 : 0}%`, backgroundColor: "#8b5cf6", transition: "width 1.2s ease" }} />
                              </div>
                              <div className="flex items-center gap-3 mt-2">
                                {planDone > 0 && <span className="flex items-center gap-1 text-xs text-emerald-600"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />{planDone} done</span>}
                                {planAnswered > 0 && <span className="flex items-center gap-1 text-xs text-violet-600"><span className="w-1.5 h-1.5 rounded-full bg-violet-500 inline-block" />{planAnswered} answered</span>}
                                {planTotal > 0 && planDone + planAnswered < planTotal && (
                                  <span className="text-xs text-slate-400">{planTotal - planDone - planAnswered} pending</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Activity</h3>
                  {tasks.length === 0 ? (
                    <div className="text-center py-8 text-gray-400 text-sm">No tasks yet</div>
                  ) : (
                    (() => {
                      const sorted = [...tasks].sort((a, b) =>
                        new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()
                      );
                      const todayMidnight = new Date(); todayMidnight.setHours(0, 0, 0, 0);
                      const yesterdayMidnight = new Date(todayMidnight); yesterdayMidnight.setDate(yesterdayMidnight.getDate() - 1);
                      const getDateLabel = (ds: string) => {
                        const d = new Date(ds); d.setHours(0, 0, 0, 0);
                        if (d.getTime() === todayMidnight.getTime()) return "Today";
                        if (d.getTime() === yesterdayMidnight.getTime()) return "Yesterday";
                        return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
                      };
                      const getTimeStr = (ds: string) => new Date(ds).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
                      const groups: { label: string; tasks: Task[] }[] = [];
                      for (const task of sorted) {
                        const label = getDateLabel(task.updated_at || task.created_at);
                        const last = groups[groups.length - 1];
                        if (last && last.label === label) last.tasks.push(task);
                        else groups.push({ label, tasks: [task] });
                      }
                      return (
                        <div className="space-y-4">
                          {groups.map(group => (
                            <div key={group.label}>
                              <div className="flex items-center gap-2 mb-2">
                                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{group.label}</span>
                                <div className="flex-1 h-px bg-gray-100 dark:bg-gray-700" />
                              </div>
                              <div className="space-y-1.5">
                                {group.tasks.map(task => (
                                  <div key={task.id} onClick={() => handleTaskClick(task)}
                                    className={`flex items-center gap-3 p-3 rounded-lg border border-gray-100 dark:border-gray-700 cursor-pointer hover:shadow-sm transition-all ${getTaskRowBg(task.status)}`}>
                                    <div className="flex-shrink-0">
                                      {task.status === "completed" ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                        : task.status === "answered" ? <Clock className="w-4 h-4 text-violet-500" />
                                        : task.status === "in_progress" ? <Clock className="w-4 h-4 text-blue-500" />
                                        : <AlertCircle className="w-4 h-4 text-gray-400" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{task.title}</p>
                                      {task.plan_iso_code && <p className="text-xs text-gray-500">{task.plan_iso_code}</p>}
                                    </div>
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                      {task.auto_generated
                                        ? <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">Auto</span>
                                        : <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-600">Dashboard</span>}
                                      {task.answered_via === "email" && <span className="flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium"><Mail className="w-3 h-3" /></span>}
                                      {task.answered_via !== "email" && task.placeholder_key && sentPlaceholderKeys.has(task.placeholder_key) && task.status === "pending" && <span className="flex items-center gap-1 px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs font-medium"><Mail className="w-3 h-3" /></span>}
                                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>{task.status.replace("_", " ")}</span>
                                      <span className="text-xs text-gray-400 tabular-nums">{getTimeStr(task.updated_at || task.created_at)}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      );
                    })()
                  )}
                </div>
              </div>
            )}

            {/* Coverage Tab */}
            {activeTab === "coverage" && (
              <div className="space-y-8">
                {plans.length === 0 ? (
                  <div className="text-center py-12">
                    <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <p className="text-xl text-gray-600 dark:text-gray-400">No ISO plans assigned</p>
                  </div>
                ) : (
                  plans.map(plan => (
                    <div key={plan.id}>
                      <CoverageView key={plan.id} isoId={plan.iso_standard_id} customerId={parseInt(customerId)} />
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Interview Tab */}
            {activeTab === "interview" && (
              <div>
                {plans.length > 1 && (
                  <div className="flex gap-2 mb-6">
                    {plans.map(p => (
                      <button key={p.id} onClick={() => setSelectedPlanId(p.id)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${selectedPlanId === p.id ? "bg-blue-600 text-white" : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200"}`}>
                        {p.iso_code}
                      </button>
                    ))}
                  </div>
                )}
                {questionsLoading ? (
                  <div className="flex justify-center py-16"><div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" /></div>
                ) : !questions ? (
                  <div className="text-center py-12 text-gray-500">Select a plan to start the interview</div>
                ) : (
                  <div>
                    {/* Interview search + toggles */}
                    <div className="flex items-center gap-3 mb-5 flex-wrap">
                      <div className="relative flex-1 min-w-48">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type="text" value={interviewSearch} onChange={e => setInterviewSearch(e.target.value)}
                          placeholder="Search questions..."
                          className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white focus:border-blue-400 focus:outline-none"
                        />
                      </div>
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox" checked={unansweredOnly}
                          onChange={e => setUnansweredOnly(e.target.checked)}
                          className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-600 dark:text-gray-400">Unanswered only</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox" checked={showCancelledInInterview}
                          onChange={e => setShowCancelledInInterview(e.target.checked)}
                          className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-600 dark:text-gray-400">Show cancelled</span>
                      </label>
                      {interviewSearch && (
                        <button onClick={() => setInterviewSearch("")} className="text-xs text-blue-600 hover:underline">Clear</button>
                      )}
                    </div>

                    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-700">
                      <div className="flex justify-between text-sm mb-2">
                        <span className="font-medium text-gray-700 dark:text-gray-300">Overall — {questions.answered} / {questions.total} approved</span>
                        <span className="font-bold text-blue-600">{questions.completion_pct}%</span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all" style={{ width: `${questions.completion_pct}%` }} />
                      </div>
                    </div>
                    {(() => {
                      const sq = interviewSearch.toLowerCase().trim();
                      const visibleCategories = questions.categories.map((cat: any) => ({
                        ...cat,
                        questions: cat.questions.filter((q: any) => {
                          if (!showCancelledInInterview && q.task_status === "cancelled") return false;
                          if (unansweredOnly && (q.task_status === "completed" || q.task_status === "answered")) return false;
                          if (sq) return (q.question || q.display_label || q.placeholder_key || "").toLowerCase().includes(sq);
                          return true;
                        }),
                        evidence_tasks: cat.evidence_tasks.filter((ev: any) => {
                          if (!showCancelledInInterview && ev.status === "cancelled") return false;
                          if (unansweredOnly && (ev.status === "completed" || ev.status === "answered")) return false;
                          if (sq) return (ev.title || "").toLowerCase().includes(sq);
                          return true;
                        }),
                      })).filter((cat: any) => cat.questions.length > 0 || cat.evidence_tasks.length > 0);
                      return (
                    <div className="space-y-4">
                      {visibleCategories.length === 0 && (
                        <div className="text-center py-8 text-gray-400 text-sm">No questions match your search</div>
                      )}
                      {visibleCategories.map((cat: any) => {
                        const isOpen = expandedCategories.has(cat.category);
                        const catPct = cat.total ? Math.round(cat.answered / cat.total * 100) : 0;
                        return (
                          <div key={cat.category} className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
                            <button onClick={() => { const next = new Set(expandedCategories); isOpen ? next.delete(cat.category) : next.add(cat.category); setExpandedCategories(next); }}
                              className="w-full flex items-center justify-between px-5 py-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                              <div className="flex items-center gap-3">
                                <span className="font-semibold text-gray-900 dark:text-white">{cat.category}</span>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${catPct === 100 ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>{cat.answered}/{cat.total}</span>
                              </div>
                              <div className="flex items-center gap-3">
                                <div className="w-24 bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                                  <div className={`h-1.5 rounded-full transition-all ${catPct === 100 ? "bg-green-500" : "bg-blue-500"}`} style={{ width: `${catPct}%` }} />
                                </div>
                                <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                              </div>
                            </button>
                            {isOpen && (
                              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                                {cat.questions.map((q: any, idx: number) => {
                                  const isApproved = q.task_status === "completed";
                                  const isAnswered = q.task_status === "answered";
                                  const isCancelled = q.task_status === "cancelled";
                                  return (
                                    <div key={`${cat.category}-${q.placeholder_key}-${idx}`} className={`p-5 ${isCancelled ? "opacity-50 bg-slate-50/60 dark:bg-slate-800/30" : isApproved ? "bg-green-50/40 dark:bg-green-900/10" : isAnswered ? "bg-amber-50/40 dark:bg-amber-900/10" : ""}`}>
                                      <div className="flex items-start gap-3">
                                        <div className="flex-shrink-0 mt-0.5">
                                          {isCancelled ? <X className="w-4 h-4 text-gray-400" /> : isApproved ? <ShieldCheck className="w-4 h-4 text-green-500" /> : <Clock className={`w-4 h-4 ${isAnswered ? "text-amber-500" : "text-gray-300"}`} />}
                                        </div>
                                        <div className="flex-1">
                                          <div className="flex items-center gap-2 mb-1">
                                            <p className={`text-sm font-medium ${isCancelled ? "line-through text-gray-400" : "text-gray-900 dark:text-white"}`}>{q.question || q.display_label || q.placeholder_key}</p>
                                            {isCancelled && <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">Cancelled</span>}
                                            {isApproved && <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">Approved</span>}
                                            {isAnswered && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">Pending Review</span>}
                                          </div>
                                          {q.hint && <p className="text-xs text-gray-500 mb-2">{q.hint}</p>}
                                          {!isCancelled && <div className="flex items-center gap-2">
                                            <input
                                              value={editValues[q.placeholder_key] ?? (q.field_value || "")}
                                              onChange={e => handleAnswerChange(q.placeholder_key, e.target.value, selectedPlanId!)}
                                              disabled={isApproved}
                                              className={`flex-1 px-3 py-2 text-sm border rounded-lg focus:outline-none ${isApproved ? "border-green-200 bg-green-50 text-gray-600 cursor-not-allowed" : "border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-400"}`}
                                              placeholder={q.example_value || "Type answer..."}
                                            />
                                            {savedKeys.has(q.placeholder_key) && <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />}
                                            {isAnswered && q.task_id && (
                                              <button onClick={() => approveTask(q.task_id)} className="flex items-center gap-1.5 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors flex-shrink-0">
                                                <ThumbsUp className="w-3.5 h-3.5" /> Approve
                                              </button>
                                            )}
                                            {isApproved && q.task_id && (
                                              <button onClick={() => reopenTask(q.task_id)} className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 text-gray-600 text-xs font-semibold rounded-lg transition-colors flex-shrink-0">
                                                <Pencil className="w-3.5 h-3.5" /> Edit
                                              </button>
                                            )}
                                          </div>}
                                          {q.documents?.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-2">
                                              {q.documents.map((d: any) => <span key={d.doc_id} className="text-xs px-2 py-0.5 bg-purple-50 text-purple-600 rounded-full">{d.document_name}</span>)}
                                            </div>
                                          )}
                                          {isApproved && q.approved_by_name ? (
                                            <p className="text-xs text-green-600 mt-1.5 flex items-center gap-1"><ShieldCheck className="w-3 h-3" />Approved by {q.approved_by_name} · {q.approved_at ? new Date(q.approved_at).toLocaleString() : ""}</p>
                                          ) : q.filled_by_name ? (
                                            <p className="text-xs text-gray-400 mt-1.5">Filled by {q.filled_by_name} · {q.filled_via} · {q.filled_at ? new Date(q.filled_at).toLocaleString() : ""}</p>
                                          ) : null}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                            {isOpen && cat.evidence_tasks?.length > 0 && (
                              <div className="border-t-2 border-dashed border-orange-200 dark:border-orange-800">
                                <div className="px-5 py-2 bg-orange-50 dark:bg-orange-900/20">
                                  <span className="text-xs font-semibold text-orange-600 uppercase tracking-wide">Evidence Required</span>
                                </div>
                                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                                  {cat.evidence_tasks.map((ev: any) => {
                                    const isApproved = ev.status === "completed";
                                    const isAnswered = ev.status === "answered";
                                    const evCancelled = ev.status === "cancelled";
                                    return (
                                      <div key={ev.id} className={`p-5 ${evCancelled ? "opacity-50 bg-slate-50/60" : isApproved ? "bg-green-50/40 dark:bg-green-900/10" : isAnswered ? "bg-amber-50/40 dark:bg-amber-900/10" : ""}`}>
                                        <div className="flex items-start gap-3">
                                          <div className="flex-shrink-0 mt-0.5">
                                            {evCancelled ? <X className="w-4 h-4 text-gray-400" /> : isApproved ? <ShieldCheck className="w-4 h-4 text-green-500" /> : isAnswered ? <Clock className="w-4 h-4 text-amber-500" /> : <Upload className="w-4 h-4 text-orange-400" />}
                                          </div>
                                          <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                              <p className={`text-sm font-medium ${evCancelled ? "line-through text-gray-400" : "text-gray-900 dark:text-white"}`}>{ev.title}</p>
                                              {evCancelled && <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">Cancelled</span>}
                                              {isApproved && <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">Approved</span>}
                                              {isAnswered && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">Pending Review</span>}
                                            </div>
                                            {ev.evidence_description && <p className="text-xs text-gray-500 mb-2">{ev.evidence_description}</p>}
                                            {ev.document_name && <span className="text-xs px-2 py-0.5 bg-purple-50 text-purple-600 rounded-full">{ev.document_name}</span>}
                                            {!evCancelled && <div className="mt-2 flex items-center gap-2 flex-wrap">
                                              {ev.evidence_uploaded && ev.answer_file_path && (
                                                <span className="text-xs text-gray-600 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-green-500" />{ev.answer_file_path.split('/').pop()}</span>
                                              )}
                                              {!isApproved && (
                                                <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-orange-100 text-orange-700 rounded-lg text-xs font-medium cursor-pointer hover:bg-orange-200 transition-colors">
                                                  <Upload className="w-3.5 h-3.5" />{ev.evidence_uploaded ? "Replace" : "Upload file"}
                                                  <input type="file" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) uploadEvidence(ev.id, f); }} />
                                                </label>
                                              )}
                                              {isAnswered && (
                                                <button onClick={() => approveTask(ev.id)} className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors">
                                                  <ThumbsUp className="w-3.5 h-3.5" /> Approve
                                                </button>
                                              )}
                                              {isApproved && (
                                                <button onClick={() => reopenTask(ev.id)} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-semibold rounded-lg transition-colors">
                                                  <Pencil className="w-3.5 h-3.5" /> Edit
                                                </button>
                                              )}
                                            </div>}
                                            {isApproved && ev.approved_by_name ? (
                                              <p className="text-xs text-green-600 mt-1.5 flex items-center gap-1"><ShieldCheck className="w-3 h-3" />Approved by {ev.approved_by_name} · {ev.approved_at ? new Date(ev.approved_at).toLocaleString() : ""}</p>
                                            ) : ev.answered_by_name ? (
                                              <p className="text-xs text-gray-400 mt-1.5">Uploaded by {ev.answered_by_name} · {ev.answered_at ? new Date(ev.answered_at).toLocaleString() : ""}</p>
                                            ) : null}
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

            {/* Automation Tab */}
            {activeTab === "automation" && (
              <AutomationTab
                customerId={parseInt(customerId)}
                plans={plans.map(p => ({ id: p.id, iso_code: p.iso_code, iso_name: p.iso_name, plan_status: p.plan_status }))}
              />
            )}

      {/* Delete Document Confirmation Modal */}
      {deleteDocConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            {/* Header */}
            <div className={`flex items-start gap-3 p-6 border-b ${deleteDocConfirm.nonPendingTasks.length > 0 ? "border-amber-100 bg-amber-50 rounded-t-2xl" : "border-red-100 bg-red-50 rounded-t-2xl"}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${deleteDocConfirm.nonPendingTasks.length > 0 ? "bg-amber-100" : "bg-red-100"}`}>
                {deleteDocConfirm.nonPendingTasks.length > 0
                  ? <TriangleAlert className="w-5 h-5 text-amber-600" />
                  : <Trash2 className="w-5 h-5 text-red-600" />}
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">
                  {deleteDocConfirm.nonPendingTasks.length > 0 ? "Warning: Active Tasks Will Be Cancelled" : "Delete Document"}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  <span className="font-medium text-slate-700">"{deleteDocConfirm.docName}"</span>
                  {deleteDocConfirm.totalTasks > 0
                    ? ` and its ${deleteDocConfirm.totalTasks} associated task${deleteDocConfirm.totalTasks !== 1 ? "s" : ""} will be permanently deleted.`
                    : " will be permanently deleted."}
                </p>
              </div>
            </div>

            {/* Impacted tasks list */}
            {deleteDocConfirm.nonPendingTasks.length > 0 && (
              <div className="p-5">
                <p className="text-xs font-semibold text-amber-700 mb-3 flex items-center gap-1.5">
                  <TriangleAlert className="w-3.5 h-3.5" />
                  {deleteDocConfirm.nonPendingTasks.length} task{deleteDocConfirm.nonPendingTasks.length !== 1 ? "s" : ""} with progress will be cancelled:
                </p>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {deleteDocConfirm.nonPendingTasks.map(t => (
                    <div key={t.id} className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        t.status === "completed" ? "bg-emerald-500" :
                        t.status === "in_progress" ? "bg-blue-500" :
                        t.status === "on_hold" ? "bg-amber-500" : "bg-slate-400"
                      }`} />
                      <span className="text-xs text-slate-700 flex-1 truncate">{t.title}</span>
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        t.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                        t.status === "in_progress" ? "bg-blue-100 text-blue-700" :
                        "bg-amber-100 text-amber-700"
                      }`}>{t.status.replace("_", " ")}</span>
                      {t.requires_evidence && <Upload className="w-3 h-3 text-orange-500 flex-shrink-0" />}
                    </div>
                  ))}
                </div>
                {deleteDocConfirm.pendingCount > 0 && (
                  <p className="text-xs text-slate-400 mt-2">+{deleteDocConfirm.pendingCount} pending task{deleteDocConfirm.pendingCount !== 1 ? "s" : ""} also cancelled.</p>
                )}
              </div>
            )}

            {/* Simple message when only pending tasks */}
            {deleteDocConfirm.nonPendingTasks.length === 0 && deleteDocConfirm.totalTasks > 0 && (
              <div className="px-6 py-4">
                <p className="text-sm text-slate-500">
                  {deleteDocConfirm.totalTasks} pending task{deleteDocConfirm.totalTasks !== 1 ? "s" : ""} will also be cancelled.
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-slate-100">
              <button
                onClick={() => setDeleteDocConfirm(null)}
                disabled={deletingDoc}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteDoc}
                disabled={deletingDoc}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 ${
                  deleteDocConfirm.nonPendingTasks.length > 0
                    ? "bg-amber-600 hover:bg-amber-700"
                    : "bg-red-600 hover:bg-red-700"
                }`}
              >
                {deletingDoc ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                {deleteDocConfirm.nonPendingTasks.length > 0 ? "Delete Anyway" : "Delete Document"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Document Customize Modal */}
      {customizeModal && (
        <TemplateEditorModal
          title={customizeModal.docName}
          subtitle="Customer document — edits apply to this customer's copy only"
          warning="Changes here affect this customer's document only, not the master template."
          structure={customizeModal.structure}
          dictionary={customizeModal.dictionary}
          onSave={handleCustomizeSave}
          onClose={() => setCustomizeModal(null)}
        />
      )}

      {/* Task Detail Modal */}
      {showTaskModal && selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => { setShowTaskModal(false); setSelectedTask(null); }}
          onTaskUpdated={handleTaskUpdated}
        />
      )}

      {/* Document Preview Modal */}
      {previewDocId && (() => {
        const token = typeof window !== "undefined" ? (localStorage.getItem("access_token") || "") : "";
        return (
          <div className="fixed inset-0 z-50 flex flex-col bg-black/80 backdrop-blur-sm">
            <div className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
              <h3 className="font-semibold text-gray-900 dark:text-white text-sm">Document Preview — with filled values</h3>
              <button
                onClick={() => setPreviewDocId(null)}
                className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            <div className="flex-1">
              <iframe
                src={`/api/document-preview?docId=${previewDocId}&lang=en&token=${encodeURIComponent(token)}`}
                className="w-full h-full border-0 bg-white"
                title="Document Preview"
              />
            </div>
          </div>
        );
      })()}
    </div>
  );
}
