"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Send, Bot, Sparkles, Trash2, Download, Copy, Check, Maximize2, Minimize2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message { id: string; text: string; sender: "user" | "bot"; }
interface Props { customerName: string; isoCode: string; isOpen: boolean; onClose: () => void; dark: boolean; }

export default function ChatWidget({ customerName, isoCode, isOpen, onClose, dark }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const currentRef = useRef("");

  const bg = dark ? "var(--surface)" : "#ffffff";
  const msgBg = dark ? "var(--bg)" : "#f5f5f7";
  const inputBg = dark ? "var(--surface2)" : "#f0f0f5";

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (!isOpen) {
      setWs((prev) => { prev?.close(); return null; });
      setIsConnecting(false);
      return;
    }

    let cancelled = false;
    setMessages([]);
    setIsConnecting(true);
    setIsTyping(false);
    currentRef.current = "";

    const wsUrl = process.env.NEXT_PUBLIC_PORTAL_WS_URL || "ws://localhost:4010";
    const socket = new WebSocket(`${wsUrl}/portal/chat`);

    socket.onmessage = (e) => {
      if (cancelled) return;
      const data = JSON.parse(e.data);
      if (data.type === "welcome") {
        setIsConnecting(false);
        setMessages([{ id: "w-" + Date.now(), text: data.content, sender: "bot" }]);
      } else if (data.type === "token") {
        setIsConnecting(false);
        currentRef.current += data.content;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.id.startsWith("t-")) return [...prev.slice(0, -1), { ...last, text: currentRef.current }];
          return [...prev, { id: "t-" + Date.now(), text: currentRef.current, sender: "bot" }];
        });
      } else if (data.type === "done") {
        currentRef.current = "";
        setIsTyping(false);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.id.startsWith("t-")) return [...prev.slice(0, -1), { ...last, id: "b-" + Date.now() }];
          return prev;
        });
      } else if (data.type === "error") {
        setIsTyping(false);
        setIsConnecting(false);
        currentRef.current = "";
        setMessages((prev) => [...prev, { id: "e-" + Date.now(), text: data.content || "An error occurred", sender: "bot" }]);
      }
    };

    socket.onerror = () => {
      if (cancelled) return;
      setIsConnecting(false);
      setMessages([{ id: "e-0", text: "Could not connect to assistant. Please try again.", sender: "bot" }]);
    };

    socket.onclose = () => {
      if (cancelled) return;
      setIsConnecting(false);
      setIsTyping(false);
    };

    setWs(socket);

    return () => {
      cancelled = true;
      socket.close();
    };
  }, [isOpen]);

  function send() {
    if (!input.trim() || isTyping || !ws || ws.readyState !== WebSocket.OPEN) return;
    setMessages((prev) => [...prev, { id: "u-" + Date.now(), text: input, sender: "user" }]);
    ws.send(JSON.stringify({ message: input }));
    setInput(""); setIsTyping(true); currentRef.current = "";
  }

  function clearChat() {
    setMessages([]);
  }

  function exportChat() {
    const text = messages.map((m) => `[${m.sender === "user" ? "You" : "AI"}] ${m.text}`).join("\n\n");
    const blob = new Blob([text], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `chat-${isoCode}-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
  }

  function copyMsg(id: string, text: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  const prompts = ["Show me my urgent tasks", `What does ${isoCode} require?`, "Help me understand a task"];
  const showDots = isConnecting || isTyping;
  const showPrompts = !isConnecting && messages.length <= 1;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }} transition={{ duration: 0.2 }}
          className={`fixed bottom-6 right-6 flex flex-col rounded-2xl overflow-hidden z-50 transition-all duration-300 ${expanded ? "w-[680px] h-[80vh]" : "w-96 h-[580px]"}`}
          style={{ background: bg, border: "1px solid var(--border)", boxShadow: "0 24px 64px rgba(0,0,0,0.4)" }}>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
                <Sparkles size={14} className="text-white" />
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: "var(--text)" }}>AI Assistant</div>
                <div className="text-xs" style={{ color: "var(--muted)" }}>
                  {isConnecting ? "Connecting…" : `${isoCode} guidance`}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setExpanded(!expanded)} title={expanded ? "Collapse" : "Expand"}
                className="p-1.5 rounded-lg transition-colors hover:bg-black/5" style={{ color: "var(--muted)" }}>
                {expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              </button>
              <button onClick={exportChat} title="Export chat"
                className="p-1.5 rounded-lg transition-colors hover:bg-black/5" style={{ color: "var(--muted)" }}>
                <Download size={14} />
              </button>
              <button onClick={clearChat} title="Clear chat"
                className="p-1.5 rounded-lg transition-colors hover:bg-black/5" style={{ color: "var(--muted)" }}>
                <Trash2 size={14} />
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-black/5" style={{ color: "var(--muted)" }}>
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" style={{ background: msgBg }}>
            {messages.map((m) => (
              <div key={m.id} className={`flex group ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
                {m.sender === "bot" && (
                  <div className="w-6 h-6 rounded-full flex items-center justify-center mr-2 flex-shrink-0 mt-0.5"
                    style={{ background: "rgba(99,102,241,0.2)" }}>
                    <Bot size={12} style={{ color: "#818cf8" }} />
                  </div>
                )}
                <div className="relative max-w-[80%]">
                  <div className="rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed"
                    style={m.sender === "user"
                      ? { background: "rgba(99,102,241,0.2)", color: dark ? "#c7d2fe" : "#4338ca", borderBottomRightRadius: 4 }
                      : { background: dark ? "var(--surface2)" : "#ffffff", color: "var(--text)", border: "1px solid var(--border)", borderBottomLeftRadius: 4 }}>
                    {m.sender === "user" ? (
                      <span>{m.text}</span>
                    ) : (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc ml-4 mb-2 space-y-0.5">{children}</ul>,
                          ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 space-y-0.5">{children}</ol>,
                          li: ({ children }) => <li>{children}</li>,
                          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                          em: ({ children }) => <em className="italic">{children}</em>,
                          code: ({ children }) => (
                            <code className="rounded px-1 py-0.5 text-xs font-mono"
                              style={{ background: "rgba(99,102,241,0.1)" }}>{children}</code>
                          ),
                          hr: () => <hr className="my-2 opacity-20" />,
                        }}
                      >
                        {m.text}
                      </ReactMarkdown>
                    )}
                  </div>
                  <button onClick={() => copyMsg(m.id, m.text)}
                    className="absolute -top-1 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md"
                    style={{ [m.sender === "user" ? "left" : "right"]: "-24px", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--muted)" }}>
                    {copiedId === m.id ? <Check size={10} style={{ color: "#10b981" }} /> : <Copy size={10} />}
                  </button>
                </div>
              </div>
            ))}

            {/* Typing / connecting dots */}
            {showDots && (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: "rgba(99,102,241,0.2)" }}>
                  <Bot size={12} style={{ color: "#818cf8" }} />
                </div>
                <div className="flex gap-1 px-3.5 py-2.5 rounded-2xl" style={{ background: dark ? "var(--surface2)" : "#ffffff", border: "1px solid var(--border)" }}>
                  {[0, 0.15, 0.3].map((d, i) => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: "#6366f1", animationDelay: `${d}s` }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Suggested prompts — shown after welcome lands */}
          {showPrompts && (
            <div className="px-4 py-2 flex flex-wrap gap-1.5 border-t" style={{ borderColor: "var(--border)" }}>
              {prompts.map((p, i) => (
                <button key={i} onClick={() => setInput(p)}
                  className="text-xs px-2.5 py-1 rounded-full transition-colors"
                  style={{ background: "rgba(99,102,241,0.1)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.2)" }}>
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="px-3 py-3 border-t" style={{ borderColor: "var(--border)" }}>
            <div className="flex gap-2">
              <input value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
                placeholder="Ask anything…" disabled={isTyping || isConnecting}
                className="flex-1 px-3 py-2 rounded-lg text-sm focus:outline-none"
                style={{ background: inputBg, border: "1px solid var(--border)", color: "var(--text)" }}
              />
              <button onClick={send} disabled={isTyping || isConnecting || !input.trim()}
                className="w-9 h-9 rounded-lg flex items-center justify-center transition-all disabled:opacity-30"
                style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8" }}>
                <Send size={14} />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
