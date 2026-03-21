"use client";

import { usePortfolio } from "@/hooks/usePortfolio";

function formatCurrency(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function PositionsTable() {
  const { portfolio, loading } = usePortfolio();
  const positions = portfolio?.positions ?? [];

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-terminal-border">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          Positions
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-terminal-panel">
            <tr className="text-text-muted border-b border-terminal-border">
              <th className="text-left px-3 py-1.5 font-medium">Ticker</th>
              <th className="text-right px-3 py-1.5 font-medium">Qty</th>
              <th className="text-right px-3 py-1.5 font-medium">Avg Cost</th>
              <th className="text-right px-3 py-1.5 font-medium">Price</th>
              <th className="text-right px-3 py-1.5 font-medium">P&L</th>
              <th className="text-right px-3 py-1.5 font-medium">%</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={6}
                  className="text-center text-text-muted py-6 px-3"
                >
                  Loading positions...
                </td>
              </tr>
            ) : positions.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="text-center text-text-muted py-6 px-3"
                >
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((pos) => (
                <tr
                  key={pos.ticker}
                  className="border-b border-terminal-border/50 hover:bg-terminal-surface/50"
                >
                  <td className="px-3 py-1.5 font-semibold text-text-primary">
                    {pos.ticker}
                  </td>
                  <td className="text-right px-3 py-1.5 text-text-secondary">
                    {pos.quantity.toLocaleString("en-US", {
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 3,
                    })}
                  </td>
                  <td className="text-right px-3 py-1.5 text-text-secondary">
                    ${formatCurrency(pos.avg_cost)}
                  </td>
                  <td className="text-right px-3 py-1.5 text-text-primary">
                    ${formatCurrency(pos.current_price)}
                  </td>
                  <td
                    className={`text-right px-3 py-1.5 font-mono ${
                      pos.unrealized_pnl >= 0
                        ? "text-trade-green"
                        : "text-trade-red"
                    }`}
                  >
                    {pos.unrealized_pnl >= 0 ? "+" : ""}$
                    {formatCurrency(Math.abs(pos.unrealized_pnl))}
                  </td>
                  <td
                    className={`text-right px-3 py-1.5 font-mono ${
                      pos.pnl_pct >= 0
                        ? "text-trade-green"
                        : "text-trade-red"
                    }`}
                  >
                    {pos.pnl_pct >= 0 ? "+" : ""}
                    {pos.pnl_pct.toFixed(2)}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
