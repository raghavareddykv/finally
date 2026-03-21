import { test, expect, waitForAppReady, executeTrade, getPortfolio } from "./fixtures";

test.describe("Portfolio visualization", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);

    // Buy small positions to populate the portfolio (uses minimal cash)
    await executeTrade(page, "AAPL", "buy", 0.1);
    await executeTrade(page, "TSLA", "buy", 0.1);
    await executeTrade(page, "NVDA", "buy", 0.01);
  });

  test("portfolio endpoint returns positions with P&L", async ({ page }) => {
    const portfolio = await getPortfolio(page);
    expect(portfolio.cash).toBeDefined();
    expect(portfolio.positions).toBeDefined();
    expect(portfolio.positions.length).toBeGreaterThanOrEqual(3);

    for (const pos of portfolio.positions) {
      expect(pos.ticker).toBeDefined();
      expect(pos.quantity).toBeGreaterThan(0);
      expect(pos.avg_cost).toBeGreaterThan(0);
      expect(pos.current_price).toBeGreaterThan(0);
      expect(pos.market_value).toBeDefined();
      expect(typeof pos.unrealized_pnl).toBe("number");
      expect(typeof pos.pnl_pct).toBe("number");
    }
  });

  test("portfolio history endpoint returns snapshots", async ({ page }) => {
    const response = await page.request.get("/api/portfolio/history");
    expect(response.ok()).toBeTruthy();
    const history = await response.json();

    // Should have snapshots recorded after trades
    expect(Array.isArray(history)).toBeTruthy();
    expect(history.length).toBeGreaterThan(0);
    expect(history[0].total_value).toBeDefined();
    expect(history[0].recorded_at).toBeDefined();
  });

  test("positions table shows all held positions", async ({ page }) => {
    // Reload to get fresh UI state
    await page.reload();
    await waitForAppReady(page);
    await page.waitForTimeout(2_000);

    // The positions table should show our tickers
    const table = page.locator("table").first();
    await expect(table).toContainText("AAPL");
    await expect(table).toContainText("TSLA");
    await expect(table).toContainText("NVDA");
  });

  test("header shows portfolio total value", async ({ page }) => {
    await page.reload();
    await waitForAppReady(page);
    await page.waitForTimeout(1_000);

    // The header contains "Portfolio" label and a dollar value
    const header = page.locator("header");
    await expect(header).toContainText("Portfolio");
    await expect(header).toContainText("$");
  });

  test("heatmap section is visible", async ({ page }) => {
    await page.reload();
    await waitForAppReady(page);
    await page.waitForTimeout(1_000);

    // Look for "Portfolio Heatmap" heading
    await expect(page.getByText("Portfolio Heatmap")).toBeVisible();
  });

  test("P&L section is visible", async ({ page }) => {
    await page.reload();
    await waitForAppReady(page);

    await expect(page.getByText("P&L").first()).toBeVisible();
  });
});
