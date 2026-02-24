"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import Image from "next/image";
import Link from "next/link";
import {
  LayoutDashboard, Users, FileText, Settings, LogOut,
  Shield, Upload, BookOpen, Activity, ChevronRight, Wrench,
} from "lucide-react";
import ISOStandards from "@/components/admin/ISOStandards";
import TemplateLibrary from "@/components/admin/TemplateLibrary";
import TemplateCatalog from "@/components/admin/TemplateCatalog";
import CustomerManagement from "@/components/admin/CustomerManagement";
import SystemHealth from "@/components/admin/SystemHealth";
import AIConfig from "@/components/admin/AIConfig";

type AdminSection = "iso-standards" | "reference-docs" | "templates" | "customers" | "configuration" | "system-health";

const CONTENT_ITEMS: { id: AdminSection; label: string; icon: any; desc: string }[] = [
  { id: "iso-standards",  label: "ISO Standards",    icon: Shield,   desc: "Manage standards & AI build" },
  { id: "reference-docs", label: "Reference Docs",   icon: Upload,   desc: "Upload .docx → build templates" },
  { id: "templates",      label: "Templates",        icon: BookOpen, desc: "Review, approve & edit" },
];

const SYSTEM_ITEMS: { id: AdminSection; label: string; icon: any; desc: string }[] = [
  { id: "customers",      label: "Customers",        icon: Users,    desc: "Manage customer accounts" },
  { id: "configuration",  label: "Configuration",    icon: Wrench,   desc: "LLM providers & AI prompts" },
  { id: "system-health",  label: "System Health",    icon: Activity, desc: "Services & monitoring" },
];

const SECTION_TITLES: Record<AdminSection, string> = {
  "iso-standards":  "ISO Standards",
  "reference-docs": "Reference Documents",
  "templates":      "Template Catalog",
  "customers":      "Customer Management",
  "configuration":  "Configuration",
  "system-health":  "System Health",
};

export default function AdminPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, fetchUser, logout } = useAuthStore();
  const [active, setActive] = useState<AdminSection>("iso-standards");

  useEffect(() => { fetchUser(); }, [fetchUser]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push("/login");
    else if (!isLoading && isAuthenticated && user?.role !== "admin") router.push("/");
  }, [isLoading, isAuthenticated, user, router]);

  if (isLoading || !isAuthenticated || user?.role !== "admin") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  const SidebarItem = ({ id, label, icon: Icon, desc }: { id: AdminSection; label: string; icon: any; desc: string }) => (
    <button
      onClick={() => setActive(id)}
      className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-left transition-all group ${
        active === id
          ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
          : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-white"
      }`}
    >
      <Icon className={`w-4 h-4 flex-shrink-0 ${active === id ? "text-blue-500" : "text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300"}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{label}</p>
        <p className="text-xs text-gray-400 dark:text-gray-500 truncate">{desc}</p>
      </div>
      {active === id && <ChevronRight className="w-3 h-3 text-blue-400 flex-shrink-0" />}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      {/* Top Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        <div className="px-4 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center space-x-2 hover:opacity-80 transition-opacity">
            <Image src="/dna_q_logo.png" alt="DNA" width={36} height={36} className="rounded-lg" />
            <div>
              <p className="text-sm font-bold text-gray-900 dark:text-white leading-tight">DNA Dashboard</p>
              <p className="text-xs text-gray-400">Admin Panel</p>
            </div>
          </Link>

          {/* Main nav */}
          <nav className="hidden md:flex items-center space-x-1">
            {[
              { href: "/", label: "Dashboard", icon: LayoutDashboard },
              { href: "/customers", label: "Customers", icon: Users },
              { href: "/documents", label: "Documents", icon: FileText },
            ].map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </Link>
            ))}
            <span className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium">
              <Settings className="w-4 h-4" />
              <span>Admin</span>
            </span>
          </nav>

          <div className="flex items-center space-x-3">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-gray-900 dark:text-white">{user?.full_name || user?.email}</p>
              <p className="text-xs text-gray-400">Administrator</p>
            </div>
            <button onClick={async () => { await logout(); router.push("/login"); }}
              className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Body: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-56 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex-shrink-0 overflow-y-auto">
          <div className="p-3 space-y-4">
            {/* Content section */}
            <div>
              <p className="px-3 mb-1 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">Content</p>
              <div className="space-y-0.5">
                {CONTENT_ITEMS.map(item => <SidebarItem key={item.id} {...item} />)}
              </div>
            </div>

            <div className="border-t border-gray-100 dark:border-gray-700" />

            {/* System section */}
            <div>
              <p className="px-3 mb-1 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">System</p>
              <div className="space-y-0.5">
                {SYSTEM_ITEMS.map(item => <SidebarItem key={item.id} {...item} />)}
              </div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-7xl mx-auto">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
              {SECTION_TITLES[active]}
            </h2>

            {active === "iso-standards"  && <ISOStandards />}
            {active === "reference-docs" && <TemplateLibrary />}
            {active === "templates"      && <TemplateCatalog />}
            {active === "customers"      && <CustomerManagement />}
            {active === "configuration"  && <AIConfig />}
            {active === "system-health"  && <SystemHealth />}
          </div>
        </main>
      </div>
    </div>
  );
}
