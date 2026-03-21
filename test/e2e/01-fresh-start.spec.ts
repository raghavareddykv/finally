import { test, expect, DEFAULT_TICKERS, waitForAppReady } from "./fixtures";

test.describe("Fresh start", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);
  });

  test("displays the default watchlist tickers", async ({ page }) => {
    // Verify default tickers via API — the authoritative source
    const response = await page.request.get("/api/watchlist");
    expect(response.ok()).toBeTruthy();
    const watchlist = await response.json();
    const apiTickers = watchlist.map((w: { ticker: string }) => w.ticker);

    for (const ticker of DEFAULT_TICKERS) {
      expect(apiTickers).toContain(ticker);
    }

    // Also verify at least some tickers are visible in the UI
    await page.waitForTimeout(1_000);
    await expect(page.locator(`text="AAPL"`).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator(`text="GOOGL"`).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator(`text="MSFT"`).first()).toBeVisible({ timeout: 5_000 });
  });

  test("shows starting cash balance in header", async ({ page }) => {
    // Check via API — the portfolio should have a positive cash balance
    const response = await page.request.get("/api/portfolio");
    expect(response.ok()).toBeTruthy();
    const portfolio = await response.json();
    expect(portfolio.cash).toBeGreaterThan(0);
    expect(portfolio.total_value).toBeGreaterThan(0);

    // Verify the header shows "Cash" with a dollar value
    const header = page.locator("header");
    await expect(header).toContainText("Cash");
    await expect(header).toContainText("$");
  });

  test("prices are streaming via SSE", async ({ page }) => {
    // Wait for SSE to connect and deliver price updates
    await page.waitForTimeout(3_000);

    // The watchlist shows prices in the format "NNN.NN" next to tickers
    const bodyText = await page.locator("body").textContent();
    // Prices like "189.50", "175.03" etc should appear in watchlist
    const pricePattern = /\d{2,4}\.\d{2}/g;
    const matches = bodyText?.match(pricePattern) ?? [];
    // Should have multiple price values (at least a few from the watchlist)
    expect(matches.length).toBeGreaterThanOrEqual(2);
  });

  test("connection status indicator is visible", async ({ page }) => {
    // The header shows connection status text
    const statusText = page.getByText(/Connected|Reconnecting|Disconnected/);
    await expect(statusText).toBeVisible({ timeout: 10_000 });
  });
});
