"use client";

import { useState, useRef, useEffect } from "react";
import { usePortfolio } from "@/hooks/usePortfolio";
import type { ChatMessage, ChatResponse } from "@/lib/types";

function ActionBadge({
  children,
  variant,
}: {
  children: React.ReactNode;
  variant: "trade" | "watchlist";
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded ${
        variant === "trade"
          ? "bg-accent-blue/10 text-accent-blue border border-accent-blue/20"
          : "bg-accent-yellow/10 text-accent-yellow border border-accent-yellow/20"
      }`}
    >
      {children}
    </span>
  );
}

function ChatMessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-2`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-xs ${
          isUser
            ? "bg-accent-purple/20 text-text-primary border border-accent-purple/30"
            : "bg-terminal-surface text-text-primary border border-terminal-border"
        }`}
      >
        <div className="whitespace-pre-wrap">{msg.content}</div>

        {msg.actions?.trades && msg.actions.trades.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.actions.trades.map((trade, i) => (
              <ActionBadge key={i} variant="trade">
                {trade.side === "buy" ? "BUY" : "SELL"} {trade.quantity}{" "}
                {trade.ticker}
              </ActionBadge>
            ))}
          </div>
        )}

        {msg.actions?.watchlist_changes &&
          msg.actions.watchlist_changes.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {msg.actions.watchlist_changes.map((change, i) => (
                <ActionBadge key={i} variant="watchlist">
                  {change.action === "add" ? "+" : "-"} {change.ticker}
                </ActionBadge>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}

export function ChatPanel() {
  const [isOpen, setIsOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { refresh } = usePortfolio();

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (res.ok) {
        const data: ChatResponse = await res.json();
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.message,
          actions: {
            trades: data.trades,
            watchlist_changes: data.watchlist_changes,
          },
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // Refresh portfolio if trades were executed
        if (data.trades && data.trades.length > 0) {
          refresh();
        }
      } else {
        const err = await res.json().catch(() => ({ error: "Unknown error" }));
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: err.error || "Something went wrong. Please try again.",
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Network error. Please check your connection.",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed right-4 bottom-4 bg-accent-purple text-white text-xs font-semibold rounded-full px-4 py-2 shadow-lg hover:bg-accent-purple/80 transition-colors z-10"
      >
        AI Chat
      </button>
    );
  }

  return (
    <div className="flex flex-col h-full border-l border-terminal-border bg-terminal-panel">
      <div className="flex items-center justify-between px-3 py-2 border-b border-terminal-border">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          AI Assistant
        </h2>
        <button
          onClick={() => setIsOpen(false)}
          className="text-text-muted hover:text-text-primary text-xs"
        >
          Hide
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3">
        {messages.length === 0 ? (
          <div className="text-text-muted text-xs text-center py-8">
            Ask me about your portfolio, market analysis, or to execute trades.
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessageBubble key={msg.id} msg={msg} />
          ))
        )}

        {loading && (
          <div className="flex justify-start mb-2">
            <div className="bg-terminal-surface text-text-muted border border-terminal-border rounded-lg px-3 py-2 text-xs">
              <span className="inline-flex gap-1">
                <span className="animate-pulse">.</span>
                <span className="animate-pulse" style={{ animationDelay: "0.2s" }}>.</span>
                <span className="animate-pulse" style={{ animationDelay: "0.4s" }}>.</span>
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="p-2 border-t border-terminal-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask FinAlly..."
            disabled={loading}
            className="flex-1 bg-terminal-surface border border-terminal-border text-text-primary text-xs rounded px-2 py-1.5 focus:outline-none focus:border-accent-blue disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="bg-accent-purple text-white text-xs font-semibold rounded px-3 py-1.5 hover:bg-accent-purple/80 transition-colors disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
