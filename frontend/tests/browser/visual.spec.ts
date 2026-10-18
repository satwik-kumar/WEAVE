import { expect, test } from "@playwright/test";

test("redesigned workspace: empty, populated, evidence, selection and responsive screenshots", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".canvas-empty strong")).toHaveText(
    "Context, connected.",
  );
  await page.screenshot({
    path: "test-results/redesign-empty.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Why do authentication tokens expire?" })
    .click();
  await expect(page.locator(".brain-answer")).toContainText("INC-007");
  await expect(page.locator(".evidence article")).not.toHaveCount(0);
  await expect(page.locator(".react-flow__node")).not.toHaveCount(0);
  await page.waitForTimeout(400); // Wait for measured graph layout before visual capture.
  const panels = await page
    .locator(".chat-panel, .graph-panel")
    .evaluateAll((items) =>
      items.map((item) => item.getBoundingClientRect().toJSON()),
    );
  expect(panels[0].right).toBeLessThanOrEqual(panels[1].left + 1);
  await page.screenshot({
    path: "test-results/redesign-populated.png",
    fullPage: true,
  });
  await page
    .locator('.react-flow__node[data-id="service:authentication-api"]')
    .click();
  await expect(page.getByLabel("Entity details")).toBeVisible();
  await page.screenshot({
    path: "test-results/redesign-selected.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.locator(".evidence").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/redesign-evidence.png",
    fullPage: true,
  });
  for (const width of [390, 760, 1024]) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForTimeout(450);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const graph = await page.locator(".canvas").boundingBox();
    expect(graph!.height).toBeGreaterThan(280);
    await page.screenshot({
      path: `test-results/redesign-${width}.png`,
      fullPage: true,
    });
  }
});
