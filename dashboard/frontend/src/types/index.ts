/**
 * DNA Frontend - Type Definitions
 * =================================
 */

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: 'admin' | 'viewer';
  is_active: boolean;
  last_login: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface DashboardStats {
  total_customers: number;
  active_documents: number;
  pending_tasks: number;
  completion_rate: number;
}
