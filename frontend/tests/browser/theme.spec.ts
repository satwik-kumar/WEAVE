import { expect, test } from "@playwright/test";

test.use({ colorScheme: "light" });

test("reference design: both themes across empty, loading, populated, details, expansion and error states", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.locator(".canvas-empty strong")).toBeVisible();
  await expect(page.getByLabel("Color theme")).toHaveValue("system");
  const capture = async (state: string) => {
    const original = page.viewportSize()!;
    const widths = state.startsWith("narrow-") ? [original.width] : [1440, 390];
    for (const width of widths) {
      await page.setViewportSize({ width, height: width === 1440 ? 950 : 844 });
      await page.waitForTimeout(300);
      for (const theme of ["light", "dark"]) {
        await page.getByLabel("Color theme").selectOption(theme);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.screenshot({
          path: `test-results/reference-${theme}-${state}-${width}.png`,
          fullPage: true,
        });
      }
    }
    await page.setViewportSize(original);
  };
  await capture("empty");
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/chat", async (route) => {
    await gate;
    await route.continue();
  });
  await page
    .getByRole("button", { name: "Why do authentication tokens expire?" })
    .click();
  await page.locator(".loading").scrollIntoViewIfNeeded();
  await expect(page.locator(".question-form button")).toBeDisabled();
  await capture("loading");
  release();
  await expect(page.locator(".brain-answer")).toContainText("INC-007");
  await page.unroute("**/api/chat");
  await expect(page.locator(".react-flow__node")).toHaveCount(5);
  await page.waitForTimeout(250);
  await capture("populated");
  const colors: string[] = [];
  for (const theme of ["light", "dark"]) {
    await page.getByLabel("Color theme").selectOption(theme);
    colors.push(
      await page
        .locator(".entity-node")
        .first()
        .evaluate((element) => getComputedStyle(element).backgroundColor),
    );
    const contrast = await page
      .locator(".entity-node")
      .first()
      .evaluate((element) => {
        const rgb = (value: string) =>
          value
            .match(/[\d.]+/g)!
            .slice(0, 3)
            .map(Number)
            .map((n) => {
              const c = n / 255;
              return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
        const luminance = (value: string) =>
          rgb(value).reduce(
            (sum, n, i) => sum + n * [0.2126, 0.7152, 0.0722][i],
            0,
          );
        const bg = luminance(getComputedStyle(element).backgroundColor);
        return [
          ...element.querySelectorAll("strong, small, .entity-node > span"),
        ].map((child) => {
          const fg = luminance(getComputedStyle(child).color);
          return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
        });
      });
    expect(Math.min(...contrast)).toBeGreaterThanOrEqual(4.5);
  }
  expect(colors[0]).not.toBe(colors[1]);
  await page
    .locator('.react-flow__node[data-id="service:authentication-api"]')
    .click();
  await expect(page.getByLabel("Entity details")).toBeVisible();
  await page.waitForTimeout(250);
  await capture("selected");
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Entity details")).toHaveCount(0);
  let expand: () => void = () => {};
  const expansion = new Promise<void>((resolve) => {
    expand = resolve;
  });
  await page.route("**/api/graph/neighborhood/**", async (route) => {
    await expansion;
    await route.continue();
  });
  await page
    .locator('.react-flow__node[data-id="service:authentication-api"]')
    .dblclick();
  await expect(page.locator(".entity-node")).toContainText([
    "Expanding neighborhood...",
  ]);
  await capture("expanding");
  expand();
  await expect(
    page.getByText("Expanding neighborhood...", { exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/api/graph/neighborhood/**");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.route("**/api/chat", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
  );
  await page
    .getByLabel("Ask about your engineering knowledge")
    .fill("Who owns authentication?");
  await page.locator(".question-form button").click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await page.getByRole("alert").scrollIntoViewIfNeeded();
  await capture("error");
  expect(await page.locator(".react-flow__node").count()).toBeGreaterThan(0);
  for (const width of [390, 760, 1024]) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForTimeout(350);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await capture(`narrow-${width}`);
  }
  await page.unroute("**/api/chat");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("theme bootstrap, persistence, system updates, keyboard access and reduced motion", async ({
  page,
}) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem("weave-theme"))
      localStorage.setItem("weave-theme", "dark");
  });
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/src/main.tsx", async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto("/", { waitUntil: "commit" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(
    await page
      .locator("html")
      .evaluate((element) => getComputedStyle(element).backgroundColor),
  ).toBe("rgb(25, 28, 25)");
  release();
  await expect(page.getByLabel("Color theme")).toHaveValue("dark");
  await page.unroute("**/src/main.tsx");
  await page.reload();
  await expect(page.getByLabel("Color theme")).toHaveValue("dark");
  const control = page.getByLabel("Color theme");
  await control.focus();
  await page.keyboard.press("Home");
  await page.keyboard.press("Enter");
  await expect(control).toHaveValue("system");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await control.selectOption("light");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(control).toHaveValue("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page
    .getByRole("button", { name: "Why do authentication tokens expire?" })
    .click();
  await expect(page.locator(".react-flow__node")).toHaveCount(5);
  await page
    .locator('.react-flow__node[data-id="service:authentication-api"]')
    .click();
  await expect(page.getByLabel("Entity details")).toBeVisible();
  expect(
    await page
      .getByLabel("Entity details")
      .evaluate((element) =>
        element
          .getAnimations()
          .some((animation) => animation.playState === "running"),
      ),
  ).toBe(false);
  await expect(page.locator(".react-flow__edge.animated")).toHaveCount(0);
});

test("theme control remains usable when browser storage is blocked", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new DOMException("Blocked", "SecurityError");
      },
    }),
  );
  await page.goto("/");
  await expect(page.getByLabel("Color theme")).toHaveValue("system");
  await page.getByLabel("Color theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
