"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Shield,
  FileText,
  Plus,
  X,
  Check,
  Loader2,
  Calendar,
  Target,
  Sparkles,
  AlertCircle,
  ChevronRight,
  Layers,
  Zap,
  CheckCircle2,
  Clock,
  ArrowRight,
  Info,
  Trash2,
  RefreshCw,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface ISO {
  id: string;
  code: string;
  name: string;
  description: string;
}

interface Template {
  id: string;
  name: string;
  description: string;
  fillable_sections_count: number;
}

interface Plan {
  id: string;
  iso_standard_id: string;
  iso_code: string;
  iso_name: string;
  plan_name: string;
  target_completion_date: string | null;
  total_templates: number;
  total_tasks: number;
  progress_percentage: number;
}

interface Customer {
  id: number;
  name: string;
  email: string;
}

interface ManageCustomerPlanProps {
  customerId?: number;
  customerName?: string;
  onClose?: () => void;
  onPlanUpdated?: () => void;
}

export default function ManageCustomerPlan({
  customerId: propCustomerId,
  customerName: propCustomerName,
  onClose,
  onPlanUpdated,
}: ManageCustomerPlanProps = {}) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(propCustomerId ?? null);
  const [isos, setIsos] = useState<ISO[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [existingPlans, setExistingPlans] = useState<Plan[]>([]);
  const [selectedISO, setSelectedISO] = useState<ISO | null>(null);
  const [selectedTemplates, setSelectedTemplates] = useState<string[]>([]);
  const [targetDate, setTargetDate] = useState("");
  const [planName, setPlanName] = useState("");
  const [loading, setLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [step, setStep] = useState(1); // 1: Select Customer, 2: Select ISO, 3: Select Templates, 4: Preview & Confirm

  useEffect(() => {
    loadCustomers();
  }, []);

  useEffect(() => {
    if (selectedCustomerId) {
      loadData();
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

  useEffect(() => {
    if (selectedISO) {
      loadTemplatesForISO(selectedISO.id);
    }
  }, [selectedISO]);

  const loadData = async () => {
    if (!selectedCustomerId) return;

    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const headers = { Authorization: `Bearer ${token}` };

      const [isosRes, plansRes] = await Promise.all([
        axios.get(`${API_BASE}/api/v1/iso-standards`, { headers }),
        axios.get(`${API_BASE}/api/v1/customers/${selectedCustomerId}/plans`, { headers }),
      ]);

      setIsos(isosRes.data || []);
      setExistingPlans(plansRes.data || []);
    } catch (error) {
      console.error("Error loading data:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplatesForISO = async (isoId: string) => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(
        `${API_BASE}/api/v1/iso-standards/${isoId}/templates`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setTemplates(response.data || []);
    } catch (error) {
      console.error("Error loading templates:", error);
    }
  };

  const handleCreatePlan = async () => {
    if (!selectedISO || selectedTemplates.length === 0) {
      alert("Please select an ISO standard and at least one template");
      return;
    }

    try {
      setIsSaving(true);
      const token = localStorage.getItem("access_token");
      const headers = { Authorization: `Bearer ${token}` };

      // 1. Create plan
      const planRes = await axios.post(
        `${API_BASE}/api/v1/plans`,
        {
          customer_id: selectedCustomerId,
          iso_standard_id: selectedISO.id,
          plan_name: planName || `${selectedISO.code} Compliance Plan`,
          target_completion_date: targetDate || null,
        },
        { headers }
      );

      const planId = planRes.data.id;

      // 2. Add templates to plan
      await axios.post(
        `${API_BASE}/api/v1/plans/${planId}/templates`,
        { template_ids: selectedTemplates },
        { headers }
      );

      onPlanUpdated?.();
      onClose?.();
    } catch (error: any) {
      console.error("Error creating plan:", error);
      alert(error.response?.data?.detail || "Failed to create plan");
    } finally {
      setIsSaving(false);
    }
  };

  const toggleTemplate = (templateId: string) => {
    setSelectedTemplates((prev) =>
      prev.includes(templateId)
        ? prev.filter((id) => id !== templateId)
        : [...prev, templateId]
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-white/20 rounded-lg">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Manage Customer Plan</h2>
              <p className="text-sm text-white/80">{propCustomerName ?? customers.find(c => c.id === selectedCustomerId)?.name ?? ""}</p>
            </div>
          </div>
          <button
            onClick={() => onClose?.()}
            className="p-2 hover:bg-white/20 rounded-lg transition-all"
          >
            <X className="w-6 h-6 text-white" />
          </button>
        </div>

        {/* Progress Steps */}
        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-center space-x-4">
            <div className="flex items-center">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full ${
                  step >= 1
                    ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white"
                    : "bg-gray-300 dark:bg-gray-700 text-gray-500"
                } font-bold transition-all duration-300`}
              >
                {step > 1 ? <Check className="w-5 h-5" /> : "1"}
              </div>
              <span className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                Select ISO
              </span>
            </div>

            <ChevronRight className="w-5 h-5 text-gray-400" />

            <div className="flex items-center">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full ${
                  step >= 2
                    ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white"
                    : "bg-gray-300 dark:bg-gray-700 text-gray-500"
                } font-bold transition-all duration-300`}
              >
                {step > 2 ? <Check className="w-5 h-5" /> : "2"}
              </div>
              <span className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                Select Templates
              </span>
            </div>

            <ChevronRight className="w-5 h-5 text-gray-400" />

            <div className="flex items-center">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full ${
                  step >= 3
                    ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white"
                    : "bg-gray-300 dark:bg-gray-700 text-gray-500"
                } font-bold transition-all duration-300`}
              >
                3
              </div>
              <span className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                Review & Confirm
              </span>
            </div>
          </div>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {/* Step 1: Select ISO */}
          {step === 1 && (
            <div className="space-y-6 animate-slide-in">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Choose ISO Standard
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Select the compliance standard for this customer
                </p>
              </div>

              {/* Existing Plans Warning */}
              {existingPlans.length > 0 && (
                <div className="p-4 bg-blue-50 dark:bg-blue-900 rounded-xl border-2 border-blue-200 dark:border-blue-800">
                  <div className="flex items-start space-x-3">
                    <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                        Existing Plans for this customer:
                      </p>
                      <ul className="mt-2 space-y-1">
                        {existingPlans.map((plan) => (
                          <li
                            key={plan.id}
                            className="text-sm text-blue-700 dark:text-blue-300"
                          >
                            • {plan.iso_code} - {plan.total_templates} templates, {plan.progress_percentage}% complete
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {isos.map((iso) => {
                  const hasExistingPlan = existingPlans.some(
                    (p) => p.iso_standard_id === iso.id
                  );

                  return (
                    <button
                      key={iso.id}
                      onClick={() => !hasExistingPlan && setSelectedISO(iso)}
                      disabled={hasExistingPlan}
                      className={`p-5 rounded-xl border-2 text-left transition-all duration-300 transform hover:-translate-y-1 ${
                        selectedISO?.id === iso.id
                          ? "border-purple-500 bg-purple-50 dark:bg-purple-900 shadow-lg"
                          : hasExistingPlan
                          ? "border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 opacity-60 cursor-not-allowed"
                          : "border-gray-300 dark:border-gray-700 hover:border-purple-400 hover:shadow-md"
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <div
                            className={`p-2 rounded-lg ${
                              selectedISO?.id === iso.id
                                ? "bg-purple-600"
                                : "bg-gray-200 dark:bg-gray-700"
                            }`}
                          >
                            <Shield
                              className={`w-5 h-5 ${
                                selectedISO?.id === iso.id
                                  ? "text-white"
                                  : "text-gray-600 dark:text-gray-400"
                              }`}
                            />
                          </div>
                          <div>
                            <h4 className="font-bold text-gray-900 dark:text-white">
                              {iso.code}
                            </h4>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                              {iso.name}
                            </p>
                          </div>
                        </div>
                        {selectedISO?.id === iso.id && (
                          <CheckCircle2 className="w-6 h-6 text-purple-600 flex-shrink-0" />
                        )}
                        {hasExistingPlan && (
                          <span className="px-2 py-1 bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-300 text-xs font-semibold rounded-full">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                        {iso.description}
                      </p>
                    </button>
                  );
                })}
              </div>

              <div className="flex justify-end">
                <button
                  onClick={() => setStep(2)}
                  disabled={!selectedISO}
                  className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  <span>Next: Select Templates</span>
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Select Templates */}
          {step === 2 && selectedISO && (
            <div className="space-y-6 animate-slide-in">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Select Compliance Templates
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Choose templates for {selectedISO.code}
                </p>
              </div>

              <div className="p-4 bg-purple-50 dark:bg-purple-900 rounded-xl border-2 border-purple-200 dark:border-purple-800">
                <p className="text-sm text-purple-900 dark:text-purple-100">
                  Selected: <span className="font-bold">{selectedTemplates.length}</span> template
                  {selectedTemplates.length !== 1 ? "s" : ""}
                </p>
              </div>

              <div className="space-y-3">
                {templates.length === 0 ? (
                  <div className="text-center py-12 bg-gray-50 dark:bg-gray-700 rounded-xl">
                    <FileText className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                    <p className="text-gray-600 dark:text-gray-400">
                      No templates found for this ISO standard
                    </p>
                  </div>
                ) : (
                  templates.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => toggleTemplate(template.id)}
                      className={`w-full p-4 rounded-xl border-2 text-left transition-all duration-200 ${
                        selectedTemplates.includes(template.id)
                          ? "border-purple-500 bg-purple-50 dark:bg-purple-900 shadow-md"
                          : "border-gray-300 dark:border-gray-700 hover:border-purple-400"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start space-x-3 flex-1">
                          <div
                            className={`p-2 rounded-lg flex-shrink-0 ${
                              selectedTemplates.includes(template.id)
                                ? "bg-purple-600"
                                : "bg-gray-200 dark:bg-gray-700"
                            }`}
                          >
                            <FileText
                              className={`w-5 h-5 ${
                                selectedTemplates.includes(template.id)
                                  ? "text-white"
                                  : "text-gray-600 dark:text-gray-400"
                              }`}
                            />
                          </div>
                          <div className="flex-1">
                            <h4 className="font-semibold text-gray-900 dark:text-white">
                              {template.name}
                            </h4>
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                              {template.description || "No description available"}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-500 mt-2 flex items-center">
                              <Layers className="w-3 h-3 mr-1" />
                              {template.fillable_sections_count || 0} questions
                            </p>
                          </div>
                        </div>
                        {selectedTemplates.includes(template.id) && (
                          <CheckCircle2 className="w-6 h-6 text-purple-600 flex-shrink-0" />
                        )}
                      </div>
                    </button>
                  ))
                )}
              </div>

              <div className="flex items-center justify-between">
                <button
                  onClick={() => setStep(1)}
                  className="px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
                >
                  Back
                </button>
                <button
                  onClick={() => setStep(3)}
                  disabled={selectedTemplates.length === 0}
                  className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  <span>Next: Review</span>
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Review & Confirm */}
          {step === 3 && selectedISO && (
            <div className="space-y-6 animate-slide-in">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Review & Configure Plan
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Review your selections and set target dates
                </p>
              </div>

              {/* Plan Details */}
              <div className="space-y-4">
                <div className="p-5 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-900 dark:to-blue-900 rounded-xl border-2 border-purple-200 dark:border-purple-800">
                  <div className="flex items-center space-x-3 mb-4">
                    <Shield className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                    <h4 className="font-bold text-gray-900 dark:text-white">
                      {selectedISO.code} - {selectedISO.name}
                    </h4>
                  </div>
                  <div className="flex items-center space-x-6 text-sm">
                    <span className="flex items-center text-gray-700 dark:text-gray-300">
                      <FileText className="w-4 h-4 mr-2 text-purple-600 dark:text-purple-400" />
                      {selectedTemplates.length} templates
                    </span>
                    <span className="flex items-center text-gray-700 dark:text-gray-300">
                      <Layers className="w-4 h-4 mr-2 text-blue-600 dark:text-blue-400" />
                      ~
                      {templates
                        .filter((t) => selectedTemplates.includes(t.id))
                        .reduce((sum, t) => sum + (t.fillable_sections_count || 0), 0)}{" "}
                      questions total
                    </span>
                  </div>
                </div>

                {/* Configuration */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Plan Name (optional)
                    </label>
                    <input
                      type="text"
                      value={planName}
                      onChange={(e) => setPlanName(e.target.value)}
                      placeholder={`${selectedISO.code} Compliance Plan`}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Target Completion Date
                    </label>
                    <input
                      type="date"
                      value={targetDate}
                      onChange={(e) => setTargetDate(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all"
                    />
                  </div>
                </div>

                {/* What Happens Next */}
                <div className="p-4 bg-blue-50 dark:bg-blue-900 rounded-xl border-2 border-blue-200 dark:border-blue-800">
                  <div className="flex items-start space-x-3">
                    <Sparkles className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">
                        What happens next:
                      </p>
                      <ul className="space-y-1 text-sm text-blue-700 dark:text-blue-300">
                        <li>• Plan will be created for {propCustomerName ?? customers.find(c => c.id === selectedCustomerId)?.name}</li>
                        <li>• All {selectedTemplates.length} templates will be assigned</li>
                        <li>
                          • Tasks will be auto-generated from template questions (~
                          {templates
                            .filter((t) => selectedTemplates.includes(t.id))
                            .reduce((sum, t) => sum + (t.fillable_sections_count || 0), 0)}{" "}
                          tasks)
                        </li>
                        <li>• Customer can start working immediately</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => setStep(2)}
                  className="px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
                >
                  Back
                </button>
                <button
                  onClick={handleCreatePlan}
                  disabled={isSaving}
                  className="flex items-center space-x-2 px-8 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Creating Plan...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-5 h-5" />
                      <span>Create Plan & Generate Tasks</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

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
            transform: translateX(20px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
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
      `}</style>
    </div>
  );
}
