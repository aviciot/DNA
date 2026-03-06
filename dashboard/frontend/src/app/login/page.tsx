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
