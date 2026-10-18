import { expect, test } from "@playwright/test";

test("fixture HTTP slice: ask, inspect, expand, deduplicate, filter and replace graph", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Ask Brain", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/desktop-empty.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Who owns the authentication service?" })
    .click();
  await expect(page.locator(".brain-answer")).toContainText(
    "Platform Engineering",
  );
  await expect(page.locator(".react-flow__node")).toHaveCount(12);
  await expect(page.locator(".brain-answer")).toContainText(
    "Development fixture",
  );
  const auth = page.locator(
    '.react-flow__node[data-id="service:authentication-api"]',
  );
  await auth.click();
  await expect(page.getByLabel("Entity details")).toContainText(
    "service:authentication-api",
  );
  await expect(page.getByLabel("Entity details")).toContainText(
    "Freshness: unknown",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .locator('.react-flow__node[data-id="team:platform-engineering"]')
    .dblclick();
  await expect(page.locator(".react-flow__node")).toHaveCount(14);
  await page
    .locator('.react-flow__node[data-id="team:platform-engineering"]')
    .dblclick();
  await expect(page.locator(".react-flow__node")).toHaveCount(14);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "● team", exact: true }).click();
  await expect(
    page.locator('.react-flow__node[data-id="team:platform-engineering"]'),
  ).toHaveCount(0);
  await expect(
    page.locator(
      '.react-flow__edge[data-id="team:platform-engineering::OWNS::service:authentication-api"]',
    ),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "● team", exact: true }).click();
  await page.getByRole("button", { name: "Fit view", exact: true }).click();
  await page.screenshot({
    path: "test-results/desktop-graph.png",
    fullPage: true,
  });
  await page
    .getByLabel("Ask about your engineering knowledge")
    .fill("What breaks if authentication goes down?");
  await page.getByRole("button", { name: "Ask ↗", exact: true }).click();
  await expect(page.locator(".brain-answer")).toHaveCount(2);
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
  expect(errors).toEqual([]);
});

test("HTTP failure preserves the previous answer and graph, then retry recovers", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Who owns the authentication service?" })
    .click();
  await expect(page.locator(".react-flow__node")).toHaveCount(12);
  await page.route("**/api/chat", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
  );
  await page.getByLabel("Ask about your engineering knowledge").fill("auth");
  await page.getByRole("button", { name: "Ask ↗", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(page.locator(".react-flow__node")).toHaveCount(12);
  await expect(page.locator(".brain-answer")).toHaveCount(1);
  await page.unroute("**/api/chat");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".brain-answer")).toHaveCount(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("mobile layout and direct-route reload stay usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Who owns the authentication service?" })
    .click();
  await expect(page.locator(".react-flow__node")).toHaveCount(12);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  await page.goto("/does-not-exist");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Page unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Return to Ask Brain" }),
  ).toBeVisible();
});

test("followups, decision timeline and context-menu connection use the shared API", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Who owns the authentication service?" })
    .click();
  const followups = page.getByLabel("Suggested followups");
  await expect(followups).toBeVisible();
  await followups.getByRole("button", { name: /experts/ }).click();
  await expect(page.locator(".brain-answer")).toHaveCount(2);
  await expect(page.locator(".brain-answer").last()).toContainText(
    "Priya Sharma",
  );
  const auth = page.locator(
    '.react-flow__node[data-id="service:authentication-api"]',
  );
  await auth.click();
  const details = page.getByLabel("Entity details");
  await expect(details.getByLabel("Decision timeline")).toContainText(
    "Envoy proxy standard",
  );
  await expect(details.getByLabel("Decision timeline")).toContainText(
    "superseded",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .locator('.react-flow__node[data-id="team:platform-engineering"]')
    .click({ button: "right" });
  await page.getByRole("menuitem", { name: "Start connection here" }).click();
  await auth.click();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await expect(
    page.locator(
      '.react-flow__edge[data-id="team:platform-engineering::OWNS::service:authentication-api"]',
    ),
  ).toBeVisible();
});

test("health and onboarding reports work through navigation and direct reloads", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/health");
  await expect(
    page.getByRole("heading", { name: "Knowledge Health", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Knowledge health score")).toContainText("66.7");
  await page.screenshot({ path: "test-results/health.png", fullPage: true });
  await page
    .getByRole("button", { name: "Data Pipeline", exact: true })
    .first()
    .click();
  await expect(page.getByLabel("Entity details")).toContainText(
    "service:data-pipeline",
  );
  await page.getByRole("link", { name: "Onboarding", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Service Onboarding", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".report-content")).toContainText("Priya Sharma");
  await expect(page.locator(".report-content")).toContainText(
    "Rotate legacy signing keys",
  );
  await page.screenshot({
    path: "test-results/onboarding.png",
    fullPage: true,
  });
  await page.getByLabel("Choose service").selectOption("service:data-pipeline");
  await expect(page.locator(".report-content")).toContainText(
    "No owning team recorded.",
  );
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".report-content")).toContainText(
    "No owning team recorded.",
  );
  expect(errors).toEqual([]);
});
