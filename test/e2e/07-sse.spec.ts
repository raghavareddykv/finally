import { test, expect, waitForAppReady } from "./fixtures";

test.describe("SSE price streaming", () => {
  test("SSE delivers price events via EventSource", async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);

    // The SSE stream uses named events "price_update", not the default message event
    const pricesReceived = await page.evaluate(() => {
      return new Promise<boolean>((resolve) => {
        const es = new EventSource("/api/stream/prices");
        let received = false;

        es.addEventListener("price_update", () => {
          received = true;
          es.close();
          resolve(true);
        });

        es.onerror = () => {
          es.close();
          resolve(received);
        };

        setTimeout(() => {
          es.close();
          resolve(received);
        }, 8_000);
      });
    });

    expect(pricesReceived).toBeTruthy();
  });

  test("prices update on the page over time", async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);

    // Wait for SSE to deliver updates and prices to appear in the watchlist
    await page.waitForTimeout(3_000);

    // The watchlist should now show prices (not just "--")
    const bodyText = await page.locator("body").textContent();
    // Look for price patterns like "189.50" in the page
    const pricePattern = /\d{2,4}\.\d{2}/g;
    const matches = bodyText?.match(pricePattern) ?? [];
    // Should have several prices visible from the watchlist
    expect(matches.length).toBeGreaterThan(2);
  });

  test("SSE receives multiple events", async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);

    const multipleReceived = await page.evaluate(() => {
      return new Promise<boolean>((resolve) => {
        const es = new EventSource("/api/stream/prices");
        let messageCount = 0;

        es.addEventListener("price_update", () => {
          messageCount++;
          if (messageCount >= 3) {
            es.close();
            resolve(true);
          }
        });

        es.onerror = () => {
          // EventSource will auto-reconnect on error
        };

        setTimeout(() => {
          es.close();
          resolve(messageCount >= 2);
        }, 10_000);
      });
    });

    expect(multipleReceived).toBeTruthy();
  });

  test("price flash animations are set up", async ({ page }) => {
    await page.goto("/");
    await waitForAppReady(page);
    await page.waitForTimeout(3_000);

    // Check if the CSS for price flash animations exists in the page
    // The WatchlistPanel uses "price-flash-up" and "price-flash-down" classes
    const hasFlashCSS = await page.evaluate(() => {
      for (const sheet of document.styleSheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule.cssText?.includes("price-flash")) {
              return true;
            }
          }
        } catch {
          // Cross-origin stylesheet, skip
        }
      }
      return false;
    });

    // Also check if any elements have flash classes (they appear briefly)
    const hasFlashElements = await page.evaluate(() => {
      const els = document.querySelectorAll(
        ".price-flash-up, .price-flash-down"
      );
      return els.length > 0;
    });

    // At minimum, the flash CSS should be defined in the stylesheet
    // (Elements may or may not have the class at the exact moment we check)
    expect(hasFlashCSS || hasFlashElements).toBeTruthy();
  });
});
