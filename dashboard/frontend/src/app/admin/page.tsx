"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/authStore";
import {
  Shield, BookOpen, Users, Activity, FileText, Sparkles, Mail, Settings2,
  Zap, LogOut, ArrowLeft, Cpu,
} from "lucide-react";
import ISOStandards from "@/components/admin/ISOStandards";
import TemplateCatalog from "@/components/admin/TemplateCatalog";
import TemplateLibrary from "@/components/admin/TemplateLibrary";
import CustomerManagement from "@/components/admin/CustomerManagement";
import AIConfig from "@/components/admin/AIConfig";
import LLMProvidersConfig from "@/components/admin/LLMProvidersConfig";
import SystemHealth from "@/components/admin/SystemHealth";
import AutomationConfig from "@/components/admin/AutomationConfig";
import PortalConfig from "@/components/admin/PortalConfig";
import SecurityConfig from "@/components/admin/SecurityConfig";
import NotificationCenter from "@/components/notifications/NotificationCenter";

type Section =
  | "iso-standards" | "templates" | "reference-docs"
  | "customers"
  | "ai-providers" | "template-ai" | "automation" | "customer-portal"
  | "system-health"
  | "security";

interface TabDef { id: Section; label: string; icon: any }
interface CategoryDef { id: string; label: string; icon: any; tabs: TabDef[] }

const CATEGORIES: CategoryDef[] = [
  {
    id: "iso-studio",
    label: "ISO Studio",
    icon: Shield,
    tabs: [
      { id: "iso-standards",  label: "ISO Standards",  icon: Shield },
      { id: "templates",      label: "Templates",      icon: BookOpen },
      { id: "reference-docs", label: "Reference Docs", icon: FileText },
    ],
  },
  {
    id: "customers",
    label: "Customers",
    icon: Users,
    tabs: [
      { id: "customers", label: "Customers", icon: Users },
    ],
  },
  {
    id: "configuration",
    label: "Configuration",
    icon: Settings2,
    tabs: [
      { id: "ai-providers",    label: "AI Providers",    icon: Cpu },
      { id: "template-ai",     label: "Template AI",     icon: Sparkles },
      { id: "automation",      label: "Automation",      icon: Mail },
      { id: "customer-portal", label: "Customer Portal", icon: Zap },
      { id: "security",        label: "Security",        icon: Shield },
    ],
  },
  {
    id: "system-health",
    label: "System Health",
    icon: Activity,
    tabs: [
      { id: "system-health", label: "System Health", icon: Activity },
    ],
  },
];

// Map each section to its parent category
const SECTION_TO_CATEGORY: Record<Section, string> = {
  "iso-standards":  "iso-studio",
  "templates":      "iso-studio",
  "reference-docs": "iso-studio",
  "customers":      "customers",
  "ai-providers":      "configuration",
  "template-ai":       "configuration",
  "automation":        "configuration",
  "customer-portal":   "configuration",
  "security":           "configuration",
  "system-health":  "system-health",
};

export default function AdminPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading, logout } = useAuthStore();
  // Default to iso-standards; guard against stale "configuration" URL param from old bookmarks
  const rawSection = searchParams.get("section") as Section;
  const validSections: Section[] = ["iso-standards","templates","reference-docs","customers","ai-providers","template-ai","automation","customer-portal","system-health","security"];
  const [active, setActive] = useState<Section>(
    validSections.includes(rawSection) ? rawSection : "iso-standards"
  );

  const initials = (user?.full_name || user?.email || "U")
    .split(" ").map((w: string) => w[0]).join("").toUpperCase().slice(0, 2);

  useEffect(() => {
    if (!isLoading && user?.role !== "admin") router.push("/");
  }, [isLoading, user, router]);

  useEffect(() => {
    const s = searchParams.get("section") as Section;
    if (s && validSections.includes(s)) setActive(s);
  }, [searchParams]);

  if (isLoading || user?.role !== "admin") return null;

  const navigate = (id: Section) => {
    setActive(id);
    router.replace(`/admin?section=${id}`, { scroll: false });
  };

  const activeCategoryId = SECTION_TO_CATEGORY[active];
  const activeCategory = CATEGORIES.find(c => c.id === activeCategoryId) ?? CATEGORIES[0];

  return (
    <div className="flex min-h-screen bg-slate-50">

      {/* Left sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-slate-100 flex flex-col fixed h-full z-20">
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

        {/* Back to app */}
        <div className="px-3 pt-3 pb-1">
          <Link
            href="/"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to app
          </Link>
        </div>

        {/* Category nav */}
        <nav className="flex-1 px-3 py-2 space-y-0.5">
          <p className="px-3 mb-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Admin</p>
          {CATEGORIES.map(cat => {
            const isActive = cat.id === activeCategoryId;
            const CatIcon = cat.icon;
            return (
              <button
                key={cat.id}
                onClick={() => navigate(cat.tabs[0].id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-left transition-all ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-500 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <CatIcon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-blue-600" : "text-slate-400"}`} />
                {cat.label}
              </button>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-slate-100">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors group">
            <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
              <span className="text-[10px] font-bold text-blue-700">{initials}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate leading-tight">{user?.full_name || user?.email}</p>
              <p className="text-[10px] text-slate-400 leading-tight">Administrator</p>
            </div>
            <button
              onClick={async () => { await logout(); router.push("/login"); }}
              className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main area — offset by fixed sidebar */}
      <div className="flex-1 flex flex-col min-w-0 ml-56">

        {/* Sub-tab bar — only shown when category has >1 tab */}
        {activeCategory?.tabs && activeCategory.tabs.length > 1 && (
          <div className="bg-white border-b border-slate-100 px-6 flex items-center gap-1 h-11 flex-shrink-0">
            {activeCategory.tabs.map(tab => {
              const TabIcon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => navigate(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    active === tab.id
                      ? "bg-blue-50 text-blue-700"
                      : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                  }`}
                >
                  <TabIcon className={`w-3.5 h-3.5 ${active === tab.id ? "text-blue-600" : "text-slate-400"}`} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {active === "iso-standards"  && <ISOStandards />}
          {active === "reference-docs" && <TemplateLibrary />}
          {active === "templates"      && <TemplateCatalog />}
          {active === "customers"      && <CustomerManagement />}
          {active === "ai-providers"   && <LLMProvidersConfig />}
          {active === "template-ai"    && <AIConfig />}
          {active === "automation"     && (
            <div className="max-w-2xl">
              <AutomationConfig />
            </div>
          )}
          {active === "customer-portal" && <PortalConfig />}
          {active === "security"        && <SecurityConfig />}
          {active === "system-health"  && <SystemHealth />}
        </div>
      </div>
    </div>
  );
}
