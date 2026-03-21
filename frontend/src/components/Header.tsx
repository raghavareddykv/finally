"use client";

import { useMarket } from "@/lib/market-context";
import { usePortfolio } from "@/hooks/usePortfolio";
import { ConnectionStatus } from "./ConnectionStatus";

function formatCurrency(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function Header() {
  const { state } = useMarket();
  const { portfolio } = usePortfolio();

  const totalValue = portfolio?.total_value ?? 10000;
  const cashBalance = portfolio?.cash ?? 10000;
  const pnl = totalValue - 10000;
  const pnlPercent = ((totalValue - 10000) / 10000) * 100;

  return (
    <header className="flex items-center justify-between px-4 py-2 border-b border-terminal-border bg-terminal-panel">
      <div className="flex items-center gap-3">
        <h1 className="text-accent-yellow font-bold text-lg tracking-wide">
          FinAlly
        </h1>
        <span className="text-text-muted text-xs">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted">Portfolio</span>
            <span className="text-text-primary font-semibold">
              ${formatCurrency(totalValue)}
            </span>
            <span
              className={`text-xs ${
                pnl >= 0 ? "text-trade-green" : "text-trade-red"
              }`}
            >
              {pnl >= 0 ? "+" : ""}
              {pnlPercent.toFixed(2)}%
            </span>
          </div>
          <div>
            <span className="text-text-muted">Cash </span>
            <span className="text-text-primary font-semibold">
              ${formatCurrency(cashBalance)}
            </span>
          </div>
        </div>
        <ConnectionStatus status={state.connectionStatus} />
      </div>
    </header>
  );
}
