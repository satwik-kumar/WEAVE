import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  testIgnore:
    process.env.WEAVE_BROWSER_LIVE === "1"
      ? "**/ask-brain.spec.ts"
      : "**/live.spec.ts",
  use: {
    baseURL: "http://127.0.0.1:5173",
    browserName: "chromium",
    video: "on",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 950 },
  },
  webServer: [
    {
      command: `${process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python"} -m uvicorn weave_brain.api.main:app --host 127.0.0.1 --port 8010`,
      cwd: "../backend",
      url: "http://127.0.0.1:8010/api/live",
      env: {
        DEVELOPMENT_FIXTURES:
          process.env.WEAVE_BROWSER_LIVE === "1" ? "false" : "true",
        CHAT_MODE: "retrieval",
        ALLOWED_ORIGINS: "http://127.0.0.1:5173",
      },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8010" },
      reuseExistingServer: false,
    },
  ],
});
