import {
  defineConfig,
  devices,
} from "./apps/web/node_modules/@playwright/test";
import path from "node:path";
import fs from "node:fs";

const localPython = path.resolve(
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const python =
  process.env.E2E_PYTHON ||
  (fs.existsSync(localPython) ? localPython : "python");
const database = path.resolve(".runtime/e2e.db").replaceAll("\\", "/");

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : {}),
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn aegisgraph.main:app --host 127.0.0.1 --port 8100`,
      url: "http://127.0.0.1:8100/health",
      reuseExistingServer: process.env.E2E_REUSE_SERVERS === "1",
      timeout: 30_000,
      env: {
        DATABASE_URL: `sqlite:///${database}`,
        AI_PROVIDER: "deterministic",
        ALLOWED_ORIGINS: "http://127.0.0.1:3100,http://localhost:3100",
      },
    },
    {
      command:
        "node apps/web/node_modules/next/dist/bin/next dev apps/web --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: process.env.E2E_REUSE_SERVERS === "1",
      timeout: 120_000,
      env: {
        API_INTERNAL_URL: "http://127.0.0.1:8100",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
