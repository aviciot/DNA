"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import Image from "next/image";
import Link from "next/link";
import {
  LayoutDashboard,
  Users,
  FileText,
  Settings,
  LogOut,
  Upload,
  Shield,
  FolderOpen,
  Activity,
} from "lucide-react";
import TemplateLibrary from "@/components/admin/TemplateLibrary";
import TemplateCatalog from "@/components/admin/TemplateCatalog";
import ISOStandards from "@/components/admin/ISOStandards";
import SystemHealth from "@/components/admin/SystemHealth";
import CustomerManagement from "@/components/admin/CustomerManagement";

type AdminTab = "reference-docs" | "catalog" | "iso-standards" | "customers" | "system-health";

export default function AdminPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, fetchUser, logout } = useAuthStore();
  const [activeTab, setActiveTab] = useState<AdminTab>("reference-docs");

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    } else if (!isLoading && isAuthenticated && user?.role !== "admin") {
      // Non-admin users can't access admin page
      router.push("/");
    }
  }, [isLoading, isAuthenticated, user, router]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  if (isLoading || !isAuthenticated || user?.role !== "admin") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const navItems = [
    { name: "Dashboard", icon: LayoutDashboard, href: "/", admin: false },
    { name: "Customers", icon: Users, href: "/customers", admin: false },
    { name: "Documents", icon: FileText, href: "/documents", admin: false },
    { name: "Admin", icon: Settings, href: "/admin", admin: true, active: true },
  ];

  const adminTabs = [
    { id: "reference-docs" as AdminTab, label: "Reference Documents", icon: Upload },
    { id: "catalog" as AdminTab, label: "Template Catalog", icon: FolderOpen },
    { id: "iso-standards" as AdminTab, label: "ISO Standards", icon: Shield },
    { id: "customers" as AdminTab, label: "Customers", icon: Users },
    { id: "system-health" as AdminTab, label: "System Health", icon: Activity },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo and Title */}
            <Link href="/" className="flex items-center space-x-3 cursor-pointer hover:opacity-80 transition-opacity">
              <Image
                src="/dna_q_logo.png"
                alt="DNA Logo"
                width={75}
                height={75}
                className="rounded-lg shadow-md hover:shadow-lg transition-shadow"
              />
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                  DNA Dashboard
                </h1>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  ISO Certification Management
                </p>
              </div>
            </Link>

            {/* User Info and Logout */}
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  {user?.full_name || user?.email}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Administrator
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 min-h-[calc(100vh-4rem)]">
          <nav className="p-4 space-y-2">
            {navItems.map((item) => (
              <a
                key={item.name}
                href={item.href}
                className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                  item.active
                    ? "bg-blue-50 dark:bg-gray-700 text-blue-600 dark:text-blue-400"
                    : "text-gray-700 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-gray-700 hover:text-blue-600 dark:hover:text-blue-400"
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span className="font-medium">{item.name}</span>
              </a>
            ))}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-8">
          <div className="max-w-7xl mx-auto">
            {/* Page Header */}
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
                Admin Configuration
              </h2>
              <p className="mt-1 text-gray-600 dark:text-gray-400">
                Manage templates, ISO standards, and system settings
              </p>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
              <nav className="-mb-px flex space-x-8">
                {adminTabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                      activeTab === tab.id
                        ? "border-blue-500 text-blue-600 dark:text-blue-400"
                        : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600"
                    }`}
                  >
                    <tab.icon className="w-5 h-5" />
                    <span>{tab.label}</span>
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab Content */}
            <div className="mt-6">
              {activeTab === "reference-docs" && <TemplateLibrary />}
              {activeTab === "catalog" && <TemplateCatalog />}
              {activeTab === "iso-standards" && <ISOStandards />}
              {activeTab === "customers" && <CustomerManagement />}
              {activeTab === "system-health" && <SystemHealth />}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
