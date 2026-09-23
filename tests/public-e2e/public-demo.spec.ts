import { test, expect } from "../../apps/web/node_modules/@playwright/test";

test("public investigation retains evidence and both deterministic analyst examples", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByText("Read-only public demo", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open investigation" }).click();
  await expect(
    page.getByRole("heading", { name: "Evidence timeline" }),
  ).toBeVisible();
  await expect(page.getByText("Manage incident", { exact: false })).toHaveCount(
    0,
  );
  await page
    .getByRole("button", { name: /^Inspect evidence / })
    .first()
    .click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(
    drawer.getByRole("button", { name: "Save assessment" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.getByRole("tab", { name: "Entities", exact: true }).click();
  await page
    .getByRole("button", { name: "Device · DEV-UNRECOGNIZED-01", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Selected entity" }),
  ).toContainText("DEV-UNRECOGNIZED-01");
  await page
    .getByRole("button", { name: "What most likely happened?", exact: true })
    .click();
  await expect(page.getByLabel("Investigation question")).toHaveAttribute(
    "readonly",
    "",
  );
  await page.getByRole("button", { name: "Ask analyst", exact: true }).click();
  const answer = page.locator(".analysis-answer");
  await expect(answer).toContainText("deterministic");
  await expect(answer.locator(".analysis-findings > li")).not.toHaveCount(0);
  await expect(
    answer.getByRole("button", { name: "Review as finding" }),
  ).toHaveCount(0);
  await answer
    .getByRole("button", { name: /^Inspect evidence / })
    .first()
    .click();
  await expect(drawer).toBeVisible();
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page
    .getByRole("button", { name: "What malware family was used?", exact: true })
    .click();
  await page.getByRole("button", { name: "Ask analyst", exact: true }).click();
  await expect(answer).toContainText("Insufficient evidence");
  expect(errors).toEqual([]);
});

test("public proxy refuses writes and exposes no reset or API docs", async ({
  request,
}) => {
  for (const [method, path] of [
    ["PATCH", "/api/incidents/INC-fe8fa4b9508c"],
    ["POST", "/api/incidents/INC-fe8fa4b9508c/notes"],
    ["POST", "/api/incidents/INC-fe8fa4b9508c/report/approve"],
    ["POST", "/api/evaluations/run"],
    ["POST", "/api/demo-reset"],
    ["DELETE", "/api/detections"],
  ]) {
    expect((await request.fetch(path, { method, data: {} })).status()).toBe(
      403,
    );
  }
  const response = await request.post(
    "/api/incidents/INC-fe8fa4b9508c/analysis",
    {
      data: { question: "What most likely happened?" },
      headers: { Origin: "https://untrusted.example" },
    },
  );
  expect(response.status()).toBe(403);
  expect((await request.get("/api/docs")).status()).toBe(404);
  expect((await request.get("/api/openapi.json")).status()).toBe(404);
});

test("all eight primary public routes remain explorable", async ({ page }) => {
  for (const route of [
    "/",
    "/events",
    "/detections",
    "/alerts",
    "/incidents",
    "/incidents/INC-fe8fa4b9508c",
    "/evaluations",
    "/architecture",
  ]) {
    await page.goto(route);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(
      page.getByText("Read-only public demo", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // Next's global route announcer is an ARIA alert; check application errors in main.
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  }
  await page.goto("/evaluations");
  await page
    .getByRole("button", { name: "Deterministic boundary suite" })
    .click();
  await expect(
    page.getByRole("button", { name: "Run deterministic suite" }),
  ).toHaveCount(0);
  await expect(
    page
      .locator(".eval-metrics .metric")
      .filter({ hasText: "Executed cases" })
      .locator(".metric-value"),
  ).toHaveText("28");
  await expect(
    page
      .locator(".eval-metrics .metric")
      .filter({ hasText: "Passed" })
      .locator(".metric-value"),
  ).toHaveText("28");
  await expect(
    page
      .locator(".eval-metrics .metric")
      .filter({ hasText: "Failed" })
      .locator(".metric-value"),
  ).toHaveText("0");
});
