"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  Users,
  Search,
  Plus,
  Building2,
  Mail,
  Phone,
  MapPin,
  TrendingUp,
  CheckCircle,
  Clock,
  Target,
  Sparkles,
  Edit2,
  Trash2,
  X,
  Loader2,
  ChevronRight,
  Filter,
  BarChart3,
  Calendar,
  Send,
  Settings,
  Eye,
  RefreshCw,
  UserPlus,
  Zap,
  Shield,
  FileText,
  Activity,
  Globe,
  Inbox,
  Briefcase,
  AlignLeft,
  ListChecks,
} from "lucide-react";
import ManagePlanModal from "./ManagePlanModal";
import CustomerTasks from "./CustomerTasks";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
  email: string;
  website: string | null;
  compliance_email: string | null;
  contract_email: string | null;
  contact_person: string | null;
  phone: string | null;
  address: string | null;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  total_plans: number;
  active_tasks: number;
  completed_tasks: number;
  overall_progress: number;
}

interface DashboardStats {
  total_customers: number;
  active_customers: number;
  total_iso_plans: number;
  total_templates_assigned: number;
  total_tasks: number;
  completed_tasks: number;
  pending_tasks: number;
  overdue_tasks: number;
}

export default function CustomerManagementV3() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [filteredCustomers, setFilteredCustomers] = useState<Customer[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);
  const [isTasksModalOpen, setIsTasksModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [customerToEdit, setCustomerToEdit] = useState<Customer | null>(null);
  const [customerForPlan, setCustomerForPlan] = useState<Customer | null>(null);
  const [customerForTasks, setCustomerForTasks] = useState<Customer | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    website: "",
    compliance_email: "",
    contract_email: "",
    contact_person: "",
    phone: "",
    address: "",
    description: "",
    status: "active",
    send_welcome_email: false,
    welcome_email_schedule: "immediate",
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    filterCustomers();
  }, [searchQuery, statusFilter, customers]);

  const loadData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const headers = { Authorization: `Bearer ${token}` };

      // Load customers and stats in parallel
      const [customersRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/v1/customers?page=1&page_size=100`, { headers }),
        axios.get(`${API_BASE}/api/v1/dashboard/stats`, { headers }),
      ]);

      console.log("✅ Customers loaded:", customersRes.data);
      console.log("✅ Dashboard stats:", statsRes.data);

      setCustomers(customersRes.data.customers || []);
      setDashboardStats(statsRes.data);
    } catch (error: any) {
      console.error("Error loading data:", error);
    } finally {
      setLoading(false);
    }
  };

  const filterCustomers = () => {
    let filtered = customers;

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.name.toLowerCase().includes(query) ||
          c.email.toLowerCase().includes(query) ||
          c.contact_person?.toLowerCase().includes(query)
      );
    }

    // Status filter
    if (statusFilter !== "all") {
      filtered = filtered.filter((c) => c.status === statusFilter);
    }

    setFilteredCustomers(filtered);
  };

  const handleCreateCustomer = async () => {
    if (!formData.name || !formData.email || !formData.contact_person || !formData.phone) {
      alert("Please fill in all required fields: Company Name, Email, Contact Person, and Phone");
      return;
    }

    try {
      setIsSaving(true);
      const token = localStorage.getItem("access_token");

      // Clean formData - remove empty strings for optional fields
      const cleanedData = {
        name: formData.name,
        email: formData.email,
        contact_person: formData.contact_person,
        phone: formData.phone,
        status: formData.status,
        send_welcome_email: formData.send_welcome_email,
        welcome_email_schedule: formData.welcome_email_schedule,
        ...(formData.website && { website: formData.website }),
        ...(formData.compliance_email && { compliance_email: formData.compliance_email }),
        ...(formData.contract_email && { contract_email: formData.contract_email }),
        ...(formData.address && { address: formData.address }),
        ...(formData.description && { description: formData.description }),
      };

      const response = await axios.post(`${API_BASE}/api/v1/customers`, cleanedData, {
        headers: { Authorization: `Bearer ${token}` },
      });

      console.log("✅ Customer created successfully:", response.data);

      // Show success message
      alert(`✅ Customer "${response.data.name}" created successfully!`);

      setIsCreateModalOpen(false);
      resetForm();
      await loadData();
    } catch (error: any) {
      console.error("Error creating customer:", error);
      const errorMsg = error.response?.data?.detail || error.message || "Failed to create customer";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setIsSaving(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      email: "",
      website: "",
      compliance_email: "",
      contract_email: "",
      contact_person: "",
      phone: "",
      address: "",
      description: "",
      status: "active",
      send_welcome_email: false,
      welcome_email_schedule: "immediate",
    });
    setCustomerToEdit(null);
  };

  const handleEditCustomer = (customer: Customer) => {
    setCustomerToEdit(customer);
    setFormData({
      name: customer.name,
      email: customer.email,
      website: customer.website || "",
      compliance_email: customer.compliance_email || customer.email,
      contract_email: customer.contract_email || "",
      contact_person: customer.contact_person || "",
      phone: customer.phone || "",
      address: customer.address || "",
      description: customer.description || "",
      status: customer.status,
      send_welcome_email: false,
      welcome_email_schedule: "immediate",
    });
    setIsEditModalOpen(true);
  };

  const handleUpdateCustomer = async () => {
    if (!customerToEdit) return;
    if (!formData.name || !formData.email || !formData.contact_person || !formData.phone) {
      alert("Please fill in all required fields: Company Name, Email, Contact Person, and Phone");
      return;
    }

    try {
      setIsSaving(true);
      const token = localStorage.getItem("access_token");

      const cleanedData = {
        name: formData.name,
        email: formData.email,
        contact_person: formData.contact_person,
        phone: formData.phone,
        status: formData.status,
        ...(formData.website && { website: formData.website }),
        ...(formData.compliance_email && { compliance_email: formData.compliance_email }),
        ...(formData.contract_email && { contract_email: formData.contract_email }),
        ...(formData.address && { address: formData.address }),
        ...(formData.description && { description: formData.description }),
      };

      await axios.patch(`${API_BASE}/api/v1/customers/${customerToEdit.id}`, cleanedData, {
        headers: { Authorization: `Bearer ${token}` },
      });

      alert(`✅ Customer "${formData.name}" updated successfully!`);

      setIsEditModalOpen(false);
      resetForm();
      await loadData();
    } catch (error: any) {
      console.error("Error updating customer:", error);
      const errorMsg = error.response?.data?.detail || error.message || "Failed to update customer";
      alert(`❌ Error: ${errorMsg}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeactivateCustomer = async (customer: Customer) => {
    if (!confirm(`Are you sure you want to deactivate "${customer.name}"?\n\nThis will hide the customer but keep all data.`)) {
      return;
    }

    try {
      const token = localStorage.getItem("access_token");
      await axios.patch(
        `${API_BASE}/api/v1/customers/${customer.id}`,
        { status: "inactive" },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert(`✅ Customer "${customer.name}" deactivated successfully!`);
      await loadData();
    } catch (error: any) {
      console.error("Error deactivating customer:", error);
      const errorMsg = error.response?.data?.detail || error.message || "Failed to deactivate customer";
      alert(`❌ Error: ${errorMsg}`);
    }
  };

  const getProgressColor = (progress: number) => {
    if (progress >= 80) return "from-green-500 to-emerald-500";
    if (progress >= 50) return "from-blue-500 to-cyan-500";
    if (progress >= 25) return "from-yellow-500 to-orange-500";
    return "from-red-500 to-pink-500";
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      active: "bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-400",
      inactive: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
      pending: "bg-yellow-100 text-yellow-700 dark:bg-yellow-800 dark:text-yellow-400",
    };
    return badges[status as keyof typeof badges] || badges.active;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="ml-3 text-gray-600 dark:text-gray-400">Loading customers...</span>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl shadow-lg">
            <Users className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Customer Management
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Manage customers, plans, and track progress
            </p>
          </div>
        </div>

        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200"
        >
          <UserPlus className="w-5 h-5" />
          <span>Create Customer</span>
          <Sparkles className="w-4 h-4" />
        </button>
      </div>

      {/* Dashboard Stats */}
      {dashboardStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900 dark:to-blue-800 rounded-xl p-6 border border-blue-200 dark:border-blue-800 transform hover:scale-105 transition-all duration-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-blue-600 dark:text-blue-400 font-medium">Total Customers</p>
                <p className="text-3xl font-bold text-blue-900 dark:text-blue-100 mt-2">
                  {dashboardStats.active_customers}
                </p>
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                  {dashboardStats.total_customers} total
                </p>
              </div>
              <div className="p-4 bg-blue-100 rounded-xl">
                <Users className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900 dark:to-purple-800 rounded-xl p-6 border border-purple-200 dark:border-purple-800 transform hover:scale-105 transition-all duration-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-purple-600 dark:text-purple-400 font-medium">ISO Plans</p>
                <p className="text-3xl font-bold text-purple-900 dark:text-purple-100 mt-2">
                  {dashboardStats.total_iso_plans}
                </p>
                <p className="text-xs text-purple-600 dark:text-purple-400 mt-1">
                  Active compliance plans
                </p>
              </div>
              <div className="p-4 bg-purple-100 rounded-xl">
                <Shield className="w-8 h-8 text-purple-600 dark:text-purple-400" />
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900 dark:to-green-800 rounded-xl p-6 border border-green-200 dark:border-green-800 transform hover:scale-105 transition-all duration-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-green-600 dark:text-green-400 font-medium">Completed Tasks</p>
                <p className="text-3xl font-bold text-green-900 dark:text-green-100 mt-2">
                  {dashboardStats.completed_tasks}
                </p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                  {dashboardStats.pending_tasks} pending
                </p>
              </div>
              <div className="p-4 bg-green-100 rounded-xl">
                <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900 dark:to-orange-800 rounded-xl p-6 border border-orange-200 dark:border-orange-800 transform hover:scale-105 transition-all duration-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-orange-600 dark:text-orange-400 font-medium">Overdue Tasks</p>
                <p className="text-3xl font-bold text-orange-900 dark:text-orange-100 mt-2">
                  {dashboardStats.overdue_tasks}
                </p>
                <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">
                  Needs attention
                </p>
              </div>
              <div className="p-4 bg-orange-100 rounded-xl">
                <Clock className="w-8 h-8 text-orange-600 dark:text-orange-400" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search customers by name, email, or contact..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-5 h-5 text-gray-500" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-3 border-2 border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="pending">Pending</option>
          </select>

          <button
            onClick={loadData}
            className="p-3 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800 transition-all"
          >
            <RefreshCw className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
        </div>
      </div>

      {/* Customer List */}
      <div className="space-y-4">
        {filteredCustomers.length === 0 ? (
          <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700">
            <Users className="w-16 h-16 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              No customers found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {searchQuery || statusFilter !== "all"
                ? "Try adjusting your filters"
                : "Get started by creating your first customer"}
            </p>
            {!searchQuery && statusFilter === "all" && (
              <button
                onClick={() => setIsCreateModalOpen(true)}
                className="inline-flex items-center space-x-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-all"
              >
                <Plus className="w-5 h-5" />
                <span>Create First Customer</span>
              </button>
            )}
          </div>
        ) : (
          filteredCustomers.map((customer, index) => (
            <div
              key={customer.id}
              className="bg-white dark:bg-gray-800 rounded-xl border-2 border-gray-200 dark:border-gray-700 p-6 hover:border-blue-500 hover:shadow-lg transition-all duration-300 transform hover:-translate-y-1"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg">
                      <Building2 className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                        {customer.name}
                      </h3>
                      <div className="flex items-center space-x-4 mt-1">
                        <span className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                          <Mail className="w-4 h-4 mr-1" />
                          {customer.email}
                        </span>
                        {customer.contact_person && (
                          <span className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                            <Users className="w-4 h-4 mr-1" />
                            {customer.contact_person}
                          </span>
                        )}
                      </div>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusBadge(
                        customer.status
                      )}`}
                    >
                      {customer.status.charAt(0).toUpperCase() + customer.status.slice(1)}
                    </span>
                  </div>

                  {/* Progress Section */}
                  <div className="grid grid-cols-4 gap-4 mt-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                        {customer.total_plans}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">ISO Plans</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                        {customer.active_tasks}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Active Tasks</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                        {customer.completed_tasks}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Completed</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                        {customer.overall_progress}%
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Progress</p>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Overall Progress
                      </span>
                      <span className="text-sm font-bold text-gray-900 dark:text-white">
                        {customer.overall_progress}%
                      </span>
                    </div>
                    <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full bg-gradient-to-r ${getProgressColor(
                          customer.overall_progress
                        )} rounded-full transition-all duration-1000 ease-out`}
                        style={{
                          width: `${customer.overall_progress}%`,
                          animation: `slideIn 1s ease-out ${index * 100}ms`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                <div className="flex flex-col space-y-2 ml-4">
                  <button
                    onClick={() => setSelectedCustomer(customer)}
                    className="p-2 bg-blue-100 text-blue-600 dark:bg-blue-800 dark:text-blue-400 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900 transition-all"
                    title="View Details"
                  >
                    <Eye className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => {
                      setCustomerForPlan(customer);
                      setIsPlanModalOpen(true);
                    }}
                    className="p-2 bg-purple-100 text-purple-600 dark:bg-purple-800 dark:text-purple-400 rounded-lg hover:bg-purple-200 dark:hover:bg-purple-900 transition-all"
                    title="Manage ISO Plans"
                  >
                    <Settings className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => {
                      setCustomerForTasks(customer);
                      setIsTasksModalOpen(true);
                    }}
                    className="relative p-2 bg-green-100 text-green-600 dark:bg-green-800 dark:text-green-400 rounded-lg hover:bg-green-200 dark:hover:bg-green-900 transition-all"
                    title="View Tasks"
                  >
                    <ListChecks className="w-5 h-5" />
                    {customer.active_tasks > 0 && (
                      <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                        {customer.active_tasks}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => handleEditCustomer(customer)}
                    className="p-2 bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-all"
                    title="Edit Customer"
                  >
                    <Edit2 className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => handleDeactivateCustomer(customer)}
                    className="p-2 bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-400 rounded-lg hover:bg-red-200 dark:hover:bg-red-800 transition-all"
                    title="Deactivate Customer"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create Customer Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 flex items-center justify-between rounded-t-2xl">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-white/20 rounded-lg">
                  <UserPlus className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Create New Customer</h2>
                  <p className="text-sm text-white/80">Add a new customer to the system</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setIsCreateModalOpen(false);
                  resetForm();
                }}
                className="p-2 hover:bg-white/20 rounded-lg transition-all"
              >
                <X className="w-6 h-6 text-white" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Basic Information */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
                  <Building2 className="w-5 h-5 mr-2 text-blue-600" />
                  Basic Information
                </h3>

                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Company Name *
                    </label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="Enter company name"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Email Address *
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => {
                        setFormData({ ...formData, email: e.target.value });
                        // Auto-populate compliance email if empty
                        if (!formData.compliance_email) {
                          setFormData(prev => ({ ...prev, email: e.target.value, compliance_email: e.target.value }));
                        }
                      }}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="company@example.com"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Website
                    </label>
                    <input
                      type="url"
                      value={formData.website}
                      onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="https://example.com"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Contact Person *
                    </label>
                    <input
                      type="text"
                      value={formData.contact_person}
                      onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="John Doe"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Phone Number *
                    </label>
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="+1 (555) 000-0000"
                      required
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Address
                    </label>
                    <textarea
                      value={formData.address}
                      onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                      rows={2}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="Enter company address"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Description
                    </label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      rows={3}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="Optional notes about the customer..."
                    />
                  </div>

                  <div>
                    <label className="flex items-center text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Compliance Email
                      <span className="ml-2 px-2 py-0.5 text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full">
                        AI
                      </span>
                    </label>
                    <input
                      type="email"
                      value={formData.compliance_email}
                      onChange={(e) => setFormData({ ...formData, compliance_email: e.target.value })}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="compliance@example.com"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      For receiving evidence and documents
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Contract Email
                    </label>
                    <input
                      type="email"
                      value={formData.contract_email}
                      onChange={(e) => setFormData({ ...formData, contract_email: e.target.value })}
                      className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      placeholder="legal@example.com"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      For CISO/Legal communications
                    </p>
                  </div>
                </div>
              </div>

              {/* Welcome Email */}
              <div className="space-y-4 p-4 bg-blue-50 dark:bg-blue-900 rounded-xl border-2 border-blue-200 dark:border-blue-800">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Send className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Welcome Email
                    </h3>
                  </div>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.send_welcome_email}
                      onChange={(e) =>
                        setFormData({ ...formData, send_welcome_email: e.target.checked })
                      }
                      className="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <span className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                      Send welcome email
                    </span>
                  </label>
                </div>

                {formData.send_welcome_email && (
                  <div className="space-y-3 animate-slide-down">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      When to send
                    </label>
                    <div className="flex space-x-4">
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="radio"
                          name="email_schedule"
                          value="immediate"
                          checked={formData.welcome_email_schedule === "immediate"}
                          onChange={(e) =>
                            setFormData({ ...formData, welcome_email_schedule: e.target.value })
                          }
                          className="w-4 h-4 text-blue-600"
                        />
                        <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                          Immediately
                        </span>
                      </label>
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="radio"
                          name="email_schedule"
                          value="after_plan_setup"
                          checked={formData.welcome_email_schedule === "after_plan_setup"}
                          onChange={(e) =>
                            setFormData({ ...formData, welcome_email_schedule: e.target.value })
                          }
                          className="w-4 h-4 text-blue-600"
                        />
                        <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                          After plan setup
                        </span>
                      </label>
                    </div>
                    <p className="text-xs text-blue-600 dark:text-blue-400 flex items-center">
                      <Sparkles className="w-3 h-3 mr-1" />
                      Customer will receive login credentials and next steps
                    </p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    resetForm();
                  }}
                  className="px-6 py-3 border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateCustomer}
                  disabled={isSaving}
                  className="flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-5 h-5" />
                      <span>Create Customer</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Customer Modal */}
      {isEditModalOpen && customerToEdit && (
        <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 px-8 py-6 flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white">Edit Customer</h2>
              <button onClick={() => { setIsEditModalOpen(false); resetForm(); }} className="text-white hover:bg-white hover:bg-opacity-20 p-2 rounded-lg transition-all">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-8 space-y-6">
              <div className="space-y-4">
                <h3 className="text-lg font-semibold flex items-center">
                  <Building2 className="w-5 h-5 mr-2 text-blue-600" />
                  Customer Information
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Company Name *</label>
                    <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Email *</label>
                    <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Website</label>
                    <input type="url" value={formData.website} onChange={(e) => setFormData({ ...formData, website: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="https://example.com" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Contact Person *</label>
                    <input type="text" value={formData.contact_person} onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="John Doe" required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Phone *</label>
                    <input type="tel" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="+1 (555) 000-0000" required />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Address</label>
                    <textarea value={formData.address} onChange={(e) => setFormData({ ...formData, address: e.target.value })} rows={2} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="Company address" />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Description</label>
                    <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} rows={3} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="Optional notes..." />
                  </div>
                  <div>
                    <label className="flex items-center text-sm font-medium mb-2">
                      Compliance Email
                      <span className="ml-2 px-2 py-0.5 text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full">
                        AI
                      </span>
                    </label>
                    <input type="email" value={formData.compliance_email} onChange={(e) => setFormData({ ...formData, compliance_email: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="compliance@example.com" />
                    <p className="text-xs text-gray-500 mt-1">For evidence/documents</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Contract Email</label>
                    <input type="email" value={formData.contract_email} onChange={(e) => setFormData({ ...formData, contract_email: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700" placeholder="legal@example.com" />
                    <p className="text-xs text-gray-500 mt-1">For CISO/Legal</p>
                  </div>
                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Status</label>
                    <select value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-700">
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4 border-t">
                <button onClick={() => { setIsEditModalOpen(false); resetForm(); }} className="px-6 py-3 border-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700">Cancel</button>
                <button onClick={handleUpdateCustomer} disabled={isSaving} className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl disabled:opacity-50">
                  {isSaving ? "Updating..." : "Update Customer"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Manage Plan Modal */}
      {isPlanModalOpen && customerForPlan && (
        <ManagePlanModal
          customer={{
            id: customerForPlan.id,
            name: customerForPlan.name,
            email: customerForPlan.email,
          }}
          onClose={() => {
            setIsPlanModalOpen(false);
            setCustomerForPlan(null);
          }}
          onSuccess={() => {
            loadData(); // Refresh customer list to show updated stats
          }}
        />
      )}

      {/* Customer Tasks Modal */}
      {isTasksModalOpen && customerForTasks && (
        <CustomerTasks
          customer={{
            id: customerForTasks.id,
            name: customerForTasks.name,
          }}
          onClose={() => {
            setIsTasksModalOpen(false);
            setCustomerForTasks(null);
          }}
          onTaskUpdate={() => {
            loadData(); // Refresh customer list to show updated stats
          }}
        />
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

        @keyframes slideIn {
          from {
            width: 0;
          }
        }

        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }

        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }

        .animate-slide-down {
          animation: slide-down 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
