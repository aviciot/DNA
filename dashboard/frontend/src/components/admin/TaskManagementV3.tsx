/**
 * TaskManagementV3.tsx
 *
 * Impressive Task Management Interface
 * - Beautiful task cards with animated priorities
 * - Filter and sort options with smooth transitions
 * - Task creation from templates or manual
 * - Task resolution workflow
 * - Real-time status updates
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Plus, Filter, Search, Calendar, User, CheckCircle2, Clock,
  AlertCircle, FileText, Upload, MessageSquare, X,
  Sparkles, Target, Flag
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8400';

interface Task {
  id: string;
  customer_id: number;
  customer_name?: string;
  plan_id?: string;
  iso_name?: string;
  task_type: 'question' | 'evidence_request' | 'follow_up' | 'manual';
  task_scope: 'customer' | 'plan' | 'template' | 'manual';
  title: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'on_hold' | 'completed' | 'cancelled';
  priority: 'urgent' | 'high' | 'medium' | 'low';
  due_date?: string;
  is_overdue?: boolean;
  assigned_to?: number;
  assigned_to_name?: string;
  auto_generated: boolean;
  created_at: string;
  updated_at: string;
}

interface TaskTemplate {
  id: string;
  name: string;
  description: string;
  task_type: string;
  default_priority: string;
  estimated_duration_days?: number;
  required_variables?: string[];
}

interface Customer {
  id: number;
  name: string;
  email: string;
}

interface ISOPlan {
  id: string;
  iso_standard_name: string;
  customer_id: number;
}

interface TaskFilters {
  customer_id?: number;
  plan_id?: string;
  status?: string;
  priority?: string;
  assigned_to?: number;
  search?: string;
}

const TaskManagementV3: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [plans, setPlans] = useState<ISOPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // Filters
  const [filters, setFilters] = useState<TaskFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  // Create task form
  const [createMode, setCreateMode] = useState<'manual' | 'template'>('manual');
  const [formData, setFormData] = useState({
    customer_id: 0,
    task_type: 'manual',
    task_scope: 'customer',
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    template_id: '',
    variables: {} as Record<string, string>,
  });

  // Resolution form
  const [resolutionData, setResolutionData] = useState({
    resolution_type: 'answer_provided',
    resolution_data: {} as Record<string, any>,
    comments: '',
    requires_approval: false,
  });

  useEffect(() => {
    loadData();
  }, [filters]);

  const loadData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };

      console.log('🔵 TaskManagementV3: Starting to load data...');
      console.log('🔵 API_BASE:', API_BASE);

      // Load customers first
      const customersRes = await axios.get(`${API_BASE}/api/v1/customers`, { headers });
      console.log('🔵 Customers response type:', typeof customersRes.data);
      console.log('🔵 Customers response:', JSON.stringify(customersRes.data, null, 2));
      console.log('🔵 Is array?', Array.isArray(customersRes.data));

      let allCustomers = [];
      if (Array.isArray(customersRes.data)) {
        allCustomers = customersRes.data;
      } else if (customersRes.data && customersRes.data.customers) {
        allCustomers = customersRes.data.customers;
      } else if (customersRes.data && typeof customersRes.data === 'object') {
        // Maybe it's wrapped differently
        console.log('🔵 Keys in response:', Object.keys(customersRes.data));
        allCustomers = [];
      }

      console.log('🔵 Loaded customers:', allCustomers.length, allCustomers);
      console.log('🔵 Is allCustomers an array?', Array.isArray(allCustomers));
      setCustomers(allCustomers);

      // Load tasks from ALL customers in parallel
      console.log('🔵 Loading tasks from all customers...');
      const taskPromises = allCustomers.map((customer: Customer) =>
        axios
          .get(`${API_BASE}/api/v1/customers/${customer.id}/tasks`, {
            headers,
            params: { include_ignored: true },
          })
          .then((res) => {
            console.log(`🔵 Customer ${customer.name} (${customer.id}): ${res.data?.length || 0} tasks`);
            return (res.data || []).map((task: any) => ({
              ...task,
              customer_name: customer.name,
              iso_name: task.plan_iso_name,
            }));
          })
          .catch((err) => {
            console.error(`🔴 Error loading tasks for customer ${customer.id}:`, err.response?.data || err.message);
            return [];
          })
      );

      const tasksArrays = await Promise.all(taskPromises);
      let allTasks = tasksArrays.flat();
      console.log('🔵 Total tasks loaded:', allTasks.length);
      console.log('🔵 Sample task:', allTasks[0]);

      // Apply filters
      if (filters.customer_id) {
        allTasks = allTasks.filter(t => t.customer_id === filters.customer_id);
        console.log('🔵 After customer filter:', allTasks.length);
      }
      if (filters.status) {
        allTasks = allTasks.filter(t => t.status === filters.status);
        console.log('🔵 After status filter:', allTasks.length);
      }
      if (filters.priority) {
        allTasks = allTasks.filter(t => t.priority === filters.priority);
        console.log('🔵 After priority filter:', allTasks.length);
      }

      console.log('🔵 Setting tasks:', allTasks.length);
      setTasks(allTasks);

      // Load templates (keep this for task creation)
      try {
        const templatesRes = await axios.get(`${API_BASE}/api/v1/task-templates`, { headers });
        setTemplates(templatesRes.data.templates || []);
      } catch {
        setTemplates([]);
      }
    } catch (error) {
      console.error('🔴 Failed to load data:', error);
      if (axios.isAxiosError(error)) {
        console.error('🔴 Response:', error.response?.data);
        console.error('🔴 Status:', error.response?.status);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadPlansForCustomer = async (customerId: number) => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API_BASE}/api/v1/customers/${customerId}/plans`, { headers });
      setPlans(response.data.plans || []);
    } catch (error) {
      console.error('Failed to load plans:', error);
    }
  };

  const handleCreateTask = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };

      if (createMode === 'template') {
        await axios.post(
          `${API_BASE}/api/v1/tasks/from-template`,
          {
            customer_id: formData.customer_id,
            template_id: formData.template_id,
            variables: formData.variables,
            due_date: formData.due_date || null,
          },
          { headers }
        );
      } else {
        await axios.post(
          `${API_BASE}/api/v1/tasks`,
          {
            customer_id: formData.customer_id,
            task_type: formData.task_type,
            task_scope: formData.task_scope,
            title: formData.title,
            description: formData.description,
            priority: formData.priority,
            due_date: formData.due_date || null,
          },
          { headers }
        );
      }

      setShowCreateModal(false);
      resetForm();
      loadData();
    } catch (error) {
      console.error('Failed to create task:', error);
      alert('Failed to create task');
    }
  };

  const handleResolveTask = async () => {
    if (!selectedTask) return;

    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };

      await axios.post(
        `${API_BASE}/api/v1/tasks/${selectedTask.id}/resolve`,
        {
          resolution_type: resolutionData.resolution_type,
          resolution_data: resolutionData.resolution_data,
          comments: resolutionData.comments,
          requires_approval: resolutionData.requires_approval,
          is_final: true,
        },
        { headers }
      );

      setShowResolveModal(false);
      setSelectedTask(null);
      resetResolutionForm();
      loadData();
    } catch (error) {
      console.error('Failed to resolve task:', error);
      alert('Failed to resolve task');
    }
  };

  const handleIgnoreTask = async (taskId: string) => {
    const reason = prompt('Reason for archiving this task?');
    if (reason === null) return;

    try {
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };

      // Archive the task using cancel endpoint
      await axios.post(
        `${API_BASE}/api/v1/tasks/${taskId}/cancel`,
        {},
        {
          headers,
          params: { reason: reason || 'Archived by admin' }
        }
      );

      loadData();
    } catch (error) {
      console.error('Failed to archive task:', error);
      alert('Failed to archive task');
    }
  };

  const resetForm = () => {
    setFormData({
      customer_id: 0,
      task_type: 'manual',
      task_scope: 'customer',
      title: '',
      description: '',
      priority: 'medium',
      due_date: '',
      template_id: '',
      variables: {},
    });
  };

  const resetResolutionForm = () => {
    setResolutionData({
      resolution_type: 'answer_provided',
      resolution_data: {},
      comments: '',
      requires_approval: false,
    });
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'from-red-500 to-rose-600';
      case 'high':
        return 'from-orange-500 to-amber-600';
      case 'medium':
        return 'from-blue-500 to-cyan-600';
      case 'low':
        return 'from-green-500 to-emerald-600';
      default:
        return 'from-gray-500 to-slate-600';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-300';
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-300';
      case 'on_hold':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-800 dark:text-yellow-300';
      case 'pending':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
      case 'cancelled':
        return 'bg-red-100 text-red-800 dark:bg-red-800 dark:text-red-300';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'in_progress':
        return <Clock className="w-4 h-4" />;
      case 'under_review':
        return <AlertCircle className="w-4 h-4" />;
      case 'pending':
        return <Calendar className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const filteredTasks = tasks.filter((task) => {
    if (filters.search) {
      const search = filters.search.toLowerCase();
      return (
        task.title.toLowerCase().includes(search) ||
        task.description?.toLowerCase().includes(search) ||
        task.customer_name?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  const taskStats = {
    total: filteredTasks.length,
    pending: filteredTasks.filter((t) => t.status === 'pending').length,
    in_progress: filteredTasks.filter((t) => t.status === 'in_progress').length,
    on_hold: filteredTasks.filter((t) => t.status === 'on_hold').length,
    completed: filteredTasks.filter((t) => t.status === 'completed').length,
    cancelled: filteredTasks.filter((t) => t.status === 'cancelled').length,
    overdue: filteredTasks.filter((t) => t.is_overdue).length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading tasks...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
            Task Management
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Manage and track all customer tasks
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${
              showFilters
                ? 'bg-purple-50 border-purple-500 text-purple-700 dark:bg-purple-800'
                : 'border-gray-300 hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:shadow-lg transition-all transform hover:scale-105"
          >
            <Plus className="w-4 h-4" />
            Create Task
          </button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4">
        <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900 dark:to-purple-800 p-4 rounded-xl border border-purple-200 dark:border-purple-700 animate-slide-up" style={{ animationDelay: '0ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-purple-600 dark:text-purple-400 font-medium">Total</p>
              <p className="text-3xl font-bold text-purple-900 dark:text-purple-100">{taskStats.total}</p>
            </div>
            <Target className="w-8 h-8 text-purple-500" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 dark:from-yellow-900 dark:to-yellow-800 p-4 rounded-xl border border-yellow-200 dark:border-yellow-700 animate-slide-up" style={{ animationDelay: '50ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium">Pending</p>
              <p className="text-3xl font-bold text-yellow-900 dark:text-yellow-100">{taskStats.pending}</p>
            </div>
            <Calendar className="w-8 h-8 text-yellow-500" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900 dark:to-blue-800 p-4 rounded-xl border border-blue-200 dark:border-blue-700 animate-slide-up" style={{ animationDelay: '100ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-600 dark:text-blue-400 font-medium">In Progress</p>
              <p className="text-3xl font-bold text-blue-900 dark:text-blue-100">{taskStats.in_progress}</p>
            </div>
            <Clock className="w-8 h-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 dark:from-yellow-900 dark:to-yellow-800 p-4 rounded-xl border border-yellow-200 dark:border-yellow-700 animate-slide-up" style={{ animationDelay: '150ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium">On Hold</p>
              <p className="text-3xl font-bold text-yellow-900 dark:text-yellow-100">{taskStats.on_hold}</p>
            </div>
            <Clock className="w-8 h-8 text-yellow-500" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900 dark:to-green-800 p-4 rounded-xl border border-green-200 dark:border-green-700 animate-slide-up" style={{ animationDelay: '200ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">Completed</p>
              <p className="text-3xl font-bold text-green-900 dark:text-green-100">{taskStats.completed}</p>
            </div>
            <CheckCircle2 className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-red-50 to-red-100 dark:from-red-900 dark:to-red-800 p-4 rounded-xl border border-red-200 dark:border-red-700 animate-slide-up" style={{ animationDelay: '225ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-red-600 dark:text-red-400 font-medium">Cancelled</p>
              <p className="text-3xl font-bold text-red-900 dark:text-red-100">{taskStats.cancelled}</p>
            </div>
            <X className="w-8 h-8 text-red-500" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900 dark:to-orange-800 p-4 rounded-xl border border-orange-200 dark:border-orange-700 animate-slide-up" style={{ animationDelay: '250ms' }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-orange-600 dark:text-orange-400 font-medium">Overdue</p>
              <p className="text-3xl font-bold text-orange-900 dark:text-orange-100">{taskStats.overdue}</p>
            </div>
            <Flag className="w-8 h-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 animate-slide-down">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Customer</label>
              <select
                value={filters.customer_id || ''}
                onChange={(e) => setFilters({ ...filters, customer_id: e.target.value ? parseInt(e.target.value) : undefined })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
              >
                <option value="">All Customers</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Status</label>
              <select
                value={filters.status || ''}
                onChange={(e) => setFilters({ ...filters, status: e.target.value || undefined })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
              >
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="on_hold">On Hold</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Priority</label>
              <select
                value={filters.priority || ''}
                onChange={(e) => setFilters({ ...filters, priority: e.target.value || undefined })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
              >
                <option value="">All Priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-2">Search</label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
                <input
                  type="text"
                  value={filters.search || ''}
                  onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                  placeholder="Search tasks..."
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <button
              onClick={() => setFilters({})}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>
      )}

      {/* Tasks Table */}
      {filteredTasks.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-12 text-center">
          <Sparkles className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 text-lg">No tasks found</p>
          <p className="text-gray-500 dark:text-gray-500 text-sm mt-2">
            {Object.keys(filters).length > 0 ? 'Try adjusting your filters' : 'Create your first task to get started'}
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Customer / Company
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Task
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    ISO Standard
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Priority
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Due Date
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {filteredTasks.map((task) => (
                  <tr key={task.id} className="hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <User className="w-5 h-5 text-purple-500 mr-2" />
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {task.customer_name || 'Unknown'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900 dark:text-white">
                        {task.title}
                      </div>
                      {task.description && (
                        <div className="text-sm text-gray-500 dark:text-gray-400 line-clamp-1 mt-1">
                          {task.description}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {task.iso_name ? (
                        <span className="text-sm text-gray-900 dark:text-white">
                          {task.iso_name}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-gradient-to-r ${getPriorityColor(task.priority)} text-white`}>
                        {task.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                        {getStatusIcon(task.status)}
                        {task.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {task.due_date ? (
                        <div className={task.is_overdue ? 'text-red-600 dark:text-red-400 font-semibold' : ''}>
                          {new Date(task.due_date).toLocaleDateString()}
                          {task.is_overdue && ' (Overdue)'}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end gap-2">
                        {task.status !== 'completed' && task.status !== 'cancelled' && (
                          <button
                            onClick={() => {
                              setSelectedTask(task);
                              setShowResolveModal(true);
                            }}
                            className="text-green-600 hover:text-green-900 dark:text-green-400 dark:hover:text-green-300"
                            title="Resolve"
                          >
                            <CheckCircle2 className="w-5 h-5" />
                          </button>
                        )}
                        {task.status !== 'cancelled' && task.status !== 'completed' && (
                          <button
                            onClick={() => handleIgnoreTask(task.id)}
                            className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                            title="Cancel"
                          >
                            <X className="w-5 h-5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between sticky top-0 bg-white dark:bg-gray-800 z-10">
              <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                Create New Task
              </h2>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Mode Selection */}
              <div className="flex gap-4">
                <button
                  onClick={() => setCreateMode('manual')}
                  className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                    createMode === 'manual'
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-800'
                      : 'border-gray-300 dark:border-gray-600 hover:border-purple-300'
                  }`}
                >
                  <FileText className="w-6 h-6 mx-auto mb-2 text-purple-600" />
                  <p className="font-medium">Manual Task</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Create from scratch</p>
                </button>
                <button
                  onClick={() => setCreateMode('template')}
                  className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                    createMode === 'template'
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-800'
                      : 'border-gray-300 dark:border-gray-600 hover:border-purple-300'
                  }`}
                >
                  <Sparkles className="w-6 h-6 mx-auto mb-2 text-purple-600" />
                  <p className="font-medium">From Template</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">Use predefined template</p>
                </button>
              </div>

              {/* Customer Selection */}
              <div>
                <label className="block text-sm font-medium mb-2">Customer *</label>
                <select
                  value={formData.customer_id}
                  onChange={(e) => {
                    const customerId = parseInt(e.target.value);
                    setFormData({ ...formData, customer_id: customerId });
                    if (customerId > 0) {
                      loadPlansForCustomer(customerId);
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                  required
                >
                  <option value={0}>Select Customer</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              {createMode === 'template' ? (
                <>
                  {/* Template Selection */}
                  <div>
                    <label className="block text-sm font-medium mb-2">Template *</label>
                    <select
                      value={formData.template_id}
                      onChange={(e) => setFormData({ ...formData, template_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                      required
                    >
                      <option value="">Select Template</option>
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                    {formData.template_id && templates.find(t => t.id === formData.template_id)?.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                        {templates.find(t => t.id === formData.template_id)?.description}
                      </p>
                    )}
                  </div>

                  {/* Variables */}
                  {formData.template_id && templates.find(t => t.id === formData.template_id)?.required_variables && (
                    <div className="space-y-3">
                      <label className="block text-sm font-medium">Template Variables</label>
                      {templates.find(t => t.id === formData.template_id)?.required_variables?.map((variable) => (
                        <div key={variable}>
                          <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                            {variable.replace(/_/g, ' ')}
                          </label>
                          <input
                            type="text"
                            value={formData.variables[variable] || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              variables: { ...formData.variables, [variable]: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                            placeholder={`Enter ${variable.replace(/_/g, ' ')}`}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  {/* Manual Task Fields */}
                  <div>
                    <label className="block text-sm font-medium mb-2">Task Type *</label>
                    <select
                      value={formData.task_type}
                      onChange={(e) => setFormData({ ...formData, task_type: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                    >
                      <option value="manual">Manual</option>
                      <option value="follow_up">Follow Up</option>
                      <option value="question">Question</option>
                      <option value="evidence_request">Evidence Request</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Title *</label>
                    <input
                      type="text"
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                      placeholder="Task title"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Description</label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                      rows={4}
                      placeholder="Task description"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Priority *</label>
                    <select
                      value={formData.priority}
                      onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="urgent">Urgent</option>
                    </select>
                  </div>
                </>
              )}

              {/* Common Fields */}
              <div>
                <label className="block text-sm font-medium mb-2">Due Date</label>
                <input
                  type="date"
                  value={formData.due_date}
                  onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 dark:bg-gray-700"
                />
              </div>
            </div>

            <div className="p-6 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3 sticky bottom-0 bg-white dark:bg-gray-800">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                }}
                className="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTask}
                disabled={!formData.customer_id || (createMode === 'manual' && !formData.title) || (createMode === 'template' && !formData.template_id)}
                className="px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:shadow-lg transition-all transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              >
                Create Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resolve Task Modal */}
      {showResolveModal && selectedTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between sticky top-0 bg-white dark:bg-gray-800 z-10">
              <h2 className="text-2xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                Resolve Task
              </h2>
              <button
                onClick={() => {
                  setShowResolveModal(false);
                  setSelectedTask(null);
                  resetResolutionForm();
                }}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Task Info */}
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">{selectedTask.title}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">{selectedTask.description}</p>
              </div>

              {/* Resolution Type */}
              <div>
                <label className="block text-sm font-medium mb-2">Resolution Type *</label>
                <select
                  value={resolutionData.resolution_type}
                  onChange={(e) => setResolutionData({ ...resolutionData, resolution_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700"
                >
                  <option value="answer_provided">Answer Provided</option>
                  <option value="evidence_uploaded">Evidence Uploaded</option>
                  <option value="manual_completion">Manual Completion</option>
                </select>
              </div>

              {/* Resolution Data Based on Type */}
              {resolutionData.resolution_type === 'answer_provided' && (
                <div>
                  <label className="block text-sm font-medium mb-2">Answer *</label>
                  <textarea
                    value={resolutionData.resolution_data.answer || ''}
                    onChange={(e) => setResolutionData({
                      ...resolutionData,
                      resolution_data: { ...resolutionData.resolution_data, answer: e.target.value }
                    })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700"
                    rows={4}
                    placeholder="Enter the answer"
                    required
                  />
                </div>
              )}

              {resolutionData.resolution_type === 'evidence_uploaded' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-2">File Path *</label>
                    <input
                      type="text"
                      value={resolutionData.resolution_data.file_path || ''}
                      onChange={(e) => setResolutionData({
                        ...resolutionData,
                        resolution_data: { ...resolutionData.resolution_data, file_path: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700"
                      placeholder="/uploads/evidence.pdf"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">File Name *</label>
                    <input
                      type="text"
                      value={resolutionData.resolution_data.file_name || ''}
                      onChange={(e) => setResolutionData({
                        ...resolutionData,
                        resolution_data: { ...resolutionData.resolution_data, file_name: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700"
                      placeholder="evidence.pdf"
                      required
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="requiresApproval"
                      checked={resolutionData.requires_approval}
                      onChange={(e) => setResolutionData({ ...resolutionData, requires_approval: e.target.checked })}
                      className="w-4 h-4 text-green-600 rounded focus:ring-green-500"
                    />
                    <label htmlFor="requiresApproval" className="text-sm">
                      Requires admin approval
                    </label>
                  </div>
                </>
              )}

              {/* Comments */}
              <div>
                <label className="block text-sm font-medium mb-2">Comments</label>
                <textarea
                  value={resolutionData.comments}
                  onChange={(e) => setResolutionData({ ...resolutionData, comments: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-green-500 dark:bg-gray-700"
                  rows={3}
                  placeholder="Optional comments"
                />
              </div>
            </div>

            <div className="p-6 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3 sticky bottom-0 bg-white dark:bg-gray-800">
              <button
                onClick={() => {
                  setShowResolveModal(false);
                  setSelectedTask(null);
                  resetResolutionForm();
                }}
                className="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleResolveTask}
                className="px-6 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:shadow-lg transition-all transform hover:scale-105"
              >
                Submit Resolution
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slide-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes slide-down {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
        .animate-slide-up {
          animation: slide-up 0.4s ease-out forwards;
        }
        .animate-slide-down {
          animation: slide-down 0.3s ease-out;
        }
      `}</style>
    </div>
  );
};

export default TaskManagementV3;
