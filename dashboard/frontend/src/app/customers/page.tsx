"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import axios from "axios";
import {
  Users, Clock, CheckCircle2, AlertCircle, ArrowRight, Search, Filter, Sparkles,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
  email: string;
  phone?: string;
  created_at: string;
  active_tasks?: number;
  completed_tasks?: number;
  overdue_tasks?: number;
  progress?: number;
}

export default function CustomersPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "attention">("all");

  useEffect(() => { loadCustomers(); }, []);

  const loadCustomers = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const response = await axios.get(`${API_BASE}/api/v1/customers`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const customersData = Array.isArray(response.data) ? response.data : response.data?.customers || [];

      const withStats = await Promise.all(
        customersData.map(async (c: Customer) => {
          try {
            const r = await axios.get(`${API_BASE}/api/v1/customers/${c.id}/tasks`, {
              headers: { Authorization: `Bearer ${token}` },
              params: { include_ignored: false },
            });
            const tasks = r.data || [];
            const completed = tasks.filter((t: any) => t.status === "completed").length;
            return {
              ...c,
              active_tasks: tasks.filter((t: any) => t.status !== "completed" && t.status !== "cancelled").length,
              completed_tasks: completed,
              overdue_tasks: tasks.filter((t: any) => t.due_date && new Date(t.due_date) < new Date() && t.status !== "completed").length,
              progress: tasks.length > 0 ? Math.round((completed / tasks.length) * 100) : 0,
            };
          } catch { return c; }
        })
      );
      setCustomers(withStats);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const filtered = customers.filter((c) => {
    const matchSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchStatus = statusFilter === "all" || (statusFilter === "active" && (c.active_tasks || 0) > 0) || (statusFilter === "attention" && (c.overdue_tasks || 0) > 0);
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Customers</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Manage ISO certification for your customers</p>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 mb-6 flex flex-col md:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search customers..." className="w-full pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm" />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm">
              <option value="all">All</option>
              <option value="active">Active Tasks</option>
              <option value="attention">Needs Attention</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-gray-500">Loading customers...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
            <Sparkles className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No customers found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((customer) => (
              <div key={customer.id} onClick={() => router.push(`/customers/${customer.id}`)}
                className="bg-white dark:bg-gray-800 rounded-xl border-2 border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-lg transition-all cursor-pointer">
                <div className="p-5 border-b border-gray-100 dark:border-gray-700">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-bold text-gray-900 dark:text-white">{customer.name}</h3>
                      <p className="text-xs text-gray-500 mt-0.5">{customer.email}</p>
                    </div>
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                      <Users className="w-5 h-5 text-white" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>Progress</span>
                    <span className="font-bold text-gray-900 dark:text-white">{customer.progress || 0}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all"
                      style={{ width: `${customer.progress || 0}%` }} />
                  </div>
                </div>
                <div className="p-4">
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    <div className="text-center p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <Clock className="w-3.5 h-3.5 text-blue-500 mx-auto mb-0.5" />
                      <p className="text-lg font-bold text-blue-600">{customer.active_tasks || 0}</p>
                      <p className="text-xs text-gray-500">Active</p>
                    </div>
                    <div className="text-center p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-500 mx-auto mb-0.5" />
                      <p className="text-lg font-bold text-green-600">{customer.completed_tasks || 0}</p>
                      <p className="text-xs text-gray-500">Done</p>
                    </div>
                    <div className="text-center p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                      <AlertCircle className="w-3.5 h-3.5 text-red-500 mx-auto mb-0.5" />
                      <p className="text-lg font-bold text-red-600">{customer.overdue_tasks || 0}</p>
                      <p className="text-xs text-gray-500">Overdue</p>
                    </div>
                  </div>
                  <button className="w-full flex items-center justify-center gap-2 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-sm rounded-lg hover:opacity-90 transition-opacity">
                    Open Workspace <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
