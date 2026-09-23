import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "../../apps/web/node_modules/@playwright/test";

async function workbench(request: APIRequestContext) {
  const response = await request.get("/api/detections/APP-002/workbench");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function restoreBaseline(request: APIRequestContext) {
  const current = await workbench(request);
  if (current.rule.threshold === 1000) return;
  const proposed = await request.post("/api/detections/APP-002/versions", {
    data: {
      parameters: { threshold: 1000 },
      base_ruleset_digest: current.ruleset_digest,
      base_generation: current.generation,
      base_version: current.version,
      reason:
        "Restore the shipped threshold after the isolated browser workflow.",
    },
  });
  expect(proposed.ok()).toBeTruthy();
  const revision = await proposed.json();
  const compared = await request.post(
    `/api/detection-versions/${revision.id}/regressions`,
    { data: {} },
  );
  expect(compared.ok()).toBeTruthy();
  const run = await compared.json();
  expect(run.result.gate.decision).not.toBe("BLOCK");
  const reviewed = await request.post(
    `/api/detection-versions/${revision.id}/review`,
    {
      data: {
        decision: "approve",
        regression_id: run.id,
        reason:
          "Reviewed the restoration comparison and deliberately restored the original fixture baseline, including its benign alert burden.",
      },
    },
  );
  expect(reviewed.ok()).toBeTruthy();
  expect((await workbench(request)).rule.threshold).toBe(1000);
}

async function proposeAndCompare(page: Page, threshold: number) {
  await page.goto("/detections/APP-002");
  await expect(
    page.getByRole("heading", {
      name: "Abnormal account data volume",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("spinbutton", { name: "Threshold", exact: true })
    .fill(String(threshold));
  await page
    .getByLabel("Proposal reason", { exact: true })
    .fill(`Browser review of the ${threshold}-record fixture tradeoff.`);
  const proposed = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/detections/APP-002/versions") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Save proposal", exact: true })
    .click();
  const proposalResponse = await proposed;
  expect(proposalResponse.ok()).toBeTruthy();
  const revision = await proposalResponse.json();
  await expect(
    page.getByRole("heading", {
      name: `2. Inspect revision ${revision.version}`,
      exact: true,
    }),
  ).toBeVisible();
  const compared = page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith(`/api/detection-versions/${revision.id}/regressions`) &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Run corpus comparison", exact: true })
    .click();
  const comparisonResponse = await compared;
  expect(comparisonResponse.ok()).toBeTruthy();
  const run = await comparisonResponse.json();
  await expect(
    page.getByText("SYNTHETIC FIXTURE MEASUREMENTS", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", {
        name: "Scenario signal and correlation differences",
      })
      .locator("tbody tr"),
  ).toHaveCount(run.result.scenarios.length);
  return { revision, run };
}

test.beforeEach(async ({ request }) => {
  const runtime = await (await request.get("/api/runtime")).json();
  expect(runtime.app_mode).toBe("local");
  expect(runtime.capabilities.rule_workbench).toBe(1);
  await restoreBaseline(request);
});

test("typed rule proposal compares the corpus, records approval, and restores its saved history", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const cases = await (await request.get("/api/incidents")).json();
  const incidentId = cases.items[0].id;
  const original = await (
    await request.get(`/api/incidents/${incidentId}`)
  ).json();
  try {
    const { revision, run } = await proposeAndCompare(page, 1500);
    expect(run.result.gate.decision).toBe("PASS");
    expect(run.result.metrics.before.selected_rule).toEqual({
      tp: 2,
      fp: 1,
      fn: 0,
      tn: 1,
    });
    expect(run.result.metrics.after.selected_rule).toEqual({
      tp: 2,
      fp: 0,
      fn: 0,
      tn: 2,
    });
    await expect(
      page.getByRole("button", { name: "Approve revision", exact: true }),
    ).toBeDisabled();
    const reason =
      "Browser reviewer checked all fixture obligations before approving the reduced benign alert burden.";
    await page.getByLabel("Review reason", { exact: true }).fill(reason);
    await page
      .getByRole("button", { name: "Approve revision", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Revision approved.");
    expect((await workbench(request)).rule.threshold).toBe(1500);
    await page.reload();
    await expect(
      page.getByRole("heading", {
        name: `2. Inspect revision ${revision.version}`,
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByText(reason, { exact: true })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Approve revision", exact: true }),
    ).toHaveCount(0);
    const restored = await (
      await request.get(`/api/detection-versions/${revision.id}`)
    ).json();
    expect(restored.review.decision).toBe("approve");
    expect(restored.runs).toHaveLength(2); // Explicit comparison plus independent approval recomputation.
    const preserved = await (
      await request.get(`/api/incidents/${incidentId}`)
    ).json();
    expect(preserved.evidence).toEqual(original.evidence);
    expect(preserved.alerts).toEqual(original.alerts);
    expect(errors).toEqual([]);
  } finally {
    await restoreBaseline(request);
  }
});

test("BLOCK prevents approval and WARN requires an explicit acknowledgment before approval", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  try {
    const blocked = await proposeAndCompare(page, 2200);
    expect(blocked.run.result.gate.decision).toBe("BLOCK");
    await page
      .getByLabel("Review reason", { exact: true })
      .fill(
        "Reject the proposal because it loses the required service-access signal and correlation.",
      );
    await expect(
      page.getByRole("button", { name: "Approve revision", exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByText(/A blocking gate cannot be approved/),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Reject revision", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Revision rejected.");
    expect((await workbench(request)).rule.threshold).toBe(1000);

    const warning = await proposeAndCompare(page, 1100);
    expect(warning.run.result.gate.decision).toBe("WARN");
    await page
      .getByLabel("Review reason", { exact: true })
      .fill(
        "Deliberately approve the bounded unchanged fixture behavior for this browser exercise; no improvement is claimed.",
      );
    await expect(
      page.getByRole("button", { name: "Approve revision", exact: true }),
    ).toBeDisabled();
    await page
      .getByRole("checkbox", { name: /I reviewed the warning/ })
      .check();
    await page
      .getByRole("button", { name: "Approve revision", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Revision approved.");
    expect((await workbench(request)).rule.threshold).toBe(1100);
  } finally {
    await restoreBaseline(request);
  }
});

test("rule inspection supports narrow screens, light theme, high zoom, and keyboard controls", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/detections/APP-002");
  const threshold = page.getByRole("spinbutton", {
    name: "Threshold",
    exact: true,
  });
  await expect(threshold).toBeVisible();
  await threshold.focus();
  await page.keyboard.press("Tab");
  await expect(
    page.getByLabel("Proposal reason", { exact: true }),
  ).toBeFocused();
  for (const theme of ["dark", "light"]) {
    if (theme === "light")
      await page.getByRole("button", { name: "Switch to light theme" }).click();
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth + 1,
      ),
    ).toBeTruthy();
  }
  await page.setViewportSize({ width: 640, height: 900 });
  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth + 1,
    ),
  ).toBeTruthy();
  await expect(threshold).toBeVisible();
  const provenance = page
    .locator("summary")
    .filter({ hasText: /^Effective ruleset provenance$/ });
  await provenance.focus();
  await page.keyboard.press("Enter");
  await expect(provenance.locator("..")).toHaveAttribute("open", "");
});
