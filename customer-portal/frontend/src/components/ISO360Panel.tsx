"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Crown, Calendar, CheckCircle2, AlertTriangle, Clock,
  ChevronRight, ChevronDown, X, Upload, User, Sparkles,
  Shield, RefreshCw, FileText,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface Step { order: number; instruction: string }
interface EvidenceField { field_name: string; field_type: string; required: boolean }

interface Activity {
  id: string;
  placeholder_key: string;
  title: string;
  type: string;
  update_frequency: string;
  next_due_date: string | null;
  last_completed_at: string | null;
  urgency: "overdue" | "due_soon" | "upcoming" | "completed";
  steps: Step[];
  evidence_fields: EvidenceField[];
  responsible_role: string | null;
}

interface ProfileEntry { key: string; value: string; label: string | null }

interface ISO360Data {
  enabled: boolean;
  adjustment_pass_done: boolean;
  activities: Activity[];
  profile: ProfileEntry[];
  stats: { total: number; done: number; overdue: number; due_soon: number; score: number };
}

interface Props { planId: string; dark: boolean }

// ── Config ───────────────────────────────────────────────────────────────────

const URGENCY = {
  overdue:   { color: "#ef4444", bg: "rgba(239,68,68,0.12)",  glow: "rgba(239,68,68,0.25)",  label: "Overdue",   Icon: AlertTriangle },
  due_soon:  { color: "#f59e0b", bg: "rgba(245,158,11,0.12)", glow: "rgba(245,158,11,0.25)", label: "Due Soon",  Icon: Clock },
  upcoming:  { color: "#6366f1", bg: "rgba(99,102,241,0.12)", glow: "rgba(99,102,241,0.2)",  label: "Upcoming",  Icon: Calendar },
  completed: { color: "#10b981", bg: "rgba(16,185,129,0.12)", glow: "rgba(16,185,129,0.2)",  label: "Completed", Icon: CheckCircle2 },
} as const;

const FREQ_LABEL: Record<string, string> = {
  monthly: "Monthly", quarterly: "Quarterly", yearly: "Annual", event_based: "Event-based",
};

const KYC_LABELS: Record<string, string> = {
  compliance_owner_and_team:                  "Compliance Owner & Team",
  staff_size_locations_and_access_model:      "Staff & Locations",
  systems_and_business_tools_used:            "Systems & Tools",
  security_tools_and_controls_in_use:         "Security Controls",
  existing_certifications_and_frameworks:     "Existing Certifications",
  existing_policies_and_documents:            "Existing Policies",
  documentation_management_practices:         "Document Management",
  industry_regulatory_and_customer_requirements: "Regulatory Requirements",
  current_risk_and_security_concerns:         "Security Concerns",
  current_information_security_processes:     "Security Processes",
};

// ── Score gauge ──────────────────────────────────────────────────────────────

function ScoreGauge({ score, dark }: { score: number; dark: boolean }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const scoreColor = score >= 70 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative flex flex-col items-center justify-center gap-1">
      <div className="relative w-36 h-36">
        <svg className="absolute inset-0" width="144" height="144" viewBox="0 0 144 144"
          style={{ transform: "rotate(-90deg)" }}>
          <circle cx="72" cy="72" r={r} fill="none" strokeWidth="10"
            stroke={dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.07)"} />
          <motion.circle cx="72" cy="72" r={r} fill="none" strokeWidth="10"
            stroke={`url(#scoreGrad-${dark ? "d" : "l"})`} strokeLinecap="round"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: circ - (score / 100) * circ }}
            transition={{ duration: 1.4, ease: "easeOut", delay: 0.2 }}
          />
          <defs>
            <linearGradient id={`scoreGrad-${dark ? "d" : "l"}`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor={scoreColor} />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.div className="text-3xl font-bold tabular-nums"
            style={{ color: "var(--text)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
            {score}%
          </motion.div>
          <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>Compliance</div>
        </div>
      </div>
    </div>
  );
}

// ── Activity card ─────────────────────────────────────────────────────────────

function ActivityCard({ a, onSelect, selected }: { a: Activity; onSelect: () => void; selected: boolean }) {
  const u = URGENCY[a.urgency];
  const { Icon } = u;

  return (
    <motion.button
      layout
      onClick={onSelect}
      whileHover={{ scale: 1.008 }}
      whileTap={{ scale: 0.995 }}
      className="w-full text-left rounded-2xl overflow-hidden transition-shadow"
      style={{
        background: "var(--surface)",
        border: `1px solid ${selected ? u.color + "60" : "var(--border)"}`,
        boxShadow: selected ? `0 0 0 2px ${u.glow}, 0 4px 20px ${u.glow}` : "0 1px 4px rgba(0,0,0,0.08)",
      }}
    >
      <div className="flex">
        {/* Urgency stripe */}
        <div className="w-1 flex-shrink-0 rounded-l-2xl" style={{ background: u.color }} />

        <div className="flex-1 px-4 py-4">
          {/* Badges row */}
          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ background: "var(--surface2)", color: "var(--muted)", border: "1px solid var(--border)" }}>
              {FREQ_LABEL[a.update_frequency] ?? a.update_frequency}
            </span>
            {a.urgency !== "upcoming" && (
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold flex items-center gap-1"
                style={{ background: u.bg, color: u.color }}>
                <Icon size={10} />{u.label}
              </span>
            )}
          </div>

          {/* Title */}
          <p className="text-sm font-semibold leading-snug" style={{ color: "var(--text)" }}>{a.title}</p>

          {/* Due date / meta */}
          <div className="flex items-center justify-between mt-2.5">
            <div className="flex items-center gap-1.5">
              {a.next_due_date ? (
                <span className="text-xs flex items-center gap-1" style={{ color: "var(--muted)" }}>
                  <Calendar size={11} />
                  {a.urgency === "completed" ? "Done" : "Due"}{" "}
                  {new Date(a.next_due_date + "T00:00:00").toLocaleDateString("en-GB", {
                    day: "numeric", month: "short", year: "numeric",
                  })}
                </span>
              ) : (
                <span className="text-xs" style={{ color: "var(--muted)" }}>Event-based</span>
              )}
              {a.responsible_role && (
                <span className="text-xs flex items-center gap-1" style={{ color: "var(--muted)" }}>
                  · <User size={10} /> {a.responsible_role}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs" style={{ color: "var(--muted)" }}>{a.steps.length} steps</span>
              <ChevronRight size={13} style={{ color: "var(--muted)" }} />
            </div>
          </div>
        </div>
      </div>
    </motion.button>
  );
}

// ── Activity detail panel / sheet ─────────────────────────────────────────────

function ActivityDetail({ activity: a, dark, onClose, isMobile }:
  { activity: Activity; dark: boolean; onClose: () => void; isMobile: boolean }) {
  const u = URGENCY[a.urgency];

  const slideVariant = isMobile
    ? { initial: { y: "100%" }, animate: { y: 0 }, exit: { y: "100%" } }
    : { initial: { x: "100%" }, animate: { x: 0 }, exit: { x: "100%" } };

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(6px)" }}
        onClick={onClose}
      />

      {/* Panel */}
      <motion.div
        {...slideVariant}
        transition={{ type: "spring", damping: 30, stiffness: 280 }}
        className="fixed z-50 overflow-y-auto"
        style={{
          background: "var(--surface)",
          borderTop: isMobile ? `3px solid ${u.color}` : "none",
          borderLeft: !isMobile ? `3px solid ${u.color}` : "none",
          boxShadow: "-6px 0 40px rgba(0,0,0,0.35)",
          // Mobile: bottom sheet
          ...(isMobile ? {
            bottom: 0, left: 0, right: 0,
            borderRadius: "20px 20px 0 0",
            maxHeight: "92dvh",
          } : {
            // Desktop: right panel
            top: 0, right: 0, bottom: 0,
            width: "min(480px, 95vw)",
          }),
        }}
      >
        {/* Drag handle (mobile only) */}
        {isMobile && (
          <div className="flex justify-center pt-3 pb-1">
            <div className="w-10 h-1 rounded-full" style={{ background: "var(--border)" }} />
          </div>
        )}

        {/* Header */}
        <div className="sticky top-0 px-5 pt-4 pb-4 border-b flex items-start gap-3"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-xs px-2.5 py-1 rounded-full font-semibold flex items-center gap-1.5"
                style={{ background: u.bg, color: u.color }}>
                <u.Icon size={11} />{u.label}
              </span>
              <span className="text-xs px-2.5 py-1 rounded-full font-medium"
                style={{ background: "var(--surface2)", color: "var(--muted)", border: "1px solid var(--border)" }}>
                {FREQ_LABEL[a.update_frequency] ?? a.update_frequency}
              </span>
            </div>
            <h2 className="text-base font-bold leading-snug" style={{ color: "var(--text)" }}>{a.title}</h2>
            {a.next_due_date && (
              <p className="text-xs mt-1.5 flex items-center gap-1" style={{ color: "var(--muted)" }}>
                <Calendar size={11} />
                {a.urgency === "completed" ? "Completed" : "Due"}{" "}
                {new Date(a.next_due_date + "T00:00:00").toLocaleDateString("en-GB", {
                  day: "numeric", month: "short", year: "numeric",
                })}
              </p>
            )}
          </div>
          <button onClick={onClose}
            className="rounded-full p-2 flex-shrink-0 transition-colors"
            style={{ background: "var(--surface2)", color: "var(--muted)" }}>
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5 space-y-7 pb-16">

          {/* Responsible role */}
          {a.responsible_role && (
            <div className="flex items-center gap-2.5 text-sm px-3 py-2.5 rounded-xl"
              style={{ background: "var(--surface2)", border: "1px solid var(--border)" }}>
              <User size={14} style={{ color: u.color }} />
              <span style={{ color: "var(--muted)" }}>Responsible: </span>
              <span className="font-medium" style={{ color: "var(--text)" }}>{a.responsible_role}</span>
            </div>
          )}

          {/* Steps */}
          {a.steps.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: "var(--muted)" }}>
                Steps to Complete
              </h3>
              <div className="space-y-4">
                {a.steps.map((step, i) => (
                  <div key={i} className="flex gap-3.5">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold mt-0.5"
                      style={{ background: u.bg, color: u.color, border: `1px solid ${u.color}40` }}>
                      {i + 1}
                    </div>
                    <p className="text-sm leading-relaxed flex-1 pt-0.5" style={{ color: "var(--text)" }}>
                      {step.instruction}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence fields */}
          {a.evidence_fields.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: "var(--muted)" }}>
                Evidence Required
              </h3>
              <div className="space-y-2">
                {a.evidence_fields.map((ef, i) => (
                  <div key={i} className="flex items-center justify-between px-4 py-3 rounded-xl"
                    style={{ background: dark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.03)", border: "1px solid var(--border)" }}>
                    <div className="flex items-center gap-2.5 flex-1 min-w-0">
                      <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: ef.required ? "#f59e0b" : "var(--muted)" }} />
                      <span className="text-sm capitalize" style={{ color: "var(--text)" }}>
                        {ef.field_name.replace(/_/g, " ")}
                      </span>
                      {ef.required && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full"
                          style={{ background: "rgba(245,158,11,0.1)", color: "#f59e0b" }}>
                          Required
                        </span>
                      )}
                    </div>
                    {ef.field_type === "file" && (
                      <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ml-3 flex-shrink-0"
                        style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)" }}>
                        <Upload size={11} />Upload
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Consultant note */}
          <div className="rounded-xl p-4 flex gap-3"
            style={{ background: dark ? "rgba(99,102,241,0.06)" : "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}>
            <Shield size={16} className="flex-shrink-0 mt-0.5" style={{ color: "#818cf8" }} />
            <p className="text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
              Once you have completed this activity and gathered the evidence, contact your compliance consultant to record it in your compliance log.
            </p>
          </div>
        </div>
      </motion.div>
    </>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

type SubTab = "upcoming" | "all" | "done";

export default function ISO360Panel({ planId, dark }: Props) {
  const [data, setData] = useState<ISO360Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [subTab, setSubTab] = useState<SubTab>("upcoming");
  const [selected, setSelected] = useState<Activity | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`/api/portal/iso360?plan_id=${planId}`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [planId]);

  useEffect(() => { load(); }, [load]);

  // ── Loading ──
  if (loading) return (
    <div className="flex flex-col items-center justify-center py-32 gap-3">
      <div className="w-8 h-8 rounded-full border-2 animate-spin"
        style={{ borderColor: "rgba(245,158,11,0.2)", borderTopColor: "#f59e0b" }} />
      <p className="text-sm" style={{ color: "var(--muted)" }}>Loading compliance hub…</p>
    </div>
  );

  // ── Not enabled ──
  if (!data?.enabled) return (
    <div className="flex flex-col items-center justify-center py-24 text-center px-6">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
        style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.25)" }}>
        <Crown size={26} style={{ color: "#f59e0b" }} />
      </div>
      <h3 className="text-base font-bold mb-2" style={{ color: "var(--text)" }}>ISO360 Not Active</h3>
      <p className="text-sm max-w-xs" style={{ color: "var(--muted)" }}>
        ISO360 premium compliance management is not enabled for this plan. Contact your consultant to activate it.
      </p>
    </div>
  );

  // ── Personalisation in progress ──
  if (!data.adjustment_pass_done) return (
    <div className="flex flex-col items-center justify-center py-24 text-center px-6">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 relative"
        style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.25)" }}>
        <Crown size={26} style={{ color: "#f59e0b" }} className="opacity-60" />
        <motion.div className="absolute inset-0 rounded-2xl"
          animate={{ opacity: [0.3, 0.7, 0.3] }} transition={{ duration: 2, repeat: Infinity }}>
          <div className="w-full h-full rounded-2xl" style={{ background: "rgba(245,158,11,0.15)" }} />
        </motion.div>
      </div>
      <h3 className="text-base font-bold mb-2" style={{ color: "var(--text)" }}>Personalising Your Plan</h3>
      <p className="text-sm max-w-xs mb-5" style={{ color: "var(--muted)" }}>
        Our AI is tailoring your compliance schedule based on your answers. This usually takes just a few minutes.
      </p>
      <button onClick={load}
        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors"
        style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)" }}>
        <RefreshCw size={13} />Check again
      </button>
    </div>
  );

  const { activities, stats, profile } = data;

  const filtered = activities.filter((a) => {
    if (subTab === "upcoming") return a.urgency !== "completed";
    if (subTab === "done") return a.urgency === "completed";
    return true;
  });

  const ORDER: Record<Activity["urgency"], number> = { overdue: 0, due_soon: 1, upcoming: 2, completed: 3 };
  const sorted = [...filtered].sort((a, b) => ORDER[a.urgency] - ORDER[b.urgency]);

  return (
    <>
      <div className="space-y-4">

        {/* ── Hero card ── */}
        <div className="rounded-2xl p-5 relative overflow-hidden"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {/* Ambient glow */}
          <div className="absolute inset-0 pointer-events-none"
            style={{ background: "radial-gradient(ellipse at top right, rgba(245,158,11,0.10), transparent 65%)" }} />

          {/* Header row */}
          <div className="flex items-center justify-between mb-5 relative">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center"
                style={{ background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.3)" }}>
                <Crown size={15} style={{ color: "#f59e0b" }} />
              </div>
              <span className="text-sm font-bold" style={{ color: "var(--text)" }}>ISO360 Compliance Hub</span>
            </div>
            <span className="text-xs px-2.5 py-1 rounded-full font-bold tracking-wide"
              style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)" }}>
              PREMIUM
            </span>
          </div>

          {/* Score + stat grid */}
          <div className="flex flex-col sm:flex-row items-center gap-5 relative">
            <ScoreGauge score={stats.score} dark={dark} />
            <div className="flex-1 grid grid-cols-2 gap-3 w-full">
              {[
                { label: "Activities",  value: stats.total,    color: "#818cf8" },
                { label: "Completed",   value: stats.done,     color: "#10b981" },
                { label: "Overdue",     value: stats.overdue,  color: "#ef4444" },
                { label: "Due Soon",    value: stats.due_soon, color: "#f59e0b" },
              ].map((s) => (
                <div key={s.label} className="rounded-xl p-3.5"
                  style={{ background: dark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)", border: "1px solid var(--border)" }}>
                  <div className="text-2xl font-bold tabular-nums" style={{ color: s.color }}>{s.value}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Sub-tabs ── */}
        <div className="flex gap-1 p-1 rounded-2xl"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {(["upcoming", "all", "done"] as SubTab[]).map((t) => {
            const count = t === "upcoming" ? activities.filter(a => a.urgency !== "completed").length
              : t === "done" ? stats.done : activities.length;
            const active = subTab === t;
            return (
              <button key={t} onClick={() => setSubTab(t)}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-1.5"
                style={{
                  background: active ? "rgba(245,158,11,0.14)" : "transparent",
                  color: active ? "#f59e0b" : "var(--muted)",
                  border: active ? "1px solid rgba(245,158,11,0.3)" : "1px solid transparent",
                }}>
                {t === "upcoming" ? "Upcoming" : t === "done" ? "Done" : "All"}
                <span className="text-xs px-1.5 py-0.5 rounded-full tabular-nums"
                  style={{ background: active ? "rgba(245,158,11,0.2)" : "var(--surface2)", color: active ? "#f59e0b" : "var(--muted)" }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* ── Activity list ── */}
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {sorted.length === 0 ? (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="text-center py-14 flex flex-col items-center gap-3">
                <CheckCircle2 size={36} style={{ color: "#10b981" }} />
                <div className="text-sm font-semibold" style={{ color: "var(--text)" }}>All clear!</div>
                <div className="text-xs" style={{ color: "var(--muted)" }}>No activities in this view.</div>
              </motion.div>
            ) : sorted.map((a, i) => (
              <motion.div key={a.id}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ delay: i * 0.04, duration: 0.2 }}>
                <ActivityCard a={a} selected={selected?.id === a.id} onSelect={() => setSelected(a)} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* ── KYC Profile ── */}
        {profile.length > 0 && (
          <div className="rounded-2xl overflow-hidden"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <button
              className="w-full flex items-center justify-between px-5 py-4 transition-colors"
              onClick={() => setProfileOpen(!profileOpen)}>
              <div className="flex items-center gap-2.5">
                <Sparkles size={15} style={{ color: "#f59e0b" }} />
                <span className="text-sm font-bold" style={{ color: "var(--text)" }}>Your Compliance Profile</span>
                <span className="text-xs px-2 py-0.5 rounded-full tabular-nums"
                  style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}>
                  {profile.length}
                </span>
              </div>
              <motion.div animate={{ rotate: profileOpen ? 180 : 0 }} transition={{ duration: 0.25 }}>
                <ChevronDown size={15} style={{ color: "var(--muted)" }} />
              </motion.div>
            </button>

            <AnimatePresence>
              {profileOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{ overflow: "hidden" }}>
                  <div className="px-5 pb-5 border-t" style={{ borderColor: "var(--border)" }}>
                    <p className="text-xs pt-4 pb-4 leading-relaxed" style={{ color: "var(--muted)" }}>
                      This information was collected during your onboarding and used to personalise your compliance activities.
                    </p>
                    <div className="space-y-3">
                      {profile.map((p) => (
                        <div key={p.key} className="rounded-xl p-4"
                          style={{ background: dark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.03)", border: "1px solid var(--border)" }}>
                          <div className="text-xs font-bold mb-2 uppercase tracking-wide" style={{ color: "#f59e0b" }}>
                            {p.label ?? KYC_LABELS[p.key] ?? p.key.replace(/_/g, " ")}
                          </div>
                          <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}>{p.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Bottom breathing room for mobile nav */}
        <div className="h-4 md:h-0" />
      </div>

      {/* ── Activity detail overlay ── */}
      <AnimatePresence>
        {selected && (
          <ActivityDetail
            key={selected.id}
            activity={selected}
            dark={dark}
            isMobile={isMobile}
            onClose={() => setSelected(null)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
