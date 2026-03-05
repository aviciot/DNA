"use client";

import { useState, useEffect } from "react";
import {
  Users, Search, Plus, Edit2, Trash2, X, Check, Loader2,
  Building2, Mail, Phone, Shield, AlertCircle, ChevronDown, ChevronUp,
  FileText, CheckCircle2, Circle, RefreshCw,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import CustomerCreationWizard from "@/components/CustomerCreationWizard";
import api from "@/lib/api";

interface Customer {
  id: number; name: string; email: string; contact_person: string | null;
  phone: string | null; portal_enabled: boolean; portal_username: string | null;
  storage_type: string; iso_plans_count: number; documents_count: number;
  created_at: string; status: string;
}

interface ISOStandard { id: string; code: string; name: string; }

interface ISOPlan {
  id: string; iso_code: string; iso_name: string; plan_status: string;
  document_count: number; task_count: number;
}

interface PlanTemplate {
  id: string; name: string; document_type: string; version_number: number;
  document_id: string | null; has_document: boolean;
}

const inp = "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm";

const canWrite = (role?: string) => role === "admin" || role === "dna_operator";
const canDelete = (role?: string) => role === "admin";

export default function CustomerManagement() {
  const { user } = useAuthStore();
  const role = user?.role;

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);

  const [showWizard, setShowWizard] = useState(false);

  // Edit modal
  const [editCustomer, setEditCustomer] = useState<Customer | null>(null);
  const [editForm, setEditForm] = useState({ name: "", email: "", contact_person: "", phone: "" });
  const [isSaving, setIsSaving] = useState(false);

  // Plan manager modal
  const [manageCustomer, setManageCustomer] = useState<Customer | null>(null);
  const [customerPlans, setCustomerPlans] = useState<ISOPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(false);
  // Add new plan
  const [selectedISO, setSelectedISO] = useState("");
  const [assignMode, setAssignMode] = useState<"all" | "selective">("all");
  const [isAssigning, setIsAssigning] = useState(false);
  // Per-plan template expansion
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);
  const [planTemplates, setPlanTemplates] = useState<Record<string, PlanTemplate[]>>({});
  const [templatesLoading, setTemplatesLoading] = useState<string | null>(null);
  const [templateAction, setTemplateAction] = useState<string | null>(null); // template id being added/removed
  // Delete plan confirm (inline, per plan)
  const [deletingPlanId, setDeletingPlanId] = useState<string | null>(null);
  const [isDeletingPlan, setIsDeletingPlan] = useState(false);
  // Remove template confirm (inline)
  const [removingTemplate, setRemovingTemplate] = useState<{ planId: string; templateId: string } | null>(null);

  // Expanded plans in customer list (read-only)
  const [expandedCustomer, setExpandedCustomer] = useState<number | null>(null);
  const [expandedPlans, setExpandedPlans] = useState<Record<number, ISOPlan[]>>({});

  // Delete customer
  const [deleteCustomer, setDeleteCustomer] = useState<Customer | null>(null);

  useEffect(() => { loadCustomers(); loadISOStandards(); }, []);

  const loadCustomers = async () => {
    try {
      const r = await api.get("/api/v1/iso-customers");
      setCustomers(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadISOStandards = async () => {
    try {
      const r = await api.get("/api/v1/iso-standards?active_only=true");
      setISOStandards(r.data);
    } catch (e) { console.error(e); }
  };

  const loadCustomerPlans = async (customerId: number): Promise<ISOPlan[]> => {
    try {
      const r = await api.get(`/api/v1/iso-plans/customer/${customerId}`);
      return r.data as ISOPlan[];
    } catch { return []; }
  };

  const openManage = async (c: Customer) => {
    setManageCustomer(c);
    setExpandedPlanId(null);
    setPlanTemplates({});
    setDeletingPlanId(null);
    setRemovingTemplate(null);
    setSelectedISO("");
    setAssignMode("all");
    setPlansLoading(true);
    setCustomerPlans(await loadCustomerPlans(c.id));
    setPlansLoading(false);
  };

  const closeManage = () => {
    setManageCustomer(null);
    setCustomerPlans([]);
    setExpandedPlanId(null);
    setPlanTemplates({});
    setDeletingPlanId(null);
    setRemovingTemplate(null);
  };

  const togglePlanTemplates = async (planId: string) => {
    if (expandedPlanId === planId) { setExpandedPlanId(null); return; }
    setExpandedPlanId(planId);
    setRemovingTemplate(null);
    if (!planTemplates[planId]) {
      setTemplatesLoading(planId);
      try {
        const r = await api.get(`/api/v1/iso-plans/${planId}/templates`);
        setPlanTemplates(prev => ({ ...prev, [planId]: r.data }));
      } catch (e) { console.error(e); }
      finally { setTemplatesLoading(null); }
    }
  };

  const handleAddTemplate = async (planId: string, templateId: string) => {
    setTemplateAction(templateId);
    try {
      await api.post(`/api/v1/iso-plans/${planId}/templates/${templateId}`);
      // Refresh template list and plan stats
      const [tmplR, plansR] = await Promise.all([
        api.get(`/api/v1/iso-plans/${planId}/templates`),
        loadCustomerPlans(manageCustomer!.id),
      ]);
      setPlanTemplates(prev => ({ ...prev, [planId]: tmplR.data }));
      setCustomerPlans(plansR);
      await loadCustomers();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setTemplateAction(null); }
  };

  const handleRemoveTemplate = async (planId: string, templateId: string) => {
    setRemovingTemplate(null);
    setTemplateAction(templateId);
    try {
      await api.delete(`/api/v1/iso-plans/${planId}/templates/${templateId}`);
      const [tmplR, plansR] = await Promise.all([
        api.get(`/api/v1/iso-plans/${planId}/templates`),
        loadCustomerPlans(manageCustomer!.id),
      ]);
      setPlanTemplates(prev => ({ ...prev, [planId]: tmplR.data }));
      setCustomerPlans(plansR);
      await loadCustomers();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setTemplateAction(null); }
  };

  const handleDeletePlan = async (planId: string) => {
    setIsDeletingPlan(true);
    try {
      await api.delete(`/api/v1/iso-plans/${planId}`);
      const updated = await loadCustomerPlans(manageCustomer!.id);
      setCustomerPlans(updated);
      if (expandedPlanId === planId) setExpandedPlanId(null);
      setPlanTemplates(prev => { const n = { ...prev }; delete n[planId]; return n; });
      await loadCustomers();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsDeletingPlan(false); setDeletingPlanId(null); }
  };

  const handleAssignISO = async () => {
    if (!manageCustomer || !selectedISO) return;
    setIsAssigning(true);
    try {
      await api.post("/api/v1/iso-plans", {
        customer_id: manageCustomer.id, iso_standard_id: selectedISO,
        template_selection_mode: assignMode, auto_generate_documents: true,
      });
      setCustomerPlans(await loadCustomerPlans(manageCustomer.id));
      setSelectedISO("");
      await loadCustomers();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsAssigning(false); }
  };

  const handleEdit = async () => {
    if (!editCustomer) return;
    setIsSaving(true);
    try {
      await api.put(`/api/v1/iso-customers/${editCustomer.id}`,
        { name: editForm.name, email: editForm.email, contact_person: editForm.contact_person || null, phone: editForm.phone || null });
      await loadCustomers();
      setEditCustomer(null);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsSaving(false); }
  };

  const handleDeleteCustomer = async () => {
    if (!deleteCustomer) return;
    try {
      await api.delete(`/api/v1/iso-customers/${deleteCustomer.id}`);
      await loadCustomers();
      setDeleteCustomer(null);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); setDeleteCustomer(null); }
  };

  const toggleExpand = async (customerId: number) => {
    if (expandedCustomer === customerId) { setExpandedCustomer(null); return; }
    setExpandedCustomer(customerId);
    if (!expandedPlans[customerId]) {
      setExpandedPlans({ ...expandedPlans, [customerId]: await loadCustomerPlans(customerId) });
    }
  };

  const planStatusColor = (s: string) =>
    s === "completed" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
    : s === "active" || s === "generated" ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
    : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300";

  const filtered = customers.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Customer Management</h3>
          <p className="text-sm text-gray-500">Create customers and manage ISO plans</p>
        </div>
        {canWrite(role) && (
          <button onClick={() => setShowWizard(true)}
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
            <Plus className="w-4 h-4" /> New Customer
          </button>
        )}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input className="w-full pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm"
          placeholder="Search customers..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <div className="space-y-3">
        {filtered.map((c) => (
          <div key={c.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="p-4 flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Building2 className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900 dark:text-white">{c.name}</h4>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
                    <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{c.email}</span>
                    {c.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{c.phone}</span>}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span className="flex items-center gap-1"><Shield className="w-3 h-3" />{c.iso_plans_count} ISO plan(s)</span>
                    <button onClick={() => toggleExpand(c.id)} className="text-blue-500 hover:underline flex items-center gap-0.5">
                      {expandedCustomer === c.id ? <><ChevronUp className="w-3 h-3" />Hide plans</> : <><ChevronDown className="w-3 h-3" />View plans</>}
                    </button>
                  </div>
                  {expandedCustomer === c.id && expandedPlans[c.id] && (
                    <div className="mt-2 space-y-1">
                      {expandedPlans[c.id].length === 0 ? (
                        <p className="text-xs text-gray-400">No ISO plans assigned</p>
                      ) : expandedPlans[c.id].map((p) => (
                        <div key={p.id} className="flex items-center gap-2 text-xs">
                          <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded font-medium">{p.iso_code}</span>
                          <span className="text-gray-600 dark:text-gray-400">{p.iso_name}</span>
                          <span className={`px-1.5 py-0.5 rounded ${planStatusColor(p.plan_status)}`}>{p.plan_status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {canWrite(role) && (
                  <button onClick={() => openManage(c)} title="Manage ISO Plans"
                    className="p-1.5 text-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded">
                    <Shield className="w-4 h-4" />
                  </button>
                )}
                {canWrite(role) && (
                  <button onClick={() => { setEditCustomer(c); setEditForm({ name: c.name, email: c.email, contact_person: c.contact_person || "", phone: c.phone || "" }); }}
                    className="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded">
                    <Edit2 className="w-4 h-4" />
                  </button>
                )}
                {canDelete(role) && (
                  <button onClick={() => setDeleteCustomer(c)} className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>{search ? "No customers match your search" : "No customers yet"}</p>
          </div>
        )}
      </div>

      <CustomerCreationWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        onSuccess={() => { setShowWizard(false); loadCustomers(); }}
      />

      {/* ── Edit customer modal ─────────────────────────────────────────── */}
      {editCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Edit {editCustomer.name}</h3>
              <button onClick={() => setEditCustomer(null)}><X className="w-5 h-5 text-gray-500" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Name *</label>
                <input className={inp} value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Email *</label>
                <input className={inp} type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-xs font-medium text-gray-600 mb-1">Contact Person</label>
                  <input className={inp} value={editForm.contact_person} onChange={(e) => setEditForm({ ...editForm, contact_person: e.target.value })} /></div>
                <div><label className="block text-xs font-medium text-gray-600 mb-1">Phone</label>
                  <input className={inp} value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => setEditCustomer(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleEdit} disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Manage ISO Plans modal ──────────────────────────────────────── */}
      {manageCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-xl max-h-[85vh] flex flex-col">
            {/* Header */}
            <div className="flex justify-between items-start p-5 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Manage ISO Plans</h3>
                <p className="text-sm text-gray-500 mt-0.5">{manageCustomer.name}</p>
              </div>
              <button onClick={closeManage}><X className="w-5 h-5 text-gray-500" /></button>
            </div>

            <div className="overflow-y-auto flex-1 p-5 space-y-5">

              {/* Existing Plans */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Existing Plans</p>
                {plansLoading ? (
                  <div className="flex items-center gap-2 text-sm text-gray-400 py-3">
                    <Loader2 className="w-4 h-4 animate-spin" /> Loading plans…
                  </div>
                ) : customerPlans.length === 0 ? (
                  <p className="text-sm text-gray-400 py-2">No ISO plans assigned yet.</p>
                ) : (
                  <div className="space-y-2">
                    {customerPlans.map((plan) => (
                      <div key={plan.id} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                        {/* Plan header row */}
                        <div className="flex items-center gap-2 p-3 bg-gray-50 dark:bg-gray-700/50">
                          <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs font-semibold">
                            {plan.iso_code}
                          </span>
                          <span className="text-sm font-medium text-gray-800 dark:text-gray-200 flex-1 truncate">{plan.iso_name}</span>
                          <span className={`px-1.5 py-0.5 rounded text-xs ${planStatusColor(plan.plan_status)}`}>{plan.plan_status}</span>
                          <span className="text-xs text-gray-400 flex items-center gap-1">
                            <FileText className="w-3 h-3" />{plan.document_count}
                          </span>
                          {/* Expand templates toggle */}
                          <button
                            onClick={() => togglePlanTemplates(plan.id)}
                            className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded"
                            title="Manage templates"
                          >
                            {expandedPlanId === plan.id
                              ? <ChevronUp className="w-4 h-4" />
                              : <ChevronDown className="w-4 h-4" />}
                          </button>
                          {/* Delete plan */}
                          {canDelete(role) && (
                            deletingPlanId === plan.id ? (
                              <div className="flex items-center gap-1">
                                <span className="text-xs text-red-600">Delete plan?</span>
                                <button
                                  onClick={() => handleDeletePlan(plan.id)}
                                  disabled={isDeletingPlan}
                                  className="text-xs px-2 py-0.5 bg-red-600 hover:bg-red-700 text-white rounded disabled:opacity-50"
                                >
                                  {isDeletingPlan ? <Loader2 className="w-3 h-3 animate-spin" /> : "Yes"}
                                </button>
                                <button onClick={() => setDeletingPlanId(null)} className="text-xs px-2 py-0.5 text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600 rounded">No</button>
                              </div>
                            ) : (
                              <button
                                onClick={() => { setDeletingPlanId(plan.id); setExpandedPlanId(null); }}
                                className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                                title="Delete plan"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )
                          )}
                        </div>

                        {/* Template list (expanded) */}
                        {expandedPlanId === plan.id && (
                          <div className="border-t border-gray-200 dark:border-gray-700">
                            {templatesLoading === plan.id ? (
                              <div className="flex items-center gap-2 text-sm text-gray-400 p-3">
                                <Loader2 className="w-4 h-4 animate-spin" /> Loading templates…
                              </div>
                            ) : (planTemplates[plan.id] || []).length === 0 ? (
                              <p className="text-sm text-gray-400 p-3">No templates available for this ISO standard.</p>
                            ) : (
                              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                                {(planTemplates[plan.id] || []).map((tmpl) => {
                                  const isBusy = templateAction === tmpl.id;
                                  const isRemoving = removingTemplate?.planId === plan.id && removingTemplate?.templateId === tmpl.id;
                                  return (
                                    <div key={tmpl.id} className={`flex items-center gap-2 px-3 py-2 text-sm ${tmpl.has_document ? "bg-white dark:bg-gray-800" : "bg-gray-50/50 dark:bg-gray-800/50"}`}>
                                      {tmpl.has_document
                                        ? <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                                        : <Circle className="w-4 h-4 text-gray-300 flex-shrink-0" />}
                                      <span className={`flex-1 truncate ${tmpl.has_document ? "text-gray-800 dark:text-gray-200" : "text-gray-400"}`}>
                                        {tmpl.name}
                                      </span>
                                      <span className="text-xs text-gray-400 flex-shrink-0">{tmpl.document_type}</span>
                                      {canDelete(role) && (
                                        tmpl.has_document ? (
                                          isRemoving ? (
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                              <span className="text-xs text-red-600">Remove?</span>
                                              <button
                                                onClick={() => handleRemoveTemplate(plan.id, tmpl.id)}
                                                disabled={isBusy}
                                                className="text-xs px-1.5 py-0.5 bg-red-600 hover:bg-red-700 text-white rounded disabled:opacity-50"
                                              >
                                                {isBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : "Yes"}
                                              </button>
                                              <button onClick={() => setRemovingTemplate(null)} className="text-xs px-1.5 py-0.5 text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600 rounded">No</button>
                                            </div>
                                          ) : (
                                            <button
                                              onClick={() => setRemovingTemplate({ planId: plan.id, templateId: tmpl.id })}
                                              disabled={isBusy}
                                              className="text-xs px-2 py-0.5 text-red-500 border border-red-200 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/30 rounded disabled:opacity-40 flex-shrink-0"
                                            >
                                              {isBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : "Remove"}
                                            </button>
                                          )
                                        ) : (
                                          <button
                                            onClick={() => handleAddTemplate(plan.id, tmpl.id)}
                                            disabled={isBusy}
                                            className="text-xs px-2 py-0.5 text-blue-600 border border-blue-200 hover:bg-blue-50 dark:border-blue-800 dark:hover:bg-blue-900/30 rounded disabled:opacity-40 flex-shrink-0 flex items-center gap-1"
                                          >
                                            {isBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <><RefreshCw className="w-3 h-3" /> Add</>}
                                          </button>
                                        )
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Add New Plan */}
              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Add New Plan</p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">ISO Standard</label>
                    <select className={inp} value={selectedISO} onChange={(e) => setSelectedISO(e.target.value)}>
                      <option value="">Select ISO standard…</option>
                      {isoStandards
                        .filter((iso) => !customerPlans.some((p) => p.iso_code === iso.code))
                        .map((iso) => <option key={iso.id} value={iso.id}>{iso.code} — {iso.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Template Mode</label>
                    <select className={inp} value={assignMode} onChange={(e) => setAssignMode(e.target.value as "all" | "selective")}>
                      <option value="all">All templates (recommended)</option>
                      <option value="selective">Selective</option>
                    </select>
                  </div>
                  <button
                    onClick={handleAssignISO}
                    disabled={!selectedISO || isAssigning}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50"
                  >
                    {isAssigning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                    Assign Plan
                  </button>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
              <button onClick={closeManage} className="w-full px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete customer modal ───────────────────────────────────────── */}
      {deleteCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center gap-3 mb-3">
              <AlertCircle className="w-6 h-6 text-red-500 flex-shrink-0" />
              <h3 className="font-bold text-gray-900 dark:text-white">Delete {deleteCustomer.name}?</h3>
            </div>
            <p className="text-sm text-gray-500 mb-3">This will permanently delete the customer and all associated data.</p>
            {deleteCustomer.iso_plans_count > 0 ? (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-4">
                <p className="text-sm text-amber-700 dark:text-amber-300 font-medium">
                  {deleteCustomer.iso_plans_count} ISO plan(s) must be deleted first.
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  Use the plan manager to remove all plans before deleting this customer.
                </p>
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteCustomer(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              {deleteCustomer.iso_plans_count > 0 ? (
                <button
                  onClick={() => { setDeleteCustomer(null); openManage(deleteCustomer); }}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg"
                >
                  <Shield className="w-4 h-4" /> Manage Plans
                </button>
              ) : (
                <button onClick={handleDeleteCustomer}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg">
                  <Trash2 className="w-4 h-4" /> Delete
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
