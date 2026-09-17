import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EvaluationResults } from "./evaluation-results";
import { api } from "@/lib/api";
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const run = {
  id: "EVAL-001",
  provider: "deterministic",
  total: 3,
  passed: 2,
  failed: 1,
  cases: [
    {
      id: "GND-1",
      category: "grounding",
      name: "Valid citation accepted",
      passed: true,
      detail: "Accepted an existing reference.",
    },
    {
      id: "GND-2",
      category: "grounding",
      name: "Unknown citation rejected",
      passed: true,
    },
    {
      id: "INJ-1",
      category: "prompt_injection",
      name: "Untrusted instruction isolated",
      passed: false,
      detail: "Boundary assertion failed.",
    },
  ],
};
describe("evaluation display", () => {
  it("renders actual failed cases, supports filtering, and exposes case details", async () => {
    render(<EvaluationResults initial={run} />);
    expect(screen.getByText("Showing 3 of 3 executed cases")).toBeVisible();
    await userEvent.selectOptions(
      screen.getByLabelText("Evaluation category"),
      "prompt_injection",
    );
    expect(screen.getByText("Showing 1 of 3 executed cases")).toBeVisible();
    expect(
      screen.queryByText("Valid citation accepted"),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByText("Untrusted instruction isolated", {
        selector: "summary",
      }),
    );
    expect(screen.getByText("Boundary assertion failed.")).toBeVisible();
  });
  it("does not display invented scores before a run and loads executed results on request", async () => {
    vi.mocked(api).mockResolvedValue(run);
    render(<EvaluationResults initial={null} />);
    expect(screen.getByText("No evaluation has been run")).toBeVisible();
    expect(screen.queryByText("Passed")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Run deterministic suite" }),
    );
    expect(
      await screen.findByText("Showing 3 of 3 executed cases"),
    ).toBeVisible();
    expect(api).toHaveBeenCalledWith("/evaluations/run", { method: "POST" });
  });
});
