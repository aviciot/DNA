"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import axios from "axios";
import {
  Users,
  ClipboardList,
  FileText,
  TrendingUp,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  Search,
  Filter,
  Sparkles,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
  email: string;
  phone?: string;
  created_at: string;
  active_plans?: number;
  active_tasks?: number;
  completed_tasks?: number;
  overdue_tasks?: number;
  progress?: number;
}

export default function CustomersPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, fetchUser } = useAuthStore();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "attention">("all");

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    } else if (!isLoading && isAuthenticated) {
      loadCustomers();
    }
  }, [isLoading, isAuthenticated, router]);

  const loadCustomers = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/customers`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      const customersData = Array.isArray(response.data)
        ? response.data
        : response.data?.customers || [];

      // Load task stats for each customer
      const customersWithStats = await Promise.all(
        customersData.map(async (customer: Customer) => {
          try {
            const tasksRes = await axios.get(
              `${API_BASE}/api/v1/customers/${customer.id}/tasks`,
              {
                headers: { Authorization: `Bearer ${token}` },
                params: { include_ignored: false },
              }
            );

            const tasks = tasksRes.data || [];
            const activeTasks = tasks.filter(
              (t: any) => t.status !== "completed" && t.status !== "cancelled"
            ).length;
            const completedTasks = tasks.filter((t: any) => t.status === "completed").length;
            const overdueTasks = tasks.filter(
              (t: any) =>
                t.due_date &&
                new Date(t.due_date) < new Date() &&
                t.status !== "completed"
            ).length;

            const progress = tasks.length > 0 ? Math.round((completedTasks / tasks.length) * 100) : 0;

            return {
              ...customer,
              active_tasks: activeTasks,
              completed_tasks: completedTasks,
              overdue_tasks: overdueTasks,
              progress,
            };
          } catch {
            return customer;
          }
        })
      );

      setCustomers(customersWithStats);
    } catch (error) {
      console.error("Failed to load customers:", error);
    } finally {
      setLoading(false);
    }
  };

  const filteredCustomers = customers.filter((customer) => {
    // Search filter
    const matchesSearch =
      customer.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      customer.email.toLowerCase().includes(searchQuery.toLowerCase());

    // Status filter
    let matchesStatus = true;
    if (statusFilter === "active") {
      matchesStatus = (customer.active_tasks || 0) > 0;
    } else if (statusFilter === "attention") {
      matchesStatus = (customer.overdue_tasks || 0) > 0;
    }

    return matchesSearch && matchesStatus;
  });

  const handleCustomerClick = (customerId: number) => {
    router.push(`/customers/${customerId}`);
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-900 dark:to-gray-800">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-900 dark:to-gray-800">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                My Customers
              </h1>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Manage ISO certification for your customers
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm text-gray-500 dark:text-gray-400">Welcome back,</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {user?.full_name || user?.email}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search customers by name or email..."
                  className="w-full pl-10 pr-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-500" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
                className="px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              >
                <option value="all">All Customers</option>
                <option value="active">Active Tasks</option>
                <option value="attention">Needs Attention</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Customers Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        {loading ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading customers...</p>
          </div>
        ) : filteredCustomers.length === 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
            <Sparkles className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <p className="text-xl text-gray-600 dark:text-gray-400">No customers found</p>
            <p className="text-gray-500 dark:text-gray-500 mt-2">
              {searchQuery || statusFilter !== "all"
                ? "Try adjusting your filters"
                : "No customers assigned to you yet"}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCustomers.map((customer, index) => (
              <div
                key={customer.id}
                onClick={() => handleCustomerClick(customer.id)}
                className="group bg-white dark:bg-gray-800 rounded-xl shadow-lg border-2 border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-2xl transition-all duration-300 cursor-pointer transform hover:-translate-y-1"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Card Header */}
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                        {customer.name}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {customer.email}
                      </p>
                    </div>
                    <div className="flex-shrink-0">
                      <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                        <Users className="w-6 h-6 text-white" />
                      </div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                        Overall Progress
                      </span>
                      <span className="text-sm font-bold text-gray-900 dark:text-white">
                        {customer.progress || 0}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          (customer.progress || 0) >= 75
                            ? "bg-gradient-to-r from-green-500 to-emerald-600"
                            : (customer.progress || 0) >= 50
                            ? "bg-gradient-to-r from-blue-500 to-cyan-600"
                            : (customer.progress || 0) >= 25
                            ? "bg-gradient-to-r from-yellow-500 to-orange-600"
                            : "bg-gradient-to-r from-red-500 to-rose-600"
                        }`}
                        style={{ width: `${customer.progress || 0}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {/* Task Stats */}
                <div className="p-6">
                  <div className="grid grid-cols-3 gap-3">
                    {/* Active Tasks */}
                    <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <div className="flex items-center justify-center mb-1">
                        <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                        {customer.active_tasks || 0}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Active</p>
                    </div>

                    {/* Completed Tasks */}
                    <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <div className="flex items-center justify-center mb-1">
                        <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                      </div>
                      <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                        {customer.completed_tasks || 0}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Done</p>
                    </div>

                    {/* Overdue Tasks */}
                    <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                      <div className="flex items-center justify-center mb-1">
                        <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                      </div>
                      <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                        {customer.overdue_tasks || 0}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Overdue</p>
                    </div>
                  </div>

                  {/* Action Button */}
                  <button className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 transition-all group-hover:shadow-lg">
                    <span className="font-medium">Open Workspace</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </button>
                </div>

                {/* Attention Badge */}
                {(customer.overdue_tasks || 0) > 0 && (
                  <div className="absolute top-3 right-3">
                    <span className="px-3 py-1 bg-red-500 text-white text-xs font-bold rounded-full shadow-lg animate-pulse">
                      Needs Attention
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
