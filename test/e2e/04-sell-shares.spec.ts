import { test, expect, waitForAppReady, executeTrade, getPortfolio } from "./fixtures";

test.describe("Sell shares", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);

    // Buy a small amount so we have something to sell
    await executeTrade(page, "GOOGL", "buy", 1);
  });

  test("selling shares increases cash and updates position", async ({
    page,
  }) => {
    const before = await getPortfolio(page);
    const googlBefore = before.positions?.find(
      (p: { ticker: string }) => p.ticker === "GOOGL"
    );
    expect(googlBefore).toBeDefined();

    await executeTrade(page, "GOOGL", "sell", 0.5);

    const after = await getPortfolio(page);
    expect(after.cash).toBeGreaterThan(before.cash);

    const googlAfter = after.positions?.find(
      (p: { ticker: string }) => p.ticker === "GOOGL"
    );
    expect(googlAfter).toBeDefined();
    expect(googlAfter.quantity).toBeLessThan(googlBefore.quantity);
  });

  test("selling all shares removes the position", async ({ page }) => {
    // Get current GOOGL quantity and sell it all
    const before = await getPortfolio(page);
    const googlBefore = before.positions?.find(
      (p: { ticker: string }) => p.ticker === "GOOGL"
    );
    expect(googlBefore).toBeDefined();

    await executeTrade(page, "GOOGL", "sell", googlBefore.quantity);

    const after = await getPortfolio(page);
    const googlAfter = after.positions?.find(
      (p: { ticker: string }) => p.ticker === "GOOGL"
    );
    expect(googlAfter).toBeUndefined();
  });

  test("selling more shares than owned fails", async ({ page }) => {
    const response = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "GOOGL", side: "sell", quantity: 999999 },
    });
    expect(response.ok()).toBeFalsy();
    const body = await response.json();
    expect(body.code).toBe("INSUFFICIENT_SHARES");
  });

  test("selling a ticker with no position fails", async ({ page }) => {
    const response = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "BA", side: "sell", quantity: 1 },
    });
    expect(response.ok()).toBeFalsy();
    const body = await response.json();
    expect(body.code).toBe("INSUFFICIENT_SHARES");
  });

  test("sell reflects in the UI positions table", async ({ page }) => {
    // Sell a small amount
    await executeTrade(page, "GOOGL", "sell", 0.1);

    // Reload and wait for portfolio data to load
    await page.reload();
    await waitForAppReady(page);
    await page.waitForTimeout(2_000);

    // Positions table should show GOOGL (we still hold some)
    const table = page.locator("table").first();
    await expect(table).toContainText("GOOGL");
  });
});
