"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/authStore";
import {
  LayoutDashboard, Users, FileText, Shield, BookOpen,
  Wrench, Activity, LogOut, ChevronRight, Zap,
} from "lucide-react";
import NotificationCenter from "@/components/notifications/NotificationCenter";

const USER_NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/documents", label: "Documents", icon: FileText },
];

const ADMIN_NAV = [
  { href: "/admin?section=iso-standards", label: "ISO Studio", icon: Shield },
  { href: "/admin?section=customers", label: "Customers", icon: Users },
  { href: "/admin?section=ai-providers", label: "Configuration", icon: Wrench },
  { href: "/admin?section=system-health", label: "System Health", icon: Activity },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading, fetchUser, logout } = useAuthStore();

  useEffect(() => { fetchUser(); }, [fetchUser]);
  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push("/login");
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8F9FB]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-slate-400">Loading...</span>
        </div>
      </div>
    );
  }

  const isAdmin = user?.role === "admin";
  const initials = (user?.full_name || user?.email || "U")
    .split(" ").map((w: string) => w[0]).join("").toUpperCase().slice(0, 2);

  const NavItem = ({ href, label, icon: Icon }: { href: string; label: string; icon: any }) => {
    const base = href.split("?")[0];
    const isActive = pathname === base && (
      !href.includes("?") ||
      (typeof window !== "undefined" && window.location.href.includes(href.split("?")[1]))
    );
    return (
      <Link href={href}
        className={`group flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
          isActive
            ? "bg-blue-50 text-blue-700"
            : "text-slate-500 hover:text-slate-900 hover:bg-slate-50"
        }`}>
        <Icon className={`w-4 h-4 flex-shrink-0 transition-colors ${isActive ? "text-blue-600" : "text-slate-400 group-hover:text-slate-600"}`} />
        <span className="flex-1">{label}</span>
        {isActive && <ChevronRight className="w-3 h-3 text-blue-400" />}
      </Link>
    );
  };

  const isAdminPage = pathname === "/admin" || pathname.startsWith("/admin/");
  const activeSection = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("section") : "";

  return (
    <div className="min-h-screen bg-[#F8F9FB] flex">
      <aside className="w-56 bg-white border-r border-slate-100 flex flex-col flex-shrink-0 fixed h-full z-20">
          {/* Logo */}
          <div className="h-14 flex items-center px-4 border-b border-slate-100 justify-between">
            <Link href="/" className="flex items-center gap-2.5 hover:opacity-80 transition-opacity">
              <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <Zap className="w-4 h-4 text-white" />
              </div>
              <div>
                <span className="text-sm font-bold text-slate-900 tracking-tight">DNA</span>
                <span className="text-xs text-slate-400 block leading-none">ISO Platform</span>
              </div>
            </Link>
            <NotificationCenter />
          </div>

          {/* Nav */}
          <nav className="flex-1 overflow-y-auto p-3 space-y-5">
            <div>
              <p className="px-3 mb-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Workspace</p>
              <div className="space-y-0.5">
                {USER_NAV.map(item => <NavItem key={item.href} {...item} />)}
              </div>
            </div>

            {isAdmin && (
              <div>
                <p className="px-3 mb-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Admin</p>
                <div className="space-y-0.5">
                  {ADMIN_NAV.map(item => {
                    const sectionParam = item.href.split("section=")[1];
                    const categoryMap: Record<string, string> = {
                      "iso-standards": "iso-studio", "templates": "iso-studio", "reference-docs": "iso-studio", "iso360": "iso-studio", "iso360-health": "iso-studio",
                      "customers": "customers",
                      "ai-providers": "configuration", "template-ai": "configuration", "automation": "configuration", "customer-portal": "configuration", "security": "configuration",
                      "system-health": "system-health",
                    };
                    const targetCategory = categoryMap[sectionParam] ?? sectionParam;
                    const currentCategory = categoryMap[activeSection ?? ""] ?? activeSection;
                    const isActive = isAdminPage && targetCategory === currentCategory;
                    const Icon = item.icon;
                    return (
                      <Link key={item.href} href={item.href}
                        className={`group flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                          isActive ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:text-slate-900 hover:bg-slate-50"
                        }`}>
                        <Icon className={`w-4 h-4 flex-shrink-0 transition-colors ${isActive ? "text-blue-600" : "text-slate-400 group-hover:text-slate-600"}`} />
                        <span className="flex-1">{item.label}</span>
                        {isActive && <ChevronRight className="w-3 h-3 text-blue-400" />}
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}
          </nav>

          {/* User */}
          <div className="p-3 border-t border-slate-100">
            <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors group">
              <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] font-bold text-blue-700">{initials}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-800 truncate leading-tight">{user?.full_name || user?.email}</p>
                <p className="text-[10px] text-slate-400 leading-tight">{isAdmin ? "Administrator" : "Viewer"}</p>
              </div>
              <button
                onClick={async () => { await logout(); router.push("/login"); }}
                className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                title="Sign out">
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </aside>

      {/* Content */}
      <main className="flex-1 min-h-screen overflow-y-auto ml-56">
        {children}
      </main>
    </div>
  );
}
