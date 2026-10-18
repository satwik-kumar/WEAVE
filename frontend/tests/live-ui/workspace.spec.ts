import { expect, test } from "@playwright/test";

test("running services: chat, evidence, graph discovery, expansion and reports in both themes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByLabel("Ask about your engineering knowledge")
    .fill("Who owns the authentication service?");
  await page.getByLabel("Ask about your engineering knowledge").press("Enter");
  await expect(page.locator(".brain-answer")).toContainText(
    "Platform Engineering",
  );
  await expect(page.locator(".evidence article").first()).toBeAttached();
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
  await page.getByLabel("Find graph entity").fill("authentication");
  await page.getByLabel("Find graph entity").press("Enter");
  await expect(page.locator(".entity-detail h2")).toContainText(
    "Authentication",
  );
  await expect(page.locator(".zoom-level")).toHaveText("100%");
  await page
    .getByRole("button", { name: "Expand neighborhood", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Expand neighborhood", exact: true }),
  ).toBeEnabled();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 950 });
    for (const theme of ["light", "dark"]) {
      await page.getByLabel("Color theme").selectOption(theme);
      await page.waitForTimeout(300);
      await page.screenshot({
        path: `.ui-review.local/live-${theme}-${width}-selected.png`,
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  }
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Show all entities" }).click();
  await page.getByRole("button", { name: "Maximize graph" }).click();
  await page.getByRole("button", { name: "Fit view", exact: true }).click();
  await page.screenshot({
    path: ".ui-review.local/live-expanded.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  for (const route of ["/health", "/onboarding"]) {
    await page.goto(route);
    await expect(page.locator(".report-content")).not.toContainText(
      "unavailable",
    );
    await expect(page.locator(".report-content article").first()).toBeVisible();
    for (const theme of ["light", "dark"]) {
      await page.getByLabel("Color theme").selectOption(theme);
      await page.screenshot({
        path: `.ui-review.local/live-${theme}-${route.slice(1)}.png`,
        fullPage: true,
      });
    }
  }
  expect(errors).toEqual([]);
});
