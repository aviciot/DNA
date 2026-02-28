"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users, FileText, CheckCircle2, Clock, ArrowUpRight,
  TrendingUp, AlertCircle, Zap, ChevronRight,
} from "lucide-react";

import api from "@/lib/api";

interface Stats {
  total_customers: number;
  active_plans: number;
  pending_tasks: number;
  avg_completion: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.get("/customers/")
      .then(r => r.data)
      .then(data => {
        if (Array.isArray(data)) {
          setStats({
            total_customers: data.length,
            active_plans: data.filter((c: any) => c.status === "active").length,
            pending_tasks: 0,
            avg_completion: 0,
          });
        }
      })
      .catch(() => {});
  }, []);

  const statCards = [
    {
      label: "Total Customers",
      value: stats?.total_customers ?? "—",
      icon: Users,
      color: "blue",
      href: "/customers",
    },
    {
      label: "Active Plans",
      value: stats?.active_plans ?? "—",
      icon: TrendingUp,
      color: "emerald",
      href: "/customers",
    },
    {
      label: "Pending Tasks",
      value: stats?.pending_tasks ?? "—",
      icon: Clock,
      color: "amber",
      href: "/customers",
    },
    {
      label: "Avg. Completion",
      value: stats ? `${stats.avg_completion}%` : "—",
      icon: CheckCircle2,
      color: "violet",
      href: "/customers",
    },
  ];

  const colorMap: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
    violet: "bg-violet-50 text-violet-600",
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-slate-500">ISO certification operations at a glance</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map(card => (
          <Link key={card.label} href={card.href}
            className="bg-white rounded-xl border border-slate-100 p-5 hover:border-slate-200 hover:shadow-sm transition-all group">
            <div className="flex items-start justify-between mb-3">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colorMap[card.color]}`}>
                <card.icon className="w-4.5 h-4.5 w-[18px] h-[18px]" />
              </div>
              <ArrowUpRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 transition-colors" />
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{card.value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{card.label}</p>
          </Link>
        ))}
      </div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick actions */}
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">Quick Actions</h2>
          <div className="space-y-2">
            {[
              { label: "Add New Customer", href: "/customers", icon: Users, desc: "Register and assign ISO plan" },
              { label: "Upload ISO Standard", href: "/admin?section=iso-standards", icon: Zap, desc: "Build templates with AI" },
              { label: "Review Templates", href: "/admin?section=templates", icon: FileText, desc: "Approve pending templates" },
            ].map(action => (
              <Link key={action.label} href={action.href}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors group">
                <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-50 transition-colors">
                  <action.icon className="w-4 h-4 text-slate-500 group-hover:text-blue-600 transition-colors" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800">{action.label}</p>
                  <p className="text-xs text-slate-400 truncate">{action.desc}</p>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-500 transition-colors flex-shrink-0" />
              </Link>
            ))}
          </div>
        </div>

        {/* Platform status */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-100 p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">Platform Status</h2>
          <div className="space-y-3">
            {[
              { label: "AI Service", status: "operational", desc: "Template builder & automation" },
              { label: "Document Engine", status: "operational", desc: "PDF generation & export" },
              { label: "Customer Portal", status: "operational", desc: "Self-service access" },
              { label: "Email Automation", status: "coming_soon", desc: "Question collection via email" },
            ].map(svc => (
              <div key={svc.label} className="flex items-center gap-3 py-2 border-b border-slate-50 last:border-0">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  svc.status === "operational" ? "bg-emerald-400" :
                  svc.status === "degraded" ? "bg-amber-400" : "bg-slate-200"
                }`} />
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-800">{svc.label}</p>
                  <p className="text-xs text-slate-400">{svc.desc}</p>
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  svc.status === "operational" ? "bg-emerald-50 text-emerald-600" :
                  svc.status === "degraded" ? "bg-amber-50 text-amber-600" :
                  "bg-slate-100 text-slate-400"
                }`}>
                  {svc.status === "coming_soon" ? "Soon" : svc.status}
                </span>
              </div>
            ))}
          </div>

          {/* AI highlight */}
          <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-100 flex items-start gap-3">
            <Zap className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-blue-800">AI-Powered Platform</p>
              <p className="text-xs text-blue-600 mt-0.5">
                Upload an ISO PDF → AI builds all templates automatically. Placeholders are deduplicated across documents — fill once, apply everywhere.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
