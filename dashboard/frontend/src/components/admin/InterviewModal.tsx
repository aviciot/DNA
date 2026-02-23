"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";
import {
  X, CheckCircle2, ChevronRight, ChevronLeft, Upload, Loader2,
  FileText, Hash, Calendar, Sparkles, Check, SkipForward,
  Radio, Mail, Globe, Bot, BarChart2,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8400";

const CHANNEL_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  manual:       { label: "Interview",    icon: <Radio className="w-3.5 h-3.5" />,   color: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300" },
  email:        { label: "Email",        icon: <Mail className="w-3.5 h-3.5" />,    color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
  self_service: { label: "Self-service", icon: <Globe className="w-3.5 h-3.5" />,   color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" },
  ai_chat:      { label: "AI Chat",      icon: <Bot className="w-3.5 h-3.5" />,     color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" },
  automation:   { label: "Automation",   icon: <Sparkles className="w-3.5 h-3.5" />,color: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300" },
};

interface DocProgress { document_id?: string; template_name: string; completion_percentage: number; }

interface Question {
  placeholder_key: string;
  display_label: string;
  data_type: string;
  is_required: boolean;
  status: string;
  allowed_channels: string[];
  template_count: number;
  template_names: string[];
  document_progress: DocProgress[];
}

interface InterviewSession {
  customer_id: number;
  customer_name: string;
  total_pending: number;
  total_collected: number;
  questions: Question[];
}

interface Props {
  customer: { id: number; name: string };
  onClose: () => void;
  onComplete: () => void;
}

export default function InterviewModal({ customer, onClose, onComplete }: Props) {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [saving, setSaving] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [activeChannel, setActiveChannel] = useState("manual");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });

  useEffect(() => { loadSession(); }, []);

  const loadSession = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/api/v1/customers/${customer.id}/interview`, { headers: headers() });
      setSession(res.data);
      const firstPending = res.data.questions.findIndex((q: Question) => q.status === "pending");
      setCurrentIndex(firstPending >= 0 ? firstPending : 0);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const pendingQuestions = session?.questions.filter((q) => q.status === "pending") ?? [];
  const collectedQuestions = session?.questions.filter((q) => q.status === "collected") ?? [];
  const currentQuestion = pendingQuestions[currentIndex] ?? null;
  const progress = session
    ? Math.round((session.total_collected / Math.max(1, session.total_collected + session.total_pending)) * 100)
    : 0;

  const handleSave = async () => {
    if (!currentQuestion || !answer.trim()) return;
    setSaving(true);
    try {
      await axios.post(
        `${API_BASE}/api/v1/customers/${customer.id}/interview/answer`,
        { placeholder_key: currentQuestion.placeholder_key, answer: answer.trim(), source: activeChannel },
        { headers: headers() }
      );
      setAnswer("");
      await loadSession();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const handleFile = async (file: File) => {
    if (!currentQuestion) return;
    setSaving(true);
    try {
      const form = new FormData();
      form.append("placeholder_key", currentQuestion.placeholder_key);
      form.append("source", activeChannel);
      form.append("file", file);
      await axios.post(
        `${API_BASE}/api/v1/customers/${customer.id}/interview/answer-file`,
        form,
        { headers: { ...headers(), "Content-Type": "multipart/form-data" } }
      );
      await loadSession();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const isFile = currentQuestion?.data_type === "file" || currentQuestion?.data_type === "image";

  // Group pending questions by first template name for sidebar display
  const grouped = pendingQuestions.reduce<Record<string, Question[]>>((acc, q) => {
    const doc = q.template_names[0] || "General";
    (acc[doc] = acc[doc] || []).push(q);
    return acc;
  }, {});

  if (loading) return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 flex items-center gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        <span className="text-gray-700 dark:text-gray-300">Loading interview...</span>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-lg"><Sparkles className="w-5 h-5 text-white" /></div>
            <div>
              <h2 className="text-lg font-bold text-white">Customer Interview</h2>
              <p className="text-sm text-white/70">{customer.name}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/20 rounded-lg transition-all">
            <X className="w-5 h-5 text-white" />
          </button>
        </div>

        {/* Progress */}
        <div className="px-6 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex justify-between mb-1.5 text-sm">
            <span className="text-gray-600 dark:text-gray-400">
              {session?.total_collected} of {(session?.total_collected ?? 0) + (session?.total_pending ?? 0)} collected
            </span>
            <span className="font-bold text-indigo-600 dark:text-indigo-400">{progress}%</span>
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-700"
              style={{ width: `${progress}%` }} />
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">

          {/* Sidebar — grouped by document */}
          <div className="w-64 border-r border-gray-200 dark:border-gray-700 overflow-y-auto flex-shrink-0 bg-gray-50 dark:bg-gray-800">
            <div className="p-3">
              {Object.entries(grouped).map(([docName, qs]) => (
                <div key={docName} className="mb-3">
                  <div className="flex items-center gap-1.5 px-2 mb-1">
                    <FileText className="w-3 h-3 text-gray-400" />
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider truncate">{docName}</p>
                  </div>
                  {qs.map((q) => {
                    const globalIdx = pendingQuestions.indexOf(q);
                    return (
                      <button key={q.placeholder_key}
                        onClick={() => { setCurrentIndex(globalIdx); setAnswer(""); }}
                        className={`w-full text-left px-3 py-2 rounded-lg mb-0.5 transition-all flex items-center gap-2 ${
                          globalIdx === currentIndex
                            ? "bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 font-medium"
                            : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                        }`}>
                        <span className="flex-shrink-0 w-5 h-5 rounded-full border-2 border-current flex items-center justify-center text-xs">
                          {globalIdx + 1}
                        </span>
                        <span className="text-xs line-clamp-2">{q.display_label}</span>
                      </button>
                    );
                  })}
                </div>
              ))}

              {collectedQuestions.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1 px-2">
                    Collected ({collectedQuestions.length})
                  </p>
                  {collectedQuestions.map((q) => (
                    <div key={q.placeholder_key} className="flex items-center gap-2 px-3 py-1.5 text-xs text-green-600 dark:text-green-400">
                      <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="line-clamp-1">{q.display_label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Main area */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {pendingQuestions.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mb-4">
                  <Check className="w-8 h-8 text-green-600 dark:text-green-400" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">All done!</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-6">All information collected for {customer.name}.</p>
                <button onClick={() => { onComplete(); onClose(); }}
                  className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all">
                  Close Interview
                </button>
              </div>
            ) : currentQuestion ? (
              <div className="flex-1 flex flex-col p-6 overflow-y-auto gap-4">

                {/* Question meta */}
                <div>
                  <div className="flex items-center gap-2 flex-wrap mb-3">
                    {currentQuestion.is_required && (
                      <span className="px-2.5 py-1 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded-full text-xs font-medium">Required</span>
                    )}
                    <span className="px-2.5 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-full text-xs">
                      Used in {currentQuestion.template_count} document{currentQuestion.template_count !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white leading-relaxed">
                    {currentQuestion.display_label}
                  </h3>
                  <p className="text-xs font-mono text-gray-400 mt-1">{currentQuestion.placeholder_key}</p>
                </div>

                {/* Document progress */}
                {currentQuestion.document_progress.length > 0 && (
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-4 space-y-2">
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                      <BarChart2 className="w-3.5 h-3.5" /> Related Documents
                    </p>
                    {currentQuestion.document_progress.map((doc) => (
                      <div key={doc.template_name}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-700 dark:text-gray-300 truncate">{doc.template_name}</span>
                          <span className="text-gray-500 ml-2 shrink-0">{doc.completion_percentage}%</span>
                        </div>
                        <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full transition-all ${
                            doc.completion_percentage >= 100 ? "bg-green-500"
                            : doc.completion_percentage > 0 ? "bg-indigo-500"
                            : "bg-gray-300"
                          }`} style={{ width: `${doc.completion_percentage}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Channel selector */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Answer Channel</p>
                  <div className="flex flex-wrap gap-2">
                    {currentQuestion.allowed_channels.map((ch) => {
                      const meta = CHANNEL_META[ch];
                      if (!meta) return null;
                      return (
                        <button key={ch} onClick={() => setActiveChannel(ch)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border-2 transition-all ${
                            activeChannel === ch
                              ? `${meta.color} border-current`
                              : "border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-400"
                          }`}>
                          {meta.icon}{meta.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Answer input */}
                {isFile ? (
                  <div
                    className={`flex-1 min-h-32 border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-8 cursor-pointer transition-all ${
                      dragOver ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30"
                        : "border-gray-300 dark:border-gray-600 hover:border-indigo-400"
                    }`}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="w-10 h-10 text-gray-400 mb-3" />
                    <p className="text-gray-700 dark:text-gray-300 font-medium">Drop file here or click to browse</p>
                    <input ref={fileInputRef} type="file" className="hidden"
                      accept={currentQuestion.data_type === "image" ? "image/*" : "*"}
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
                  </div>
                ) : (
                  <textarea
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder="Type the answer here..."
                    rows={4}
                    className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all resize-none"
                    onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) handleSave(); }}
                  />
                )}
                {!isFile && <p className="text-xs text-gray-400 -mt-2">Ctrl+Enter to save</p>}
              </div>
            ) : null}

            {/* Footer */}
            {pendingQuestions.length > 0 && currentQuestion && (
              <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between flex-shrink-0 bg-white dark:bg-gray-900">
                <div className="flex items-center gap-2">
                  <button onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))} disabled={currentIndex === 0}
                    className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 transition-all">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-sm text-gray-500">{currentIndex + 1} / {pendingQuestions.length}</span>
                  <button onClick={() => setCurrentIndex(Math.min(pendingQuestions.length - 1, currentIndex + 1))}
                    disabled={currentIndex === pendingQuestions.length - 1}
                    className="p-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 transition-all">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex items-center gap-3">
                  <button onClick={() => setCurrentIndex(Math.min(pendingQuestions.length - 1, currentIndex + 1))}
                    className="flex items-center gap-1.5 px-4 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-all text-sm">
                    <SkipForward className="w-4 h-4" /> Skip
                  </button>
                  {!isFile && (
                    <button onClick={handleSave} disabled={saving || !answer.trim()}
                      className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all">
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                      Save & Next
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
