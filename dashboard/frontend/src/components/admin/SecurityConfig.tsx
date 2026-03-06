"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Shield, Users, Plus, Trash2, UserCheck, UserX,
  ChevronDown, ExternalLink, Info, RefreshCw,
} from "lucide-react";

const ROLES = ["admin", "dna_operator", "viewer"] as const;
type Role = (typeof ROLES)[number];

interface UserRow {
  id: number;
  email: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string | null;
  last_login: string | null;
}

interface CFInfo {
  cf_team_domain: string | null;
  cf_app_aud_configured: boolean;
  bypass_mode: boolean;
  auth_method: string;
  cf_dashboard_url: string | null;
}

// ---------------------------------------------------------------------------
// Sub-sections
// ---------------------------------------------------------------------------

function InfoBadge({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`text-sm font-medium ${ok === false ? "text-red-500" : ok === true ? "text-emerald-600" : "text-slate-800"}`}>
        {value}
      </span>
    </div>
  );
}

function IdentityProviderSection({ info }: { info: CFInfo | null }) {
  if (!info) return <div className="text-sm text-slate-400">Loading...</div>;
  return (
    <div className="space-y-1">
      <InfoBadge label="Auth Method" value={info.auth_method} ok={!info.bypass_mode} />
      <InfoBadge label="CF Team Domain" value={info.cf_team_domain ?? "Not configured"} ok={!!info.cf_team_domain} />
      <InfoBadge label="App Audience (AUD)" value={info.cf_app_aud_configured ? "Configured" : "Missing"} ok={info.cf_app_aud_configured} />
      <InfoBadge label="Bypass Mode" value={info.bypass_mode ? "Enabled (dev)" : "Disabled (production)"} ok={!info.bypass_mode} />
      {info.cf_dashboard_url && (
        <div className="pt-3">
          <a href={info.cf_dashboard_url} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
            Open Cloudflare Access Dashboard <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      )}
    </div>
  );
}

function AddUserModal({ onAdd, onClose }: {
  onAdd: (email: string, name: string, role: Role) => Promise<void>;
  onClose: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try { await onAdd(email, name, role); onClose(); }
    catch (ex: any) { setErr(ex?.response?.data?.detail || "Failed to add user"); }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
        <h3 className="text-lg font-semibold text-slate-900">Provision New User</h3>
        {err && <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3">{err}</p>}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="user@company.com" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
            <input type="text" required value={name} onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Jane Smith" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Role</label>
            <select value={role} onChange={e => setRole(e.target.value as Role)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm text-white font-medium disabled:opacity-50">
              {loading ? "Adding..." : "Add User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RoleBadge({ role }: { role: Role }) {
  const colors: Record<Role, string> = {
    admin: "bg-purple-100 text-purple-700",
    dna_operator: "bg-blue-100 text-blue-700",
    viewer: "bg-slate-100 text-slate-600",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[role]}`}>{role}</span>
  );
}

function UserProvisioningSection() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  const load = async () => {
    setLoading(true);
    try { const r = await api.get("/api/v1/security/users"); setUsers(r.data); }
    catch { /* handled by interceptor */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const addUser = async (email: string, full_name: string, role: Role) => {
    await api.post("/api/v1/security/users", { email, full_name, role });
    await load();
  };

  const changeRole = async (id: number, role: Role) => {
    await api.patch(`/api/v1/security/users/${id}/role`, { role });
    await load();
  };

  const toggleActive = async (u: UserRow) => {
    const endpoint = u.is_active ? "deactivate" : "activate";
    await api.patch(`/api/v1/security/users/${u.id}/${endpoint}`);
    await load();
  };

  const deleteUser = async (u: UserRow) => {
    if (!confirm(`Delete ${u.email}? This cannot be undone.`)) return;
    await api.delete(`/api/v1/security/users/${u.id}`);
    await load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Users must be provisioned here before they can access the dashboard after CF authentication.
        </p>
        <div className="flex gap-2">
          <button onClick={load} className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg">
            <Plus className="w-4 h-4" />Add User
          </button>
        </div>
      </div>

      {showAdd && <AddUserModal onAdd={addUser} onClose={() => setShowAdd(false)} />}

      <div className="overflow-hidden border border-slate-100 rounded-xl">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">User</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Role</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Last Login</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {loading ? (
              <tr><td colSpan={5} className="text-center py-8 text-slate-400">Loading users...</td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-8 text-slate-400">No users provisioned</td></tr>
            ) : users.map(u => (
              <tr key={u.id} className={`hover:bg-slate-50 ${!u.is_active ? "opacity-50" : ""}`}>
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-900">{u.full_name || u.email}</div>
                  {u.full_name && <div className="text-xs text-slate-400">{u.email}</div>}
                </td>
                <td className="px-4 py-3">
                  <select value={u.role} onChange={e => changeRole(u.id, e.target.value as Role)}
                    className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600"}`}>
                    {u.is_active ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                    {u.is_active ? "Active" : "Deactivated"}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 justify-end">
                    <button onClick={() => toggleActive(u)} title={u.is_active ? "Deactivate" : "Reactivate"}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700">
                      {u.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                    </button>
                    <button onClick={() => deleteUser(u)} title="Delete"
                      className="p-1.5 rounded-lg hover:bg-red-50 text-slate-300 hover:text-red-500">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
type Tab = "identity" | "users";

export default function SecurityConfig() {
  const [tab, setTab] = useState<Tab>("users");
  const [info, setInfo] = useState<CFInfo | null>(null);

  useEffect(() => {
    api.get("/api/v1/security/info")
      .then(r => setInfo(r.data))
      .catch(() => {});
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: "users", label: "User Provisioning" },
    { id: "identity", label: "Identity Provider" },
  ];

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Shield className="w-5 h-5 text-blue-600" />Security & Access
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Manage Cloudflare Zero Trust configuration and user provisioning.
        </p>
      </div>

      {info?.bypass_mode && (
        <div className="flex items-start gap-2 p-4 bg-yellow-50 border border-yellow-200 rounded-xl text-sm text-yellow-800">
          <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>Running in <strong>local dev bypass mode</strong> -- CF Access is not enforced. Set CF_BYPASS_LOCAL=false in production.</span>
        </div>
      )}

      <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden">
        <div className="flex border-b border-slate-100">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-6 py-3 text-sm font-medium transition-colors ${tab === t.id ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50/50" : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="p-6">
          {tab === "identity" && <IdentityProviderSection info={info} />}
          {tab === "users" && <UserProvisioningSection />}
        </div>
      </div>
    </div>
  );
}
