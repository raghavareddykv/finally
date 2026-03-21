"use client";

import { useState } from "react";
import { useMarket } from "@/lib/market-context";
import { usePortfolio } from "@/hooks/usePortfolio";

export function TradeBar() {
  const { state } = useMarket();
  const { refresh } = usePortfolio();
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [feedback, setFeedback] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const tickers = Object.keys(state.tickers).sort();

  const executeTrade = async (side: "buy" | "sell") => {
    const selectedTicker = ticker || state.selectedTicker;
    const qty = parseFloat(quantity);

    if (!selectedTicker) {
      setFeedback({ message: "Select a ticker", type: "error" });
      return;
    }
    if (!qty || qty < 0.001) {
      setFeedback({ message: "Min quantity: 0.001", type: "error" });
      return;
    }

    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch("/api/portfolio/trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: selectedTicker,
          quantity: qty,
          side,
        }),
      });

      if (res.ok) {
        setFeedback({
          message: `${side === "buy" ? "Bought" : "Sold"} ${qty} ${selectedTicker}`,
          type: "success",
        });
        setQuantity("");
        refresh();
      } else {
        const err = await res.json();
        setFeedback({
          message: err.error || "Trade failed",
          type: "error",
        });
      }
    } catch {
      setFeedback({ message: "Network error", type: "error" });
    } finally {
      setSubmitting(false);
      setTimeout(() => setFeedback(null), 3000);
    }
  };

  const selectedTicker = ticker || state.selectedTicker || "";

  return (
    <div className="flex items-center gap-2 px-3 py-2 border-t border-terminal-border bg-terminal-panel">
      <select
        value={selectedTicker}
        onChange={(e) => setTicker(e.target.value)}
        className="bg-terminal-surface border border-terminal-border text-text-primary text-xs rounded px-2 py-1.5 focus:outline-none focus:border-accent-blue min-w-[80px]"
      >
        <option value="">Ticker</option>
        {tickers.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <input
        type="number"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") executeTrade("buy");
        }}
        placeholder="Qty"
        min="0.001"
        step="0.001"
        className="bg-terminal-surface border border-terminal-border text-text-primary text-xs rounded px-2 py-1.5 w-20 focus:outline-none focus:border-accent-blue"
      />

      <button
        onClick={() => executeTrade("buy")}
        disabled={submitting}
        className="bg-trade-green/20 text-trade-green border border-trade-green/30 text-xs font-semibold rounded px-3 py-1.5 hover:bg-trade-green/30 transition-colors disabled:opacity-50"
      >
        Buy
      </button>

      <button
        onClick={() => executeTrade("sell")}
        disabled={submitting}
        className="bg-trade-red/20 text-trade-red border border-trade-red/30 text-xs font-semibold rounded px-3 py-1.5 hover:bg-trade-red/30 transition-colors disabled:opacity-50"
      >
        Sell
      </button>

      {selectedTicker && state.tickers[selectedTicker] && (
        <span className="text-xs text-text-muted ml-1">
          @$
          {state.tickers[selectedTicker].price.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </span>
      )}

      {feedback && (
        <span
          className={`text-xs ml-2 ${
            feedback.type === "success" ? "text-trade-green" : "text-trade-red"
          }`}
        >
          {feedback.message}
        </span>
      )}
    </div>
  );
}
