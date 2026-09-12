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
  await expect(page.getByRole("heading", { name: "Operational analytics" })).toBeVisible();
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

test("fixture routes and draft retry keep operator work local", async ({ page }) => {
  await page.goto("/customers/customer-jordan-lee");
  await expect(page.getByRole("heading", { name: "Customer profile" })).toBeVisible();
  await expect(page.getByText("Jordan Lee", { exact: false })).toBeVisible();

  await page.goto("/rules");
  await expect(page.getByRole("heading", { name: "Assignment rules" })).toBeVisible();
  await expect(page.getByText("rule-shipment-delay", { exact: true })).toBeVisible();

  await page.goto("/settings/integrations");
  await expect(page.getByRole("heading", { name: "Fixture connectors" })).toBeVisible();
  await expect(page.getByText("not_configured", { exact: false })).toBeVisible();

  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "Operational analytics" })).toBeVisible();

  await page.goto("/inbox");
  await page.getByRole("button", { name: "Simulate draft failure" }).click();
  await expect(page.locator(".error-banner")).toContainText("fixture_transient_draft_failure");
  await page.getByRole("button", { name: "Retry draft (1/3)" }).click();
  await expect(page.getByLabel("Editable response draft")).toBeVisible();
});

test("visible polling preserves a dirty draft and offers stale recovery", async ({ page, request }) => {
  await page.goto("/inbox");
  await page.getByRole("button", { name: "Run safe draft" }).click();
  const draft = page.getByLabel("Editable response draft");
  await draft.fill("Unsaved operator correction.");

  const current = await request.get(`${API_BASE}/api/v1/conversations/conversation-ft-204`);
  const claimed = await request.post(`${API_BASE}/api/v1/conversations/conversation-ft-204/claim`, {
    data: { actor_id: "second-operator", expected_version: (await current.json()).version },
  });
  expect(claimed.ok()).toBeTruthy();

  await expect(page.getByText("Version conflict", { exact: false })).toBeVisible({ timeout: 8_000 });
  await expect(draft).toHaveValue("Unsaved operator correction.");
  await page.getByRole("button", { name: "Reapply my draft text" }).click();
  await expect(draft).toHaveValue("Unsaved operator correction.");
});

test("secondary routes show a safe error when their fixture read fails", async ({ page }) => {
  await page.route("**/api/v1/customers/customer-jordan-lee?workspace_id=demo-workspace", async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ message: "fixture_unavailable" }) });
  });
  await page.goto("/customers/customer-jordan-lee");
  await expect(page.locator(".error-banner")).toContainText("Fixture data is unavailable");
});

test("explicit conversation selection replaces the current detail", async ({ page }) => {
  await page.route("**/api/v1/conversations?workspace_id=demo-workspace", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const second = { ...body.items[0], id: "conversation-ft-205", subject: "Second fixture conversation" };
    await route.fulfill({ response, json: { ...body, items: [body.items[0], second] } });
  });
  await page.route("**/api/v1/conversations/conversation-ft-205*", async (route) => {
    const response = await route.fetch({ url: "http://127.0.0.1:8103/api/v1/conversations/conversation-ft-204?workspace_id=demo-workspace" });
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, id: "conversation-ft-205", subject: "Second fixture conversation" } });
  });

  await page.goto("/inbox");
  await page.getByRole("button", { name: /Second fixture conversation/ }).click();
  await expect(page.getByRole("heading", { name: "Second fixture conversation" })).toBeVisible();
});

test("customer route requests the selected customer id", async ({ page }) => {
  let requestedPath = "";
  await page.route("**/api/v1/customers/*?*", async (route) => {
    requestedPath = new URL(route.request().url()).pathname;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ name: "Acme Customer", address: "Fixture address", conversations: [] }),
    });
  });

  await page.goto("/customers/customer-acme");
  await expect(page.getByText("Acme Customer", { exact: false })).toBeVisible();
  expect(requestedPath).toBe("/api/v1/customers/customer-acme");
});

test("draft failure simulation stops after three attempts", async ({ page }) => {
  await page.goto("/inbox");
  const simulate = page.getByRole("button", { name: "Simulate draft failure" });
  await simulate.click();
  await simulate.click();
  await page.reload();
  await expect(page.getByRole("button", { name: "Retry draft (2/3)" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Simulate draft failure" })).toBeVisible();
  await simulate.click();
  await expect(page.getByText("Manual recovery required after three failed attempts.")).toBeVisible();
  await expect(simulate).toBeHidden();
});
