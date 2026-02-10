"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import Image from "next/image";
import { Mail, Lock, LogIn } from "lucide-react";

const DEV_LOGIN_HELPER = process.env.NEXT_PUBLIC_DEV_LOGIN_HELPER === 'true';

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push("/");
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(email, password);
      router.push("/");
    } catch (err: any) {
      const errorMessage = err?.message || err?.response?.data?.detail || err?.toString() || "Invalid email or password";
      setError(errorMessage);
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDevLogin = async () => {
    setEmail("admin@dna.local");
    setPassword("admin123");
    setError("");
    setLoading(true);
    
    try {
      await login("admin@dna.local", "admin123");
      router.push("/");
    } catch (err: any) {
      const errorMessage = err?.message || err?.response?.data?.detail || err?.toString() || "Invalid email or password";
      setError(errorMessage);
      console.error('Dev login error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (isAuthenticated) {
    return null; // Will redirect
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 px-4 relative overflow-hidden">
      {/* Decorative Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-0 w-96 h-96 bg-blue-400/20 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2"></div>
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-indigo-400/20 rounded-full blur-3xl translate-x-1/2 translate-y-1/2"></div>
      </div>

      {/* Login Card */}
      <div className="w-full max-w-lg bg-white/95 dark:bg-gray-800/95 backdrop-blur-sm rounded-3xl shadow-2xl p-10 space-y-7 relative z-10 border border-white/20">
        {/* Logo Section */}
        <div className="text-center">
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-600/20 rounded-2xl blur-xl"></div>
              <Image
                src="/dna_q_logo.png"
                alt="DNA Logo"
                width={120}
                height={120}
                style={{ width: 'auto', height: 'auto', maxWidth: '120px' }}
                className="rounded-2xl shadow-2xl relative z-10"
                priority
              />
            </div>
          </div>

          <h2 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-3">
            Welcome to DNA
          </h2>
          <p className="text-base text-gray-600 dark:text-gray-400">
            ISO Certification Management System
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-4">
            <p className="text-base font-medium text-red-800 dark:text-red-200 text-center">
              {error}
            </p>
          </div>
        )}

        {/* Form */}
        <form className="space-y-6" onSubmit={handleSubmit}>
          {/* Email Input */}
          <div className="space-y-2">
            {/* Label - 20% larger (text-sm → text-base) */}
            <label htmlFor="email" className="block text-base font-semibold text-gray-700 dark:text-gray-300">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              {/* Input - 20% larger padding (py-3 → py-4, text-base → text-lg) */}
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-12 pr-4 py-4 text-lg bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="admin@dna.local"
              />
            </div>
          </div>

          {/* Password Input */}
          <div className="space-y-2">
            {/* Label - 20% larger (text-sm → text-base) */}
            <label htmlFor="password" className="block text-base font-semibold text-gray-700 dark:text-gray-300">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              {/* Input - 20% larger padding (py-3 → py-4, text-base → text-lg) */}
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-12 pr-4 py-4 text-lg bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="••••••••"
              />
            </div>
          </div>

          {/* Sign In Button - 20% larger (py-3 → py-4, text-base → text-lg) */}
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center py-4 px-4 text-lg font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Signing in...
              </>
            ) : (
              <>
                <LogIn className="w-5 h-5 mr-2" />
                Sign In
              </>
            )}
          </button>

          {/* Dev Login Button */}
          {DEV_LOGIN_HELPER && (
            <button
              type="button"
              onClick={handleDevLogin}
              disabled={loading}
              className="w-full flex items-center justify-center py-4 px-4 text-lg font-bold text-white bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="mr-2">🚀</span>
              Dev Quick Login
            </button>
          )}
        </form>

        {/* Footer Info */}
        <div className="pt-4 border-t border-gray-200 dark:border-gray-700 text-center">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Default Credentials</p>
          <p className="font-mono text-base text-gray-900 dark:text-white font-semibold">
            admin@dna.local / admin123
          </p>
        </div>
      </div>
    </div>
  );
}
