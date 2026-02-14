"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  X,
  Shield,
  FileText,
  Calendar,
  CheckCircle,
  Loader2,
  Sparkles,
  Target,
  ChevronRight,
  Trash2,
  AlertTriangle,
  Plus,
  ListChecks,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
  email: string;
}

interface ManagePlanModalProps {
  customer: Customer;
  onClose: () => void;
  onSuccess: () => void;
}

interface ISOStandard {
  id: string;
  name: string;
  version: string;
  description: string;
}

interface Template {
  id: string;
  name: string;
  description?: string;
  iso_standard?: string;
  source_filename?: string;
  status: string;
  total_fixed_sections: number;
  total_fillable_sections: number;
  semantic_tags: string[];
}

interface ExistingPlan {
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
  template_id: string;
  template_name: string;
  total_fillable_sections: number;
  tasks_created: number;
}

export default function ManagePlanModal({
  customer,
  onClose,
  onSuccess,
}: ManagePlanModalProps) {
  const [existingPlans, setExistingPlans] = useState<ExistingPlan[]>([]);
  const [viewMode, setViewMode] = useState<"list" | "create">("list");
  const [selectedPlan, setSelectedPlan] = useState<ExistingPlan | null>(null);
  const [planTemplates, setPlanTemplates] = useState<PlanTemplate[]>([]);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [planToDelete, setPlanToDelete] = useState<ExistingPlan | null>(null);

  const [isoStandards, setIsoStandards] = useState<ISOStandard[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedIso, setSelectedIso] = useState("");
  const [selectedTemplates, setSelectedTemplates] = useState<string[]>([]);
  const [targetDate, setTargetDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [step, setStep] = useState(1);

  useEffect(() => {
    loadExistingPlans();
  }, []);

  useEffect(() => {
    if (selectedIso && viewMode === "create") {
      loadTemplates(selectedIso);
      setStep(2);
    }
  }, [selectedIso, viewMode]);

  const loadExistingPlans = async () => {
    try {
      setLoadingPlans(true);
      const token = localStorage.getItem("access_token");
      const res = await axios.get(
        `${API_BASE}/api/v1/customers/${customer.id}/plans`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      console.log("Existing plans loaded:", res.data);
      setExistingPlans(res.data || []);

      // If no plans exist, go straight to create mode
      if (!res.data || res.data.length === 0) {
        setViewMode("create");
        loadIsoStandards();
      }
    } catch (error) {
      console.error("Error loading existing plans:", error);
      // If error loading plans, still allow creating new one
      setViewMode("create");
      loadIsoStandards();
    } finally {
      setLoadingPlans(false);
    }
  };

  const loadIsoStandards = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.get(`${API_BASE}/api/v1/iso-standards`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      console.log("ISO Standards loaded:", res.data);
      setIsoStandards(res.data.standards || res.data || []);
    } catch (error) {
      console.error("Error loading ISO standards:", error);
      alert("Failed to load ISO standards");
    }
  };

  const loadTemplates = async (isoId: string) => {
    try {
      setLoadingTemplates(true);
      const token = localStorage.getItem("access_token");
      const res = await axios.get(
        `${API_BASE}/api/v1/catalog-templates?iso_standard_id=${isoId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      console.log("Templates loaded:", res.data);
      setTemplates(res.data || []);
    } catch (error) {
      console.error("Error loading templates:", error);
      alert("Failed to load templates");
    } finally {
      setLoadingTemplates(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (!selectedIso || selectedTemplates.length === 0 || !targetDate) {
      alert("Please complete all steps");
      return;
    }

    setLoading(true);
    const token = localStorage.getItem("access_token");

    try {
      console.log("Creating plan with templates and tasks in one transaction...");

      // Single atomic API call - all or nothing!
      const response = await axios.post(
        `${API_BASE}/api/v1/plans/complete`,
        {
          customer_id: customer.id,
          iso_standard_id: selectedIso,
          template_ids: selectedTemplates,
          target_completion_date: targetDate,
          due_date_offset_days: 30,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      console.log("✅ Success:", response.data);

      alert(
        `✅ Success!\n\nPlan created for ${customer.name}\n${response.data.templates_added} templates assigned\n${response.data.tasks_created} tasks generated`
      );

      onSuccess();
      onClose();
    } catch (error: any) {
      console.error("Error generating plan:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to generate plan";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  const toggleTemplate = (templateId: string) => {
    if (selectedTemplates.includes(templateId)) {
      setSelectedTemplates(selectedTemplates.filter((id) => id !== templateId));
    } else {
      setSelectedTemplates([...selectedTemplates, templateId]);
    }
  };

  const selectAllTemplates = () => {
    setSelectedTemplates(templates.map((t) => t.id));
  };

  const clearAllTemplates = () => {
    setSelectedTemplates([]);
  };

  const handleDeletePlan = async (plan: ExistingPlan) => {
    setPlanToDelete(plan);
    setShowDeleteConfirm(true);
  };

  const confirmDeletePlan = async () => {
    if (!planToDelete) return;

    setLoading(true);
    const token = localStorage.getItem("access_token");

    try {
      await axios.patch(
        `${API_BASE}/api/v1/plans/${planToDelete.id}/ignore`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          params: { reason: "Plan deleted by admin" },
        }
      );

      alert(
        `✅ Plan deleted successfully!\n\n${planToDelete.total_tasks} tasks have been cancelled.`
      );

      setShowDeleteConfirm(false);
      setPlanToDelete(null);
      onSuccess();
      onClose();
    } catch (error: any) {
      console.error("Error deleting plan:", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Failed to delete plan";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNewPlan = () => {
    setViewMode("create");
    loadIsoStandards();
    setStep(1);
  };

  // Delete confirmation dialog
  const DeleteConfirmDialog = () => {
    if (!showDeleteConfirm || !planToDelete) return null;

    return (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-lg w-full p-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-full">
              <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white">
              Delete Entire Plan?
            </h3>
          </div>

          <div className="mb-6 space-y-3">
            <p className="text-gray-700 dark:text-gray-300">
              This will permanently delete the{" "}
              <span className="font-semibold">{planToDelete.iso_name}</span> plan for{" "}
              <span className="font-semibold">{customer.name}</span>.
            </p>

            <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-xl border-2 border-red-200 dark:border-red-800">
              <p className="text-sm font-medium text-red-900 dark:text-red-100 mb-2">
                ⚠️ This action will:
              </p>
              <ul className="text-sm text-red-800 dark:text-red-200 space-y-1 ml-4">
                <li>• Cancel {planToDelete.total_templates} template assignments</li>
                <li>
                  • Cancel {planToDelete.total_tasks} tasks (
                  {planToDelete.completed_tasks} completed, {planToDelete.total_tasks - planToDelete.completed_tasks} pending)
                </li>
                <li>• Mark all work as cancelled for audit trail</li>
              </ul>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-400">
              Customer's completed work will be preserved for audit but marked as cancelled.
            </p>
          </div>

          <div className="flex items-center justify-end space-x-3">
            <button
              onClick={() => {
                setShowDeleteConfirm(false);
                setPlanToDelete(null);
              }}
              disabled={loading}
              className="px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-all disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={confirmDeletePlan}
              disabled={loading}
              className="flex items-center space-x-2 px-6 py-3 bg-red-600 text-white rounded-xl font-medium hover:bg-red-700 transition-all disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Deleting...</span>
                </>
              ) : (
                <>
                  <Trash2 className="w-5 h-5" />
                  <span>Yes, Delete Plan</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      <DeleteConfirmDialog />
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-4 flex items-center justify-between rounded-t-2xl">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">
                  {viewMode === "list" ? "Manage ISO Plans" : "Create New Plan"}
                </h2>
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

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Loading State */}
          {loadingPlans && (
            <div className="text-center py-12">
              <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-blue-600" />
              <p className="text-gray-600 dark:text-gray-400">Loading plans...</p>
            </div>
          )}

          {/* List Mode - Show Existing Plans */}
          {!loadingPlans && viewMode === "list" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Existing ISO Plans ({existingPlans.length})
                </h3>
                <button
                  onClick={handleCreateNewPlan}
                  className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-medium hover:shadow-lg transition-all"
                >
                  <Plus className="w-4 h-4" />
                  <span>Create New Plan</span>
                </button>
              </div>

              {existingPlans.length === 0 ? (
                <div className="text-center py-12">
                  <Shield className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                  <p className="text-gray-600 dark:text-gray-400 mb-4">
                    No ISO plans yet
                  </p>
                  <button
                    onClick={handleCreateNewPlan}
                    className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium hover:shadow-lg transition-all"
                  >
                    Create First Plan
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {existingPlans.map((plan) => (
                    <div
                      key={plan.id}
                      className="p-6 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-400 dark:hover:border-blue-600 transition-all"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <Shield className="w-5 h-5 text-blue-600" />
                            <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                              {plan.iso_name}
                            </h4>
                            <span className="px-2 py-1 text-xs font-semibold bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded-full">
                              {plan.plan_status}
                            </span>
                          </div>
                          {plan.target_completion_date && (
                            <p className="text-sm text-gray-600 dark:text-gray-400 flex items-center">
                              <Calendar className="w-4 h-4 mr-1" />
                              Target: {new Date(plan.target_completion_date).toLocaleDateString()}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeletePlan(plan)}
                          className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all"
                          title="Delete Plan"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>

                      {/* Progress Stats */}
                      <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                        <div className="text-center">
                          <p className="text-2xl font-bold text-purple-600">
                            {plan.total_templates}
                          </p>
                          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            Templates
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-blue-600">
                            {plan.total_tasks}
                          </p>
                          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            Total Tasks
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-green-600">
                            {plan.completed_tasks}
                          </p>
                          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            Completed
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-orange-600">
                            {plan.progress_percentage}%
                          </p>
                          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            Progress
                          </p>
                        </div>
                      </div>

                      {/* Progress Bar */}
                      <div className="mt-4">
                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                          <div
                            className="bg-gradient-to-r from-blue-600 to-purple-600 h-2 rounded-full transition-all"
                            style={{ width: `${plan.progress_percentage}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Create Mode - New Plan Wizard */}
          {!loadingPlans && viewMode === "create" && (
            <>
              {/* Step Indicator */}
              <div className="flex items-center justify-center space-x-4 mb-8">
            <div
              className={`flex items-center space-x-2 ${
                step >= 1 ? "text-blue-600" : "text-gray-400"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                  step >= 1
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                1
              </div>
              <span className="font-medium">ISO Standard</span>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400" />
            <div
              className={`flex items-center space-x-2 ${
                step >= 2 ? "text-blue-600" : "text-gray-400"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                  step >= 2
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                2
              </div>
              <span className="font-medium">Templates</span>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400" />
            <div
              className={`flex items-center space-x-2 ${
                step >= 3 ? "text-blue-600" : "text-gray-400"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                  step >= 3
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                3
              </div>
              <span className="font-medium">Finalize</span>
            </div>
          </div>

          {/* Step 1: ISO Selection */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
                <Shield className="w-5 h-5 mr-2 text-blue-600" />
                Step 1: Select ISO Standard
              </h3>
              <span className="text-sm text-gray-500">
                {isoStandards.length} standards available
              </span>
            </div>

            <div className="space-y-2">
              {isoStandards.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                  Loading ISO standards...
                </div>
              ) : (
                isoStandards.map((iso) => (
                  <label
                    key={iso.id}
                    className={`flex items-center p-4 border-2 rounded-xl cursor-pointer transition-all ${
                      selectedIso === iso.id
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                        : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
                    }`}
                  >
                    <input
                      type="radio"
                      name="iso"
                      value={iso.id}
                      checked={selectedIso === iso.id}
                      onChange={(e) => setSelectedIso(e.target.value)}
                      className="w-5 h-5 text-blue-600"
                    />
                    <div className="ml-3 flex-1">
                      <p className="font-semibold text-gray-900 dark:text-white">
                        {iso.name}
                      </p>
                      {iso.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {iso.description}
                        </p>
                      )}
                    </div>
                  </label>
                ))
              )}
            </div>
          </div>

          {/* Step 2: Template Selection */}
          {selectedIso && (
            <div className="space-y-4 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
                  <FileText className="w-5 h-5 mr-2 text-purple-600" />
                  Step 2: Select Templates
                </h3>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={selectAllTemplates}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Select All
                  </button>
                  <span className="text-gray-400">|</span>
                  <button
                    onClick={clearAllTemplates}
                    className="text-sm text-gray-600 hover:underline"
                  >
                    Clear All
                  </button>
                </div>
              </div>

              {loadingTemplates ? (
                <div className="text-center py-8 text-gray-500">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                  Loading templates...
                </div>
              ) : templates.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <FileText className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                  <p>No templates found for this ISO standard</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto p-2">
                  {templates.map((template) => (
                    <label
                      key={template.id}
                      className={`flex items-start p-4 border-2 rounded-xl cursor-pointer transition-all ${
                        selectedTemplates.includes(template.id)
                          ? "border-purple-500 bg-purple-50 dark:bg-purple-900/20"
                          : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
                      }`}
                    >
                      <input
                        type="checkbox"
                        value={template.id}
                        checked={selectedTemplates.includes(template.id)}
                        onChange={() => toggleTemplate(template.id)}
                        className="w-5 h-5 text-purple-600 mt-0.5"
                      />
                      <div className="ml-3 flex-1">
                        <div className="flex items-center justify-between">
                          <p className="font-semibold text-gray-900 dark:text-white">
                            {template.name}
                          </p>
                          <span className="text-xs px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded-full">
                            {template.status}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {template.description || template.source_filename}
                          <span className="ml-2 text-purple-600 font-medium">
                            • {template.total_fillable_sections} fillable sections
                          </span>
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {selectedTemplates.length > 0 && (
                <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-xl border-2 border-purple-200 dark:border-purple-800">
                  <p className="text-sm font-medium text-purple-900 dark:text-purple-100">
                    ✓ {selectedTemplates.length} template
                    {selectedTemplates.length > 1 ? "s" : ""} selected
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Target Date */}
          {selectedTemplates.length > 0 && (
            <div className="space-y-4 pt-6 border-t border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
                <Calendar className="w-5 h-5 mr-2 text-green-600" />
                Step 3: Set Target Completion Date
              </h3>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => {
                  setTargetDate(e.target.value);
                  setStep(3);
                }}
                min={new Date().toISOString().split("T")[0]}
                className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-green-500 focus:ring-2 focus:ring-green-500/20 transition-all"
              />
            </div>
          )}

          {/* Summary */}
          {selectedIso && selectedTemplates.length > 0 && targetDate && (
            <div className="p-6 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-xl border-2 border-blue-200 dark:border-blue-800">
              <div className="flex items-center mb-4">
                <Target className="w-6 h-6 mr-2 text-blue-600" />
                <h4 className="text-lg font-bold text-gray-900 dark:text-white">
                  Plan Summary
                </h4>
              </div>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-3xl font-bold text-blue-600">
                    {selectedTemplates.length}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Templates
                  </p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-purple-600">
                    {templates
                      .filter((t) => selectedTemplates.includes(t.id))
                      .reduce((sum, t) => sum + (t.total_fillable_sections || 0), 0)}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Sections
                  </p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-green-600">
                    {targetDate ? new Date(targetDate).toLocaleDateString() : "-"}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Target Date
                  </p>
                </div>
              </div>
            </div>
          )}
            </>
          )}
        </div>

        {/* Footer */}
        {!loadingPlans && (
          <div className="flex items-center justify-between p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 rounded-b-2xl">
            <div>
              {viewMode === "create" && existingPlans.length > 0 && (
                <button
                  onClick={() => setViewMode("list")}
                  className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-all"
                >
                  ← Back to Plans
                </button>
              )}
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={onClose}
                className="px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-all"
              >
                Close
              </button>
              {viewMode === "create" && (
                <button
                  onClick={handleGeneratePlan}
                  disabled={
                    !selectedIso ||
                    selectedTemplates.length === 0 ||
                    !targetDate ||
                    loading
                  }
                  className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      <span>Generate Plan & Tasks</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  );
}
