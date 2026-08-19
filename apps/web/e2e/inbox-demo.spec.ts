import { expect, test } from "@playwright/test";

const API_BASE = "http://127.0.0.1:8103";

test.beforeEach(async ({ request }) => {
  const reset = await request.post(`${API_BASE}/api/v1/demo/reset`);
  expect(reset.ok()).toBeTruthy();
});

test("desktop completes the safe freight-delay operator path", async ({ page }) => {
  await page.goto("/inbox");
  await expect(page.getByText("Fixture mode", { exact: false })).toBeVisible();
  await expect(page.getByText("Jordan Lee", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("gmail", { exact: false }).first()).toContainText("fixture");

  await page.getByRole("button", { name: "Run safe draft" }).click();
  await expect(page.getByRole("status")).toContainText("Evidence-backed draft generated");

  await page.getByRole("button", { name: "Claim" }).click();
  await expect(page.getByRole("status")).toContainText("Conversation claimed");
  await page.getByRole("button", { name: "Start SLA" }).click();
  await expect(page.getByRole("status")).toContainText("SLA timer started");

  const draft = page.getByLabel("Editable response draft");
  await draft.fill(
    "Hi Jordan,\n\nWe are checking with the carrier for a confirmed delivery date.\n\nBest,\nFreight Operations",
  );
  await page.getByRole("button", { name: "Save edit" }).click();
  await expect(page.getByRole("status")).toContainText("Draft edited");

  const approve = page.getByRole("button", { name: /^Approve v\d+$/ });
  await expect(approve).toBeEnabled();
  const approvedVersion = await approve.textContent();
  await approve.click();
  await expect(page.getByRole("status")).toContainText("Exact draft version approved");
  expect(approvedVersion).toMatch(/^Approve v\d+$/);

  await page.getByRole("button", { name: "Send approved" }).click();
  await expect(page.getByRole("status")).toContainText("no live provider was called");
  await expect(page.getByText("gmail", { exact: false }).first()).toContainText("fixture");
  await expect(page.getByText("Fixture mode", { exact: false })).toBeVisible();

  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "Analytics is planned" })).toBeVisible();
  await expect(page.getByText("does not implement this workflow yet")).toBeVisible();
});

test("mobile keeps the workbench usable and blocks a failed send", async ({ page }) => {
  await page.goto("/inbox");
  await expect(page.getByText("Jordan Lee", { exact: true }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => window.innerWidth),
  );

  await page.getByRole("button", { name: "Run safe draft" }).click();
  await expect(page.getByLabel("Editable response draft")).toBeVisible();
  const approve = page.getByRole("button", { name: /^Approve v\d+$/ });
  await approve.click();
  await expect(page.getByRole("status")).toContainText("Exact draft version approved");

  await page.route("**/api/v1/drafts/*/send", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ message: "send_blocked" }),
    });
  });
  const send = page.getByRole("button", { name: "Send approved" });
  await send.click();
  await expect(page.locator(".error-banner")).toContainText("send_blocked");
  await expect(send).toBeDisabled();
  await expect(page.getByText("Fixture mode", { exact: false })).toBeVisible();
});
