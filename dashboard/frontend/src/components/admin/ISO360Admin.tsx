"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import api from "@/lib/api";
import ISO360TemplatesPanel from "./ISO360TemplatesPanel";

interface ISOStandard {
  id: string;
  code: string;
  name: string;
  color?: string;
  template_count: number;
}

export default function ISO360Admin() {
  const [standards, setStandards] = useState<ISOStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ISOStandard | null>(null);

  useEffect(() => {
    api.get("/api/v1/iso-standards?active_only=false")
      .then(r => {
        setStandards(r.data);
        if (r.data.length === 1) setSelected(r.data[0]);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-6 text-slate-400 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading standards…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900">ISO360 Templates</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Generate and manage recurring activity templates and static document placeholders for each ISO standard.
        </p>
      </div>

      {/* Standard selector */}
      {standards.length === 0 ? (
        <p className="text-sm text-slate-400">
          No ISO standards found. Create one in the ISO Standards tab first.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {standards.map(s => (
            <button
              key={s.id}
              onClick={() => setSelected(selected?.id === s.id ? null : s)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-all ${
                selected?.id === s.id
                  ? "border-violet-300 bg-violet-50 text-violet-700"
                  : "border-slate-200 bg-white text-slate-600 hover:border-violet-200 hover:bg-violet-50/50"
              }`}
            >
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: s.color || "#8b5cf6" }}
              />
              <span className="font-semibold">{s.code}</span>
              <span className="text-xs opacity-60">
                {s.name.length > 35 ? s.name.slice(0, 35) + "…" : s.name}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Panel */}
      {selected && (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          <ISO360TemplatesPanel
            isoId={selected.id}
            isoCode={selected.code}
            isoColor={selected.color || "#8b5cf6"}
          />
        </div>
      )}
    </div>
  );
}
