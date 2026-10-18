import { defineConfig } from "@playwright/test";

// Frontend-only visual checks. API fixtures exist solely in the browser test.
export default defineConfig({
  testDir: "./tests/browser",
  testMatch: "ui-review.spec.ts",
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 950 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
  },
});
