import { test, expect } from "../../apps/web/node_modules/@playwright/test";
import { readFile } from "node:fs/promises";

test("human review stays distinct from evidence status and becomes stale after an annotation", async ({
  page,
  request,
}) => {
  const incidentId = (await (await request.get("/api/incidents")).json())
    .items[0].id;
  const before = await (
    await request.get(`/api/incidents/${incidentId}/hypotheses`)
  ).json();
  const hypothesis = before.items.find(
    (item: { supporting_evidence_ids: string[] }) =>
      item.supporting_evidence_ids.length > 0,
  );
  await page.goto(`/incidents/${incidentId}`);
  await page.getByRole("tab", { name: "Hypotheses", exact: true }).click();
  const card = page
    .locator(".hypothesis-card")
    .filter({
      has: page.getByRole("heading", { name: hypothesis.title, exact: true }),
    });
  await card.getByLabel("Human decision").selectOption("accepted");
  await card
    .getByLabel("Review reason")
    .fill(
      "Retain this scoped working hypothesis; inspect remaining identity gaps.",
    );
  await card.getByRole("button", { name: "Save human review" }).click();
  await expect(card).toContainText(/Accepted · revision/);
  const reviewed = await (
    await request.get(`/api/incidents/${incidentId}/hypotheses`)
  ).json();
  expect(
    reviewed.items.find((item: { id: string }) => item.id === hypothesis.id)
      .epistemic_status,
  ).toBe(hypothesis.epistemic_status);
  await page.reload();
  await page.getByRole("tab", { name: "Hypotheses", exact: true }).click();
  await expect(card).toContainText(/Accepted · revision/);
  await card
    .getByRole("button", {
      name: hypothesis.supporting_evidence_ids[0],
      exact: true,
    })
    .click();
  const drawer = page.getByRole("dialog");
  await drawer
    .getByLabel("Evidence annotation")
    .fill("New source review context recorded after hypothesis acceptance.");
  await drawer.getByRole("button", { name: "Save assessment" }).click();
  await expect(drawer.getByRole("status")).toContainText("saved");
  await page.keyboard.press("Escape");
  await expect(card).toContainText(/Stale · revision/);
  await expect(card).toContainText("older evidence or findings");
});

test("downloaded evidence verifies in the browser and detects changed, missing and extra logical files without upload", async ({
  page,
  request,
}) => {
  const incidentId = (await (await request.get("/api/incidents")).json())
    .items[0].id;
  await page.goto(`/incidents/${incidentId}`);
  await page.getByRole("tab", { name: "Export", exact: true }).click();
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download evidence bundle", exact: true })
    .click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe(`AegisGraph-${incidentId}.json`);
  const bytes = await readFile((await download.path())!);
  const original = JSON.parse(bytes.toString("utf8"));
  await expect(page.getByRole("status")).toContainText("VALID");
  const requests: string[] = [];
  page.on("request", (event) => {
    if (event.url().includes("/api/")) requests.push(event.url());
  });
  const input = page.getByLabel("Verify a local bundle");
  await input.setInputFiles({
    name: "original.json",
    mimeType: "application/json",
    buffer: bytes,
  });
  await expect(page.getByRole("status")).toContainText("VALID");
  const modified = structuredClone(original);
  modified.files[0].content += " ";
  const missing = structuredClone(original);
  missing.files.pop();
  const extra = structuredClone(original);
  extra.files.push({ path: "extra.txt", content: "Synthetic extra file." });
  for (const [status, bundle] of [
    ["MODIFIED", modified],
    ["MISSING FILE", missing],
    ["UNEXPECTED FILE", extra],
  ] as const) {
    await input.setInputFiles({
      name: "changed.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(bundle)),
    });
    await expect(page.getByRole("status")).toContainText(status);
  }
  expect(requests).toEqual([]);
  await expect(page.locator("main")).toContainText(/unsigned/i);
});
