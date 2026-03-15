"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import {
  Shield, BookOpen, Users, Activity, FileText, Sparkles, Mail, Settings2,
  Zap, Cpu, RefreshCw, TrendingUp,
} from "lucide-react";
import ISOStandards from "@/components/admin/ISOStandards";
import TemplateCatalog from "@/components/admin/TemplateCatalog";
import TemplateLibrary from "@/components/admin/TemplateLibrary";
import ISO360Admin from "@/components/admin/ISO360Admin";
import ISO360HealthDashboard from "@/components/admin/ISO360HealthDashboard";
import CustomerManagement from "@/components/admin/CustomerManagement";
import AIConfig from "@/components/admin/AIConfig";
import LLMProvidersConfig from "@/components/admin/LLMProvidersConfig";
import SystemHealth from "@/components/admin/SystemHealth";
import AutomationConfig from "@/components/admin/AutomationConfig";
import PortalConfig from "@/components/admin/PortalConfig";
import SecurityConfig from "@/components/admin/SecurityConfig";

type Section =
  | "iso-standards" | "templates" | "reference-docs" | "iso360" | "iso360-health"
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
      { id: "iso360",         label: "ISO360",         icon: RefreshCw },
      { id: "iso360-health",  label: "Health",          icon: TrendingUp },
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
  "iso360":         "iso-studio",
  "iso360-health":  "iso-studio",
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
  const { user, isLoading } = useAuthStore();
  const rawSection = searchParams.get("section") as Section;
  const validSections: Section[] = ["iso-standards","templates","reference-docs","iso360","iso360-health","customers","ai-providers","template-ai","automation","customer-portal","system-health","security"];
  const [active, setActive] = useState<Section>(
    validSections.includes(rawSection) ? rawSection : "iso-standards"
  );

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
    <div className="flex flex-col min-h-screen bg-slate-50">

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
          {active === "iso360"         && <ISO360Admin />}
          {active === "iso360-health"  && <ISO360HealthDashboard />}
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
  );
}
