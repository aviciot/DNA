"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Users,
  Plus,
  Edit2,
  Trash2,
  X,
  Check,
  Loader2,
  Building2,
  Mail,
  Phone,
  AlertCircle,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8400";

interface Customer {
  id: number;
  company_name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  industry: string | null;
  active_status: boolean;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export default function CustomerManagement() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [deleteConfirmCustomer, setDeleteConfirmCustomer] = useState<Customer | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    company_name: "",
    contact_person: "",
    email: "",
    phone: "",
    address: "",
    industry: "",
    active_status: true,
  });

  useEffect(() => {
    loadCustomers();
  }, []);

  const loadCustomers = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/customers`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCustomers(response.data);
    } catch (error) {
      console.error("Failed to load customers:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setFormData({
      company_name: "",
      contact_person: "",
      email: "",
      phone: "",
      address: "",
      industry: "",
      active_status: true,
    });
    setIsCreateModalOpen(true);
  };

  const handleEdit = (customer: Customer) => {
    setEditingCustomer(customer);
    setFormData({
      company_name: customer.company_name,
      contact_person: customer.contact_person || "",
      email: customer.email || "",
      phone: customer.phone || "",
      address: customer.address || "",
      industry: customer.industry || "",
      active_status: customer.active_status,
    });
    setIsEditModalOpen(true);
  };

  const handleSaveCreate = async () => {
    if (!formData.company_name) {
      alert("Company name is required");
      return;
    }

    setIsSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.post(
        `${API_BASE}/api/v1/customers`,
        {
          company_name: formData.company_name,
          contact_person: formData.contact_person || null,
          email: formData.email || null,
          phone: formData.phone || null,
          address: formData.address || null,
          industry: formData.industry || null,
          active_status: formData.active_status,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      await loadCustomers();
      setIsCreateModalOpen(false);
    } catch (error: any) {
      console.error("Failed to create customer:", error);
      alert(`Failed to create customer: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingCustomer || !formData.company_name) return;

    setIsSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.put(
        `${API_BASE}/api/v1/customers/${editingCustomer.id}`,
        {
          company_name: formData.company_name,
          contact_person: formData.contact_person || null,
          email: formData.email || null,
          phone: formData.phone || null,
          address: formData.address || null,
          industry: formData.industry || null,
          active_status: formData.active_status,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      await loadCustomers();
      setIsEditModalOpen(false);
      setEditingCustomer(null);
    } catch (error: any) {
      console.error("Failed to update customer:", error);
      alert(`Failed to update customer: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (customer: Customer) => {
    if (customer.document_count > 0) {
      alert(
        `Cannot delete ${customer.company_name}: ${customer.document_count} document(s) are associated. Please remove documents first.`
      );
      return;
    }

    setDeleteConfirmCustomer(customer);
  };

  const confirmDelete = async () => {
    if (!deleteConfirmCustomer) return;

    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${API_BASE}/api/v1/customers/${deleteConfirmCustomer.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      await loadCustomers();
      setDeleteConfirmCustomer(null);
    } catch (error: any) {
      console.error("Failed to delete customer:", error);
      alert(`Failed to delete customer: ${error.response?.data?.detail || error.message}`);
      setDeleteConfirmCustomer(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Customer Management
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Create, update, and manage customers in the system
          </p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add Customer</span>
        </button>
      </div>

      {/* Customers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {customers.map((customer) => (
          <div
            key={customer.id}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                {/* Company Name */}
                <div className="flex items-center space-x-2 mb-2">
                  <Building2 className="w-5 h-5 text-blue-500" />
                  <h4 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {customer.company_name}
                  </h4>
                  {customer.active_status ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-900/30 text-gray-800 dark:text-gray-300">
                      Inactive
                    </span>
                  )}
                </div>

                {/* Contact Info */}
                <div className="space-y-1 text-sm text-gray-600 dark:text-gray-400">
                  {customer.contact_person && (
                    <p>
                      <span className="font-medium">Contact:</span> {customer.contact_person}
                    </p>
                  )}
                  {customer.email && (
                    <div className="flex items-center space-x-1">
                      <Mail className="w-3 h-3" />
                      <span>{customer.email}</span>
                    </div>
                  )}
                  {customer.phone && (
                    <div className="flex items-center space-x-1">
                      <Phone className="w-3 h-3" />
                      <span>{customer.phone}</span>
                    </div>
                  )}
                  {customer.industry && (
                    <p>
                      <span className="font-medium">Industry:</span> {customer.industry}
                    </p>
                  )}
                </div>

                {/* Document Count */}
                <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                  {customer.document_count} document(s)
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleEdit(customer)}
                  title="Edit customer"
                  className="p-1.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(customer)}
                  title="Delete customer"
                  className="p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}

        {customers.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500 dark:text-gray-400">
            No customers found. Click "Add Customer" to create one.
          </div>
        )}
      </div>

      {/* Create Modal */}
      {isCreateModalOpen && (
        <CustomerModal
          title="Add New Customer"
          formData={formData}
          setFormData={setFormData}
          onSave={handleSaveCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          isSaving={isSaving}
        />
      )}

      {/* Edit Modal */}
      {isEditModalOpen && editingCustomer && (
        <CustomerModal
          title="Edit Customer"
          formData={formData}
          setFormData={setFormData}
          onSave={handleSaveEdit}
          onCancel={() => {
            setIsEditModalOpen(false);
            setEditingCustomer(null);
          }}
          isSaving={isSaving}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmCustomer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6">
              <div className="flex items-center space-x-3 mb-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Delete Customer?
                </h3>
              </div>

              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Are you sure you want to delete <strong>{deleteConfirmCustomer.company_name}</strong>?
                This action cannot be undone.
              </p>

              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setDeleteConfirmCustomer(null)}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmDelete}
                  className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Modal Component
function CustomerModal({
  title,
  formData,
  setFormData,
  onSave,
  onCancel,
  isSaving,
}: {
  title: string;
  formData: any;
  setFormData: (data: any) => void;
  onSave: () => void;
  onCancel: () => void;
  isSaving: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Modal Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white">{title}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Fill in the customer details below
              </p>
            </div>
            <button
              onClick={onCancel}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Form */}
          <div className="space-y-4">
            {/* Company Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Company Name *
              </label>
              <input
                type="text"
                value={formData.company_name}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="e.g., Acme Corporation"
              />
            </div>

            {/* Contact Person */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Contact Person
              </label>
              <input
                type="text"
                value={formData.contact_person}
                onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="e.g., John Doe"
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Email
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="e.g., contact@example.com"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Phone
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="e.g., +1 234 567 8900"
              />
            </div>

            {/* Industry */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Industry
              </label>
              <input
                type="text"
                value={formData.industry}
                onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="e.g., Technology, Healthcare, Manufacturing"
              />
            </div>

            {/* Address */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Address
              </label>
              <textarea
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="Full address"
              />
            </div>

            {/* Active Status */}
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="active_status"
                checked={formData.active_status}
                onChange={(e) => setFormData({ ...formData, active_status: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="active_status" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Active
              </label>
            </div>
          </div>

          {/* Modal Actions */}
          <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={onCancel}
              disabled={isSaving}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onSave}
              disabled={isSaving || !formData.company_name}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Save</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
