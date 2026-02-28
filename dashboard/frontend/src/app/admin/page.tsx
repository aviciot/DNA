"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { Shield, BookOpen, Users, Activity, FileText, Sparkles } from "lucide-react";
import ISOStandards from "@/components/admin/ISOStandards";
import TemplateCatalog from "@/components/admin/TemplateCatalog";
import TemplateLibrary from "@/components/admin/TemplateLibrary";
import CustomerManagement from "@/components/admin/CustomerManagement";
import AIConfig from "@/components/admin/AIConfig";
import SystemHealth from "@/components/admin/SystemHealth";

type Section = "iso-standards" | "templates" | "reference-docs" | "customers" | "configuration" | "system-health";

const TABS: { id: Section; label: string; icon: any; group: "library" | "system" }[] = [
  { id: "iso-standards",  label: "ISO Standards",  icon: Shield,    group: "library" },
  { id: "templates",      label: "Templates",      icon: BookOpen,  group: "library" },
  { id: "reference-docs", label: "Reference Docs", icon: FileText,  group: "library" },
  { id: "customers",      label: "Customers",      icon: Users,     group: "library" },
  { id: "configuration",  label: "AI & Config",    icon: Sparkles,  group: "system" },
  { id: "system-health",  label: "System Health",  icon: Activity,  group: "system" },
];

export default function AdminPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading } = useAuthStore();
  const [active, setActive] = useState<Section>((searchParams.get("section") as Section) || "iso-standards");

  useEffect(() => {
    if (!isLoading && user?.role !== "admin") router.push("/");
  }, [isLoading, user, router]);

  useEffect(() => {
    const s = searchParams.get("section") as Section;
    if (s) setActive(s);
  }, [searchParams]);

  if (isLoading || user?.role !== "admin") return null;

  const navigate = (id: Section) => {
    setActive(id);
    router.replace(`/admin?section=${id}`, { scroll: false });
  };

  const library = TABS.filter(t => t.group === "library");
  const system = TABS.filter(t => t.group === "system");
  const activeTab = TABS.find(t => t.id === active);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Studio top bar */}
      <div className="bg-white border-b border-slate-100 px-6 flex items-center gap-1 h-12 flex-shrink-0">
        {/* Library group */}
        <div className="flex items-center gap-0.5">
          {library.map(tab => (
            <button key={tab.id} onClick={() => navigate(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
                active === tab.id
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
              }`}>
              <tab.icon className={`w-3.5 h-3.5 ${active === tab.id ? "text-blue-600" : "text-slate-400"}`} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-slate-200 mx-2" />

        {/* System group */}
        <div className="flex items-center gap-0.5">
          {system.map(tab => (
            <button key={tab.id} onClick={() => navigate(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
                active === tab.id
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
              }`}>
              <tab.icon className={`w-3.5 h-3.5 ${active === tab.id ? "text-blue-600" : "text-slate-400"}`} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Active indicator line */}
        <div className="flex-1" />
        <span className="text-xs text-slate-400 font-medium">ISO Studio</span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {active === "iso-standards"  && <ISOStandards />}
        {active === "reference-docs" && <TemplateLibrary />}
        {active === "templates"      && <TemplateCatalog />}
        {active === "customers"      && <CustomerManagement />}
        {active === "configuration"  && <AIConfig />}
        {active === "system-health"  && <SystemHealth />}
      </div>
    </div>
  );
}
