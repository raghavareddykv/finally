import { test, expect } from "./fixtures";

test.describe("Health check", () => {
  test("API health endpoint returns OK", async ({ page }) => {
    const response = await page.request.get("/api/health");
    expect(response.ok()).toBeTruthy();
  });

  test("static frontend is served at root", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.ok()).toBeTruthy();
    // Should return HTML
    const contentType = response?.headers()["content-type"];
    expect(contentType).toContain("text/html");
  });
});
