import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { DemoModeProvider } from "./demo-mode";
import { HypothesisLedger } from "./hypothesis-ledger";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const mockedApi = vi.mocked(api);
const provenance = {
  scenario_id: "atlas-compromise",
  scenario_version: "1",
  ruleset_digest: "a".repeat(64),
};
const row = {
  id: "HYP-1",
  kind: "account_compromise",
  title: "Account compromise",
  epistemic_status: "PARTIALLY_SUPPORTED",
  supporting_evidence_ids: ["EVD-1"],
  contradicting_evidence_ids: [],
  missing_evidence: [
    {
      category: "identity_confirmation",
      guidance:
        "Identity confirmation would help establish who used this account.",
    },
  ],
  related_finding_ids: [],
  provenance: {},
  first_observed_at: null,
  as_of: null,
  review: {
    version: 0,
    status: "open",
    recorded_status: "open",
    actor_label: null,
    reason: null,
    created_at: null,
    related_finding_ids: [],
  },
};
const ledger = {
  scope_id: "INC-1",
  context_digest: "b".repeat(64),
  read_only: false,
  items: [row],
};
beforeEach(() => vi.resetAllMocks());

it("shows supporting citations and conditional gaps without equating review with evidence status", async () => {
  mockedApi.mockResolvedValue(ledger);
  const inspect = vi.fn();
  render(
    <HypothesisLedger
      endpoint="/incidents/INC-1/hypotheses"
      incidentId="INC-1"
      onEvidence={inspect}
    />,
  );
  await userEvent.click(await screen.findByRole("button", { name: "EVD-1" }));
  expect(inspect).toHaveBeenCalledWith("EVD-1");
  expect(screen.getByText(/Partially supported/i)).toBeVisible();
  await userEvent.click(screen.getByText("What would confirm or reject this?"));
  expect(screen.getByText(/Identity confirmation would help/)).toBeVisible();
  expect(mockedApi).toHaveBeenCalledTimes(1);
});

it("requires an explicit reason and sends the loaded version and context on human review", async () => {
  mockedApi.mockResolvedValue(ledger);
  const changed = vi.fn().mockResolvedValue(undefined);
  render(
    <HypothesisLedger
      endpoint="/incidents/INC-1/hypotheses"
      incidentId="INC-1"
      onEvidence={vi.fn()}
      onChanged={changed}
    />,
  );
  const button = await screen.findByRole("button", {
    name: "Save human review",
  });
  expect(button).toBeDisabled();
  await userEvent.selectOptions(
    screen.getByLabelText("Human decision"),
    "accepted",
  );
  await userEvent.type(
    screen.getByLabelText("Review reason"),
    "Retain as a working hypothesis; identity remains unconfirmed.",
  );
  await userEvent.click(button);
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  expect(mockedApi).toHaveBeenCalledWith(
    "/incidents/INC-1/hypotheses/account_compromise/review",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        expected_version: 0,
        context_digest: ledger.context_digest,
        review_status: "accepted",
        related_finding_ids: [],
        reason: "Retain as a working hypothesis; identity remains unconfirmed.",
      }),
    }),
  );
});

it("removes actionable stale context after a conflict until explicitly reloaded", async () => {
  mockedApi
    .mockResolvedValueOnce(ledger)
    .mockRejectedValueOnce(new ApiError("Context changed", 409));
  render(
    <HypothesisLedger
      endpoint="/incidents/INC-1/hypotheses"
      incidentId="INC-1"
      onEvidence={vi.fn()}
    />,
  );
  await userEvent.type(
    await screen.findByLabelText("Review reason"),
    "Reviewed source observations.",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save human review" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(/reload/i);
  expect(
    screen.queryByRole("button", { name: "Save human review" }),
  ).not.toBeInTheDocument();
});

it("has no mutation controls in public mode even with a writable upstream payload", async () => {
  mockedApi.mockResolvedValue(ledger);
  render(
    <DemoModeProvider publicDemo>
      <HypothesisLedger
        endpoint="/incidents/INC-1/hypotheses"
        incidentId="INC-1"
        onEvidence={vi.fn()}
      />
    </DemoModeProvider>,
  );
  await screen.findByText("Account compromise");
  expect(screen.queryByLabelText("Review reason")).not.toBeInTheDocument();
});

it("refuses a completed replay ledger from another scope or ruleset", async () => {
  mockedApi.mockResolvedValue({
    ...ledger,
    provenance: { ...provenance, ruleset_digest: "c".repeat(64) },
  });
  render(
    <HypothesisLedger
      endpoint="/scenarios/atlas-compromise/hypotheses"
      readOnly
      expectedScopeId="INC-1"
      expectedProvenance={provenance}
      onEvidence={vi.fn()}
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /reset and reload replay/i,
  );
  expect(screen.queryByText("Account compromise")).not.toBeInTheDocument();
});

it("ignores an old response after the scope changes", async () => {
  let resolveOld!: (value: unknown) => void;
  mockedApi
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    )
    .mockResolvedValueOnce({
      ...ledger,
      scope_id: "INC-2",
      items: [{ ...row, title: "Current scope" }],
    });
  const view = render(
    <HypothesisLedger
      endpoint="/incidents/INC-1/hypotheses"
      incidentId="INC-1"
      onEvidence={vi.fn()}
    />,
  );
  view.rerender(
    <HypothesisLedger
      endpoint="/incidents/INC-2/hypotheses"
      incidentId="INC-2"
      onEvidence={vi.fn()}
    />,
  );
  await screen.findByText("Current scope");
  resolveOld(ledger);
  await waitFor(() =>
    expect(screen.queryByText("Account compromise")).not.toBeInTheDocument(),
  );
});
