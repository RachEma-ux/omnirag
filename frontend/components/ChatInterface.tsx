"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Message = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = (await api.search(userMsg.content, 5)) as any;
      const assistantMsg: Message = {
        role: "assistant",
        content: res.answer || "No answer generated.",
        citations: res.citations || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center text-[#555] mt-20">
            <p className="text-lg mb-2">Ask a question about your documents</p>
            <p className="text-sm">Uses hybrid retrieval (vector + keyword) with RAG generation</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm ${
                msg.role === "user"
                  ? "bg-[#6366f1] text-white"
                  : "bg-[#1e1e1e] border border-[#2a2a2a]"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-[#2a2a2a]">
                  <p className="text-xs text-[#888]">Sources:</p>
                  {msg.citations.map((c, j) => (
                    <p key={j} className="text-xs text-[#6366f1]">{c}</p>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#1e1e1e] border border-[#2a2a2a] rounded-lg px-4 py-2.5 text-sm text-[#888]">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="shrink-0 flex gap-2 pt-4 border-t border-[#2a2a2a]">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 px-3 py-2.5 bg-[#1e1e1e] border border-[#2a2a2a] rounded text-sm text-white placeholder:text-[#555]"
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          onClick={send}
          disabled={loading}
          className="px-4 py-2.5 bg-[#6366f1] text-white rounded text-sm font-medium hover:bg-[#818cf8] disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
