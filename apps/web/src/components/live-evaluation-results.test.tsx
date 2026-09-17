import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { LiveEvaluationResults } from "./live-evaluation-results";

it("retains prior provider failures when the latest live cases pass", async () => {
  render(
    <LiveEvaluationResults
      run={{
        status: "passed",
        live_cases: { total: 1, passed: 1, failed: 0, skipped: 0 },
        provider_requests_attempted: 2,
        provider_requests_succeeded: 1,
        provider_requests_failed: 1,
        attempts: [
          {
            attempt: 1,
            case_id: "LIVE-GROUNDED",
            status: "unavailable",
            http_status: 429,
          },
          {
            attempt: 2,
            case_id: "LIVE-GROUNDED",
            status: "answered",
            http_status: 200,
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("1 passed / 1 cases")).toBeVisible();
  expect(screen.getByText("1 succeeded / 1 failed")).toBeVisible();
  await userEvent.click(
    screen.getByText("Provider request history (2 attempts)"),
  );
  expect(screen.getByText("429")).toBeVisible();
  expect(screen.getByText("Unavailable")).toBeVisible();
  expect(screen.getByText("200")).toBeVisible();
});
