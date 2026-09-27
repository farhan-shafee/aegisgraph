import { test, expect } from "../../apps/web/node_modules/@playwright/test";
import type { ReplayProjection } from "../../apps/web/src/lib/replay-types";
import type { RegressionResult } from "../../apps/web/src/lib/detection-types";
import type { AnalystBenchmark } from "../../apps/web/src/lib/benchmark-types";

const canonicalId = "INC-fe8fa4b9508c";

test("public scenario replay is ephemeral and reveals completed evidence only at the final frame", async ({
  page,
  request,
}) => {
  const beforeResponse = await request.get(`/api/incidents/${canonicalId}`);
  expect(beforeResponse.ok()).toBeTruthy();
  const before = await beforeResponse.json();
  const writes: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (item) => {
    if (
      new URL(item.url()).pathname.startsWith("/api/") &&
      item.method() !== "GET"
    )
      writes.push(item.url());
  });
  const loaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/replays/isolated-anomaly",
  );
  await page.goto("/replay?scenario=isolated-anomaly");
  const projectionResponse = await loaded;
  expect(projectionResponse.ok()).toBeTruthy();
  const projection: ReplayProjection = await projectionResponse.json();
  await expect(
    page.getByText("Read-only public demo", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("heading", { name: "Completed evidence" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: /^Decision receipt for/ }),
  ).toHaveCount(0);
  expect(projection.frames.length).toBeLessThan(50);
  for (let index = 0; index < projection.frames.length - 1; index++)
    await page.getByRole("button", { name: "Step", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Completed evidence" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Step", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Completed evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger" }),
  ).toBeVisible();
  const receipt = page.getByRole("region", {
    name: "Decision receipt for USR-isolated-anomaly",
  });
  await expect(receipt).toContainText("No incident");
  await expect(receipt).toContainText("Distinct rules: 1 / 3");
  await expect(receipt).toContainText("Rule families: 1 / 2");
  await expect(
    receipt.getByRole("list", { name: "Unmet conditions" }),
  ).toContainText("Distinct rules: 1 / 3");
  await expect(
    page.getByRole("button", { name: "Save human review" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Save assessment" }),
  ).toHaveCount(0);
  const firstEvidence = projection.final_state.investigation.evidence[0];
  await page
    .getByRole("button", {
      name: `Inspect evidence ${firstEvidence.id}`,
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText(firstEvidence.event_id);
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Save assessment" }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  const after = await request.get(`/api/incidents/${canonicalId}`);
  expect(after.ok()).toBeTruthy();
  expect(await after.json()).toEqual(before);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});

test("overview links open the approved near-miss receipt and exact blocked comparison without writes", async ({
  page,
  request,
}) => {
  const before = await (
    await request.get(`/api/incidents/${canonicalId}`)
  ).json();
  const writes: string[] = [];
  page.on("request", (item) => {
    if (
      new URL(item.url()).pathname.startsWith("/api/") &&
      item.method() !== "GET"
    )
      writes.push(item.url());
  });
  await page.setViewportSize({ width: 375, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const guided = page.getByRole("list", { name: "Guided investigation" });
  await expect(
    guided.getByRole("link", { name: "Atlas: why an incident forms" }),
  ).toHaveAttribute("href", "/replay?scenario=atlas-compromise");
  const loaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/replays/approved-admin",
  );
  await guided
    .getByRole("link", { name: "Approved administration: why none forms" })
    .click();
  const projection: ReplayProjection = await (await loaded).json();
  await expect(page.getByLabel("Scenario", { exact: true })).toHaveValue(
    "approved-admin",
  );
  for (let index = 0; index < projection.frames.length; index++)
    await page.getByRole("button", { name: "Step", exact: true }).click();
  const receipt = page.getByRole("region", {
    name: "Decision receipt for USR-approved-admin",
  });
  await expect(receipt).toContainText("No incident");
  await expect(receipt).toContainText("Distinct rules: 2 / 3");
  await expect(receipt).toContainText("Rule families: 1 / 2");
  await expect(receipt).toContainText("9 min within 30 min");
  await page
    .getByRole("link", { name: "Inspect completed hypothesis context" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger" }),
  ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.goto("/");
  await page
    .getByRole("link", {
      name: "APP-002: why the 2,200-record change is blocked",
    })
    .click();
  await expect(page).toHaveURL(
    /\/detections\/APP-002\?comparison=miss-service-access$/,
  );
  await expect(page.getByText("BLOCK", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /2,200 records/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: /Save proposal|Approve revision/ }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(
    await (await request.get(`/api/incidents/${canonicalId}`)).json(),
  ).toEqual(before);
  expect(writes).toEqual([]);
});

test("public detection examples and the analyst benchmark show computed fixture measurements without write controls", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  const writes: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (item) => {
    if (
      new URL(item.url()).pathname.startsWith("/api/") &&
      item.method() !== "GET"
    )
      writes.push(item.url());
  });
  await page.goto("/detections/APP-002");
  await expect(
    page.getByRole("heading", { name: "Explore the volume tradeoff" }),
  ).toBeVisible();
  await expect(page.getByRole("spinbutton")).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: /Save proposal|Approve revision|Reject revision/,
    }),
  ).toHaveCount(0);
  for (const [id, label] of [
    ["reduce-benign-volume", /1,500 records/],
    ["miss-service-access", /2,200 records/],
  ] as const) {
    const pending = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === `/api/regressions/examples/${id}`,
    );
    await page.getByRole("button", { name: label }).click();
    const response = await pending;
    expect(response.ok()).toBeTruthy();
    const result: RegressionResult = await response.json();
    await expect(
      page.getByRole("heading", { name: "Corpus comparison" }),
    ).toBeVisible();
    await expect(
      page.getByText(result.gate.decision, { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("SYNTHETIC FIXTURE MEASUREMENTS", { exact: true }),
    ).toBeVisible();
    const measurements = page.getByRole("region", {
      name: "Selected-rule fixture measurements",
    });
    for (const [metric, label] of [
      ["tp", "TP · required scenario matched"],
      ["fp", "FP · benign scenario matched"],
      ["fn", "FN · required scenario missed"],
    ] as const) {
      const row = measurements.getByRole("row").filter({ hasText: label });
      await expect(row.getByRole("cell")).toHaveText([
        String(result.metrics.before.selected_rule[metric]),
        String(result.metrics.after.selected_rule[metric]),
      ]);
    }
    await expect(
      page
        .getByRole("region", {
          name: "Scenario signal and correlation differences",
        })
        .locator("tbody tr"),
    ).toHaveCount(result.scenarios.length);
    for (const reason of result.gate.reasons)
      await expect(
        page.getByText(reason.message, { exact: true }),
      ).toBeVisible();
  }
  const benchmarkResponse = await request.get("/api/evaluations/benchmark");
  expect(benchmarkResponse.ok()).toBeTruthy();
  const benchmark: AnalystBenchmark = await benchmarkResponse.json();
  expect(benchmark.provider).toBe("deterministic");
  expect(benchmark.live_model_tested).toBe(false);
  expect(benchmark.total).toBe(benchmark.cases.length);
  await page.goto("/evaluations");
  await page
    .getByRole("button", { name: "V2 analyst benchmark", exact: true })
    .click();
  await expect(
    page
      .locator(".eval-metrics .metric")
      .filter({ hasText: "Executed obligations" })
      .locator(".metric-value"),
  ).toHaveText(String(benchmark.total));
  await expect(
    page.getByRole("button", { name: "Run deterministic suite" }),
  ).toHaveCount(0);
  const category = benchmark.cases[0].category;
  await page.getByLabel("Benchmark category").selectOption(category);
  await expect(page.locator("tbody tr")).toHaveCount(
    benchmark.cases.filter((item) => item.category === category).length,
  );
  await page.locator(".evaluation-detail summary").first().click();
  await expect(
    page.getByText("Expected behavior", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Observed result", { exact: true }).first(),
  ).toBeVisible();
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});

test("public hypotheses and hash-verifiable export stay read-only and new write routes are denied", async ({
  page,
  request,
}) => {
  const incidentResponse = await request.get(`/api/incidents/${canonicalId}`);
  expect(incidentResponse.ok()).toBeTruthy();
  const before = await incidentResponse.json();
  const apiCalls: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (item) => {
    if (new URL(item.url()).pathname.startsWith("/api/"))
      apiCalls.push(`${item.method()} ${new URL(item.url()).pathname}`);
  });
  await page.goto(`/incidents/${canonicalId}`);
  await page.getByRole("tab", { name: "Hypotheses", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger" }),
  ).toBeVisible();
  await expect(page.locator(".hypothesis-card").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save human review" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Review reason")).toHaveCount(0);
  await page.getByRole("tab", { name: "Export", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Evidence bundle" }),
  ).toBeVisible();
  const exported = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname ===
      `/api/incidents/${canonicalId}/export`,
  );
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download evidence bundle" }).click();
  const exportResponse = await exported;
  expect(exportResponse.ok()).toBeTruthy();
  const bundle = await exportResponse.json();
  expect((await downloaded).suggestedFilename()).toBe(
    `AegisGraph-${canonicalId}.json`,
  );
  const panel = page.getByRole("tabpanel");
  await expect(panel.getByRole("status")).toContainText("VALID");
  expect(bundle.manifest.projection).toBe("public_synthetic");
  await expect(panel).toContainText("unsigned and replaceable");
  await expect(panel).toContainText("does not prove source telemetry truth");
  const apiCountBeforeLocalVerification = apiCalls.length;
  const readme = bundle.files.find(
    (item: { path: string }) => item.path === "README.txt",
  );
  expect(readme).toBeTruthy();
  readme.content += "\nModified locally by the browser regression test.";
  await page.getByLabel("Verify a local bundle").setInputFiles({
    name: "modified-synthetic-bundle.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(bundle)),
  });
  await expect(panel.getByRole("status")).toContainText("MODIFIED");
  expect(apiCalls).toHaveLength(apiCountBeforeLocalVerification);
  expect(apiCalls.every((call) => call.startsWith("GET "))).toBeTruthy();

  // A bounded sample of the new persistent-write surfaces. No rate-limit flood.
  for (const path of [
    "/api/detections/APP-002/versions",
    "/api/detection-versions/browser-denial-probe/regressions",
    "/api/detection-versions/browser-denial-probe/review",
    `/api/incidents/${canonicalId}/hypotheses/account_compromise/review`,
    "/api/scenarios/isolated-anomaly/hypotheses",
  ])
    expect((await request.post(path, { data: {} })).status(), path).toBe(403);
  const after = await request.get(`/api/incidents/${canonicalId}`);
  expect(after.ok()).toBeTruthy();
  expect(await after.json()).toEqual(before);
  expect(errors).toEqual([]);
});
