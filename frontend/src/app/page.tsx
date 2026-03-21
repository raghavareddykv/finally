"use client";

import { MarketProvider } from "@/lib/market-context";
import { PortfolioProvider } from "@/lib/portfolio-context";
import { Header } from "@/components/Header";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { ChartPanel } from "@/components/ChartPanel";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PnLChart } from "@/components/PnLChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";
import { SSEConnector } from "@/components/SSEConnector";

export default function Home() {
  return (
    <MarketProvider>
      <PortfolioProvider>
        <SSEConnector />
        <div className="flex flex-col h-full bg-terminal-bg">
          <Header />

          <div className="flex flex-1 min-h-0">
            {/* Main content area */}
            <div className="flex flex-col flex-1 min-w-0">
              {/* Top row: Watchlist + Chart + Heatmap */}
              <div className="flex flex-1 min-h-0">
                {/* Watchlist - left sidebar */}
                <div className="w-64 shrink-0 border-r border-terminal-border bg-terminal-panel overflow-hidden">
                  <WatchlistPanel />
                </div>

                {/* Chart - center main area */}
                <div className="flex-1 min-w-0 border-r border-terminal-border bg-terminal-bg overflow-hidden">
                  <ChartPanel />
                </div>

                {/* Heatmap - right of chart */}
                <div className="w-72 shrink-0 border-r border-terminal-border bg-terminal-panel overflow-hidden">
                  <PortfolioHeatmap />
                </div>
              </div>

              {/* Bottom row: P&L Chart + Positions Table */}
              <div className="flex h-56 shrink-0 border-t border-terminal-border">
                <div className="w-80 shrink-0 border-r border-terminal-border bg-terminal-panel overflow-hidden">
                  <PnLChart />
                </div>
                <div className="flex-1 min-w-0 bg-terminal-panel overflow-hidden">
                  <PositionsTable />
                </div>
              </div>

              <TradeBar />
            </div>

            {/* Chat panel - right sidebar */}
            <div className="w-80 shrink-0 overflow-hidden">
              <ChatPanel />
            </div>
          </div>
        </div>
      </PortfolioProvider>
    </MarketProvider>
  );
}
