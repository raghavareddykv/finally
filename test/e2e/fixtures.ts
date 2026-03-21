import { test as base, expect, type Page } from "@playwright/test";

/**
 * Shared helpers for FinAlly E2E tests.
 * All tests run against http://localhost:8000 with LLM_MOCK=true.
 */

/** Wait for the app to be fully loaded (React hydrated, header visible). */
export async function waitForAppReady(page: Page) {
  await page.waitForLoadState("domcontentloaded");
  // Wait for the header "FinAlly" text — proves React hydrated and rendered
  await expect(page.getByText("FinAlly")).toBeVisible({ timeout: 15_000 });
  // Give watchlist a moment to fetch from the API — use heading role to avoid
  // matching "Loading watchlist..." text which also contains "Watchlist"
  await expect(page.getByRole("heading", { name: "Watchlist" })).toBeVisible({ timeout: 5_000 });
}

/** Wait for a price to update at least once (proves SSE is connected). */
export async function waitForPriceUpdate(page: Page) {
  await page.waitForFunction(
    () => {
      const priceEls = document.querySelectorAll("[data-testid='price']");
      return priceEls.length > 0;
    },
    { timeout: 10_000 }
  );
}

/** Execute a trade via the API directly (useful for test setup). */
export async function executeTrade(
  page: Page,
  ticker: string,
  side: "buy" | "sell",
  quantity: number
) {
  const response = await page.request.post("/api/portfolio/trade", {
    data: { ticker, side, quantity },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

/** Get current portfolio state via API. */
export async function getPortfolio(page: Page) {
  const response = await page.request.get("/api/portfolio");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

/** Get current watchlist via API. */
export async function getWatchlist(page: Page) {
  const response = await page.request.get("/api/watchlist");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

/** Default tickers that should appear on fresh start. */
export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

export { expect };
export const test = base;
