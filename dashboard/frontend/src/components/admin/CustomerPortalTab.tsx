"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Globe, Copy, Check, ExternalLink, RefreshCw, Clock,
  ShieldCheck, ShieldOff, Activity, LogIn, FileUp,
  MessageSquare, AlertTriangle, RotateCcw,
} from "lucide-react";
import api from "@/lib/api";

interface ActivityEntry {
  event: string;
  detail: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

interface PortalData {
  has_access: boolean;
  portal_url?: string;
  token?: string;
  expires_at?: string;
  last_used_at?: string;
  created_at?: string;
  is_active?: boolean;
  activity: ActivityEntry[];
}

const EVENT_META: Record<string, { label: string; icon: any; color: string }> = {
  token_validated: { label: "Logged in",        icon: LogIn,        color: "text-emerald-600 bg-emerald-50" },
  answer_submitted: { label: "Submitted answer", icon: MessageSquare, color: "text-blue-600 bg-blue-50" },
  file_uploaded:    { label: "Uploaded file",    icon: FileUp,        color: "text-purple-600 bg-purple-50" },
  relink_requested: { label: "Requested new link", icon: RefreshCw,   color: "text-yellow-600 bg-yellow-50" },
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function CustomerPortalTab({ customerId }: { customerId: number }) {
  const [data, setData]       = useState<PortalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied]   = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [confirmRegen, setConfirmRegen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/api/v1/iso-customers/${customerId}/portal`);
      setData(r.data);
    } catch { /* interceptor handles 401 */ }
    finally { setLoading(false); }
  }, [customerId]);

  useEffect(() => { load(); }, [load]);

  const copyLink = () => {
    if (!data?.portal_url) return;
    navigator.clipboard.writeText(data.portal_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const regenerate = async () => {
    setRegenerating(true);
    setConfirmRegen(false);
    try {
      await api.post(`/api/v1/iso-customers/${customerId}/portal/regenerate`);
      await load();
    } finally { setRegenerating(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-16 text-slate-400">
      <RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading portal data...
    </div>
  );

  // No token yet
  if (!data?.has_access) return (
    <div className="text-center py-16 space-y-4">
      <Globe className="w-10 h-10 text-slate-300 mx-auto" />
      <p className="text-slate-500 font-medium">No portal access configured for this customer</p>
      <button onClick={regenerate} disabled={regenerating}
        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50">
        <Globe className="w-4 h-4" />Generate Portal Link
      </button>
    </div>
  );

  const isActive = data.is_active;
  const lastSeen = data.last_used_at ? timeAgo(data.last_used_at) : null;

  return (
    <div className="space-y-5">

      {/* ── Portal Link Card ── */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-blue-500" />
            <span className="font-semibold text-slate-800 text-sm">Customer Portal Link</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Status badge */}
            {isActive ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                <ShieldCheck className="w-3.5 h-3.5" />Active
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-600">
                <ShieldOff className="w-3.5 h-3.5" />Expired
              </span>
            )}
          </div>
        </div>

        <div className="p-5 space-y-4">
          {/* URL row */}
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-2 px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg overflow-hidden">
              <Globe className="w-4 h-4 text-slate-400 flex-shrink-0" />
              <span className="text-sm text-slate-700 font-mono truncate">{data.portal_url}</span>
            </div>
            <button onClick={copyLink}
              className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all flex-shrink-0 ${
                copied
                  ? "bg-emerald-100 text-emerald-700 border border-emerald-200"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-600"
              }`}>
              {copied ? <><Check className="w-4 h-4" />Copied!</> : <><Copy className="w-4 h-4" />Copy</>}
            </button>
            <a href={data.portal_url} target="_blank" rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium flex-shrink-0 transition-colors">
              <ExternalLink className="w-4 h-4" />Open
            </a>
          </div>

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
            {data.expires_at && (
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                Expires {fmtDate(data.expires_at)}
              </span>
            )}
            {lastSeen ? (
              <span className="flex items-center gap-1 text-emerald-600 font-medium">
                <Activity className="w-3.5 h-3.5" />
                Last seen {lastSeen}
              </span>
            ) : (
              <span className="flex items-center gap-1 text-slate-400">
                <Activity className="w-3.5 h-3.5" />
                Never accessed
              </span>
            )}
            {data.created_at && (
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                Created {fmtDate(data.created_at)}
              </span>
            )}
          </div>

          {/* Regenerate */}
          <div className="pt-1 border-t border-slate-100 flex items-center justify-between">
            <p className="text-xs text-slate-400">
              Generating a new link will invalidate the current one.
            </p>
            {confirmRegen ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-orange-600 font-medium flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" />Sure?
                </span>
                <button onClick={() => setConfirmRegen(false)} className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50">
                  Cancel
                </button>
                <button onClick={regenerate} disabled={regenerating}
                  className="px-3 py-1.5 text-xs bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium disabled:opacity-50 flex items-center gap-1">
                  {regenerating ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                  Regenerate
                </button>
              </div>
            ) : (
              <button onClick={() => setConfirmRegen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-slate-200 rounded-lg text-slate-600 hover:border-orange-300 hover:text-orange-600 transition-colors">
                <RotateCcw className="w-3.5 h-3.5" />New Link
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Activity Log ── */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-500" />
            <span className="font-semibold text-slate-800 text-sm">Activity</span>
            {data.activity.length > 0 && (
              <span className="px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded text-xs font-medium">
                {data.activity.length}
              </span>
            )}
          </div>
          <button onClick={load} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {data.activity.length === 0 ? (
          <div className="py-10 text-center text-slate-400 text-sm">
            No activity yet — share the portal link with the customer.
          </div>
        ) : (
          <div className="divide-y divide-slate-50">
            {data.activity.map((entry, i) => {
              const meta = EVENT_META[entry.event] ?? { label: entry.event, icon: Activity, color: "text-slate-600 bg-slate-50" };
              const Icon = meta.icon;
              return (
                <div key={i} className="flex items-start gap-3 px-5 py-3 hover:bg-slate-50/50 transition-colors">
                  <div className={`mt-0.5 p-1.5 rounded-lg flex-shrink-0 ${meta.color}`}>
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-slate-800">{meta.label}</span>
                      {entry.detail?.filename && (
                        <span className="text-xs text-slate-500 font-mono truncate max-w-[200px]">{entry.detail.filename}</span>
                      )}
                      {entry.detail?.key && (
                        <span className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-mono">{entry.detail.key}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs text-slate-400">{fmtDate(entry.created_at)}</span>
                      {entry.ip_address && (
                        <span className="text-xs text-slate-300 font-mono">{entry.ip_address}</span>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-slate-400 whitespace-nowrap flex-shrink-0">{timeAgo(entry.created_at)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
