import { test, expect, waitForAppReady } from "./fixtures";

test.describe("Watchlist management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);
    // Wait for watchlist tickers to load
    await page.waitForTimeout(1_000);
  });

  test("can add a ticker to the watchlist", async ({ page }) => {
    // First remove DIS if it already exists (from a previous test run)
    await page.request.delete("/api/watchlist/DIS");

    // The add input has placeholder "Add ticker..."
    const addInput = page.locator("input[placeholder='Add ticker...']");
    // The add button is a "+" text button
    const addButton = page.locator("button:has-text('+')");

    await addInput.fill("DIS");
    await addButton.click();

    // Verify DIS appears in the watchlist
    await expect(
      page.locator("text='DIS'").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("can remove a ticker from the watchlist via API", async ({ page }) => {
    // Make sure DIS is in the watchlist before removing
    await page.request.post("/api/watchlist", { data: { ticker: "DIS" } });

    const response = await page.request.delete("/api/watchlist/DIS");
    expect(response.ok()).toBeTruthy();

    // Verify DIS is gone from the watchlist
    const watchlist = await page.request.get("/api/watchlist");
    const watchlistBody = await watchlist.json();
    const tickers = watchlistBody.map((w: { ticker: string }) => w.ticker);
    expect(tickers).not.toContain("DIS");
  });

  test("rejects invalid ticker via API", async ({ page }) => {
    const response = await page.request.post("/api/watchlist", {
      data: { ticker: "INVALID_TICKER_XYZ" },
    });
    expect(response.ok()).toBeFalsy();
    const body = await response.json();
    expect(body.error).toBeDefined();
    expect(body.code).toBe("INVALID_TICKER");
  });

  test("rejects duplicate ticker via API", async ({ page }) => {
    // AAPL is always in the default watchlist
    const response = await page.request.post("/api/watchlist", {
      data: { ticker: "AAPL" },
    });
    expect(response.ok()).toBeFalsy();
    const body = await response.json();
    expect(body.code).toBe("TICKER_ALREADY_WATCHED");
  });
});
