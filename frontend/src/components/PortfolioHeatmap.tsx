"use client";

import { usePortfolio } from "@/hooks/usePortfolio";

function getHeatmapColor(pnlPercent: number): string {
  if (pnlPercent > 5) return "rgba(63, 185, 80, 0.6)";
  if (pnlPercent > 2) return "rgba(63, 185, 80, 0.4)";
  if (pnlPercent > 0) return "rgba(63, 185, 80, 0.2)";
  if (pnlPercent > -2) return "rgba(248, 81, 73, 0.2)";
  if (pnlPercent > -5) return "rgba(248, 81, 73, 0.4)";
  return "rgba(248, 81, 73, 0.6)";
}

export function PortfolioHeatmap() {
  const { portfolio } = usePortfolio();
  const positions = portfolio?.positions ?? [];

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-terminal-border">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          Portfolio Heatmap
        </h2>
      </div>
      <div className="flex-1 p-2">
        {positions.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <span className="text-text-muted text-sm">No positions yet</span>
          </div>
        ) : (
          <div className="h-full flex flex-wrap gap-1 content-start">
            {positions.map((pos) => {
              const value = Math.abs(pos.quantity * pos.current_price);
              const totalValue = positions.reduce(
                (sum, p) => sum + Math.abs(p.quantity * p.current_price),
                0
              );
              const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;

              return (
                <div
                  key={pos.ticker}
                  className="rounded flex flex-col items-center justify-center text-[10px] border border-terminal-border/50 overflow-hidden"
                  style={{
                    backgroundColor: getHeatmapColor(pos.pnl_pct),
                    flexBasis: `${Math.max(weight - 1, 15)}%`,
                    flexGrow: weight > 30 ? 2 : 1,
                    minHeight: "40px",
                  }}
                >
                  <span className="font-bold text-text-primary">
                    {pos.ticker}
                  </span>
                  <span
                    className={
                      pos.pnl_pct >= 0
                        ? "text-trade-green"
                        : "text-trade-red"
                    }
                  >
                    {pos.pnl_pct >= 0 ? "+" : ""}
                    {pos.pnl_pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
