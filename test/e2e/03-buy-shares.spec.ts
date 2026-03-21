import { test, expect, waitForAppReady, getPortfolio } from "./fixtures";

test.describe("Buy shares", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);
  });

  test("buying via API works correctly", async ({ page }) => {
    const before = await getPortfolio(page);

    const tradeResponse = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "MSFT", side: "buy", quantity: 0.01 },
    });
    expect(tradeResponse.ok()).toBeTruthy();

    const after = await getPortfolio(page);
    expect(after.cash).toBeLessThan(before.cash);

    const msftPosition = after.positions?.find(
      (p: { ticker: string }) => p.ticker === "MSFT"
    );
    expect(msftPosition).toBeDefined();
    expect(msftPosition.quantity).toBeGreaterThanOrEqual(0.01);
  });

  test("buying shares via UI trade bar", async ({ page }) => {
    // Wait for SSE to populate ticker options in the trade bar select
    // The select is populated from SSE price_update events via state.tickers
    const tickerSelect = page.locator("select").first();

    // Wait until the select has option elements beyond the default "Ticker" placeholder
    await page.waitForFunction(
      () => {
        const select = document.querySelector("select");
        return select && select.options.length > 1;
      },
      { timeout: 15_000 }
    );

    const before = await getPortfolio(page);

    const quantityInput = page.locator("input[placeholder='Qty']");
    const buyButton = page.getByRole("button", { name: "Buy" });

    await tickerSelect.selectOption("AAPL");
    await quantityInput.fill("0.01");
    await buyButton.click();

    // Wait for trade to process
    await page.waitForTimeout(2_000);

    const after = await getPortfolio(page);
    expect(after.cash).toBeLessThan(before.cash);
  });

  test("buying with insufficient cash fails", async ({ page }) => {
    const response = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", side: "buy", quantity: 100000 },
    });
    expect(response.ok()).toBeFalsy();
    const body = await response.json();
    expect(body.code).toBe("INSUFFICIENT_CASH");
  });

  test("buying below minimum quantity fails", async ({ page }) => {
    const response = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", side: "buy", quantity: 0.0001 },
    });
    expect(response.ok()).toBeFalsy();
    const body = await response.json();
    expect(body.code).toBe("BELOW_MINIMUM_QUANTITY");
  });
});
