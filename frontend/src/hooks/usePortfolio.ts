"use client";

import { usePortfolioContext } from "@/lib/portfolio-context";

export function usePortfolio() {
  return usePortfolioContext();
}
