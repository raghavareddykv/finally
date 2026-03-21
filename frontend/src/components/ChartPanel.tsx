"use client";

import { useEffect, useRef, useCallback } from "react";
import { useMarket } from "@/lib/market-context";

// Lightweight Charts types for our use
interface IChartApi {
  applyOptions: (options: Record<string, unknown>) => void;
  addSeries: (seriesDefinition: unknown, options?: Record<string, unknown>) => ISeriesApi;
  timeScale: () => { fitContent: () => void };
  remove: () => void;
  resize: (width: number, height: number) => void;
}

interface ISeriesApi {
  update: (bar: { time: number; value: number }) => void;
  setData: (data: { time: number; value: number }[]) => void;
  applyOptions: (options: Record<string, unknown>) => void;
}

export function ChartPanel() {
  const { state } = useMarket();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi | null>(null);
  const currentTickerRef = useRef<string | null>(null);
  const lwcModuleRef = useRef<Record<string, unknown> | null>(null);

  const selectedTicker = state.selectedTicker;
  const tickerData = selectedTicker ? state.tickers[selectedTicker] : null;

  const initChart = useCallback(async () => {
    if (!containerRef.current) return;

    // Dynamically import lightweight-charts (browser only)
    if (!lwcModuleRef.current) {
      lwcModuleRef.current = await import("lightweight-charts");
    }
    const lwc = lwcModuleRef.current;
    const createChart = lwc.createChart as (
      container: HTMLElement,
      options: Record<string, unknown>
    ) => IChartApi;
    const LineSeries = lwc.LineSeries;

    // Destroy previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
    }

    const rect = containerRef.current.getBoundingClientRect();

    const chart = createChart(containerRef.current, {
      width: rect.width,
      height: rect.height,
      layout: {
        background: { color: "#0d1117" },
        textColor: "#8b949e",
        fontFamily: "var(--font-geist-mono), monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1a1a2e" },
        horzLines: { color: "#1a1a2e" },
      },
      crosshair: {
        vertLine: { color: "#30363d", labelBackgroundColor: "#1a1a2e" },
        horzLine: { color: "#30363d", labelBackgroundColor: "#1a1a2e" },
      },
      rightPriceScale: {
        borderColor: "#30363d",
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: true,
        secondsVisible: true,
      },
    });

    const series = chart.addSeries(LineSeries, {
      color: "#209dd7",
      lineWidth: 2,
      priceLineVisible: true,
      priceLineColor: "#209dd7",
      lastValueVisible: true,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    return chart;
  }, []);

  // Initialize/rebuild chart when selected ticker changes
  useEffect(() => {
    if (!selectedTicker) {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
      currentTickerRef.current = null;
      return;
    }

    if (currentTickerRef.current !== selectedTicker) {
      currentTickerRef.current = selectedTicker;
      initChart().then(() => {
        // Load historical sparkline data as initial series data
        const data = state.tickers[selectedTicker];
        if (data && seriesRef.current) {
          const now = Math.floor(Date.now() / 1000);
          const historyData = data.priceHistory.map((price, i) => ({
            time: now - (data.priceHistory.length - 1 - i) as number,
            value: price,
          }));
          seriesRef.current.setData(historyData);
          chartRef.current?.timeScale().fitContent();
        }
      });
    }
  }, [selectedTicker, initChart, state.tickers]);

  // Push real-time updates
  useEffect(() => {
    if (
      !selectedTicker ||
      !tickerData ||
      !seriesRef.current ||
      currentTickerRef.current !== selectedTicker
    ) {
      return;
    }

    const time = Math.floor(new Date(tickerData.timestamp).getTime() / 1000);
    seriesRef.current.update({
      time,
      value: tickerData.price,
    });
  }, [selectedTicker, tickerData]);

  // Handle resize
  useEffect(() => {
    if (!containerRef.current || !chartRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chartRef.current?.resize(width, height);
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [selectedTicker]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-terminal-border flex items-center justify-between">
        <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          {selectedTicker ? `Chart — ${selectedTicker}` : "Chart"}
        </h2>
        {tickerData && (
          <span
            className={`text-xs font-mono ${
              tickerData.changeDirection === "up"
                ? "text-trade-green"
                : tickerData.changeDirection === "down"
                  ? "text-trade-red"
                  : "text-text-primary"
            }`}
          >
            $
            {tickerData.price.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        )}
      </div>
      <div ref={containerRef} className="flex-1 relative">
        {!selectedTicker && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-text-muted text-sm">
              Select a ticker to view chart
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
