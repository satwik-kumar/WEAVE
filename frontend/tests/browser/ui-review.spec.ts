import { expect, test, type Page } from "@playwright/test";
import type { ChatResponse, GraphNode, GraphView } from "../../src/types/api";

test("chat Enter sends once, Shift+Enter inserts a newline, composition does not send", async ({
  page,
}) => {
  await fixture(page);
  const questions: string[] = [];
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/chat", async (route) => {
    questions.push(route.request().postDataJSON().question);
    await gate;
    await route.fulfill({ json: response });
  });
  await page.goto("/");
  const input = page.getByLabel("Ask about your engineering knowledge");
  await input.fill("Who owns authentication?");
  await input.press("Shift+Enter");
  await expect(input).toHaveValue("Who owns authentication?\n");
  await input.dispatchEvent("keydown", { key: "Enter", isComposing: true });
  await input.dispatchEvent("keydown", { key: "Enter", keyCode: 229 });
  await input.dispatchEvent("keydown", { key: "Enter", repeat: true });
  expect(questions).toEqual([]);
  await input.press("Enter");
  await expect(input).toBeDisabled();
  await expect.poll(() => questions).toEqual(["Who owns authentication?"]);
  await page.keyboard.press("Enter");
  expect(questions).toHaveLength(1);
  release();
  await expect(page.locator(".brain-answer")).toContainText("INC-007");
  await expect(input).toHaveValue("");
  await input.press("Enter");
  expect(questions).toHaveLength(1);
});

// Synthetic records are restricted to Playwright interception, never app runtime.
const node = (
  id: string,
  type: GraphNode["type"],
  title: string,
): GraphNode => ({
  id,
  type,
  title,
  properties: { source_id: "ui-test", source_type: "fixture" },
  on_highlighted_path: false,
});
const auth = node(
  "service:authentication-api",
  "service",
  "Authentication API",
);
const team = node("team:platform-engineering", "team", "Platform Engineering");
const decision = node(
  "decision:adr-001",
  "decision",
  "Token expiry 24h policy",
);
const incident = node(
  "incident:inc-007",
  "incident",
  "Stolen long-lived token exploited",
);
const graph: GraphView = {
  nodes: [auth, team, decision, incident],
  edges: [
    [team.id, "OWNS", auth.id],
    [decision.id, "DECIDES_FOR", auth.id],
    [decision.id, "MOTIVATED_BY", incident.id],
  ].map(([source_id, relationship_type, target_id]) => ({
    id: `${source_id}::${relationship_type}::${target_id}`,
    source_id,
    target_id,
    relationship_type,
    label: relationship_type,
    properties: {},
  })),
  root_node_ids: [auth.id],
  highlighted_path_ids: [],
  truncated: false,
};
const response: ChatResponse = {
  message_id: "ui-fixture",
  intent: "decision_rationale",
  answer:
    "**Authentication API** is owned by Platform Engineering. Tokens expire after 24 hours because of the incident **INC-007**.\n\nThe decision limits exposure when credentials are stolen.",
  graph,
  highlighted_paths: [],
  related_entities: graph.nodes,
  evidence: [
    {
      source_id: "ui-test",
      source_type: "fixture",
      title: "ADR-001 · Token expiry policy",
      excerpt: "Limit token lifetime to 24 hours following INC-007.",
      relationship_path: [decision.id, auth.id],
    },
  ],
  suggested_followups: ["Who are the authentication experts?"],
  warnings: ["Visual test fixture — live integration is not verified."],
};

async function fixture(page: Page) {
  let message = 0;
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path.endsWith("/chat"))
      body = { ...response, message_id: `ui-fixture-${++message}` };
    else if (path.includes("/decisions"))
      body = { nodes: [decision], evidence: response.evidence, graph };
    else if (path.includes("/neighborhood/"))
      body = {
        ...graph,
        nodes: [
          ...graph.nodes,
          node("person:priya-sharma", "person", "Priya Sharma"),
        ],
      };
    else if (path.includes("/search")) body = [auth];
    else if (path.includes("/onboarding/"))
      body = {
        service_id: auth.id,
        service_title: auth.title,
        overview:
          "Visual fixture for service ownership, decisions and dependencies.",
        key_decisions: response.evidence,
        top_experts: [team],
        change_risks: [],
        open_incidents: [incident],
        related_tickets: [],
        graph,
        warnings: response.warnings,
      };
    else if (path.includes("/health-score"))
      body = {
        health_score: 75,
        metrics: {
          services_owned: 0.75,
          decisions_rationale: 1,
          incidents_resolved: 1,
          services_documented: 0.25,
        },
        counts: {
          total_services: 4,
          owned_services: 3,
          total_decisions: 1,
          decisions_with_rationale: 1,
          total_incidents: 1,
          resolved_incidents: 1,
          documented_services: 1,
        },
        gaps: {
          unowned_services: [],
          decisions_missing_rationale: [],
          undocumented_services: [auth],
          total_gaps: 1,
        },
        graph,
        warnings: response.warnings,
      };
    await route.fulfill({ json: body });
  });
}

for (const width of [1440, 390]) {
  for (const theme of ["light", "dark"] as const) {
    test(`${theme} ${width}: chat, graph, selection, filtering, expansion and recovery`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: width === 1440 ? 950 : 844 });
      await fixture(page);
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto("/");
      await page.getByLabel("Color theme").selectOption(theme);
      const capture = async (state: string) => {
        await page.screenshot({
          path: `test-results/ui-${theme}-${width}-${state}.png`,
          fullPage: true,
        });
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      };
      await expect(page.locator(".canvas-empty strong")).toHaveText(
        "Context, connected.",
      );
      await capture("initial");
      let release!: () => void;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      await page.route("**/api/chat", async (route) => {
        await gate;
        await route.fulfill({ json: response });
      });
      await page
        .getByRole("button", { name: "Why do authentication tokens expire?" })
        .click();
      await expect(page.locator(".question-form button")).toBeDisabled();
      await capture("loading");
      release();
      await expect(page.locator(".brain-answer")).toContainText("INC-007");
      await page.unroute("**/api/chat");
      await expect(page.locator(".react-flow__node")).toHaveCount(4);
      await page.waitForTimeout(300);
      const contrast = await page
        .locator(".entity-node")
        .evaluateAll((elements) => {
          const luminance = (color: string) => {
            const channels = color
              .match(/[\d.]+/g)!
              .slice(0, 3)
              .map(Number)
              .map((value) => {
                const c = value / 255;
                return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
              });
            return channels.reduce(
              (sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i],
              0,
            );
          };
          return elements.flatMap((element) => {
            const bg = luminance(getComputedStyle(element).backgroundColor);
            return [
              ...element.querySelectorAll("strong, small, .entity-node > span"),
            ].map((child) => {
              const fg = luminance(getComputedStyle(child).color);
              return (Math.max(bg, fg) + 0.05) / (Math.min(bg, fg) + 0.05);
            });
          });
        });
      expect(Math.min(...contrast)).toBeGreaterThanOrEqual(4.5);
      await capture("populated");
      await page.locator(`.react-flow__node[data-id="${auth.id}"]`).click();
      await expect(page.getByLabel("Entity details")).toBeVisible();
      await page.waitForTimeout(220);
      await capture("selected");
      await page
        .getByRole("button", { name: "Expand neighborhood", exact: true })
        .click();
      await expect(page.locator(".react-flow__node")).toHaveCount(5);
      await page.keyboard.press("Escape");
      await expect(page.getByLabel("Entity details")).toHaveCount(0);
      await page.locator(`.react-flow__node[data-id="${auth.id}"]`).dblclick();
      await expect(page.locator(".react-flow__node")).toHaveCount(5);
      await page.getByRole("button", { name: "Close", exact: true }).click();
      const filters = page.locator(".filters button");
      for (const filter of await filters.all()) await filter.click();
      await expect(page.locator(".canvas-empty strong")).toHaveText(
        "No entities visible",
      );
      await capture("filtered");
      for (const filter of await filters.all()) await filter.click();
      await page.getByRole("button", { name: "Fit view", exact: true }).click();
      await page.getByRole("button", { name: "Zoom in", exact: true }).click();
      await page.getByRole("button", { name: "Zoom out", exact: true }).click();
      await page.getByRole("button", { name: "Legend", exact: true }).click();
      await expect(page.locator("#graph-legend")).toBeVisible();
      await page.route("**/api/chat", (route) =>
        route.fulfill({ status: 503, json: {} }),
      );
      await page
        .getByLabel("Ask about your engineering knowledge")
        .fill("Who owns authentication?");
      await page.locator(".question-form button").click();
      await expect(page.getByRole("alert")).toContainText("unavailable");
      await page.getByRole("alert").scrollIntoViewIfNeeded();
      await capture("error");
      await expect(page.locator(".react-flow__node")).toHaveCount(5);
      await page.unroute("**/api/chat");
      await page.getByRole("button", { name: "Retry", exact: true }).click();
      await expect(page.getByRole("alert")).toHaveCount(0);
      expect(errors).toEqual([]);
    });
  }
}

test("theme bootstrap, system preference, keyboard focus, reduced motion and report routes", async ({
  page,
}) => {
  await fixture(page);
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  let boot!: () => void;
  const gate = new Promise<void>((resolve) => {
    boot = resolve;
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
  boot();
  await page.unroute("**/src/main.tsx");
  await page.getByLabel("Color theme").selectOption("light");
  await page.reload();
  await expect(page.getByLabel("Color theme")).toHaveValue("light");
  await page.getByLabel("Color theme").selectOption("system");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Tab");
  await page.locator(".skip-link").focus();
  await expect(page.locator(".skip-link")).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page
    .getByRole("button", { name: "Why do authentication tokens expire?" })
    .click();
  await page.locator(`.react-flow__node[data-id="${auth.id}"]`).click();
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
  for (const width of [1440, 1024, 800, 760, 390]) {
    await page.setViewportSize({ width, height: 950 });
    for (const route of ["/health", "/onboarding"]) {
      await page.goto(route);
      await expect(
        page.locator(".report-content article").first(),
      ).toBeVisible();
      await expect(page.locator(".react-flow__node")).toHaveCount(4);
      await page.waitForTimeout(300);
      for (const theme of ["light", "dark"]) {
        await page.getByLabel("Color theme").selectOption(theme);
        await page.screenshot({
          path: `test-results/ui-${theme}-${width}-${route.slice(1)}.png`,
          fullPage: true,
        });
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      }
    }
  }
});

test("empty retrieval stays honest and theme works with blocked storage", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new DOMException("Blocked", "SecurityError");
      },
    }),
  );
  await fixture(page);
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      json: {
        ...response,
        answer: "No matching records were retrieved.",
        evidence: [],
        graph: { ...graph, nodes: [], edges: [], root_node_ids: [] },
        related_entities: [],
        suggested_followups: [],
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel("Color theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page
    .getByRole("button", { name: "Who owns the authentication service?" })
    .click();
  await expect(page.locator(".brain-answer")).toContainText(
    "No matching records",
  );
  await expect(page.locator(".canvas-empty strong")).toHaveText(
    "No graph evidence returned",
  );
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await page.screenshot({
    path: "test-results/ui-no-results.png",
    fullPage: true,
  });
});

for (const width of [1440, 390]) {
  test(`graph discovery, copy, readable focus and expanded view at ${width}`, async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.setViewportSize({ width, height: 950 });
    await fixture(page);
    await page.goto("/");
    await page
      .getByRole("button", { name: "Why do authentication tokens expire?" })
      .click();
    await expect(page.locator(".react-flow__node")).toHaveCount(4);
    await page
      .getByRole("button", { name: "Copy answer", exact: true })
      .click();
    expect(
      (await page.evaluate(() => navigator.clipboard.readText())).replaceAll(
        "\r\n",
        "\n",
      ),
    ).toBe(response.answer);
    await page.locator(".filters button").first().click();
    const finder = page.getByRole("combobox", { name: "Find graph entity" });
    await finder.fill("not-a-real-entity");
    await expect(page.locator(".finder-empty")).toContainText(
      "No entities match",
    );
    await finder.fill("authentication");
    await finder.press("Enter");
    await expect(page.getByLabel("Entity details")).toBeVisible();
    await expect(page.locator(".entity-detail h2")).toHaveText(
      "Authentication API",
    );
    await expect(page.locator(".zoom-level")).toHaveText("100%");
    await page.getByRole("button", { name: "Copy entity ID" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
      auth.id,
    );
    await page
      .locator(".relationship-row")
      .filter({ hasText: "Platform Engineering" })
      .click();
    await expect(page.locator(".entity-detail h2")).toHaveText(
      "Platform Engineering",
    );
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: "Show all entities" }).click();
    await page.getByRole("button", { name: "Maximize graph" }).click();
    const dialog = page.getByRole("dialog", { name: "Knowledge graph" });
    await expect(dialog).toBeVisible();
    await expect(page.locator(".app-sidebar")).toHaveJSProperty("inert", true);
    // Wait for the expanded canvas measurement and camera fit, not just its shell.
    await expect
      .poll(async () => {
        const canvas = await page.locator(".canvas").boundingBox();
        const bounds = await page
          .locator(".react-flow__node")
          .evaluateAll((elements) =>
            elements.map((element) => {
              const rect = element.getBoundingClientRect();
              return { left: rect.left, right: rect.right };
            }),
          );
        const center =
          (Math.min(...bounds.map((rect) => rect.left)) +
            Math.max(...bounds.map((rect) => rect.right))) /
          2;
        return Math.abs(center - (canvas!.x + canvas!.width / 2));
      })
      .toBeLessThan(4);
    await page.getByRole("button", { name: "Fit view", exact: true }).focus();
    await page.keyboard.press("Shift+Tab");
    expect(
      await dialog.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/ui-expanded-${width}.png`,
      fullPage: true,
    });
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.locator(".app-sidebar")).toHaveJSProperty("inert", false);
  });
}

test("long questions and records remain contained; sources collapse; keyboard shortcut focuses chat", async ({
  page,
}) => {
  await fixture(page);
  const longTitle =
    "Authentication service with a very long multilingual title 工程团队 " +
    "x".repeat(160);
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      json: {
        ...response,
        graph: {
          ...graph,
          nodes: [
            {
              ...auth,
              title: longTitle,
              properties: {
                description: "A".repeat(800),
                status: "production",
                source_id: "test",
              },
            },
            team,
            decision,
            incident,
          ],
        },
        evidence: [
          {
            ...response.evidence[0],
            title: longTitle,
            excerpt: "record".repeat(200),
            source_id: "id".repeat(100),
          },
        ],
      },
    }),
  );
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/");
  await page.keyboard.press("Control+/");
  const input = page.getByLabel("Ask about your engineering knowledge");
  await expect(input).toBeFocused();
  const original = await input.evaluate((element) => element.clientHeight);
  await input.fill("A question\n".repeat(15));
  expect(
    await input.evaluate((element) => element.clientHeight),
  ).toBeGreaterThan(original);
  expect(
    await input.evaluate((element) => element.clientHeight),
  ).toBeLessThanOrEqual(160);
  await input.press("Enter");
  await expect(page.locator(".evidence article")).toBeVisible();
  await page.locator(".evidence > summary").click();
  await expect(page.locator(".evidence article")).toBeHidden();
  await page.locator(".evidence > summary").click();
  const finder = page.getByLabel("Find graph entity");
  await finder.fill("authentication");
  await finder.press("Enter");
  await expect(page.locator(".entity-detail h2")).toHaveText(longTitle);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page
      .locator(".entity-detail")
      .evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/ui-long-content-320.png",
    fullPage: true,
  });
  const toolbar = await page.locator(".toolbar-buttons").boundingBox();
  const controls = await page
    .locator(".toolbar-buttons button")
    .evaluateAll((elements) =>
      elements.map((element) => {
        const rect = element.getBoundingClientRect();
        return { left: rect.left, right: rect.right };
      }),
    );
  expect(
    controls.every(
      (control) =>
        control.left >= toolbar!.x &&
        control.right <= toolbar!.x + toolbar!.width + 1,
    ),
  ).toBe(true);
});

test("unfinished question survives route changes without persisting conversation data", async ({
  page,
}) => {
  await fixture(page);
  await page.goto("/");
  const input = page.getByLabel("Ask about your engineering knowledge");
  await input.fill("An unfinished question about ownership");
  await page
    .getByRole("link", { name: "Knowledge Health", exact: true })
    .click();
  await expect(page.locator(".report-content h1")).toHaveText(
    "Knowledge Health",
  );
  await page.getByRole("link", { name: "Ask Brain", exact: true }).click();
  await expect(input).toHaveValue("An unfinished question about ownership");
  await page.reload();
  await expect(input).toHaveValue("");
});
