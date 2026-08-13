import { defineConfig } from "@playwright/test";

// The CareMatch API (8000) and dashboard (8080) are expected to already be
// running (docker compose up or manual uvicorn/vite). These specs verify
// behavior against the live app, so no webServer is started here.
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  fullyParallel: true,
  reporter: "list",
  use: {
    actionTimeout: 15_000,
    trace: "retain-on-failure",
  },
});
