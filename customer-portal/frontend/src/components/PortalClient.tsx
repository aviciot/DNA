"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, CheckCircle2, MessageSquare, LayoutDashboard, Sun, Moon, Crown } from "lucide-react";
import ProgressPanel from "./ProgressPanel";
import QuestionList from "./QuestionList";
import ChatWidget from "./ChatWidget";
import ISO360Panel from "./ISO360Panel";

export interface Question {
  id: string;
  title: string;
  description: string | null;
  task_type: string;
  status: string;
  priority: string;
  placeholder_key: string | null;
  answer: string | null;
  requires_evidence: boolean;
  evidence_uploaded: boolean;
  evidence_description: string | null;
  due_date: string | null;
}

interface Plan {
  id: string;
  plan_name: string;
  iso_code: string;
  iso_name: string;
  target_completion_date: string | null;
  total: number;
  completed: number;
}

interface Me {
  customer_name: string;
  contact_person: string;
  contact_email: string;
  iso_code: string;
  iso_name: string;
  plan_name: string;
  target_completion_date: string | null;
}

interface Progress {
  total: number;
  completed: number;
  pending: number;
  evidence_pending: number;
  percentage: number;
}

interface Props { me: Me; progress: Progress; questions: Question[]; plans: Plan[]; iso360Plans: string[] }
type Tab = "overview" | "tasks" | "iso360";

const DARK_VARS = {
  "--bg": "#0a0a0f", "--surface": "#111118", "--surface2": "#16161f",
  "--border": "rgba(255,255,255,0.07)", "--text": "#e2e2ea", "--muted": "#5a5a72",
  "--topbar-bg": "rgba(10,10,15,0.85)",
};
const LIGHT_VARS = {
  "--bg": "#f5f5f7", "--surface": "#ffffff", "--surface2": "#f0f0f5",
  "--border": "rgba(0,0,0,0.08)", "--text": "#1a1a2e", "--muted": "#8e8ea0",
  "--topbar-bg": "rgba(245,245,247,0.85)",
};

export default function PortalClient({ me, progress, questions, plans, iso360Plans }: Props) {
  const [tab, setTab] = useState<Tab>("overview");
  const [activePlanId, setActivePlanId] = useState<string | null>(plans[0]?.id ?? null);
  const [planProgress, setPlanProgress] = useState<Progress>(progress);
  const [planQuestions, setPlanQuestions] = useState<Question[]>(questions);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [typedText, setTypedText] = useState("");
  const fullText = "Ask AI Assistant";

  useEffect(() => {
    let i = 0;
    let typing = true;
    let timeout: ReturnType<typeof setTimeout>;

    function tick() {
      if (typing) {
        i++;
        setTypedText(fullText.slice(0, i));
        if (i < fullText.length) {
          timeout = setTimeout(tick, 80);
        } else {
          timeout = setTimeout(() => { typing = false; timeout = setTimeout(tick, 100); }, 5000);
        }
      } else {
        i--;
        setTypedText(fullText.slice(0, i));
        if (i > 0) {
          timeout = setTimeout(tick, 40);
        } else {
          typing = true;
          timeout = setTimeout(tick, 400);
        }
      }
    }
    timeout = setTimeout(tick, 800);
    return () => clearTimeout(timeout);
  }, []);

  useEffect(() => {
    const vars = dark ? DARK_VARS : LIGHT_VARS;
    Object.entries(vars).forEach(([k, v]) => document.documentElement.style.setProperty(k, v));
  }, [dark]);

  const activePlan = plans.find((p) => p.id === activePlanId) ?? plans[0];
  const pending = planQuestions.filter((q) => q.status === "pending").length;
  const completed = planQuestions.filter((q) => ["completed", "answered"].includes(q.status)).length;
  const pct = planQuestions.length ? Math.round((completed / planQuestions.length) * 100) : 0;

  async function switchPlan(planId: string) {
    if (planId === activePlanId) return;
    setLoadingPlan(true); setActivePlanId(planId);
    try {
      const [prog, qs] = await Promise.all([
        fetch(`/api/portal/progress?plan_id=${planId}`).then((r) => r.json()),
        fetch(`/api/portal/questions?plan_id=${planId}`).then((r) => r.json()),
      ]);
      setPlanProgress(prog); setPlanQuestions(qs);
    } finally { setLoadingPlan(false); }
  }

  function onAnswered(taskId: string, value: string) {
    setPlanQuestions((prev) => prev.map((q) => q.id === taskId ? { ...q, answer: value, status: "answered" } : q));
  }
  function onUploaded(taskId: string) {
    setPlanQuestions((prev) => prev.map((q) => q.id === taskId ? { ...q, evidence_uploaded: true, status: "answered" } : q));
  }

  const hasISO360 = activePlan ? iso360Plans.includes(activePlan.id) : false;

  const navItems: { id: Tab; label: string; icon: React.ReactNode; badge?: number; premium?: boolean }[] = [
    { id: "overview", label: "Overview", icon: <LayoutDashboard size={16} /> },
    { id: "tasks", label: "Tasks", icon: <CheckCircle2 size={16} />, badge: pending || undefined },
    ...(hasISO360 ? [{ id: "iso360" as Tab, label: "ISO360", icon: <Crown size={16} />, premium: true }] : []),
  ];

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* Sidebar — hidden on mobile */}
      <aside className="hidden md:flex w-60 flex-shrink-0 flex-col border-r" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
        {/* Logo */}
        <div className="px-5 py-5 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
              <Shield size={16} className="text-white" />
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ color: "var(--text)" }}>DNA Compliance</div>
              <div className="text-xs" style={{ color: "var(--muted)" }}>Customer Portal</div>
            </div>
          </div>
        </div>

        {/* Customer */}
        <div className="px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
          <div className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--muted)" }}>Account</div>
          <div className="text-sm font-semibold" style={{ color: "var(--text)" }}>{me.customer_name}</div>
          <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{me.contact_person}</div>
        </div>

        {/* Plans */}
        {plans.length > 0 && (
          <div className="px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
            <div className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--muted)" }}>ISO Plans</div>
            <div className="space-y-1">
              {plans.map((plan) => {
                const planPct = plan.total ? Math.round((plan.completed / plan.total) * 100) : 0;
                const isActive = plan.id === activePlanId;
                return (
                  <button key={plan.id} onClick={() => switchPlan(plan.id)}
                    className="w-full text-left px-3 py-2.5 rounded-lg transition-all"
                    style={{ background: isActive ? "rgba(99,102,241,0.15)" : "transparent", border: isActive ? "1px solid rgba(99,102,241,0.3)" : "1px solid transparent" }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold" style={{ color: isActive ? "#818cf8" : "var(--text)" }}>{plan.iso_code}</span>
                      <span className="text-xs" style={{ color: "var(--muted)" }}>{planPct}%</span>
                    </div>
                    <div className="h-1 rounded-full" style={{ background: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)" }}>
                      <div className="h-1 rounded-full transition-all" style={{ width: `${planPct}%`, background: isActive ? "#6366f1" : "var(--muted)" }} />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="px-3 py-3 flex-1">
          {navItems.map((item) => {
            const isActive = tab === item.id;
            const isPremium = item.premium;
            return (
              <button key={item.id} onClick={() => setTab(item.id)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg mb-0.5 transition-all text-sm"
                style={{
                  background: isActive
                    ? isPremium ? "rgba(245,158,11,0.14)" : (dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)")
                    : "transparent",
                  color: isActive ? (isPremium ? "#f59e0b" : "var(--text)") : "var(--muted)",
                  border: isActive && isPremium ? "1px solid rgba(245,158,11,0.3)" : "1px solid transparent",
                }}>
                <div className="flex items-center gap-2.5">
                  {item.icon}{item.label}
                  {isPremium && <span className="text-xs px-1.5 py-0.5 rounded-full font-bold" style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b", fontSize: "10px" }}>PRO</span>}
                </div>
                {item.badge ? <span className="text-xs px-1.5 py-0.5 rounded-full font-medium" style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8" }}>{item.badge}</span> : null}
              </button>
            );
          })}
          <button onClick={() => setChatOpen(true)}
            className="relative w-full overflow-hidden mt-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-white flex items-center gap-2.5 transition-transform hover:scale-[1.02] active:scale-[0.98]"
            style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4)", backgroundSize: "200% 200%", animation: "aiGradient 3s ease infinite", boxShadow: "0 4px 15px rgba(99,102,241,0.4)" }}>
            <span className="absolute inset-0 rounded-xl" style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)", animation: "aiShimmer 2s ease infinite" }} />
            <MessageSquare size={15} />
            <span className="flex-1 text-left">{typedText}<span style={{ animation: "aiCursor 0.8s step-end infinite" }}>|</span></span>
            <span className="ml-auto flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
              <span className="text-xs font-normal opacity-80">Live</span>
            </span>
          </button>
          <style>{`
            @keyframes aiGradient { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
            @keyframes aiShimmer { 0%{transform:translateX(-100%)} 100%{transform:translateX(200%)} }
            @keyframes aiCursor { 0%,100%{opacity:1} 50%{opacity:0} }
          `}</style>
        </nav>

        {/* Bottom: theme toggle + consultant */}
        <div className="border-t" style={{ borderColor: "var(--border)" }}>
          {/* Theme toggle */}
          <div className="px-5 py-3 flex items-center justify-between border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-xs" style={{ color: "var(--muted)" }}>{dark ? "Dark" : "Light"} mode</span>
            <button onClick={() => setDark(!dark)}
              className="relative w-10 h-5 rounded-full transition-colors flex items-center"
              style={{ background: dark ? "rgba(99,102,241,0.4)" : "rgba(0,0,0,0.15)" }}>
              <span className="absolute w-4 h-4 rounded-full flex items-center justify-center transition-all"
                style={{ left: dark ? "calc(100% - 18px)" : "2px", background: dark ? "#818cf8" : "#fff", boxShadow: "0 1px 3px rgba(0,0,0,0.3)" }}>
                {dark ? <Moon size={9} style={{ color: "#1a1a2e" }} /> : <Sun size={9} style={{ color: "#f59e0b" }} />}
              </span>
            </button>
          </div>

          {/* Consultant */}
          {me.contact_person && (
            <div className="px-5 py-4">
              <div className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: "var(--muted)" }}>Your Consultant</div>
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8" }}>
                  {me.contact_person[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-medium truncate" style={{ color: "var(--text)" }}>{me.contact_person}</div>
                  {me.contact_email && (
                    <a href={`mailto:${me.contact_email}`} className="text-xs truncate block hover:underline" style={{ color: "var(--muted)" }}>{me.contact_email}</a>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
        <div className="sticky top-0 z-10 px-4 md:px-8 py-3 md:py-4 flex items-center justify-between border-b"
          style={{ background: "var(--topbar-bg)", backdropFilter: "blur(12px)", borderColor: "var(--border)" }}>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm md:text-base font-semibold truncate" style={{ color: "var(--text)" }}>
              {activePlan?.iso_code} — {activePlan?.plan_name || activePlan?.iso_name}
            </h1>
            <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
              {completed} of {planQuestions.length} tasks complete
              {activePlan?.target_completion_date && ` · Target ${new Date(activePlan.target_completion_date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`}
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full ml-3 flex-shrink-0" style={{ background: "var(--surface2)", border: "1px solid var(--border)" }}>
            <div className="w-16 md:w-24 h-1.5 rounded-full" style={{ background: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)" }}>
              <div className="h-1.5 rounded-full transition-all" style={{ width: `${pct}%`, background: "linear-gradient(90deg, #6366f1, #10b981)" }} />
            </div>
            <span className="text-xs font-semibold" style={{ color: "var(--text)" }}>{pct}%</span>
          </div>
        </div>

        <div className="px-4 md:px-8 py-4 md:py-6">
          <AnimatePresence mode="wait">
            {loadingPlan ? (
              <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center justify-center py-32">
                <div className="w-6 h-6 rounded-full border-2 animate-spin" style={{ borderColor: "rgba(99,102,241,0.3)", borderTopColor: "#6366f1" }} />
              </motion.div>
            ) : tab === "overview" ? (
              <motion.div key="overview" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
                <ProgressPanel me={me} progress={{ ...planProgress, percentage: pct, completed }} dark={dark} />
              </motion.div>
            ) : tab === "iso360" ? (
              <motion.div key="iso360" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
                <ISO360Panel planId={activePlan?.id ?? ""} dark={dark} />
              </motion.div>
            ) : (
              <motion.div key="tasks" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
                <QuestionList questions={planQuestions} onAnswered={onAnswered} onUploaded={onUploaded} dark={dark} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      <ChatWidget customerName={me.customer_name} isoCode={activePlan?.iso_code ?? me.iso_code} isOpen={chatOpen} onClose={() => setChatOpen(false)} dark={dark} />

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-20 flex items-center border-t"
        style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
        {navItems.map((item) => {
          const isActive = tab === item.id;
          const isPremium = item.premium;
          return (
            <button key={item.id} onClick={() => setTab(item.id)}
              className="flex-1 flex flex-col items-center gap-1 py-3 text-xs relative"
              style={{ color: isActive ? (isPremium ? "#f59e0b" : "#818cf8") : "var(--muted)" }}>
              {item.icon}
              <span>{item.label}</span>
              {item.badge ? <span className="absolute top-2 right-1/4 w-4 h-4 rounded-full text-xs flex items-center justify-center font-medium" style={{ background: "rgba(99,102,241,0.9)", color: "#fff", fontSize: "10px" }}>{item.badge}</span> : null}
            </button>
          );
        })}
        <button onClick={() => setChatOpen(true)}
          className="flex-1 flex flex-col items-center gap-1 py-3 text-xs"
          style={{ color: "var(--muted)" }}>
          <MessageSquare size={16} />
          <span>AI Chat</span>
        </button>
        <button onClick={() => setDark(!dark)}
          className="flex-1 flex flex-col items-center gap-1 py-3 text-xs"
          style={{ color: "var(--muted)" }}>
          {dark ? <Sun size={16} /> : <Moon size={16} />}
          <span>{dark ? "Light" : "Dark"}</span>
        </button>
      </nav>
    </div>
  );
}
