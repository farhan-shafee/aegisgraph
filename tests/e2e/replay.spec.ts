import { test, expect } from "../../apps/web/node_modules/@playwright/test";
import type {
  ReplayProjection,
  ScenarioAnalysis,
} from "../../apps/web/src/lib/replay-types";

test("replay preserves its causal cursor through pause, resume, step, reset, and scenario selection", async ({
  page,
}) => {
  const errors: string[] = [];
  const writes: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (
      new URL(request.url()).pathname.startsWith("/api/") &&
      request.method() !== "GET"
    )
      writes.push(`${request.method()} ${request.url()}`);
  });
  await page.clock.install({ time: new Date("2026-09-15T10:00:00Z") });
  const loaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/replays/atlas-compromise",
  );
  await page.goto("/replay");
  const projectionResponse = await loaded;
  expect(projectionResponse.ok()).toBeTruthy();
  const projection: ReplayProjection = await projectionResponse.json();
  const progress = page.getByRole("progressbar", { name: "Replay progress" });
  await expect(
    page.getByRole("button", { name: "Start", exact: true }),
  ).toBeEnabled();
  await page.clock.pauseAt(new Date("2026-09-15T11:00:00Z"));
  await expect(page.getByLabel("Scenario", { exact: true })).toHaveValue(
    "atlas-compromise",
  );
  await expect(page.getByLabel("Playback speed")).toHaveValue("20");
  await expect(progress).toHaveAttribute("value", "0");
  await expect(progress).toHaveAttribute(
    "max",
    String(projection.frames.length),
  );
  await expect(
    page.getByText("4,000 background records initialized before playback"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Completed evidence" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger" }),
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Start", exact: true }).click();
  await page.clock.runFor(100);
  await expect(progress).toHaveAttribute("value", "1");
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page.clock.runFor(5000);
  await expect(progress).toHaveAttribute("value", "1");
  await page.getByRole("button", { name: "Step", exact: true }).click();
  await expect(progress).toHaveAttribute("value", "2");
  await expect(
    page.getByRole("list", { name: "Reached replay frames", exact: true }),
  ).toContainText("Telemetry arrival");
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.clock.runFor(100);
  await expect(progress).toHaveAttribute("value", "3");

  // Inspecting a reached row pauses before a future frame can replace the focus target.
  const history = page.getByRole("list", {
    name: "Reached replay frames",
    exact: true,
  });
  await history.locator("summary").last().focus();
  await expect(
    page.getByRole("button", { name: "Resume", exact: true }),
  ).toBeVisible();
  await page.clock.runFor(5000);
  await expect(progress).toHaveAttribute("value", "3");
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(progress).toHaveAttribute("value", "0");
  await expect(history).toHaveCount(0);

  const nextProjection = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/replays/isolated-anomaly",
  );
  await page
    .getByLabel("Scenario", { exact: true })
    .selectOption("isolated-anomaly");
  expect((await nextProjection).ok()).toBeTruthy();
  await expect(
    page.getByRole("heading", {
      name: "Isolated unfamiliar sign-in",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start", exact: true }),
  ).toBeEnabled();
  await page.clock.runFor(5000);
  await expect(progress).toHaveAttribute("value", "0");
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});

test("reduced-motion replay completes manually and opens read-only evidence, hypotheses, and both curated answers", async ({
  page,
}) => {
  const errors: string[] = [];
  const analystCalls: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.includes("/analysis/"))
      analystCalls.push(request.method());
  });
  await page.setViewportSize({ width: 320, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.clock.install({ time: new Date("2026-09-15T10:00:00Z") });
  const loaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/replays/isolated-anomaly",
  );
  await page.goto("/replay?scenario=isolated-anomaly");
  const projection: ReplayProjection = await (await loaded).json();
  await expect(
    page.getByRole("button", { name: "Start", exact: true }),
  ).toBeEnabled();
  await page.clock.pauseAt(new Date("2026-09-15T11:00:00Z"));
  await expect(page.getByText(/Reduced motion: manual Step/)).toBeVisible();
  await page.clock.runFor(5000);
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "0");
  expect(projection.frames.length).toBeLessThan(50);
  for (const _frame of projection.frames)
    await page.getByRole("button", { name: "Step", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Observation scope", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save human review" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Open canonical Atlas case" }),
  ).toHaveCount(0);
  expect(analystCalls).toEqual([]);

  const evidence = projection.final_state.investigation.evidence[0];
  await page
    .getByRole("button", {
      name: `Inspect evidence ${evidence.id}`,
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText(evidence.event_id);
  await expect(
    page.getByRole("dialog").getByLabel("Evidence annotation"),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  for (const [questionId, question] of [
    ["summary", "What most likely happened?"],
    ["malware", "What malware family was used?"],
  ] as const) {
    const response = page.waitForResponse(
      (item) =>
        new URL(item.url()).pathname ===
        `/api/scenarios/isolated-anomaly/analysis/${questionId}`,
    );
    await page.getByRole("button", { name: question, exact: true }).click();
    const result: ScenarioAnalysis = await (await response).json();
    expect(result.analysis.provider).toBe("deterministic");
    expect(result.scope_id).toBe(projection.final_state.investigation.id);
    expect(result.provenance).toEqual(projection.provenance);
    const answer = page.getByRole("region", {
      name: "Scenario analyst answer",
    });
    await expect(answer).toContainText(question);
    await expect(answer).toContainText("Provider: deterministic");
    if (questionId === "malware") {
      expect(result.analysis.status).toBe("insufficient_evidence");
      await expect(answer).toContainText("Insufficient evidence");
    }
  }
  expect(analystCalls).toEqual(["GET", "GET"]);
  for (const theme of ["light", "dark"]) {
    await page
      .getByRole("button", { name: `Switch to ${theme} theme` })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth + 1,
      ),
      `${theme} replay must fit 320px`,
    ).toBeTruthy();
  }
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Hypothesis ledger" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Scenario analyst answer" }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});
