"""Helper script: write all Cloudflare Zero Trust implementation files."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def write(rel_path, content):
    path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  OK  {rel_path}")


# ============================================================
# 1. dashboard/frontend/src/app/login/page.tsx
# ============================================================
write("dashboard/frontend/src/app/login/page.tsx", '''\
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import Image from "next/image";
import { Mail, Lock, LogIn, Shield, Zap } from "lucide-react";

const CF_BYPASS = process.env.NEXT_PUBLIC_CF_BYPASS === "true";
const DEV_LOGIN_HELPER = process.env.NEXT_PUBLIC_DEV_LOGIN_HELPER === "true";

const ISO360Ring = () => (
  <div className="absolute inset-0 pointer-events-none flex items-center justify-center overflow-hidden">
    <div className="absolute w-[800px] h-[800px] border border-white/5 rounded-full animate-spin-slow opacity-20" />
    <div className="absolute w-[600px] h-[600px] border border-white/5 rounded-full animate-spin-reverse opacity-20" />
  </div>
);

/** Production: CF Access intercepts before this page is ever reached.
 *  Shown only if user navigates to /login directly while session is valid. */
function CFAuthGate() {
  const { isAuthenticated, isLoading, fetchUser } = useAuthStore();
  const router = useRouter();

  useEffect(() => { fetchUser(); }, []);
  useEffect(() => {
    if (!isLoading && isAuthenticated) router.push("/");
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="text-center space-y-4">
        <Shield className="w-12 h-12 text-blue-400 animate-pulse mx-auto" />
        <p className="text-white font-semibold text-lg">Authenticating via Cloudflare Access...</p>
        <p className="text-slate-400 text-sm">You will be redirected automatically.</p>
      </div>
    </div>
  );
}

/** Dev bypass mode: full email + password form backed by auth-service */
function DevLoginForm() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  useEffect(() => {
    if (isAuthenticated && !isLoading) router.push("/");
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try { await login(email, password); router.push("/"); }
    catch (err: any) { setError(err?.message || err?.response?.data?.detail || "Invalid credentials"); }
    finally { setLoading(false); }
  };

  const handleDevLogin = async () => {
    setError(""); setLoading(true);
    try { await login("admin@dna.local", "admin123"); router.push("/"); }
    catch (err: any) { setError(err?.message || "Login failed"); }
    finally { setLoading(false); }
  };

  if (isAuthenticated) return null;

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden bg-gray-50 dark:bg-slate-950">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-0 -left-1/4 w-[1000px] h-[1000px] bg-purple-100/40 dark:bg-purple-900/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 -right-1/4 w-[1000px] h-[1000px] bg-cyan-100/40 dark:bg-cyan-900/10 rounded-full blur-[120px]" />
      </div>
      <ISO360Ring />

      <div className={`relative z-10 w-full max-w-md transform transition-all duration-1000 ${mounted ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"}`}>
        <div className="relative bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl rounded-[2rem] shadow-xl p-8 sm:p-10 space-y-8 ring-1 ring-black/5 dark:ring-white/10">

          <div className="text-center pt-2">
            <div className="flex justify-center mb-8">
              <div className="relative">
                <div className="absolute -inset-8 rounded-full border border-gray-200 dark:border-white/10 opacity-60 animate-spin-slow" />
                <div className="relative p-2 bg-white dark:bg-slate-800 rounded-3xl shadow-xl ring-1 ring-black/5 dark:ring-white/10">
                  <div className="bg-gray-50 dark:bg-slate-900 rounded-2xl p-4">
                    <Image src="/dna_q_logo.png" alt="DNA ISO 360" width={90} height={90}
                      style={{ width: "auto", height: "auto", maxWidth: "90px" }}
                      className="rounded-xl" priority />
                  </div>
                </div>
                <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-white dark:bg-slate-800 border border-yellow-200 dark:border-yellow-900/50 rounded-full text-[10px] font-bold tracking-wider text-yellow-600 dark:text-yellow-400 shadow-lg uppercase whitespace-nowrap">
                  Dev Mode
                </div>
              </div>
            </div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2 tracking-tight">
              DNA <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-cyan-600">ISO 360</span>
            </h1>
            <p className="text-sm font-medium text-yellow-600 dark:text-yellow-400">Local Development Mode</p>
          </div>

          {error && (
            <div className="rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-300 dark:border-red-500/50 p-4">
              <p className="text-sm font-medium text-red-600 dark:text-red-300 text-center">{error}</p>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-200">Email</label>
              <div className="relative">
                <Mail className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 ${focused === "email" ? "text-purple-600" : "text-gray-400"}`} />
                <input id="email" type="email" autoComplete="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} onFocus={() => setFocused("email")} onBlur={() => setFocused(null)}
                  className="w-full pl-12 pr-4 py-4 bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 text-gray-900 dark:text-white rounded-xl focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all"
                  placeholder="admin@dna.local" />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-200">Password</label>
              <div className="relative">
                <Lock className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 ${focused === "password" ? "text-purple-600" : "text-gray-400"}`} />
                <input id="password" type="password" autoComplete="current-password" required value={password}
                  onChange={(e) => setPassword(e.target.value)} onFocus={() => setFocused("password")} onBlur={() => setFocused(null)}
                  className="w-full pl-12 pr-4 py-4 bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 text-gray-900 dark:text-white rounded-xl focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all"
                  placeholder="..." />
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="w-full flex items-center justify-center py-4 bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 rounded-xl text-white font-semibold transition-all disabled:opacity-50">
              {loading ? <span className="animate-pulse">Authenticating...</span> : <><LogIn className="w-5 h-5 mr-2" />Sign In</>}
            </button>

            {DEV_LOGIN_HELPER && (
              <button type="button" onClick={handleDevLogin} disabled={loading}
                className="w-full flex items-center justify-center py-4 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-xl text-white font-semibold transition-all disabled:opacity-50">
                <Zap className="w-5 h-5 mr-2 animate-pulse" />Dev Quick Login
              </button>
            )}
          </form>

          <div className="pt-4 border-t border-gray-200 dark:border-slate-700">
            <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
              <code className="px-2 py-1 rounded bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-300">admin@dna.local</code>
              <span>/</span>
              <code className="px-2 py-1 rounded bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-300">admin123</code>
            </div>
          </div>
        </div>
        <p className="text-center mt-6 text-xs text-gray-400 font-medium">DNA ISO 360 &bull; Local Development</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return CF_BYPASS ? <DevLoginForm /> : <CFAuthGate />;
}
''')


# ============================================================
# 2. SecurityConfig.tsx
# ============================================================
write("dashboard/frontend/src/components/admin/SecurityConfig.tsx", '''\
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
''')


# ============================================================
# 3. traefik/traefik.yml
# ============================================================
write("traefik/traefik.yml", '''\
# Traefik v3 static configuration
# All app containers register via Docker labels.
# Cloudflared tunnel points all hostnames at Traefik :80.

entryPoints:
  web:
    address: ":80"
  # TLS is terminated at the Cloudflare edge -- no need for HTTPS internally

providers:
  docker:
    exposedByDefault: false
    # Traefik reads labels from all containers on the shared networks
    network: dna-network

api:
  # Dashboard disabled in production; enable only for debugging
  dashboard: false
  insecure: false

log:
  level: INFO

accessLog: {}
''')


# ============================================================
# 4. cloudflared/config.yml
# ============================================================
write("cloudflared/config.yml", '''\
# Cloudflare Tunnel ingress configuration
# Tunnel ID and credentials are provided via TUNNEL_TOKEN env var in docker-compose.
#
# All traffic enters at Traefik :80 and is routed by Host header internally.
#
# To use this file instead of the env-var token approach:
#   tunnel: <YOUR_TUNNEL_ID>
#   credentials-file: /etc/cloudflared/credentials.json
#
# Hostname routing (configured in CF Access dashboard):
#   dna.yourcompany.com   -> internal staff dashboard (Access enforced)
#   portal.yourcompany.com -> customer portal (Access bypass, WAF active)

ingress:
  - hostname: "${CF_DNA_HOSTNAME}"
    service: http://traefik:80
    originRequest:
      noTLSVerify: false
  - hostname: "${CF_PORTAL_HOSTNAME}"
    service: http://traefik:80
    originRequest:
      noTLSVerify: false
  # Catch-all required by cloudflared
  - service: http_status:404
''')


# ============================================================
# 5. .env.example additions
# ============================================================
env_path = os.path.join(BASE, ".env.example")
with open(env_path, "r", encoding="utf-8") as f:
    existing = f.read()

cf_block = '''
# ============================================================
# Cloudflare Zero Trust
# ============================================================
# Set CF_BYPASS_LOCAL=false in production
CF_BYPASS_LOCAL=true
CF_TEAM_DOMAIN=yourteam.cloudflareaccess.com
CF_APP_AUD=your-cf-app-audience-tag-here
CF_TUNNEL_TOKEN=your-cloudflare-tunnel-token-here
CF_DNA_HOSTNAME=dna.yourcompany.com
CF_PORTAL_HOSTNAME=portal.yourcompany.com
# Internal service-to-service auth token (generate with: openssl rand -hex 32)
CF_INTERNAL_SERVICE_TOKEN=change-me-in-production

# ============================================================
# Frontend (CF mode)
# ============================================================
# Set NEXT_PUBLIC_CF_BYPASS=false in production
NEXT_PUBLIC_CF_BYPASS=true
NEXT_PUBLIC_DEV_LOGIN_HELPER=true
NEXT_PUBLIC_CF_TEAM_DOMAIN=yourteam.cloudflareaccess.com
'''

if "CF_BYPASS_LOCAL" not in existing:
    with open(env_path, "a", encoding="utf-8") as f:
        f.write(cf_block)
    print("  OK  .env.example (appended CF block)")
else:
    print("  SKIP .env.example (CF block already present)")


print("\nAll files written successfully.")
