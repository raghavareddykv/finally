"use client";

import { usePortfolio } from "@/hooks/usePortfolio";

export function PnLChart() {
  const { history } = usePortfolio();

  const width = 300;
  const height = 160;
  const padding = { top: 10, right: 10, bottom: 20, left: 50 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const hasData = history.length >= 2;
  const values = history.map((s) => s.total_value);
  const min = hasData ? Math.min(...values) : 0;
  const max = hasData ? Math.max(...values) : 10000;
  const range = max - min || 1;
  const startValue = hasData ? values[0] : 10000;
  const currentValue = hasData ? values[values.length - 1] : 10000;
  const isUp = currentValue >= startValue;

  const points = hasData
    ? history
        .map((s, i) => {
          const x =
            padding.left + (i / (history.length - 1)) * chartWidth;
          const y =
            padding.top +
            ((max - s.total_value) / range) * chartHeight;
          return `${x},${y}`;
        })
        .join(" ")
    : "";

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-terminal-border flex items-center justify-between">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          P&L
        </h2>
        {hasData && (
          <span
            className={`text-[10px] font-mono ${
              isUp ? "text-trade-green" : "text-trade-red"
            }`}
          >
            $
            {currentValue.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        )}
      </div>
      <div className="flex-1 flex items-center justify-center p-2">
        {!hasData ? (
          <span className="text-text-muted text-sm">No portfolio history</span>
        ) : (
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="w-full h-full"
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
              const y = padding.top + frac * chartHeight;
              const val = max - frac * range;
              return (
                <g key={frac}>
                  <line
                    x1={padding.left}
                    y1={y}
                    x2={width - padding.right}
                    y2={y}
                    stroke="#1a1a2e"
                    strokeWidth="0.5"
                  />
                  <text
                    x={padding.left - 4}
                    y={y + 3}
                    textAnchor="end"
                    fill="#6e7681"
                    fontSize="7"
                  >
                    {val >= 1000
                      ? `${(val / 1000).toFixed(1)}k`
                      : val.toFixed(0)}
                  </text>
                </g>
              );
            })}

            {/* Price line */}
            <polyline
              fill="none"
              stroke={isUp ? "#3fb950" : "#f85149"}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={points}
            />

            {/* Area fill */}
            <polygon
              fill={isUp ? "rgba(63,185,80,0.1)" : "rgba(248,81,73,0.1)"}
              points={`${padding.left},${padding.top + chartHeight} ${points} ${width - padding.right},${padding.top + chartHeight}`}
            />
          </svg>
        )}
      </div>
    </div>
  );
}
