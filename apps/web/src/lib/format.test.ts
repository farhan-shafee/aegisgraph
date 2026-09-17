import { describe, expect, it } from "vitest";
import { dateTime, evidenceForEntity, time } from "./format";
import { incident } from "@/test/fixtures";
describe("evidence helpers", () => {
  it("normalizes timezone-offset timestamps into UTC consistently", () => {
    expect(time("2026-09-15T10:02:00-04:00")).toBe("14:02:00");
    expect(dateTime("2026-09-15T10:02:00-04:00")).toBe(
      "2026-09-15 · 14:02:00 UTC",
    );
  });
  it("returns only evidence linked by incident relationships", () => {
    expect(
      evidenceForEntity(
        incident.entities[0],
        incident.evidence,
        incident.relationships,
      ),
    ).toEqual(incident.evidence);
    expect(
      evidenceForEntity(
        { id: "foreign", type: "user", label: "Foreign user" },
        incident.evidence,
        incident.relationships,
      ),
    ).toEqual([]);
  });
});
