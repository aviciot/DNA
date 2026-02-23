"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Shield,
  TrendingUp,
  CheckCircle,
  Clock,
  AlertCircle,
  Target,
  FileText,
  Loader2,
  RefreshCw,
  Calendar,
  BarChart3,
  X,
  ChevronDown,
  ChevronUp,
  Circle,
  CheckCircle2,
  Layers,
  Sparkles,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface ISOProgress {
  id: string;
  iso_code: string;
  iso_name: string;
  plan_name: string;
  target_completion_date: string | null;
  total_templates: number;
  completed_templates: number;
  in_progress_templates: number;
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  pending_tasks: number;
  ignored_tasks: number;
  progress_percentage: number;
}

interface CustomerProgress {
  customer_id: number;
  customer_name: string;
  iso_plans: ISOProgress[];
  total_iso_plans: number;
  total_templates: number;
  total_tasks: number;
  completed_tasks: number;
  overall_progress: number;
}

interface Customer {
  id: number;
  name: string;
  email: string;
}

export default function CustomerDashboard() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [progress, setProgress] = useState<CustomerProgress | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedISOs, setExpandedISOs] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadCustomers();
  }, []);

  useEffect(() => {
    if (selectedCustomerId) {
      loadProgress();
    }
  }, [selectedCustomerId]);

  const loadCustomers = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/customers?page=1&page_size=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCustomers(response.data.customers || []);
    } catch (error) {
      console.error("Error loading customers:", error);
    }
  };

  const loadProgress = async () => {
    if (!selectedCustomerId) return;

    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const response = await axios.get(
        `${API_BASE}/api/v1/customers/${selectedCustomerId}/progress`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setProgress(response.data);

      // Auto-expand all ISOs
      const allISOIds = new Set<string>(response.data.iso_plans.map((iso: ISOProgress) => iso.id));
      setExpandedISOs(allISOIds);
    } catch (error) {
      console.error("Error loading progress:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleISO = (isoId: string) => {
    setExpandedISOs((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(isoId)) {
        newSet.delete(isoId);
      } else {
        newSet.add(isoId);
      }
      return newSet;
    });
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 80) return { bg: "from-green-500 to-emerald-600", text: "text-green-600" };
    if (percentage >= 50) return { bg: "from-blue-500 to-cyan-600", text: "text-blue-600" };
    if (percentage >= 25) return { bg: "from-yellow-500 to-orange-600", text: "text-yellow-600" };
    return { bg: "from-red-500 to-pink-600", text: "text-red-600" };
  };

  const getDaysUntil = (dateStr: string | null) => {
    if (!dateStr) return null;
    const targetDate = new Date(dateStr);
    const today = new Date();
    const diffTime = targetDate.getTime() - today.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header with Customer Selector */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Customer Progress Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Track ISO certification progress and task completion
          </p>
        </div>

        {/* Customer Selector */}
        <div className="w-full md:w-64">
          <label className="block text-sm font-medium mb-2">Select Customer</label>
          <select
            value={selectedCustomerId || ""}
            onChange={(e) => setSelectedCustomerId(e.target.value ? parseInt(e.target.value) : null)}
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700"
          >
            <option value="">Choose a customer...</option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="w-12 h-12 animate-spin text-blue-500" />
          <p className="mt-4 text-gray-600 dark:text-gray-400">Loading progress...</p>
        </div>
      )}

      {/* No Customer Selected */}
      {!selectedCustomerId && !loading && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-12 text-center">
          <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No Customer Selected
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            Please select a customer from the dropdown above to view their progress
          </p>
        </div>
      )}

      {/* Progress Content */}
      {selectedCustomerId && !loading && progress && (
        <div className="space-y-6">
          {/* Header Info */}
          <div className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 rounded-xl p-6 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <BarChart3 className="w-8 h-8" />
                <div>
                  <h2 className="text-2xl font-bold">{customers.find(c => c.id === selectedCustomerId)?.name}</h2>
                  <p className="text-white/90">Progress Dashboard</p>
                </div>
              </div>
              <button
                onClick={loadProgress}
                className="p-2 bg-white/20 hover:bg-white/30 rounded-lg backdrop-blur-sm transition-all"
                title="Refresh"
              >
                <RefreshCw className="w-5 h-5 text-white" />
              </button>
            </div>
          </div>

          {/* Overall Progress */}
          <div className="mb-6 p-6 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900 dark:to-purple-900 rounded-2xl border-2 border-blue-200 dark:border-blue-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="p-3 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl shadow-lg">
                  <Sparkles className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                    Overall Progress
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Across all compliance standards
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  {progress.overall_progress}%
                </p>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="mb-4">
              <div className="h-4 bg-white dark:bg-gray-700 rounded-full overflow-hidden shadow-inner">
                <div
                  className={`h-full bg-gradient-to-r ${
                    getProgressColor(progress.overall_progress).bg
                  } rounded-full transition-all duration-1000 ease-out relative`}
                  style={{ width: `${progress.overall_progress}%` }}
                >
                  <div className="absolute inset-0 bg-white/20 animate-shimmer" />
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-3 bg-white/50 dark:bg-gray-800 rounded-xl backdrop-blur-sm">
                <Shield className="w-5 h-5 mx-auto text-blue-600 dark:text-blue-400 mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {progress.total_iso_plans}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">ISO Plans</p>
              </div>
              <div className="text-center p-3 bg-white/50 dark:bg-gray-800 rounded-xl backdrop-blur-sm">
                <FileText className="w-5 h-5 mx-auto text-purple-600 dark:text-purple-400 mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {progress.total_templates}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Templates</p>
              </div>
              <div className="text-center p-3 bg-white/50 dark:bg-gray-800 rounded-xl backdrop-blur-sm">
                <CheckCircle className="w-5 h-5 mx-auto text-green-600 dark:text-green-400 mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {progress.completed_tasks}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Completed</p>
              </div>
              <div className="text-center p-3 bg-white/50 dark:bg-gray-800 rounded-xl backdrop-blur-sm">
                <Layers className="w-5 h-5 mx-auto text-orange-600 dark:text-orange-400 mb-2" />
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {progress.total_tasks}
                </p>
                <p className="text-xs text-gray-600 dark:text-gray-400">Total Tasks</p>
              </div>
            </div>
          </div>

          {/* ISO Plans */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Shield className="w-5 h-5 mr-2 text-blue-600 dark:text-blue-400" />
              ISO Standards Progress
            </h3>

            {progress.iso_plans.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 dark:bg-gray-700 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700">
                <Shield className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 dark:text-gray-400">No ISO plans assigned yet</p>
              </div>
            ) : (
              progress.iso_plans.map((iso, index) => {
                const isExpanded = expandedISOs.has(iso.id);
                const progressColor = getProgressColor(iso.progress_percentage);
                const daysUntil = getDaysUntil(iso.target_completion_date);

                return (
                  <div
                    key={iso.id}
                    className="bg-white dark:bg-gray-800 rounded-xl border-2 border-gray-200 dark:border-gray-700 overflow-hidden hover:border-blue-500 transition-all duration-300 animate-slide-in"
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <button
                      onClick={() => toggleISO(iso.id)}
                      className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
                    >
                      <div className="flex items-center space-x-4 flex-1">
                        <div className="p-3 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl shadow-lg">
                          <Shield className="w-6 h-6 text-white" />
                        </div>
                        <div className="text-left flex-1">
                          <h4 className="font-bold text-gray-900 dark:text-white">
                            {iso.iso_code} - {iso.iso_name}
                          </h4>
                          {iso.plan_name && (
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {iso.plan_name}
                            </p>
                          )}
                          {daysUntil !== null && (
                            <p
                              className={`text-xs mt-1 flex items-center ${
                                daysUntil < 0
                                  ? "text-red-600 dark:text-red-400"
                                  : daysUntil < 30
                                  ? "text-orange-600 dark:text-orange-400"
                                  : "text-green-600 dark:text-green-400"
                              }`}
                            >
                              <Calendar className="w-3 h-3 mr-1" />
                              {daysUntil < 0
                                ? `${Math.abs(daysUntil)} days overdue`
                                : daysUntil === 0
                                ? "Due today"
                                : `${daysUntil} days remaining`}
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          <p className={`text-3xl font-bold ${progressColor.text}`}>
                            {iso.progress_percentage}%
                          </p>
                          <p className="text-xs text-gray-600 dark:text-gray-400">
                            {iso.completed_tasks} / {iso.total_tasks} tasks
                          </p>
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-gray-400 ml-4" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-400 ml-4" />
                      )}
                    </button>

                    {/* Progress Bar */}
                    <div className="px-6 pb-4">
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full bg-gradient-to-r ${progressColor.bg} rounded-full transition-all duration-1000 ease-out relative`}
                          style={{ width: `${iso.progress_percentage}%` }}
                        >
                          <div className="absolute inset-0 bg-white/20 animate-shimmer" />
                        </div>
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="px-6 pb-6 border-t border-gray-200 dark:border-gray-700 animate-slide-down">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4">
                          <div className="text-center p-4 bg-blue-50 dark:bg-blue-900 rounded-xl">
                            <FileText className="w-5 h-5 mx-auto text-blue-600 dark:text-blue-400 mb-2" />
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">
                              {iso.total_templates}
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                              Templates
                            </p>
                            <p className="text-xs text-green-600 dark:text-green-400 font-semibold mt-1">
                              {iso.completed_templates} completed
                            </p>
                          </div>

                          <div className="text-center p-4 bg-orange-50 dark:bg-orange-900 rounded-xl">
                            <Clock className="w-5 h-5 mx-auto text-orange-600 dark:text-orange-400 mb-2" />
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">
                              {iso.pending_tasks}
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Pending</p>
                          </div>

                          <div className="text-center p-4 bg-purple-50 dark:bg-purple-900 rounded-xl">
                            <TrendingUp className="w-5 h-5 mx-auto text-purple-600 dark:text-purple-400 mb-2" />
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">
                              {iso.in_progress_tasks}
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                              In Progress
                            </p>
                          </div>

                          <div className="text-center p-4 bg-green-50 dark:bg-green-900 rounded-xl">
                            <CheckCircle2 className="w-5 h-5 mx-auto text-green-600 dark:text-green-400 mb-2" />
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">
                              {iso.completed_tasks}
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                              Completed
                            </p>
                          </div>
                        </div>

                        {iso.ignored_tasks > 0 && (
                          <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-700 rounded-lg">
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              <AlertCircle className="inline w-4 h-4 mr-1" />
                              {iso.ignored_tasks} task{iso.ignored_tasks !== 1 ? "s" : ""} marked as ignored
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes fade-in {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes slide-up {
          from {
            transform: translateY(20px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        @keyframes slide-in {
          from {
            transform: translateX(-20px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }

        @keyframes slide-down {
          from {
            transform: translateY(-10px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(100%);
          }
        }

        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }

        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }

        .animate-slide-in {
          animation: slide-in 0.4s ease-out;
        }

        .animate-slide-down {
          animation: slide-down 0.3s ease-out;
        }

        .animate-shimmer {
          animation: shimmer 2s infinite;
        }
      `}</style>
    </div>
  );
}
