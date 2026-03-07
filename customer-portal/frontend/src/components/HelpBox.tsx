"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Sparkles, FileText, Layers, BadgeCheck } from "lucide-react";

interface Meta {
  template_name: string;
  section_title: string;
  iso_reference: string;
}

interface Props {
  taskId: string;
  onClose: () => void;
}

function isRTL(str: string) {
  return /[\u0590-\u05FF\u0600-\u06FF]/.test(str);
}

const SECTION_KEYS = ["based_on", "what_this_asks", "why_it_matters", "good_answer"] as const;
type SectionKey = typeof SECTION_KEYS[number];

export default function HelpBox({ taskId, onClose }: Props) {
  const [raw, setRaw] = useState("");                          // accumulated JSON tokens
  const [sections, setSections] = useState<Record<string, string> | null>(null); // parsed
  const [meta, setMeta] = useState<Meta | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const rtl = isRTL(Object.values(sections ?? {}).join(" "));

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        const res = await fetch("/api/portal/task-help", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: taskId }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) { setError(true); setDone(true); return; }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
          const { value, done: streamDone } = await reader.read();
          if (streamDone) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6);
            if (raw === "[DONE]") {
              // Parse accumulated JSON
              setRaw(prev => {
                try {
                  const parsed = JSON.parse(prev);
                  setSections(parsed);
                } catch { /* malformed — leave raw for fallback */ }
                return prev;
              });
              setDone(true);
              return;
            }
            // Check for metadata JSON event (first event)
            if (raw.startsWith("{")) {
              try {
                const parsed = JSON.parse(raw);
                if (parsed.type === "meta") { setMeta(parsed); continue; }
              } catch { /* not a meta event, accumulate as JSON token */ }
            }
            setRaw((prev) => prev + raw);
          }
        }
        setDone(true);
      } catch (e: any) {
        if (e?.name !== "AbortError") setError(true);
        setDone(true);
      }
    })();

    return () => controller.abort();
  }, [taskId]);

  const hasSource = meta && (meta.template_name || meta.section_title || meta.iso_reference);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className="mt-3 rounded-2xl overflow-hidden"
      style={{
        background: "var(--surface2)",
        border: "1px solid rgba(129,140,248,0.25)",
        boxShadow: "0 4px 24px rgba(99,102,241,0.12), 0 1px 4px rgba(0,0,0,0.08)",
      }}
    >
      {/* ── Gradient header ── */}
      <div
        className="relative flex items-center justify-between px-4 py-3 overflow-hidden"
        style={{
          background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
        }}
      >
        {/* Decorative orbs */}
        <div className="absolute -top-4 -left-4 w-16 h-16 rounded-full opacity-20"
          style={{ background: "radial-gradient(circle, #fff 0%, transparent 70%)" }} />
        <div className="absolute -bottom-3 right-8 w-12 h-12 rounded-full opacity-15"
          style={{ background: "radial-gradient(circle, #fff 0%, transparent 70%)" }} />

        <div className="relative flex items-center gap-2">
          <motion.div
            animate={{ rotate: done ? 0 : 360 }}
            transition={{ duration: 3, repeat: done ? 0 : Infinity, ease: "linear" }}
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(255,255,255,0.2)" }}
          >
            <Sparkles size={13} className="text-white" />
          </motion.div>
          <div>
            <p className="text-white text-xs font-semibold tracking-wide">AI Compliance Guide</p>
            {!done && !error && (
              <p className="text-purple-200 text-[10px]">Analyzing your document…</p>
            )}
          </div>
        </div>

        <button
          onClick={onClose}
          className="relative w-6 h-6 flex items-center justify-center rounded-lg transition-all hover:bg-white/20"
          style={{ color: "rgba(255,255,255,0.7)" }}
        >
          <X size={13} />
        </button>
      </div>

      {/* ── Explanation body ── */}
      <div className="px-5 py-4" dir={rtl ? "rtl" : "ltr"}>
        {error ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>Sorry, I couldn't generate an explanation right now.</p>
        ) : !done ? (
          <span style={{ color: "var(--muted)" }} className="animate-pulse text-sm">●&nbsp;&nbsp;●&nbsp;&nbsp;●</span>
        ) : sections ? (
          <div className="space-y-4">
            {Object.entries(sections).map(([key, content], idx) => (
              <div key={key}>
                {/* Section title pill */}
                <div className={`flex items-center gap-2 mb-1.5 ${rtl ? "flex-row-reverse" : ""}`}>
                  <div className="w-1 h-3.5 rounded-full flex-shrink-0"
                    style={{ background: "linear-gradient(180deg, #6366f1, #a855f7)" }} />
                  <span
                    className="text-[10px] font-bold uppercase tracking-widest"
                    style={{ color: "#818cf8" }}
                  >
                    {key.replace(/_/g, " ")}
                  </span>
                </div>
                {/* Section content */}
                <p
                  className="text-sm leading-7 pl-3"
                  style={{ color: "var(--text)", textAlign: rtl ? "right" : "left", borderInlineStart: "2px solid rgba(129,140,248,0.15)", paddingInlineStart: "12px" }}
                >
                  {content}
                </p>
              </div>
            ))}
          </div>
        ) : (
          /* Fallback: raw text if JSON parse failed */
          <p className="text-sm leading-7" style={{ color: "var(--text)" }}>{raw}</p>
        )}
      </div>

      {/* ── Source grounding card ── */}
      <AnimatePresence>
        {hasSource && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="mx-4 mb-4 rounded-xl overflow-hidden"
            style={{
              background: "linear-gradient(135deg, rgba(79,70,229,0.06) 0%, rgba(168,85,247,0.06) 100%)",
              border: "1px solid rgba(129,140,248,0.2)",
            }}
          >
            {/* Card header */}
            <div className="flex items-center gap-1.5 px-3 py-2"
              style={{ borderBottom: "1px solid rgba(129,140,248,0.15)" }}>
              <BadgeCheck size={11} style={{ color: "#818cf8" }} />
              <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#818cf8" }}>
                Grounded in your document
              </span>
            </div>

            {/* Card fields */}
            <div className="px-3 py-2.5 space-y-2">
              {meta!.template_name && (
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
                    style={{ background: "rgba(79,70,229,0.12)" }}>
                    <FileText size={11} style={{ color: "#6366f1" }} />
                  </div>
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--muted)" }}>Document</p>
                    <p className="text-xs font-medium" style={{ color: "var(--text)" }}>{meta!.template_name}</p>
                  </div>
                </div>
              )}
              {meta!.section_title && (
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
                    style={{ background: "rgba(124,58,237,0.12)" }}>
                    <Layers size={11} style={{ color: "#7c3aed" }} />
                  </div>
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--muted)" }}>Section</p>
                    <p className="text-xs font-medium" style={{ color: "var(--text)" }}>{meta!.section_title}</p>
                  </div>
                </div>
              )}
              {meta!.iso_reference && (
                <div className="flex items-center gap-2">
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{
                      background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
                      color: "white",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {meta!.iso_reference}
                  </span>
                  <span className="text-[10px]" style={{ color: "var(--muted)" }}>ISO Clause Reference</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
