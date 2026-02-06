"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Message {
  id: string;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  reaction?: string;
  toolsUsed?: string[];
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      text: "Hello! I'm the DNA AI Assistant. I can help you with ISO certification workflows, template management, and customer interactions. How can I assist you today?",
      sender: "bot",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [size, setSize] = useState({ width: 450, height: 650 });
  const currentMessageRef = useRef<string>("");

  const suggestedPrompts = [
    "Show me active ISO templates",
    "Help me create a certificate",
    "What are my pending tasks?",
    "Explain the certification workflow",
  ];

  // WebSocket connection management
  useEffect(() => {
    if (!isOpen) {
      if (ws) {
        ws.close();
        setWs(null);
      }
      return;
    }

    const token = localStorage.getItem("access_token");
    if (!token) {
      console.error("No access token found");
      return;
    }

    const websocket = new WebSocket(`ws://localhost:8400/ws/chat?token=${token}`);

    websocket.onopen = () => {
      console.log("WebSocket connected");
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (isDebugMode) {
        console.log("WebSocket message:", data);
      }

      if (data.type === "token") {
        // Accumulate streaming tokens
        currentMessageRef.current += data.content;
        
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.sender === "bot" && lastMessage.id.startsWith("bot-temp-")) {
            return [
              ...prev.slice(0, -1),
              { ...lastMessage, text: currentMessageRef.current },
            ];
          } else {
            return [
              ...prev,
              {
                id: "bot-temp-" + Date.now(),
                text: currentMessageRef.current,
                sender: "bot",
                timestamp: new Date(),
              },
            ];
          }
        });
      } else if (data.type === "done") {
        // Finalize the message
        setIsTyping(false);
        currentMessageRef.current = "";
        
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.id.startsWith("bot-temp-")) {
            return [
              ...prev.slice(0, -1),
              { ...lastMessage, id: "bot-" + Date.now() },
            ];
          }
          return prev;
        });
      } else if (data.type === "error") {
        setIsTyping(false);
        currentMessageRef.current = "";
        
        setMessages((prev) => [
          ...prev,
          {
            id: "error-" + Date.now(),
            text: `⚠️ Error: ${data.content || "An error occurred"}`,
            sender: "bot",
            timestamp: new Date(),
          },
        ]);
      }
    };

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error);
      setIsTyping(false);
    };

    websocket.onclose = () => {
      console.log("WebSocket disconnected");
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, [isOpen, isDebugMode]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when opening
  useEffect(() => {
    if (isOpen && !isMinimized) {
      inputRef.current?.focus();
    }
  }, [isOpen, isMinimized]);

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userMessage: Message = {
      id: "user-" + Date.now(),
      text: input,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);
    currentMessageRef.current = "";

    if (ws && ws.readyState === WebSocket.OPEN) {
      // Send via WebSocket
      ws.send(JSON.stringify({ message: input }));
    } else {
      // WebSocket not connected
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: "error-" + Date.now(),
          text: "⚠️ WebSocket not connected. Please close and reopen the chat window.",
          sender: "bot",
          timestamp: new Date(),
        },
      ]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: "1",
        text: "Hello! I'm the DNA AI Assistant. I can help you with ISO certification workflows, template management, and customer interactions. How can I assist you today?",
        sender: "bot",
        timestamp: new Date(),
      },
    ]);
  };

  const exportChat = () => {
    const chatText = messages
      .map((m) => `[${m.timestamp.toLocaleString()}] ${m.sender === "user" ? "You" : "DNA"}: ${m.text}`)
      .join("\n\n");
    const blob = new Blob([chatText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dna-chat-${new Date().toISOString().split("T")[0]}.txt`;
    a.click();
  };

  const addReaction = (messageId: string, reaction: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? { ...m, reaction: m.reaction === reaction ? undefined : reaction }
          : m
      )
    );
  };

  const copyMessage = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-16 h-16 bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-full shadow-2xl hover:shadow-3xl transform hover:scale-110 transition-all z-50 flex items-center justify-center group"
        aria-label="Open chat"
      >
        <svg
          className="w-8 h-8"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full border-2 border-white animate-pulse"></span>
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-6 right-6 bg-white rounded-2xl shadow-2xl flex flex-col z-50 border border-gray-200 overflow-hidden"
      style={{ width: `${size.width}px`, height: isMinimized ? "auto" : `${size.height}px` }}
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 via-blue-700 to-blue-800 text-white p-4 flex items-center justify-between shadow-lg">
        <div className="flex items-center space-x-3">
          <div className="relative">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-400 rounded-full border-2 border-blue-700"></span>
          </div>
          <div>
            <h3 className="font-bold text-sm">DNA Assistant</h3>
            <p className="text-xs text-blue-100">ISO Certification AI</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setIsDebugMode(!isDebugMode)}
            className={`text-white/80 hover:text-white transition-colors p-1 hover:bg-white/10 rounded-lg ${isDebugMode ? "bg-white/20" : ""}`}
            title="Toggle debug mode"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
          </button>
          <button onClick={exportChat} className="text-white/80 hover:text-white transition-colors p-1 hover:bg-white/10 rounded-lg" title="Export chat">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          <button onClick={clearChat} className="text-white/80 hover:text-white transition-colors p-1 hover:bg-white/10 rounded-lg" title="Clear chat">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
          <button onClick={() => setIsMinimized(!isMinimized)} className="text-white/80 hover:text-white transition-colors p-1 hover:bg-white/10 rounded-lg" title={isMinimized ? "Maximize" : "Minimize"}>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isMinimized ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              )}
            </svg>
          </button>
          <button onClick={() => setIsOpen(false)} className="text-white/80 hover:text-white transition-colors p-1 hover:bg-white/10 rounded-lg" aria-label="Close chat">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-gray-50 to-white">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"} animate-fade-in group`}>
                <div className="flex flex-col max-w-[85%]">
                  <div className={`rounded-2xl px-4 py-3 shadow-md relative ${message.sender === "user" ? "bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-br-sm" : "bg-white text-gray-800 border border-gray-200 rounded-bl-sm"}`}>
                    <div className="text-sm leading-relaxed prose prose-sm max-w-none">
                      <ReactMarkdown
                        components={{
                          code({ node, inline, className, children, ...props }: any) {
                            const match = /language-(\w+)/.exec(className || "");
                            return !inline && match ? (
                              <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" {...props}>
                                {String(children).replace(/\n$/, "")}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={`${className} bg-gray-100 px-1 rounded`} {...props}>
                                {children}
                              </code>
                            );
                          },
                        }}
                      >
                        {message.text}
                      </ReactMarkdown>
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className={`text-[10px] ${message.sender === "user" ? "text-blue-200" : "text-gray-400"}`}>
                        {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <div className="flex items-center space-x-2">
                        {message.sender === "bot" && (
                          <>
                            <button onClick={() => addReaction(message.id, "👍")} className="opacity-0 group-hover:opacity-100 transition-opacity text-xs hover:scale-125" title="Good response">
                              {message.reaction === "👍" ? "👍" : "👍🏻"}
                            </button>
                            <button onClick={() => addReaction(message.id, "👎")} className="opacity-0 group-hover:opacity-100 transition-opacity text-xs hover:scale-125" title="Bad response">
                              {message.reaction === "👎" ? "👎" : "👎🏻"}
                            </button>
                          </>
                        )}
                        <button onClick={() => copyMessage(message.text)} className={`opacity-0 group-hover:opacity-100 transition-opacity text-[10px] ${message.sender === "user" ? "text-blue-200 hover:text-white" : "text-gray-400 hover:text-gray-600"}`} title="Copy message">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                  {message.sender === "bot" && message.toolsUsed && message.toolsUsed.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1 ml-1">
                      {message.toolsUsed.map((tool, idx) => (
                        <span key={idx} className="text-[9px] px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full border border-blue-200" title="Tool used">
                          🔧 {tool}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex justify-start animate-fade-in">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-md">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
                    <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Prompts */}
          {messages.length <= 1 && (
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200">
              <p className="text-xs text-gray-500 mb-2">Suggested prompts:</p>
              <div className="flex flex-wrap gap-2">
                {suggestedPrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => setInput(prompt)}
                    className="text-xs px-3 py-1.5 bg-white border border-blue-200 text-blue-700 rounded-full hover:bg-blue-50 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="p-4 bg-white border-t border-gray-200">
            <div className="flex space-x-2 items-end">
              <div className="flex-1 relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask DNA anything..."
                  disabled={isTyping}
                  className="w-full px-4 py-3 pr-12 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent disabled:bg-gray-50 disabled:cursor-not-allowed text-gray-900 placeholder-gray-400 transition-all"
                  style={{ backgroundColor: "white", color: "black" }}
                />
                {input && (
                  <button onClick={() => setInput("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
              <button
                onClick={handleSend}
                disabled={isTyping || !input.trim()}
                className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-3 rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed shadow-lg hover:shadow-xl disabled:shadow-none transform hover:scale-105 disabled:scale-100"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
            <p className="text-[10px] text-gray-400 mt-2 text-center">
              🔒 <span className="font-semibold text-blue-600">Secure</span> • 
              {ws && ws.readyState === WebSocket.OPEN ? 
                <span className="text-green-600">✓ Connected</span> : 
                <span className="text-orange-600">⚠ Connecting...</span>
              }
            </p>
          </div>
        </>
      )}

      {/* Resize handles */}
      {!isMinimized && (
        <>
          <div
            className="absolute top-0 left-0 w-5 h-5 cursor-nwse-resize opacity-60 hover:opacity-100 transition-opacity"
            title="Resize"
            onPointerDown={(e) => {
              e.preventDefault();
              const startX = e.clientX;
              const startY = e.clientY;
              const startWidth = size.width;
              const startHeight = size.height;

              const handlePointerMove = (ev: PointerEvent) => {
                const dx = startX - ev.clientX;
                const dy = startY - ev.clientY;

                setSize({
                  width: Math.max(350, Math.min(800, startWidth + dx)),
                  height: Math.max(400, Math.min(900, startHeight + dy)),
                });
              };

              const handlePointerUp = () => {
                document.removeEventListener("pointermove", handlePointerMove);
                document.removeEventListener("pointerup", handlePointerUp);
                document.removeEventListener("pointercancel", handlePointerUp);
              };

              document.addEventListener("pointermove", handlePointerMove);
              document.addEventListener("pointerup", handlePointerUp);
              document.addEventListener("pointercancel", handlePointerUp);
            }}
          >
            <div className="w-full h-full bg-blue-200/70 hover:bg-blue-300/80" style={{ clipPath: "polygon(0 0, 100% 0, 0 100%)" }} />
          </div>
        </>
      )}

      <style jsx>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
        .prose code {
          color: inherit;
        }
      `}</style>
    </div>
  );
}
