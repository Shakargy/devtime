import { test, expect } from "@playwright/test";

test("sidebar shows the upload and export buttons", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Upload")).toBeVisible();
});
