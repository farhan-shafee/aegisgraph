import { test, expect } from "../../apps/web/node_modules/@playwright/test";

test("analyst investigates, cites evidence, rejects a false premise, and approves a report", async ({
  page,
  request,
}) => {
  const queueResponse = await request.get("/api/incidents");
  expect(queueResponse.ok()).toBeTruthy();
  const incident = (await queueResponse.json()).items[0];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Operations overview" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open investigation" }).click();
  await expect(
    page.getByRole("heading", { name: incident.title, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence timeline" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /^Inspect evidence / })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog
    .getByLabel("Relevance", { exact: true })
    .selectOption("relevant");
  await dialog
    .getByLabel("Evidence annotation")
    .fill("Reviewed during the reproducible browser workflow.");
  await dialog.getByRole("button", { name: "Save assessment" }).click();
  await expect(dialog.getByRole("status")).toContainText("saved");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);

  await page.getByRole("tab", { name: "Entities", exact: true }).click();
  const device = page.getByRole("button", {
    name: "Device · DEV-UNRECOGNIZED-01",
    exact: true,
  });
  await device.click();
  await expect(
    page.getByRole("region", { name: "Selected entity" }),
  ).toContainText("DEV-UNRECOGNIZED-01");
  await page
    .getByRole("button", { name: "Filter timeline to this entity" })
    .click();
  await expect(
    page.getByText("Showing evidence related to DEV-UNRECOGNIZED-01"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear entity filter" }).click();

  await page
    .getByLabel("Investigation question")
    .fill("What most likely happened?");
  await page.getByRole("button", { name: "Ask analyst", exact: true }).click();
  const answer = page.locator(".analysis-answer");
  await expect(answer).toContainText("deterministic");
  await expect(answer.locator(".analysis-findings > li")).not.toHaveCount(0);
  const citation = answer
    .getByRole("button", { name: /^Inspect evidence / })
    .first();
  const citedId = await citation.textContent();
  await citation.click();
  await expect(page.getByRole("dialog")).toContainText(citedId!);
  await page.getByRole("button", { name: "Close evidence" }).click();

  await answer
    .getByRole("button", { name: "Review as finding" })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Review AI-assisted draft" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save finding draft" }).click();
  await expect(
    page.getByRole("button", { name: "Approve finding" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve finding" }).click();
  await expect(page.locator(".finding-card .badge-approved")).toHaveCount(1);

  await page
    .getByLabel("Investigation question")
    .fill("What malware family was used?");
  await page.getByRole("button", { name: "Ask analyst", exact: true }).click();
  await expect(answer).toContainText("Insufficient evidence");
  await expect(answer).toContainText(/malware/i);
  await expect(answer.locator(".analysis-findings > li")).toHaveCount(0);

  await page.getByLabel("Incident status").selectOption("investigating");
  await page.getByLabel("Assigned analyst").fill("demo.reviewer");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Incident changes saved",
  );

  await page.getByRole("tab", { name: "Report", exact: true }).click();
  await page.getByRole("button", { name: "Generate report draft" }).click();
  await expect(page.locator(".report-content")).toContainText(
    "Evidence Appendix",
  );
  await expect(
    page.getByRole("button", { name: "Approve report", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "I have reviewed this report and its supporting evidence.",
    })
    .check();
  await page
    .getByRole("button", { name: "Approve report", exact: true })
    .click();
  await expect(page.getByText(/Approved by demo.analyst/)).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Markdown" }).click();
  expect((await download).suggestedFilename()).toContain("approved.md");

  await page.getByRole("tab", { name: "Notes & audit", exact: true }).click();
  await expect(page.locator(".audit-list")).toContainText("Report approved");
  await expect(page.locator(".audit-list")).toContainText(
    "Ai result validated",
  );
  expect(errors).toEqual([]);
});

test("server filters and paginates canonical events", async ({ page }) => {
  await page.goto("/events");
  await page.getByLabel("Source", { exact: true }).selectOption("identity");
  await page.getByRole("button", { name: "Filter", exact: true }).click();
  await expect(page).toHaveURL(/source=identity/);
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await page.getByRole("link", { name: "Next page" }).click();
  await expect(page).toHaveURL(/offset=25/);
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await page.getByLabel("Search events").fill("EVT-SCENARIO-002");
  await page.getByRole("button", { name: "Filter", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("EVT-SCENARIO-002");
});

test("evaluation results come from an executed suite", async ({ page }) => {
  await page.goto("/evaluations");
  const result = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/evaluations/run") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: /Run.*suite|Run evaluation/i })
    .click();
  const run = await (await result).json();
  expect(run.total).toBeGreaterThan(0);
  expect(run.failed).toBe(0);
  expect(run.passed).toBe(
    run.cases.filter((item: { passed: boolean }) => item.passed).length,
  );
  expect(run.live_model_tested).toBe(false);
  await expect(page.locator("main")).toContainText(String(run.total));
  await expect(page.locator("main")).toContainText(/deterministic/i);
});

for (const width of [320, 375, 430, 768, 1280, 1440, 1920]) {
  test(`core routes have no page overflow at ${width}px`, async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 900 });
    const incidentId = (await (await request.get("/api/incidents")).json())
      .items[0].id;
    for (const route of [
      "/",
      "/events",
      "/detections",
      "/alerts",
      "/incidents",
      `/incidents/${incidentId}`,
      "/evaluations",
      "/architecture",
    ]) {
      const response = await page.goto(route);
      expect(response?.ok(), route).toBeTruthy();
      await expect(page.locator("main h1"), route).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: /Unable to load|Incident unavailable/,
        }),
      ).toHaveCount(0);
      const dimensions = await page.evaluate(() => ({
        pageWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
      }));
      expect(
        dimensions.pageWidth,
        `${route}: page overflow at ${width}`,
      ).toBeLessThanOrEqual(dimensions.viewportWidth + 1);
    }
    // Exercise the non-default graph and report surfaces at every target width.
    await page.goto(`/incidents/${incidentId}`);
    await page.getByRole("tab", { name: "Entities", exact: true }).click();
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth + 1,
      ),
    ).toBeTruthy();
  });
}
