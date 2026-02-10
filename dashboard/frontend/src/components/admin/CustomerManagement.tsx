"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Users,
  Search,
  Edit2,
  Trash2,
  X,
  Check,
  Loader2,
  Building2,
  Mail,
  Phone,
  Key,
  RefreshCw,
  Copy,
  Eye,
  EyeOff,
  Archive,
  AlertCircle,
  Shield,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface ISOCustomer {
  id: number;
  name: string;
  website: string | null;
  contact_person: string | null;
  phone: string | null;
  address: string | null;
  email: string;
  contact_email: string | null;
  document_email: string | null;
  storage_type: string;
  portal_enabled: boolean;
  portal_username: string | null;
  portal_password: string | null;
  iso_plans_count: number;
  documents_count: number;
  created_at: string;
  updated_at: string;
}

export default function CustomerManagement() {
  const [customers, setCustomers] = useState<ISOCustomer[]>([]);
  const [filteredCustomers, setFilteredCustomers] = useState<ISOCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingCustomer, setEditingCustomer] = useState<ISOCustomer | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [deleteConfirmCustomer, setDeleteConfirmCustomer] = useState<ISOCustomer | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [copiedPassword, setCopiedPassword] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    website: "",
    contact_person: "",
    phone: "",
    address: "",
    email: "",
    contact_email: "",
    document_email: "",
    storage_type: "local",
    portal_enabled: false,
    portal_username: "",
    portal_password: "",
  });

  useEffect(() => {
    loadCustomers();
  }, []);

  useEffect(() => {
    // Filter customers based on search query
    if (searchQuery.trim() === "") {
      setFilteredCustomers(customers);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = customers.filter((customer) =>
        customer.name.toLowerCase().includes(query) ||
        customer.email.toLowerCase().includes(query) ||
        customer.contact_person?.toLowerCase().includes(query)
      );
      setFilteredCustomers(filtered);
    }
  }, [searchQuery, customers]);

  const loadCustomers = async () => {
    try {
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/iso-customers`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCustomers(response.data);
      setFilteredCustomers(response.data);
    } catch (error) {
      console.error("Failed to load customers:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (customer: ISOCustomer) => {
    setEditingCustomer(customer);
    setFormData({
      name: customer.name,
      website: customer.website || "",
      contact_person: customer.contact_person || "",
      phone: customer.phone || "",
      address: customer.address || "",
      email: customer.email,
      contact_email: customer.contact_email || "",
      document_email: customer.document_email || "",
      storage_type: customer.storage_type,
      portal_enabled: customer.portal_enabled,
      portal_username: customer.portal_username || "",
      portal_password: customer.portal_password || "",
    });
    setIsEditModalOpen(true);
  };

  const handleResetPortalCredentials = async (customer: ISOCustomer) => {
    if (!confirm(`Reset portal credentials for ${customer.name}? This will generate a new password.`)) {
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      const newPassword = generatePassword();

      await axios.put(
        `${API_BASE}/api/v1/iso-customers/${customer.id}`,
        {
          ...customer,
          portal_password: newPassword,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert(`New password generated: ${newPassword}\n\nPlease save this password!`);
      await loadCustomers();
    } catch (error: any) {
      console.error("Failed to reset portal credentials:", error);
      alert(`Failed to reset credentials: ${error.response?.data?.detail || error.message}`);
    }
  };

  const generatePassword = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let password = "";
    for (let i = 0; i < 16; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return password;
  };

  const handleSaveEdit = async () => {
    if (!editingCustomer || !formData.name || !formData.email) return;

    setIsSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.put(
        `${API_BASE}/api/v1/iso-customers/${editingCustomer.id}`,
        {
          name: formData.name,
          website: formData.website || null,
          contact_person: formData.contact_person || null,
          phone: formData.phone || null,
          address: formData.address || null,
          email: formData.email,
          contact_email: formData.contact_email || formData.email,
          document_email: formData.document_email || formData.email,
          storage_type: formData.storage_type,
          portal_enabled: formData.portal_enabled,
          portal_username: formData.portal_enabled ? formData.portal_username : null,
          portal_password: formData.portal_enabled ? formData.portal_password : null,
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

  const handleDelete = (customer: ISOCustomer) => {
    setDeleteConfirmCustomer(customer);
  };

  const confirmDelete = async (archive: boolean) => {
    if (!deleteConfirmCustomer) return;

    try {
      const token = localStorage.getItem("access_token");

      if (archive) {
        // TODO: Implement archive endpoint
        // For now, just delete
        console.log("Archive functionality coming soon");
      }

      await axios.delete(`${API_BASE}/api/v1/iso-customers/${deleteConfirmCustomer.id}`, {
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

  const copyPassword = (password: string) => {
    navigator.clipboard.writeText(password);
    setCopiedPassword(true);
    setTimeout(() => setCopiedPassword(false), 2000);
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
      {/* Header with Search */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Customer Management
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Manage customer accounts, portal access, and ISO certifications
          </p>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Search customers by name, email, or contact..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400"
          />
        </div>
      </div>

      {/* Customers List */}
      <div className="space-y-4">
        {filteredCustomers.map((customer) => (
          <div
            key={customer.id}
            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                {/* Company Name and Portal Status */}
                <div className="flex items-center space-x-3 mb-3">
                  <Building2 className="w-6 h-6 text-blue-500" />
                  <h4 className="text-xl font-bold text-gray-900 dark:text-white">
                    {customer.name}
                  </h4>
                  {customer.portal_enabled && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300">
                      <Key className="w-3 h-3 mr-1" />
                      Portal Enabled
                    </span>
                  )}
                </div>

                {/* Contact Info Grid */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="space-y-2">
                    {customer.contact_person && (
                      <p className="text-gray-600 dark:text-gray-400">
                        <span className="font-medium">Contact:</span> {customer.contact_person}
                      </p>
                    )}
                    <div className="flex items-center space-x-2 text-gray-600 dark:text-gray-400">
                      <Mail className="w-4 h-4" />
                      <span>{customer.email}</span>
                    </div>
                    {customer.phone && (
                      <div className="flex items-center space-x-2 text-gray-600 dark:text-gray-400">
                        <Phone className="w-4 h-4" />
                        <span>{customer.phone}</span>
                      </div>
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2 text-gray-600 dark:text-gray-400">
                      <Shield className="w-4 h-4" />
                      <span>{customer.iso_plans_count} ISO Plan{customer.iso_plans_count !== 1 ? 's' : ''}</span>
                    </div>
                    <p className="text-gray-600 dark:text-gray-400">
                      {customer.documents_count} Document{customer.documents_count !== 1 ? 's' : ''}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-500">
                      Created: {new Date(customer.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center space-x-2">
                {customer.portal_enabled && (
                  <button
                    onClick={() => handleResetPortalCredentials(customer)}
                    title="Reset portal credentials"
                    className="p-2 text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/30 rounded-lg transition-colors"
                  >
                    <RefreshCw className="w-5 h-5" />
                  </button>
                )}
                <button
                  onClick={() => handleEdit(customer)}
                  title="Edit customer"
                  className="p-2 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                >
                  <Edit2 className="w-5 h-5" />
                </button>
                <button
                  onClick={() => handleDelete(customer)}
                  title="Delete customer"
                  className="p-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        ))}

        {filteredCustomers.length === 0 && (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            {searchQuery ? "No customers found matching your search." : "No customers yet. Create one from the Customers page."}
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && editingCustomer && (
        <EditCustomerModal
          customer={editingCustomer}
          formData={formData}
          setFormData={setFormData}
          onSave={handleSaveEdit}
          onCancel={() => {
            setIsEditModalOpen(false);
            setEditingCustomer(null);
          }}
          isSaving={isSaving}
          showPassword={showPassword}
          setShowPassword={setShowPassword}
          copyPassword={copyPassword}
          copiedPassword={copiedPassword}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmCustomer && (
        <DeleteConfirmModal
          customer={deleteConfirmCustomer}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteConfirmCustomer(null)}
        />
      )}
    </div>
  );
}

// Edit Modal Component
function EditCustomerModal({ customer, formData, setFormData, onSave, onCancel, isSaving, showPassword, setShowPassword, copyPassword, copiedPassword }: any) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white">Edit Customer</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Update customer information and portal settings
              </p>
            </div>
            <button
              onClick={onCancel}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-6 h-6 text-gray-500" />
            </button>
          </div>

          {/* Form */}
          <div className="space-y-5">
            {/* Company Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Company Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="Acme Corporation"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="contact@acme.com"
                />
              </div>

              {/* Website */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Website
                </label>
                <input
                  type="url"
                  value={formData.website}
                  onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="https://acme.com"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Contact Person */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Contact Person
                </label>
                <input
                  type="text"
                  value={formData.contact_person}
                  onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="John Smith"
                />
              </div>

              {/* Phone */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Phone
                </label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  placeholder="+1-555-0123"
                />
              </div>
            </div>

            {/* Portal Access Section */}
            {formData.portal_enabled && (
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
                <div className="flex items-center space-x-2 mb-3">
                  <Key className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <h4 className="font-semibold text-gray-900 dark:text-white">Portal Credentials</h4>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Username
                    </label>
                    <input
                      type="text"
                      value={formData.portal_username}
                      onChange={(e) => setFormData({ ...formData, portal_username: e.target.value })}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Password
                    </label>
                    <div className="flex space-x-2">
                      <div className="flex-1 relative">
                        <input
                          type={showPassword ? "text" : "password"}
                          value={formData.portal_password}
                          onChange={(e) => setFormData({ ...formData, portal_password: e.target.value })}
                          className="w-full px-3 py-2 pr-10 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg font-mono text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                        >
                          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyPassword(formData.portal_password)}
                        className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                      >
                        {copiedPassword ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={onCancel}
              disabled={isSaving}
              className="px-6 py-2.5 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onSave}
              disabled={isSaving || !formData.name || !formData.email}
              className="flex items-center space-x-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Save Changes</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Delete Confirm Modal
function DeleteConfirmModal({ customer, onConfirm, onCancel }: any) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full">
        <div className="p-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white">
              Delete Customer?
            </h3>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            Are you sure you want to delete <strong>{customer.name}</strong>?
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            This will delete all associated:
          </p>
          <ul className="text-sm text-gray-600 dark:text-gray-400 list-disc list-inside mb-4 space-y-1">
            <li>{customer.iso_plans_count} ISO Plan(s)</li>
            <li>{customer.documents_count} Document(s)</li>
            <li>All tasks and evidence</li>
          </ul>

          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-4">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              <strong>Note:</strong> Archive functionality coming soon. Currently performs hard delete.
            </p>
          </div>

          <div className="flex justify-end space-x-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onConfirm(false)}
              className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Delete Permanently</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
