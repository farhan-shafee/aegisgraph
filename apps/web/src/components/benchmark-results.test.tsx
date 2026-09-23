import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { BenchmarkResults } from "./benchmark-results";
import type { AnalystBenchmark } from "@/lib/benchmark-types";

const benchmark: AnalystBenchmark = {
  format_version: "1",
  fixture_version: "1",
  provider: "deterministic",
  live_model_tested: false,
  scope: "Synthetic application-boundary obligations.",
  total: 2,
  passed: 1,
  failed: 1,
  provenance: {
    fixture_digest: "f".repeat(64),
    corpus_digest: "c".repeat(64),
    ruleset_digest: "r".repeat(64),
  },
  metrics: [
    {
      id: "citation",
      label: "Citation validity",
      passed: 1,
      total: 2,
      definition: "References must belong to the bounded scope.",
    },
  ],
  cases: [
    {
      id: "case-1",
      category: "citation",
      name: "Foreign reference",
      passed: true,
      expected: { status: "rejected", citation_valid: false },
      actual: { status: "rejected", citation_valid: false },
    },
    {
      id: "case-2",
      category: "insufficient",
      name: "False premise",
      passed: false,
      expected: {
        status: "insufficient_evidence",
        missing_evidence_types: ["endpoint_forensics"],
      },
      actual: { execution_error: "Boundary mismatch" },
    },
  ],
};

it("shows actual denominators, failed obligations and version provenance without claiming AI accuracy", async () => {
  render(<BenchmarkResults run={benchmark} />);
  expect(screen.getByText("1 / 2")).toBeVisible();
  expect(screen.getByText(/Metric populations overlap/)).toBeVisible();
  await userEvent.selectOptions(
    screen.getByLabelText("Benchmark result"),
    "failed",
  );
  expect(screen.queryByText("Foreign reference")).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("False premise"));
  expect(screen.getByText(/Boundary mismatch/)).toBeVisible();
  await userEvent.click(screen.getByText("Fixture and ruleset provenance"));
  expect(screen.getByText("f".repeat(64))).toBeVisible();
});
