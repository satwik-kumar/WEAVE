import { defineConfig } from "@playwright/test";

// Read-only UI smoke checks against services already running on localhost.
export default defineConfig({
  testDir: "./tests/live-ui",
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1440, height: 950 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  outputDir: ".ui-review.local/live-results",
});
