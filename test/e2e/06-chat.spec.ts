import { test, expect, waitForAppReady } from "./fixtures";

test.describe("AI chat (mocked)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);
  });

  test("chat API returns a mocked response", async ({ page }) => {
    const response = await page.request.post("/api/chat", {
      data: { message: "What is my portfolio worth?" },
    });
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.message).toBeDefined();
    expect(typeof body.message).toBe("string");
    expect(body.message.length).toBeGreaterThan(0);
  });

  test("can send a chat message via UI and see response", async ({ page }) => {
    // The chat input has placeholder "Ask FinAlly..."
    const chatInput = page.locator("input[placeholder='Ask FinAlly...']");
    const sendButton = page.getByRole("button", { name: "Send" });

    await chatInput.fill("Hello");
    await sendButton.click();

    // Wait for the assistant response to appear in the chat
    await page.waitForTimeout(3_000);

    // The mock returns a message like "I'm FinAlly, your AI trading assistant..."
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).toContain("FinAlly");
    // Should contain the user's message too
    expect(bodyText).toContain("Hello");
  });

  test("chat response with trade action executes the trade", async ({
    page,
  }) => {
    // Mock recognizes "buy N TICKER" pattern - use a tiny quantity to avoid insufficient cash
    const response = await page.request.post("/api/chat", {
      data: { message: "Buy 0.01 AAPL" },
    });
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.message).toBeDefined();
    expect(body.trades).toBeDefined();
    expect(body.trades.length).toBeGreaterThan(0);
    expect(body.trades[0].ticker).toBe("AAPL");
    expect(body.trades[0].side).toBe("buy");
    expect(body.trades[0].quantity).toBe(0.01);

    expect(body.trade_results).toBeDefined();
    expect(body.trade_results.length).toBeGreaterThan(0);
    expect(body.trade_results[0].status).toBe("executed");

    // Verify the trade was applied to the portfolio
    const portfolio = await page.request.get("/api/portfolio");
    const portfolioBody = await portfolio.json();
    const aaplPos = portfolioBody.positions?.find(
      (p: { ticker: string }) => p.ticker === "AAPL"
    );
    expect(aaplPos).toBeDefined();
    expect(aaplPos.quantity).toBeGreaterThanOrEqual(0.01);
  });

  test("chat response with watchlist action modifies watchlist", async ({
    page,
  }) => {
    // First make sure PYPL is not already in the watchlist
    // (could be added by a previous test run or chat test)
    await page.request.delete("/api/watchlist/PYPL");

    // Mock recognizes "add TICKER" pattern
    const response = await page.request.post("/api/chat", {
      data: { message: "Add PYPL to my watchlist" },
    });
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.message).toBeDefined();
    expect(body.watchlist_changes).toBeDefined();
    expect(body.watchlist_changes.length).toBeGreaterThan(0);
    expect(body.watchlist_changes[0].ticker).toBe("PYPL");
    expect(body.watchlist_changes[0].action).toBe("add");

    expect(body.watchlist_results).toBeDefined();
    expect(body.watchlist_results.length).toBeGreaterThan(0);
    expect(body.watchlist_results[0].status).toBe("added");

    // Verify PYPL was actually added
    const watchlist = await page.request.get("/api/watchlist");
    const watchlistBody = await watchlist.json();
    const tickers = watchlistBody.map((w: { ticker: string }) => w.ticker);
    expect(tickers).toContain("PYPL");
  });
});
