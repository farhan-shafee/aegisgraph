import {
  defineConfig,
  devices,
} from "./apps/web/node_modules/@playwright/test";

export default defineConfig({
  testDir: "./tests/public-e2e",
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "https://127.0.0.1:3443",
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : {}),
  },
  webServer: {
    command: "node scripts/public_e2e_servers.mjs",
    url: "https://127.0.0.1:3443",
    ignoreHTTPSErrors: true,
    reuseExistingServer: process.env.E2E_REUSE_SERVERS === "1",
    timeout: 120_000,
  },
});
