import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AuditEntry } from "@/lib/types";
import { incident } from "@/test/fixtures";
import { NotesAndAudit } from "./incident-records";

function auditRow(action: string) {
  const row = screen.getByText(action, { selector: "strong" }).closest("li");
  if (!row) throw new Error("Audit row was not rendered");
  return within(row);
}

describe("audit actor attribution", () => {
  it("uses the recorded actor type even when the actor name suggests another role", () => {
    const audit: AuditEntry[] = [
      {
        id: "AUD-1",
        timestamp: incident.created_at,
        actor: "aegisgraph",
        actor_type: "system",
        action: "incident_created",
      },
      {
        id: "AUD-2",
        timestamp: incident.created_at,
        actor: "system",
        actor_type: "human",
        action: "status_changed",
      },
      {
        id: "AUD-3",
        timestamp: incident.created_at,
        actor: "demo.analyst",
        actor_type: "model",
        action: "model_observation_recorded",
      },
      {
        id: "AUD-4",
        timestamp: incident.created_at,
        actor: "model:fixture",
        action: "legacy_record_imported",
      },
    ];
    render(
      <NotesAndAudit incident={{ ...incident, audit }} refresh={vi.fn()} />,
    );

    expect(auditRow("Incident created").getByText("System")).toBeVisible();
    expect(auditRow("Incident created").queryByText("Analyst")).toBeNull();
    expect(auditRow("Status changed").getByText("Analyst")).toBeVisible();
    expect(auditRow("Status changed").queryByText("System")).toBeNull();
    expect(
      auditRow("Model observation recorded").getByText("Model"),
    ).toBeVisible();
    expect(
      auditRow("Legacy record imported").getByText("Unspecified"),
    ).toBeVisible();
  });

  it("labels explicitly AI-assisted findings without changing the recorded author role", () => {
    const audit: AuditEntry[] = [
      {
        id: "AUD-1",
        timestamp: incident.created_at,
        actor: "demo.analyst",
        actor_type: "human",
        action: "finding_created",
        after: { ai_assisted: true, approved: false },
      },
      {
        id: "AUD-2",
        timestamp: incident.created_at,
        actor: "aegisgraph",
        actor_type: "system",
        action: "ai_result_validated",
        after: { provider: "deterministic", status: "answered" },
      },
    ];
    render(
      <NotesAndAudit incident={{ ...incident, audit }} refresh={vi.fn()} />,
    );

    const finding = auditRow("Finding created");
    expect(finding.getByText("Analyst")).toBeVisible();
    expect(finding.getByText("AI-assisted finding")).toBeVisible();
    expect(finding.queryByText("Model")).toBeNull();
    const validation = auditRow("Ai result validated");
    expect(validation.getByText("System")).toBeVisible();
    expect(validation.queryByText("AI-assisted finding")).toBeNull();
  });
});
