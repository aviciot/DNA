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
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Sparkles,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

interface Customer {
  id: number;
  name: string;
  email: string;
}

export default function CustomerDashboardSimple() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadCustomers();
  }, []);

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Customer Progress Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Track ISO certification progress and task completion
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
        <label className="block text-sm font-medium mb-2">Select Customer</label>
        <select
          value={selectedCustomerId || ""}
          onChange={(e) => setSelectedCustomerId(e.target.value ? parseInt(e.target.value) : null)}
          className="w-full md:w-64 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700"
        >
          <option value="">Choose a customer...</option>
          {customers.map((customer) => (
            <option key={customer.id} value={customer.id}>
              {customer.name}
            </option>
          ))}
        </select>
      </div>

      {!selectedCustomerId && (
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

      {selectedCustomerId && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <p className="text-gray-600 dark:text-gray-400">
            Progress dashboard for customer {selectedCustomerId} will be displayed here.
          </p>
          <p className="text-sm text-gray-500 mt-2">
            (Full progress view coming soon - customer selection is working!)
          </p>
        </div>
      )}
    </div>
  );
}
