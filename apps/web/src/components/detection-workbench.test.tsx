import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import type {
  DetectionWorkbenchData,
  RegressionResult,
  RevisionDetail,
  RuleRevision,
} from "@/lib/detection-types";
import { useCapability, usePublicDemo } from "./demo-mode";
import { DetectionWorkbench } from "./detection-workbench";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
vi.mock("./demo-mode", () => ({
  usePublicDemo: vi.fn(() => false),
  useCapability: vi.fn(() => true),
}));

const initial: DetectionWorkbenchData = {
  rule: {
    id: "APP-002",
    name: "Abnormal account data volume",
    severity: "high",
    kind: "data_volume",
    description: "A successful query accesses at least 1,000 records.",
    threshold: 1000,
    window_minutes: 0,
  },
  version: 1,
  generation: 0,
  ruleset_digest: "a".repeat(64),
  read_only: false,
  parameters: [
    {
      name: "threshold",
      label: "Threshold",
      minimum: 100,
      maximum: 10000,
      step: 1,
      default: 1000,
      value: 1000,
    },
  ],
  revisions: [],
  revision_count: 0,
};
const revision: RuleRevision = {
  id: "REV-test",
  rule_id: "APP-002",
  version: 2,
  parent_version: 1,
  base_generation: 0,
  base_ruleset_digest: initial.ruleset_digest,
  snapshot: { ...initial.rule, threshold: 1500 },
  reason: "Reduce reconciliation noise",
  actor_label: "demo.analyst",
  created_at: "2026-09-23T12:00:00+00:00",
  status: "proposed",
};
const before = {
  selected_rule: { tp: 2, fp: 1, fn: 0, tn: 1 },
  selected_rule_required_scenarios: 2,
  selected_rule_benign_scenarios: 2,
  selected_rule_other_scenarios: 4,
  required_detection_hits: 26,
  required_detection_total: 26,
  benign_alert_count: 3,
  alert_count: 30,
  incident_count: 4,
  correlation_mismatches: 0,
};
const comparison: RegressionResult = {
  selected_rule_id: "APP-002",
  measurement_scope: "synthetic_fixture",
  measurement_definitions: {},
  baseline_ruleset_digest: "a".repeat(64),
  proposed_ruleset_digest: "b".repeat(64),
  corpus_digest: "c".repeat(64),
  parameter_changes: [{ parameter: "threshold", before: 1000, after: 1500 }],
  metrics: {
    before,
    after: {
      ...before,
      selected_rule: { tp: 2, fp: 0, fn: 0, tn: 2 },
      benign_alert_count: 2,
      alert_count: 29,
    },
  },
  scenarios: [
    {
      scenario_id: "bulk-automation",
      classification: "benign",
      expected_rule_ids: ["APP-002"],
      required_rule_ids: [],
      forbidden_rule_ids: [],
      expected_incident_count: 0,
      before: {
        rule_ids: ["APP-002"],
        rule_match_counts: { "APP-002": 1 },
        alert_count: 1,
        incident_count: 0,
        missed_required_rule_ids: [],
        unexpected_rule_ids: [],
        forbidden_rule_ids: [],
        correlation_matches: true,
      },
      after: {
        rule_ids: [],
        rule_match_counts: {},
        alert_count: 0,
        incident_count: 0,
        missed_required_rule_ids: [],
        unexpected_rule_ids: [],
        forbidden_rule_ids: [],
        correlation_matches: true,
      },
      added_rule_ids: [],
      removed_rule_ids: ["APP-002"],
    },
  ],
  regression_count: 0,
  gate: {
    decision: "PASS",
    reasons: [
      {
        code: "fixture_improvement",
        message:
          "The proposal reduces benign-fixture alerts without violating fixture obligations.",
      },
    ],
  },
};
const run = {
  id: "RGR-test",
  revision_id: revision.id,
  result: comparison,
  created_at: revision.created_at,
};
const detail = (): RevisionDetail => ({ revision, runs: [], review: null });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api).mockReset();
  vi.mocked(usePublicDemo).mockReturnValue(false);
  vi.mocked(useCapability).mockReturnValue(true);
});

describe("detection workbench", () => {
  it("keeps public examples read-only and labels their actual populations", async () => {
    vi.mocked(usePublicDemo).mockReturnValue(true);
    vi.mocked(api).mockResolvedValue(comparison);
    render(<DetectionWorkbench initial={{ ...initial, read_only: true }} />);
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /save proposal/i }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /1,500 records/i }),
    );
    expect(
      await screen.findByText("SYNTHETIC FIXTURE MEASUREMENTS"),
    ).toBeVisible();
    expect(screen.getByText(/2 required scenarios/i)).toBeVisible();
    expect(screen.getByText(/2 benign scenarios/i)).toBeVisible();
    expect(screen.getByText(/4 other scenarios/i)).toBeVisible();
    expect(screen.getByText("PASS", { selector: ".badge" })).toBeVisible();
    expect(api).toHaveBeenCalledWith(
      "/regressions/examples/reduce-benign-volume",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(
      vi
        .mocked(api)
        .mock.calls.every(
          ([, options]) => !options?.method || options.method === "GET",
        ),
    ).toBe(true);
  });

  it("saves an immutable proposal, compares it, and approves only with a reason and run", async () => {
    let approved = false;
    let ran = false;
    vi.mocked(api).mockImplementation(async (path, options) => {
      if (path === "/detections/APP-002/versions") return revision;
      if (path.endsWith("/regressions")) {
        ran = true;
        return run;
      }
      if (path.endsWith("/review")) {
        approved = true;
        return { decision: "approve" };
      }
      if (path.endsWith("/workbench"))
        return {
          ...initial,
          version: 2,
          generation: 1,
          revisions: [{ ...revision, status: "approved" }],
        };
      if (options?.method === "POST") throw new Error("Unexpected write");
      return {
        revision: { ...revision, status: approved ? "approved" : "proposed" },
        runs: ran ? [run] : [],
        review: approved
          ? {
              id: "RRV-test",
              decision: "approve",
              reason: "Reviewed all scenarios",
              actor_label: "demo.analyst",
              regression_id: run.id,
              created_at: revision.created_at,
            }
          : null,
      };
    });
    const user = userEvent.setup();
    render(<DetectionWorkbench initial={initial} />);
    await user.clear(screen.getByRole("spinbutton", { name: "Threshold" }));
    await user.type(
      screen.getByRole("spinbutton", { name: "Threshold" }),
      "1500",
    );
    await user.type(
      screen.getByLabelText("Proposal reason"),
      "Reduce reconciliation noise",
    );
    await user.click(screen.getByRole("button", { name: "Save proposal" }));
    const compare = await screen.findByRole("button", {
      name: "Run corpus comparison",
    });
    await waitFor(() => expect(compare).toBeEnabled());
    await user.click(compare);
    expect(
      await screen.findByText("PASS", { selector: ".badge" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Approve revision" }),
    ).toBeDisabled();
    await user.type(
      screen.getByLabelText("Review reason"),
      "Reviewed all scenarios",
    );
    await user.click(screen.getByRole("button", { name: "Approve revision" }));
    expect(await screen.findByText(/Revision approved\./)).toBeVisible();
    expect(api).toHaveBeenCalledWith(
      "/detections/APP-002/versions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          parameters: { threshold: 1500 },
          base_ruleset_digest: initial.ruleset_digest,
          base_generation: 0,
          base_version: 1,
          reason: "Reduce reconciliation noise",
        }),
      }),
    );
    expect(api).toHaveBeenCalledWith(
      "/detection-versions/REV-test/review",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          decision: "approve",
          regression_id: "RGR-test",
          reason: "Reviewed all scenarios",
        }),
      }),
    );
  });

  it("prevents a BLOCK approval while allowing explicit rejection", async () => {
    vi.mocked(api).mockResolvedValue({
      ...detail(),
      runs: [
        {
          ...run,
          result: {
            ...comparison,
            gate: {
              decision: "BLOCK",
              reasons: [
                {
                  code: "required_detection_missing",
                  message: "APP-002 misses the service-access fixture.",
                },
              ],
            },
          },
        },
      ],
    });
    render(
      <DetectionWorkbench
        initial={{ ...initial, revisions: [revision], revision_count: 1 }}
      />,
    );
    await screen.findByText("BLOCK", { selector: ".badge" });
    await userEvent.type(
      screen.getByLabelText("Review reason"),
      "Required service detection is lost",
    );
    expect(
      screen.getByRole("button", { name: "Approve revision" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Reject revision" }),
    ).toBeEnabled();
  });

  it("requires deliberate acknowledgment before a WARN approval", async () => {
    vi.mocked(api).mockResolvedValue({
      ...detail(),
      runs: [
        {
          ...run,
          result: {
            ...comparison,
            gate: {
              decision: "WARN",
              reasons: [
                {
                  code: "no_observed_improvement",
                  message: "No measured improvement; human review is required.",
                },
              ],
            },
          },
        },
      ],
    });
    render(
      <DetectionWorkbench
        initial={{ ...initial, revisions: [revision], revision_count: 1 }}
      />,
    );
    await screen.findByText("WARN", { selector: ".badge" });
    await userEvent.type(
      screen.getByLabelText("Review reason"),
      "I reviewed the unchanged fixture outcomes",
    );
    expect(
      screen.getByRole("button", { name: "Approve revision" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /reviewed the warning/i }),
    );
    expect(
      screen.getByRole("button", { name: "Approve revision" }),
    ).toBeEnabled();
  });

  it("handles a stale baseline without silently retrying the write", async () => {
    vi.mocked(api)
      .mockRejectedValueOnce(
        new ApiError(
          "Ruleset changed; refresh the workbench before proposing",
          409,
        ),
      )
      .mockResolvedValue(initial);
    render(<DetectionWorkbench initial={initial} />);
    await userEvent.clear(
      screen.getByRole("spinbutton", { name: "Threshold" }),
    );
    await userEvent.type(
      screen.getByRole("spinbutton", { name: "Threshold" }),
      "1500",
    );
    await userEvent.type(
      screen.getByLabelText("Proposal reason"),
      "Reassess volume",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save proposal" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ruleset changed",
    );
    expect(
      screen.getByRole("button", { name: "Save proposal" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Refresh workbench" }),
    );
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/detections/APP-002/workbench"),
    );
    expect(
      vi
        .mocked(api)
        .mock.calls.filter(([, options]) => options?.method === "POST"),
    ).toHaveLength(1);
  });

  it("restores stored results and reviewer provenance after opening history", async () => {
    vi.mocked(api).mockResolvedValue({
      revision: { ...revision, status: "approved" },
      runs: [run],
      review: {
        id: "RRV-history",
        decision: "approve",
        reason: "Recorded historical review",
        actor_label: "demo.reviewer",
        regression_id: run.id,
        created_at: revision.created_at,
      },
    });
    render(
      <DetectionWorkbench
        initial={{
          ...initial,
          revisions: [{ ...revision, status: "approved" }],
          revision_count: 1,
        }}
      />,
    );
    expect(await screen.findByText("Recorded historical review")).toBeVisible();
    expect(screen.getByText(/demo.reviewer/)).toBeVisible();
    expect(screen.queryByLabelText("Review reason")).not.toBeInTheDocument();
    expect(api).toHaveBeenCalledWith(
      "/detection-versions/REV-test",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("makes no feature requests when the backend capability is absent", () => {
    vi.mocked(useCapability).mockReturnValue(false);
    render(<DetectionWorkbench initial={initial} />);
    expect(screen.getByText(/workbench is not available/i)).toBeVisible();
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(api).not.toHaveBeenCalled();
  });

  it("does not offer to repeat a saved decision when the following refresh fails", async () => {
    vi.mocked(api).mockImplementation(async (path, options) => {
      if (options?.method === "POST") return { decision: "approve" };
      if (path.endsWith("/workbench"))
        throw new ApiError("Service temporarily unavailable", 503);
      return { ...detail(), runs: [run] };
    });
    render(
      <DetectionWorkbench
        initial={{ ...initial, revisions: [revision], revision_count: 1 }}
      />,
    );
    await screen.findByText("PASS", { selector: ".badge" });
    await userEvent.type(
      screen.getByLabelText("Review reason"),
      "Reviewed fixture tradeoffs",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Approve revision" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /decision was saved/i,
    );
    expect(
      screen.queryByRole("button", { name: "Approve revision" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save proposal" }),
    ).toBeDisabled();
    expect(
      vi
        .mocked(api)
        .mock.calls.filter(([, options]) => options?.method === "POST"),
    ).toHaveLength(1);
  });

  it("retries a failed public comparison without issuing a write", async () => {
    vi.mocked(usePublicDemo).mockReturnValue(true);
    vi.mocked(api)
      .mockRejectedValueOnce(
        new ApiError("Comparison temporarily unavailable", 503),
      )
      .mockResolvedValue(comparison);
    render(<DetectionWorkbench initial={{ ...initial, read_only: true }} />);
    await userEvent.click(
      screen.getByRole("button", { name: /1,500 records/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Comparison temporarily unavailable",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Retry comparison" }),
    );
    expect(
      await screen.findByText("PASS", { selector: ".badge" }),
    ).toBeVisible();
    expect(vi.mocked(api).mock.calls).toHaveLength(2);
    expect(
      vi.mocked(api).mock.calls.every(([, options]) => !options?.method),
    ).toBe(true);
  });

  it("keeps unchanged, fractional, and out-of-range parameter proposals disabled", async () => {
    render(<DetectionWorkbench initial={initial} />);
    await userEvent.type(
      screen.getByLabelText("Proposal reason"),
      "Evaluate the bounded parameter",
    );
    const input = screen.getByRole("spinbutton", { name: "Threshold" });
    const save = screen.getByRole("button", { name: "Save proposal" });
    expect(save).toBeDisabled();
    for (const value of ["1500.5", "10001", "99"]) {
      await userEvent.clear(input);
      await userEvent.type(input, value);
      expect(save).toBeDisabled();
    }
    expect(api).not.toHaveBeenCalled();
  });
});
