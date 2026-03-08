"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Clock, FileUp, Target } from "lucide-react";

interface Props {
  me: {
    customer_name: string;
    contact_person: string;
    contact_email: string;
    iso_code: string;
    iso_name: string;
    target_completion_date: string | null;
  };
  progress: {
    total: number;
    completed: number;
    pending: number;
    evidence_pending: number;
    percentage: number;
    target_completion_date: string | null;
  };
  dark?: boolean;
}

function CircularProgress({ pct }: { pct: number }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
      <circle cx="70" cy="70" r={r} fill="none"
        stroke="url(#grad)" strokeWidth="10"
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
      </defs>
      <text x="70" y="65" textAnchor="middle" fill="#e2e2ea" fontSize="22" fontWeight="700" fontFamily="Inter, sans-serif">{pct}%</text>
      <text x="70" y="82" textAnchor="middle" fill="#5a5a72" fontSize="11" fontFamily="Inter, sans-serif">Complete</text>
    </svg>
  );
}

export default function ProgressPanel({ me, progress, dark = true }: Props) {
  const stats = [
    { label: "Total Tasks", value: progress.total, icon: <Target size={16} />, color: "#6366f1", bg: "rgba(99,102,241,0.1)" },
    { label: "Completed", value: progress.completed, icon: <CheckCircle2 size={16} />, color: "#10b981", bg: "rgba(16,185,129,0.1)" },
    { label: "Pending", value: progress.pending, icon: <Clock size={16} />, color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
    { label: "Evidence Needed", value: progress.evidence_pending, icon: <FileUp size={16} />, color: "#8b5cf6", bg: "rgba(139,92,246,0.1)" },
  ];

  return (
    <div className="space-y-6">
      {/* Hero card */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
        className="rounded-2xl p-5 md:p-6 flex flex-col md:flex-row items-center gap-5 md:gap-8"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <CircularProgress pct={progress.percentage} />
        <div className="flex-1">
          <h2 className="text-xl font-semibold mb-1" style={{ color: "var(--text)" }}>
            {progress.percentage < 100 ? "Certification in Progress" : "Ready for Certification"}
          </h2>
          <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
            {progress.percentage < 100
              ? `${progress.pending} tasks remaining before you're certification-ready.`
              : "All tasks complete — contact your consultant to schedule the audit."}
          </p>
          {progress.target_completion_date && (
            <div className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
              <Target size={14} />
              Target date: <span style={{ color: "var(--text)" }}>
                {new Date(progress.target_completion_date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
              </span>
            </div>
          )}
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.05 }}
            className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3" style={{ background: s.bg, color: s.color }}>
              {s.icon}
            </div>
            <div className="text-2xl font-bold mb-0.5" style={{ color: "var(--text)" }}>{s.value}</div>
            <div className="text-xs" style={{ color: "var(--muted)" }}>{s.label}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
