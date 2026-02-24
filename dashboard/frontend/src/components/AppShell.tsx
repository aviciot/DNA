"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useAuthStore } from "@/stores/authStore";
import {
  LayoutDashboard, Users, FileText, Shield, BookOpen,
  Wrench, Activity, LogOut, Settings,
} from "lucide-react";

const USER_NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/documents", label: "Documents", icon: FileText },
];

const ADMIN_NAV = [
  { href: "/admin?section=iso-standards", label: "ISO Standards", icon: Shield },
  { href: "/admin?section=templates", label: "Templates", icon: BookOpen },
  { href: "/admin?section=configuration", label: "Configuration", icon: Wrench },
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
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" />
      </div>
    );
  }

  const isAdmin = user?.role === "admin";

  const NavItem = ({ href, label, icon: Icon }: { href: string; label: string; icon: any }) => {
    const active = pathname === href.split("?")[0] && (
      !href.includes("?") || (typeof window !== "undefined" && window.location.search === `?${href.split("?")[1]}`)
    );
    return (
      <Link href={href}
        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${
          active
            ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium"
            : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white"
        }`}>
        <Icon className="w-4 h-4 flex-shrink-0" />
        <span>{label}</span>
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      {/* Top bar */}
      <header className="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center px-4 flex-shrink-0 z-10">
        <Link href="/" className="flex items-center space-x-2 hover:opacity-80 transition-opacity mr-6">
          <Image src="/dna_q_logo.png" alt="DNA" width={32} height={32} className="rounded-lg" />
          <span className="text-sm font-bold text-gray-900 dark:text-white">DNA Dashboard</span>
        </Link>
        <div className="flex-1" />
        <div className="flex items-center space-x-3">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium text-gray-900 dark:text-white leading-tight">{user?.full_name || user?.email}</p>
            <p className="text-xs text-gray-400">{isAdmin ? "Administrator" : "Viewer"}</p>
          </div>
          <button onClick={async () => { await logout(); router.push("/login"); }}
            className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-52 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex-shrink-0 overflow-y-auto">
          <nav className="p-3 space-y-4">
            <div>
              <p className="px-3 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">Workspace</p>
              <div className="space-y-0.5">
                {USER_NAV.map(item => <NavItem key={item.href} {...item} />)}
              </div>
            </div>

            {isAdmin && (
              <>
                <div className="border-t border-gray-100 dark:border-gray-700" />
                <div>
                  <p className="px-3 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">Admin</p>
                  <div className="space-y-0.5">
                    <NavItem href="/admin" label="Overview" icon={Settings} />
                    {ADMIN_NAV.map(item => <NavItem key={item.href} {...item} />)}
                  </div>
                </div>
              </>
            )}
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
