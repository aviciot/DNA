"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { Shield, BookOpen, Wrench, Activity, Settings, ChevronRight } from "lucide-react";
import ISOStandards from "@/components/admin/ISOStandards";
import TemplateCatalog from "@/components/admin/TemplateCatalog";
import TemplateLibrary from "@/components/admin/TemplateLibrary";
import CustomerManagement from "@/components/admin/CustomerManagement";
import AIConfig from "@/components/admin/AIConfig";
import SystemHealth from "@/components/admin/SystemHealth";

type Section = "overview" | "iso-standards" | "templates" | "reference-docs" | "customers" | "configuration" | "system-health";

const SECTIONS: { id: Section; label: string; icon: any; group: "content" | "system" }[] = [
  { id: "iso-standards",  label: "ISO Standards",  icon: Shield,   group: "content" },
  { id: "reference-docs", label: "Reference Docs", icon: BookOpen, group: "content" },
  { id: "templates",      label: "Templates",      icon: BookOpen, group: "content" },
  { id: "customers",      label: "Customers",      icon: Settings, group: "system" },
  { id: "configuration",  label: "Configuration",  icon: Wrench,   group: "system" },
  { id: "system-health",  label: "System Health",  icon: Activity, group: "system" },
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

  const content = SECTIONS.filter(s => s.group === "content");
  const system = SECTIONS.filter(s => s.group === "system");

  const SideItem = ({ id, label, icon: Icon }: { id: Section; label: string; icon: any }) => (
    <button onClick={() => navigate(id)}
      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm text-left transition-colors ${
        active === id
          ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium"
          : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
      }`}>
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4" />
        <span>{label}</span>
      </div>
      {active === id && <ChevronRight className="w-3 h-3" />}
    </button>
  );

  return (
    <div className="flex h-full">
      {/* Admin sub-sidebar */}
      <aside className="w-48 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex-shrink-0 p-3 space-y-4">
        <div>
          <p className="px-3 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">Content</p>
          <div className="space-y-0.5">
            {content.map(s => <SideItem key={s.id} {...s} />)}
          </div>
        </div>
        <div className="border-t border-gray-100 dark:border-gray-700" />
        <div>
          <p className="px-3 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">System</p>
          <div className="space-y-0.5">
            {system.map(s => <SideItem key={s.id} {...s} />)}
          </div>
        </div>
      </aside>

      {/* Section content */}
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
