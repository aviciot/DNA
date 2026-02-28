"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import Image from "next/image";
import { Mail, Lock, LogIn, Sparkles, Shield, Zap, RotateCw } from "lucide-react";

const DEV_LOGIN_HELPER = process.env.NEXT_PUBLIC_DEV_LOGIN_HELPER === 'true';

// Floating particle component
const FloatingParticle = ({ delay, duration, size, left, top }: { 
  delay: number; duration: number; size: number; left: string; top: string 
}) => (
  <div
    className="absolute rounded-full bg-white/20 animate-float-particle"
    style={{
      width: size,
      height: size,
      left,
      top,
      animationDelay: `${delay}s`,
      animationDuration: `${duration}s`,
    }}
  />
);

// Creative ISO 360 Animated Component
const ISO360Animation = () => (
  <div className="absolute inset-0 pointer-events-none flex items-center justify-center overflow-hidden">
    {/* Large revolving rings background */}
    <div className="absolute w-[800px] h-[800px] border border-white/5 rounded-full animate-spin-slow opacity-20" />
    <div className="absolute w-[600px] h-[600px] border border-white/5 rounded-full animate-spin-reverse opacity-20" />
    <div className="absolute w-[1000px] h-[1000px] border border-white/5 rounded-full animate-pulse-slow opacity-10" />
    
    {/* Floating ISO Badges in orbit */}
    <div className="absolute animate-spin-slow w-[600px] h-[600px]">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-6">
         <div className="px-3 py-1 bg-white/5 backdrop-blur-md rounded-full border border-white/10 text-xs text-white/40">ISO 27001</div>
      </div>
      <div className="absolute bottom-0 right-1/2 translate-x-1/2 translate-y-6">
         <div className="px-3 py-1 bg-white/5 backdrop-blur-md rounded-full border border-white/10 text-xs text-white/40">ISO 9001</div>
      </div>
    </div>
  </div>
);

// Right side ISO badge animation - keeping it minimal now
const ISOBadge = () => null;

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  // Generate particles only on client side
  const particles = useMemo(() => 
    [...Array(20)].map((_, i) => ({
      id: i,
      delay: Math.random() * 5,
      duration: 10 + Math.random() * 20,
      size: 4 + Math.random() * 8,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
    })), []
  );

  useEffect(() => {
    setMounted(true);
  }, []);

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
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden bg-gray-50 dark:bg-slate-950">
      
      {/* Refined Background - Subtle & Clean */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Large soft gradients */}
        <div className="absolute top-0 -left-1/4 w-[1000px] h-[1000px] bg-purple-100/40 dark:bg-purple-900/10 rounded-full blur-[120px] mix-blend-multiply" />
        <div className="absolute bottom-0 -right-1/4 w-[1000px] h-[1000px] bg-cyan-100/40 dark:bg-cyan-900/10 rounded-full blur-[120px] mix-blend-multiply" />
        
        {/* Subtle grid pattern - reduced opacity */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.02)_1px,transparent_1px)] dark:bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
      </div>

      {/* ISO 360 Animations - Background Layer */}
      <ISO360Animation />
      <ISOBadge />

      {/* Main Content Container */}
      <div className={`relative z-10 w-full max-w-md transform transition-all duration-1000 ${mounted ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}>
        
        {/* Clean Glass Card */}
        <div className="relative group">
          {/* Subtle drop shadow instead of heavy glow */}
          <div className="absolute -inset-0.5 bg-gradient-to-b from-white/80 to-transparent dark:from-white/10 rounded-[2rem] blur opacity-40" />
          
          <div className="relative bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl rounded-[2rem] shadow-[0_8px_32px_-4px_rgba(0,0,0,0.1)] dark:shadow-[0_8px_32px_-4px_rgba(0,0,0,0.3)] p-8 sm:p-10 space-y-8 ring-1 ring-black/5 dark:ring-white/10">
            
            {/* Logo Section with 360 Ring */}
            <div className="text-center pt-2">
              <div className="flex justify-center mb-8">
                <div className="relative group/logo">
                  {/* Outer rotating ring */}
                  <div className="absolute -inset-8 rounded-full border border-gray-200 dark:border-white/10 opacity-60 animate-spin-slow" />
                  
                  {/* Inner ring */}
                  <div className="absolute -inset-4 rounded-full border border-gray-200 dark:border-white/10 opacity-40 animate-spin-reverse" />
                  
                  {/* Subtle Glow - Reduced intensity */}
                  <div className="absolute -inset-4 bg-gradient-to-r from-purple-500/20 to-cyan-500/20 rounded-full blur-2xl opacity-0 group-hover/logo:opacity-100 transition-opacity duration-700" />
                  
                  {/* Logo container - More refined */}
                  <div className="relative p-2 bg-white dark:bg-slate-800 rounded-3xl shadow-xl ring-1 ring-black/5 dark:ring-white/10">
                    <div className="bg-gray-50 dark:bg-slate-900 rounded-2xl p-4 overflow-hidden relative">
                      {/* Inner highlight */}
                      <div className="absolute inset-0 bg-gradient-to-br from-white/50 to-transparent pointer-events-none" />
                      <Image
                        src="/dna_q_logo.png"
                        alt="DNA ISO 360 Logo"
                        width={90}
                        height={90}
                        style={{ width: 'auto', height: 'auto', maxWidth: '90px' }}
                        className="rounded-xl relative z-10 drop-shadow-sm"
                        priority
                      />
                    </div>
                  </div>
                  
                  {/* 360 badge - Elegant tag style */}
                  <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-white dark:bg-slate-800 border border-purple-100 dark:border-purple-900/50 rounded-full text-[10px] font-bold tracking-wider text-purple-600 dark:text-purple-400 shadow-lg uppercase">
                    360° Support
                  </div>
                </div>
              </div>

              {/* Title with Gradient Text */}
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2 tracking-tight">
                DNA <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-cyan-600">ISO 360</span>
              </h1>
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                Complete Certification Ecosystem
              </p>
            </div>

            {/* Feature Pills - Minimal */}
            <div className="flex justify-center gap-2 flex-wrap pb-4">
              {[
                { icon: RotateCw, text: '360°' },
                { icon: Sparkles, text: 'AI' },
                { icon: Zap, text: 'Fast' },
              ].map(({ icon: Icon, text }) => (
                <span key={text} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-[11px] font-medium text-gray-600 dark:text-gray-300">
                  <Icon className="w-3 h-3 text-purple-600 dark:text-purple-400" />
                  {text}
                </span>
              ))}
            </div>

            {/* Error Message with Animation */}
            {error && (
              <div className="animate-shake rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-300 dark:border-red-500/50 p-4">
                <p className="text-sm font-medium text-red-600 dark:text-red-300 text-center">
                  {error}
                </p>
              </div>
            )}

            {/* Form */}
            <form className="space-y-5" onSubmit={handleSubmit}>
              {/* Email Input */}
              <div className="space-y-2">
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                  Email Address
                </label>
                <div className={`relative group/input transition-all duration-300 ${focused === 'email' ? 'scale-[1.02]' : ''}`}>
                  <div className={`absolute -inset-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 rounded-xl blur opacity-0 transition-opacity duration-300 ${focused === 'email' ? 'opacity-50' : 'group-hover/input:opacity-25'}`} />
                  <div className="relative">
                    <Mail className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors duration-300 ${focused === 'email' ? 'text-purple-600' : 'text-gray-400'}`} />
                    <input
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onFocus={() => setFocused('email')}
                      onBlur={() => setFocused(null)}
                      className="w-full pl-12 pr-4 py-4 bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 text-gray-900 dark:text-white placeholder-gray-400 rounded-xl focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all duration-300"
                      placeholder="admin@dna.local"
                    />
                  </div>
                </div>
              </div>

              {/* Password Input */}
              <div className="space-y-2">
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                  Password
                </label>
                <div className={`relative group/input transition-all duration-300 ${focused === 'password' ? 'scale-[1.02]' : ''}`}>
                  <div className={`absolute -inset-0.5 bg-gradient-to-r from-purple-500 to-cyan-500 rounded-xl blur opacity-0 transition-opacity duration-300 ${focused === 'password' ? 'opacity-50' : 'group-hover/input:opacity-25'}`} />
                  <div className="relative">
                    <Lock className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 transition-colors duration-300 ${focused === 'password' ? 'text-purple-600' : 'text-gray-400'}`} />
                    <input
                      id="password"
                      name="password"
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onFocus={() => setFocused('password')}
                      onBlur={() => setFocused(null)}
                      className="w-full pl-12 pr-4 py-4 bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 text-gray-900 dark:text-white placeholder-gray-400 rounded-xl focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all duration-300"
                      placeholder="••••••••"
                    />
                  </div>
                </div>
              </div>

              {/* Sign In Button */}
              <button
                type="submit"
                disabled={loading}
                className="relative w-full group/btn overflow-hidden"
              >
                <div className="absolute -inset-1 bg-gradient-to-r from-purple-600 via-pink-600 to-cyan-600 rounded-xl blur-sm opacity-70 group-hover/btn:opacity-100 transition-opacity duration-300 animate-gradient-x" />
                <div className="relative flex items-center justify-center py-4 px-4 bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 rounded-xl text-white font-semibold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed">
                  {loading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className="animate-pulse">Authenticating...</span>
                    </>
                  ) : (
                    <>
                      <LogIn className="w-5 h-5 mr-2 group-hover/btn:translate-x-1 transition-transform" />
                      Sign In
                      <Sparkles className="w-4 h-4 ml-2 opacity-0 group-hover/btn:opacity-100 transition-opacity" />
                    </>
                  )}
                </div>
              </button>

              {/* Dev Login Button */}
              {DEV_LOGIN_HELPER && (
                <button
                  type="button"
                  onClick={handleDevLogin}
                  disabled={loading}
                  className="relative w-full group/dev overflow-hidden"
                >
                  <div className="absolute -inset-1 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-xl blur-sm opacity-50 group-hover/dev:opacity-75 transition-opacity duration-300" />
                  <div className="relative flex items-center justify-center py-4 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-xl text-white font-semibold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed">
                    <Zap className="w-5 h-5 mr-2 animate-pulse" />
                    Dev Quick Login
                  </div>
                </button>
              )}
            </form>

            {/* Footer */}
            <div className="pt-4 border-t border-gray-200 dark:border-slate-700">
              <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
                <span className="px-2 py-1 rounded bg-gray-100 dark:bg-slate-800 font-mono text-gray-600 dark:text-gray-300">
                  admin@dna.local
                </span>
                <span>/</span>
                <span className="px-2 py-1 rounded bg-gray-100 dark:bg-slate-800 font-mono text-gray-600 dark:text-gray-300">
                  admin123
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Text */}
        <p className="text-center mt-6 text-xs text-gray-400 dark:text-gray-500 font-medium tracking-wide">
          DNA ISO 360° &bull; Advanced Certification Platform
        </p>
      </div>
    </div>
  );
}
