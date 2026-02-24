"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Users, Search, Plus, Edit2, Trash2, X, Check, Loader2,
  Building2, Mail, Phone, Shield, AlertCircle, ChevronDown, ChevronUp,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3010";

interface Customer {
  id: number; name: string; email: string; contact_person: string | null;
  phone: string | null; portal_enabled: boolean; portal_username: string | null;
  storage_type: string; iso_plans_count: number; documents_count: number;
  created_at: string; status: string;
}

interface ISOStandard { id: string; code: string; name: string; color?: string; }
interface ISOPlan { id: string; iso_code: string; iso_name: string; plan_status: string; }

const BLANK = { name: "", email: "", contact_person: "", phone: "", portal_enabled: false, storage_type: "local" };
const inp = "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm";

export default function CustomerManagement() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [isoStandards, setISOStandards] = useState<ISOStandard[]>([]);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState(BLANK);
  const [isSaving, setIsSaving] = useState(false);
  const [createdCreds, setCreatedCreds] = useState<{ username: string; password: string } | null>(null);

  // Edit modal
  const [editCustomer, setEditCustomer] = useState<Customer | null>(null);
  const [editForm, setEditForm] = useState(BLANK);

  // ISO plan assignment
  const [assignCustomer, setAssignCustomer] = useState<Customer | null>(null);
  const [customerPlans, setCustomerPlans] = useState<ISOPlan[]>([]);
  const [selectedISO, setSelectedISO] = useState("");
  const [assignMode, setAssignMode] = useState<"all" | "selective">("all");
  const [isAssigning, setIsAssigning] = useState(false);

  // Expanded plans view
  const [expandedCustomer, setExpandedCustomer] = useState<number | null>(null);
  const [expandedPlans, setExpandedPlans] = useState<Record<number, ISOPlan[]>>({});

  // Delete
  const [deleteCustomer, setDeleteCustomer] = useState<Customer | null>(null);

  const token = () => localStorage.getItem("access_token");
  const headers = () => ({ Authorization: `Bearer ${token()}` });

  useEffect(() => { loadCustomers(); loadISOStandards(); }, []);

  const loadCustomers = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/iso-customers`, { headers: headers() });
      setCustomers(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadISOStandards = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/iso-standards?active_only=true`, { headers: headers() });
      setISOStandards(r.data);
    } catch (e) { console.error(e); }
  };

  const loadCustomerPlans = async (customerId: number) => {
    try {
      const r = await axios.get(`${API_BASE}/api/v1/iso-plans/customer/${customerId}`, { headers: headers() });
      return r.data as ISOPlan[];
    } catch { return []; }
  };

  const handleCreate = async () => {
    if (!createForm.name || !createForm.email) { alert("Name and email required"); return; }
    setIsSaving(true);
    try {
      const r = await axios.post(`${API_BASE}/api/v1/iso-customers`, createForm, { headers: headers() });
      if (r.data.portal_credentials) setCreatedCreds(r.data.portal_credentials);
      else { setShowCreate(false); setCreateForm(BLANK); }
      await loadCustomers();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsSaving(false); }
  };

  const handleEdit = async () => {
    if (!editCustomer) return;
    setIsSaving(true);
    try {
      await axios.put(`${API_BASE}/api/v1/iso-customers/${editCustomer.id}`,
        { name: editForm.name, email: editForm.email, contact_person: editForm.contact_person || null, phone: editForm.phone || null },
        { headers: headers() });
      await loadCustomers();
      setEditCustomer(null);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsSaving(false); }
  };

  const handleDelete = async () => {
    if (!deleteCustomer) return;
    try {
      await axios.delete(`${API_BASE}/api/v1/iso-customers/${deleteCustomer.id}`, { headers: headers() });
      await loadCustomers();
      setDeleteCustomer(null);
    } catch (e: any) { alert(e.response?.data?.detail || e.message); setDeleteCustomer(null); }
  };

  const openAssign = async (c: Customer) => {
    setAssignCustomer(c);
    const plans = await loadCustomerPlans(c.id);
    setCustomerPlans(plans);
    setSelectedISO("");
  };

  const handleAssignISO = async () => {
    if (!assignCustomer || !selectedISO) return;
    setIsAssigning(true);
    try {
      await axios.post(`${API_BASE}/api/v1/iso-plans`,
        { customer_id: assignCustomer.id, iso_standard_id: selectedISO, template_selection_mode: assignMode, auto_generate_documents: true },
        { headers: headers() });
      const plans = await loadCustomerPlans(assignCustomer.id);
      setCustomerPlans(plans);
      setSelectedISO("");
      await loadCustomers();
    } catch (e: any) { alert(e.response?.data?.detail || e.message); }
    finally { setIsAssigning(false); }
  };

  const toggleExpand = async (customerId: number) => {
    if (expandedCustomer === customerId) { setExpandedCustomer(null); return; }
    setExpandedCustomer(customerId);
    if (!expandedPlans[customerId]) {
      const plans = await loadCustomerPlans(customerId);
      setExpandedPlans({ ...expandedPlans, [customerId]: plans });
    }
  };

  const filtered = customers.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Customer Management</h3>
          <p className="text-sm text-gray-500">Create customers and assign ISO plans</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
          <Plus className="w-4 h-4" /> New Customer
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input className="w-full pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm"
          placeholder="Search customers..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {/* List */}
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
                          <span className={`px-1.5 py-0.5 rounded ${p.plan_status === "completed" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>{p.plan_status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => openAssign(c)} title="Assign ISO Plan"
                  className="p-1.5 text-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded" >
                  <Shield className="w-4 h-4" />
                </button>
                <button onClick={() => { setEditCustomer(c); setEditForm({ name: c.name, email: c.email, contact_person: c.contact_person || "", phone: c.phone || "", portal_enabled: c.portal_enabled, storage_type: c.storage_type }); }}
                  className="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded">
                  <Edit2 className="w-4 h-4" />
                </button>
                <button onClick={() => setDeleteCustomer(c)} className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded">
                  <Trash2 className="w-4 h-4" />
                </button>
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

      {/* Create Modal */}
      {showCreate && !createdCreds && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">New Customer</h3>
              <button onClick={() => { setShowCreate(false); setCreateForm(BLANK); }}><X className="w-5 h-5 text-gray-500" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Company Name *</label>
                <input className={inp} value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} placeholder="Acme Corp" /></div>
              <div><label className="block text-xs font-medium text-gray-600 mb-1">Email *</label>
                <input className={inp} type="email" value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} placeholder="contact@acme.com" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-xs font-medium text-gray-600 mb-1">Contact Person</label>
                  <input className={inp} value={createForm.contact_person} onChange={(e) => setCreateForm({ ...createForm, contact_person: e.target.value })} /></div>
                <div><label className="block text-xs font-medium text-gray-600 mb-1">Phone</label>
                  <input className={inp} value={createForm.phone} onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })} /></div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={createForm.portal_enabled} onChange={(e) => setCreateForm({ ...createForm, portal_enabled: e.target.checked })} className="w-4 h-4" />
                <span className="text-sm text-gray-700 dark:text-gray-300">Enable portal access (auto-generate credentials)</span>
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => { setShowCreate(false); setCreateForm(BLANK); }} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleCreate} disabled={isSaving || !createForm.name || !createForm.email}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50">
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Portal Credentials Modal */}
      {createdCreds && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-sm w-full p-6">
            <div className="flex items-center gap-2 mb-4">
              <Check className="w-6 h-6 text-green-500" />
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Customer Created!</h3>
            </div>
            <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3 mb-4">
              Save these credentials — the password cannot be retrieved later.
            </p>
            <div className="space-y-2 font-mono text-sm bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
              <p><span className="text-gray-500">Username:</span> <strong>{createdCreds.username}</strong></p>
              <p><span className="text-gray-500">Password:</span> <strong>{createdCreds.password}</strong></p>
            </div>
            <button onClick={() => { setCreatedCreds(null); setShowCreate(false); setCreateForm(BLANK); }}
              className="w-full mt-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">Done</button>
          </div>
        </div>
      )}

      {/* Edit Modal */}
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

      {/* Assign ISO Plan Modal */}
      {assignCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Assign ISO Plan</h3>
                <p className="text-sm text-gray-500">{assignCustomer.name}</p>
              </div>
              <button onClick={() => setAssignCustomer(null)}><X className="w-5 h-5 text-gray-500" /></button>
            </div>

            {/* Existing plans */}
            {customerPlans.length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Current Plans</p>
                <div className="space-y-1">
                  {customerPlans.map((p) => (
                    <div key={p.id} className="flex items-center gap-2 text-sm p-2 bg-gray-50 dark:bg-gray-700 rounded-lg">
                      <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs font-medium">{p.iso_code}</span>
                      <span className="text-gray-700 dark:text-gray-300 flex-1">{p.iso_name}</span>
                      <span className="text-xs text-gray-400">{p.plan_status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Add new plan */}
            <div className="space-y-3">
              <p className="text-xs font-medium text-gray-500 uppercase">Add New Plan</p>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">ISO Standard</label>
                <select className={inp} value={selectedISO} onChange={(e) => setSelectedISO(e.target.value)}>
                  <option value="">Select ISO standard...</option>
                  {isoStandards
                    .filter((iso) => !customerPlans.some((p) => p.iso_code === iso.code))
                    .map((iso) => (
                      <option key={iso.id} value={iso.id}>{iso.code} — {iso.name}</option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Template Mode</label>
                <select className={inp} value={assignMode} onChange={(e) => setAssignMode(e.target.value as "all" | "selective")}>
                  <option value="all">All templates (recommended)</option>
                  <option value="selective">Selective</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => setAssignCustomer(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Close</button>
              <button onClick={handleAssignISO} disabled={!selectedISO || isAssigning}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50">
                {isAssigning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />} Assign Plan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-sm w-full p-6">
            <div className="flex items-center gap-3 mb-3">
              <AlertCircle className="w-6 h-6 text-red-500" />
              <h3 className="font-bold text-gray-900 dark:text-white">Delete {deleteCustomer.name}?</h3>
            </div>
            <p className="text-sm text-gray-500 mb-1">This will delete all associated plans, documents and tasks.</p>
            {deleteCustomer.iso_plans_count > 0 && (
              <p className="text-sm text-red-500 mb-4">⚠ Customer has {deleteCustomer.iso_plans_count} ISO plan(s). Delete plans first.</p>
            )}
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteCustomer(null)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleDelete} disabled={deleteCustomer.iso_plans_count > 0}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50">
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
