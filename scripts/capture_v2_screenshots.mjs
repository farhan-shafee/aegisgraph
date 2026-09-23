// Real public UI captures. Start the production HTTPS rehearsal before running.
// Usage: node scripts/capture_v2_screenshots.mjs
// Optional: CAPTURE_BASE_URL=https://127.0.0.1:3443 PLAYWRIGHT_CHANNEL=chrome
// This script never starts services, submits analyst questions, or submits writes.
import assert from "node:assert/strict";
import { mkdir, copyFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  chromium,
  expect,
  request,
} from "../apps/web/node_modules/@playwright/test/index.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const origin = new URL(
  process.env.CAPTURE_BASE_URL || "https://127.0.0.1:3443",
);
assert(
  ["https:", "http:"].includes(origin.protocol) &&
    origin.pathname === "/" &&
    !origin.username &&
    !origin.password &&
    !origin.search &&
    !origin.hash,
  "CAPTURE_BASE_URL must be an HTTP(S) origin without credentials or a path.",
);
const loopback = ["127.0.0.1", "localhost", "[::1]"].includes(origin.hostname);
assert(
  origin.protocol === "https:" || loopback,
  "Remote capture requires HTTPS.",
);
const baseURL = origin.origin;
const ignoreHTTPSErrors = loopback;
const incidentId = "INC-fe8fa4b9508c";
const outputDirectory = path.join(root, "docs", "screenshots");
const stagingDirectory = path.join(root, ".runtime", "v2-screenshot-capture");
const screenshots = [];
const problems = [];
const apiReads = [];
let browser;
let context;
const client = await request.newContext({
  baseURL,
  ignoreHTTPSErrors,
  timeout: 20_000,
});

async function getJson(route) {
  assert(
    route.startsWith("/api/"),
    "Inspection must use an application API route.",
  );
  const response = await client.get(route, { maxRedirects: 0 });
  assert(response.ok(), `${route} returned HTTP ${response.status()}.`);
  apiReads.push(route);
  return response.json();
}

try {
  // Validate the deployment boundary before launching a browser or acting on its UI.
  const runtime = await getJson("/api/runtime");
  assert.equal(
    runtime.app_mode,
    "public_demo",
    "Capture requires public_demo mode.",
  );
  assert.equal(
    runtime.read_only,
    true,
    "Capture requires a read-only service.",
  );
  assert.equal(
    runtime.analyst_provider,
    "deterministic",
    "Capture requires the deterministic public analyst contract.",
  );
  assert.deepEqual(
    [...runtime.questions].sort(),
    ["What most likely happened?", "What malware family was used?"].sort(),
  );
  for (const capability of [
    "scenarios",
    "replay",
    "hypotheses",
    "rule_workbench",
    "evidence_bundle",
    "analyst_benchmark",
  ]) {
    assert.equal(
      runtime.capabilities?.[capability],
      1,
      `Missing capability: ${capability}.`,
    );
  }
  const canonicalBefore = await getJson(`/api/incidents/${incidentId}`);
  await mkdir(stagingDirectory, { recursive: true });
  browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : {}),
  });
  context = await browser.newContext({
    baseURL,
    ignoreHTTPSErrors,
    viewport: { width: 1440, height: 1100 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
    acceptDownloads: true,
    serviceWorkers: "block",
  });
  // Fail closed even if a future UI accidentally adds a write or external request.
  await context.route("**/*", async (route) => {
    const outgoing = route.request();
    const url = new URL(outgoing.url());
    if (!["http:", "https:"].includes(url.protocol)) return route.continue();
    if (
      url.origin !== baseURL ||
      !["GET", "HEAD"].includes(outgoing.method())
    ) {
      problems.push(
        `Blocked unexpected ${outgoing.method()} request to ${url.origin}${url.pathname}.`,
      );
      return route.abort("blockedbyclient");
    }
    if (url.pathname.startsWith("/api/")) apiReads.push(url.pathname);
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  page.setDefaultNavigationTimeout(30_000);
  page.on("pageerror", (error) =>
    problems.push(`Page error: ${error.message}`),
  );
  page.on("console", (message) => {
    if (message.type() === "error")
      problems.push(`Console error: ${message.text()}`);
  });

  async function go(route) {
    const response = await page.goto(route, { waitUntil: "domcontentloaded" });
    assert(response?.ok(), `Navigation failed: ${route}.`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(
      page.getByText("Read-only public demo", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    assert.equal(
      await page.locator("nextjs-portal").count(),
      0,
      "Use the production server; developer overlays must not be hidden or captured.",
    );
    // This changes only the scroll position, never rendered content or styles.
    await page.evaluate(() => window.scrollTo(0, 0));
  }

  async function frameAt(locator, offset = 24) {
    await expect(locator).toBeVisible();
    await locator.evaluate((element) =>
      element.scrollIntoView({ block: "start", behavior: "instant" }),
    );
    await page.evaluate((pixels) => window.scrollBy(0, -pixels), offset);
  }

  async function capture(filename, state) {
    assert.deepEqual(
      problems,
      [],
      "Browser errors or blocked requests invalidate captures.",
    );
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    assert(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth + 1,
      ),
      "The capture viewport has horizontal overflow.",
    );
    const imagePath = path.join(stagingDirectory, filename);
    // Playwright captures app pixels only: no browser chrome, OS UI, or hidden layers.
    await page.screenshot({
      path: imagePath,
      fullPage: false,
      timeout: 20_000,
    });
    screenshots.push({ filename, route: new URL(page.url()).pathname, state });
    console.log(`Captured ${filename}`);
  }

  const replayResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/replays/atlas-compromise",
  );
  await go("/replay?scenario=atlas-compromise");
  const replay = await replayResponse;
  assert(replay.ok(), "Atlas projection failed.");
  const projection = await replay.json();
  assert.equal(projection.provenance.scenario_id, "atlas-compromise");
  assert.equal(projection.summary.frame_count, projection.frames.length);
  const thresholdFrame = projection.frames.findIndex(
    (frame) => frame.stage === "incident" && frame.data.change === "created",
  );
  assert(
    thresholdFrame >= 0 && thresholdFrame < projection.frames.length - 1,
    "Atlas requires an intermediate incident-creation frame.",
  );
  assert(
    projection.frames.length <= 600,
    "Replay exceeded its bounded contract.",
  );
  await expect(
    page.getByRole("button", { name: "Start", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("Playback speed").selectOption("20");
  for (let cursor = 0; cursor <= thresholdFrame; cursor++) {
    await page.getByRole("button", { name: "Step", exact: true }).click();
  }
  await expect(
    page.getByRole("progressbar", { name: "Replay progress" }),
  ).toHaveAttribute("value", String(thresholdFrame + 1));
  await expect(
    page.getByRole("button", { name: "Resume", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: projection.frames[thresholdFrame].data.incident.title,
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Completed evidence", exact: true }),
  ).toHaveCount(0);
  await frameAt(
    page.getByRole("heading", {
      name: "Replay the investigation",
      exact: true,
    }),
  );
  await capture("v2-replay.png", {
    scenario: "atlas-compromise",
    cursor: thresholdFrame + 1,
    total_frames: projection.frames.length,
    stage: "incident",
    source_timestamp: projection.frames[thresholdFrame].timestamp,
    ruleset_digest: projection.provenance.ruleset_digest,
  });

  await go(`/incidents/${incidentId}`);
  await page.getByRole("tab", { name: "Hypotheses", exact: true }).click();
  const ledger = page.getByRole("region", { name: "Hypothesis ledger" });
  await expect(ledger.locator(".hypothesis-card").first()).toBeVisible();
  await expect(
    ledger.getByRole("button", { name: "Save human review" }),
  ).toHaveCount(0);
  await ledger.locator(".hypothesis-gaps > summary").first().click();
  await expect(
    ledger
      .getByText("These are investigation gaps, not observed facts.")
      .first(),
  ).toBeVisible();
  await frameAt(page.getByRole("tablist", { name: "Investigation views" }));
  await capture("v2-hypotheses.png", {
    incident_id: incidentId,
    view: "read_only_hypothesis_ledger",
    first_gap_guidance_expanded: true,
  });

  await go("/detections/APP-002");
  const comparisonResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname ===
      "/api/regressions/examples/reduce-benign-volume",
  );
  await page.getByRole("button", { name: /1,500 records/ }).click();
  const compared = await comparisonResponse;
  assert(compared.ok(), "Public comparison failed.");
  const comparison = await compared.json();
  assert.equal(comparison.selected_rule_id, "APP-002");
  assert.equal(
    comparison.gate.decision,
    "PASS",
    "The requested baseline 1,500-record example must compute PASS.",
  );
  assert(
    comparison.parameter_changes.some(
      (change) => change.parameter === "threshold" && change.after === 1500,
    ),
  );
  await expect(page.getByText("PASS", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("region", {
        name: "Scenario signal and correlation differences",
      })
      .locator("tbody tr"),
  ).toHaveCount(comparison.scenarios.length);
  await expect(page.getByRole("spinbutton")).toHaveCount(0);
  await frameAt(
    page.getByRole("heading", { name: "Corpus comparison", exact: true }),
  );
  await capture("v2-detection-regression.png", {
    rule: "APP-002",
    threshold: 1500,
    gate: comparison.gate.decision,
    metrics: comparison.metrics,
    corpus_digest: comparison.corpus_digest,
  });

  await go(`/incidents/${incidentId}`);
  await page.getByRole("tab", { name: "Export", exact: true }).click();
  const exportResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname ===
      `/api/incidents/${incidentId}/export`,
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download evidence bundle" }).click();
  const exported = await exportResponse;
  assert(exported.ok(), "Public evidence export failed.");
  const bundle = await exported.json();
  assert.equal(bundle.manifest.projection, "public_synthetic");
  const download = await downloadPromise;
  assert.equal(
    await download.failure(),
    null,
    "Verified export download failed.",
  );
  const exportPanel = page.getByRole("tabpanel");
  await expect(exportPanel.getByRole("status")).toContainText("VALID");
  await expect(exportPanel.getByRole("status")).toContainText(
    "Contents match the supplied manifest.",
  );
  await expect(exportPanel).toContainText("unsigned and replaceable");
  await frameAt(
    page.getByRole("heading", { name: "Evidence bundle", exact: true }),
  );
  await capture("v2-bundle-verification.png", {
    incident_id: incidentId,
    projection: bundle.manifest.projection,
    verification: "VALID",
    declared_files: bundle.manifest.files.length,
    generated_at: bundle.manifest.generated_at,
  });
  await download.delete();

  const benchmark = await getJson("/api/evaluations/benchmark");
  assert.equal(benchmark.provider, "deterministic");
  assert.equal(benchmark.live_model_tested, false);
  assert.equal(benchmark.total, benchmark.cases.length);
  await go("/evaluations");
  await page
    .getByRole("button", { name: "V2 analyst benchmark", exact: true })
    .click();
  for (const [label, value] of [
    ["Executed obligations", benchmark.total],
    ["Passed", benchmark.passed],
    ["Failed", benchmark.failed],
  ]) {
    await expect(
      page
        .locator(".eval-metrics .metric")
        .filter({ hasText: label })
        .locator(".metric-value"),
    ).toHaveText(String(value));
  }
  await expect(
    page.getByRole("heading", {
      name: "Defined metric populations",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run deterministic suite" }),
  ).toHaveCount(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await capture("v2-evaluations.png", {
    provider: benchmark.provider,
    total: benchmark.total,
    passed: benchmark.passed,
    failed: benchmark.failed,
    provenance: benchmark.provenance,
  });

  assert.deepEqual(
    await getJson(`/api/incidents/${incidentId}`),
    canonicalBefore,
    "Canonical case changed during capture.",
  );
  assert.deepEqual(
    problems,
    [],
    "Browser errors or blocked requests invalidate captures.",
  );
  // Publish the set only after all five real states and the unchanged case pass.
  await mkdir(outputDirectory, { recursive: true });
  for (const { filename } of screenshots)
    await copyFile(
      path.join(stagingDirectory, filename),
      path.join(outputDirectory, filename),
    );
  await writeFile(
    path.join(stagingDirectory, "capture-record.json"),
    JSON.stringify(
      {
        captured_at: new Date().toISOString(),
        base_url: baseURL,
        viewport: { width: 1440, height: 1100 },
        runtime,
        screenshots,
        api_reads: apiReads,
        canonical_case_unchanged: true,
        browser_errors: problems,
      },
      null,
      2,
    ),
  );
  console.log(
    `Published ${screenshots.length} real UI screenshots to docs/screenshots. Canonical case unchanged; no writes or analyst questions.`,
  );
} finally {
  await context?.close();
  await browser?.close();
  await client.dispose();
}
