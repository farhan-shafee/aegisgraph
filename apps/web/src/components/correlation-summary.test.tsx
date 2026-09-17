import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CorrelationSummary } from "./correlation-summary";
describe("correlation explanation", () => {
  it("renders only server-provided counts and distinguishes supporting context", () => {
    render(
      <CorrelationSummary
        correlation={{
          principal_ids: ["USR-01"],
          alert_count: 10,
          distinct_rule_count: 9,
          rule_ids: [],
          rule_families: ["AUTH", "IAM"],
          first_alert_at: "2026-09-15T14:02:00Z",
          last_alert_at: "2026-09-15T14:24:00Z",
          span_minutes: 22,
          window_minutes: 30,
          minimum_rules: 3,
          minimum_families: 2,
          grouping_keys: ["principal", "event_time"],
          context_only: ["device", "session", "ip"],
          explanation: ["Fixture rationale"],
        }}
      />,
    );
    expect(screen.getByText("9")).toBeVisible();
    expect(
      screen.getByText("10 alerts · minimum 3 distinct rules"),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Device, session, and IP relationships provide investigation context/,
      ),
    ).toBeVisible();
  });
  it("does not manufacture a correlation rationale when the API omitted it", () => {
    const { container } = render(
      <CorrelationSummary correlation={undefined} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
