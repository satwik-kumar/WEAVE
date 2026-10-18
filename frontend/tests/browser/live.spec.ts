import { test, expect } from "@playwright/test";

test("real seeded FalkorDB: grounded answers, inspection, expansion and report routes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByRole("button", { name: "Who owns the authentication service?" })
    .click();
  await expect(page.locator(".brain-answer")).toContainText(
    "Platform Engineering",
  );
  await expect(page.locator(".brain-answer")).toContainText("acme/auth-api");
  await expect(page.locator(".brain-answer")).not.toContainText(
    "Development fixture",
  );
  await expect(
    page.locator(
      '.react-flow__edge[data-id="team:platform-engineering::OWNS::service:authentication-api"]',
    ),
  ).toBeVisible();
  await page
    .locator('.react-flow__node[data-id="service:authentication-api"]')
    .click();
  await expect(page.getByLabel("Entity details")).toContainText("svc-auth-api");
  await expect(page.getByLabel("Decision timeline")).toContainText(
    "Envoy proxy standard",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .locator('.react-flow__node[data-id="service:authentication-api"]')
    .dblclick();
  await expect(
    page.locator('.react-flow__node[data-id="incident:inc-007"]'),
  ).toBeVisible();
  await page
    .locator(".question-form textarea")
    .fill("Why do authentication tokens expire?");
  await page.getByRole("button", { name: "Ask ↗", exact: true }).click();
  await expect(page.locator(".brain-answer").last()).toContainText("INC-007");
  await expect(
    page.locator(
      '.react-flow__edge[data-id="decision:adr-001::MOTIVATED_BY::incident:inc-007"]',
    ),
  ).toBeVisible();
  await expect.poll(async () => {
    const canvas = await page.locator(".canvas").boundingBox();
    const boxes = await page.locator(".react-flow__node").evaluateAll((nodes) =>
      nodes.map((node) => {
        const box = node.getBoundingClientRect();
        return { top: box.top, bottom: box.bottom, left: box.left, right: box.right };
      }),
    );
    return !!canvas && boxes.every((box) =>
      box.top >= canvas.y && box.bottom <= canvas.y + canvas.height &&
      box.left >= canvas.x && box.right <= canvas.x + canvas.width,
    );
  }).toBe(true);
  await page.screenshot({
    path: "test-results/live-rationale.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Knowledge Health", exact: true })
    .click();
  await expect(page.getByLabel("Knowledge health score")).toContainText("66.7");
  await page.getByRole("link", { name: "Onboarding", exact: true }).click();
  await expect(page.locator(".report-content")).toContainText("Priya Sharma");
  await page.reload();
  await expect(page.locator(".report-content")).toContainText(
    "Rotate legacy signing keys",
  );
  expect(errors).toEqual([]);
});
