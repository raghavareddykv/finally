"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useMarket } from "@/lib/market-context";
import { Sparkline } from "./Sparkline";
import type { WatchlistItem } from "@/lib/types";

function formatPrice(price: number): string {
  return price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatChange(current: number, previous: number): string {
  if (!previous || previous === 0) return "0.00%";
  const pct = ((current - previous) / previous) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

interface WatchlistRowProps {
  ticker: string;
  isSelected: boolean;
  onSelect: (ticker: string) => void;
}

function WatchlistRow({ ticker, isSelected, onSelect }: WatchlistRowProps) {
  const { state } = useMarket();
  const tickerData = state.tickers[ticker];
  const flashRef = useRef<HTMLDivElement>(null);
  const prevPriceRef = useRef<number | null>(null);

  useEffect(() => {
    if (!tickerData || !flashRef.current) return;
    const prev = prevPriceRef.current;
    prevPriceRef.current = tickerData.price;
    if (prev === null || prev === tickerData.price) return;

    const el = flashRef.current;
    const cls =
      tickerData.price > prev ? "price-flash-up" : "price-flash-down";
    el.classList.remove("price-flash-up", "price-flash-down");
    // Force reflow to restart animation
    void el.offsetWidth;
    el.classList.add(cls);
  }, [tickerData?.price, tickerData]);

  const price = tickerData?.price ?? 0;
  const prevPrice = tickerData?.previousPrice ?? price;
  const direction = tickerData?.changeDirection ?? "unchanged";
  const priceHistory = tickerData?.priceHistory ?? [];

  return (
    <div
      ref={flashRef}
      onClick={() => onSelect(ticker)}
      className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer rounded transition-colors ${
        isSelected
          ? "bg-accent-blue/10 border-l-2 border-accent-blue"
          : "hover:bg-terminal-surface border-l-2 border-transparent"
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-text-primary">
            {ticker}
          </span>
          <span
            className={`text-xs font-mono ${
              direction === "up"
                ? "text-trade-green"
                : direction === "down"
                  ? "text-trade-red"
                  : "text-text-primary"
            }`}
          >
            {price > 0 ? formatPrice(price) : "--"}
          </span>
        </div>
        <div className="flex items-center justify-between mt-0.5">
          <Sparkline data={priceHistory} width={60} height={16} />
          <span
            className={`text-[10px] ${
              price >= prevPrice ? "text-trade-green" : "text-trade-red"
            }`}
          >
            {price > 0 ? formatChange(price, prevPrice) : "--"}
          </span>
        </div>
      </div>
    </div>
  );
}

export function WatchlistPanel() {
  const { state, selectTicker } = useMarket();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [addInput, setAddInput] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch("/api/watchlist");
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.watchlist ?? data);
      }
    } catch {
      // will retry on next interaction
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const handleAdd = async () => {
    const ticker = addInput.trim().toUpperCase();
    if (!ticker) return;
    try {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker }),
      });
      if (res.ok) {
        setAddInput("");
        fetchWatchlist();
      }
    } catch {
      // ignore
    }
  };

  const handleRemove = async (ticker: string) => {
    try {
      const res = await fetch(`/api/watchlist/${ticker}`, { method: "DELETE" });
      if (res.ok) {
        fetchWatchlist();
      }
    } catch {
      // ignore
    }
  };

  const handleSelect = (ticker: string) => {
    selectTicker(
      state.selectedTicker === ticker ? null : ticker
    );
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-terminal-border">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          Watchlist
        </h2>
      </div>

      {/* Add ticker input */}
      <div className="flex gap-1 px-2 py-1.5 border-b border-terminal-border">
        <input
          type="text"
          value={addInput}
          onChange={(e) => setAddInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="Add ticker..."
          className="flex-1 bg-terminal-surface border border-terminal-border text-text-primary text-[10px] rounded px-1.5 py-1 focus:outline-none focus:border-accent-blue"
        />
        <button
          onClick={handleAdd}
          className="text-accent-blue text-[10px] font-semibold px-1.5 hover:text-accent-blue/70"
        >
          +
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="text-text-muted text-xs text-center py-8">
            Loading watchlist...
          </div>
        ) : watchlist.length === 0 ? (
          <div className="text-text-muted text-xs text-center py-8">
            No tickers in watchlist
          </div>
        ) : (
          watchlist.map((item) => (
            <div key={item.id} className="group relative">
              <WatchlistRow
                ticker={item.ticker}
                isSelected={state.selectedTicker === item.ticker}
                onSelect={handleSelect}
              />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemove(item.ticker);
                }}
                className="absolute right-1 top-1 hidden group-hover:block text-text-muted hover:text-trade-red text-[10px]"
                title="Remove"
              >
                x
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
