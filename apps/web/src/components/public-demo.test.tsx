import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { DemoModeProvider } from "./demo-mode";
import { IncidentWorkspace } from "./incident-workspace";
import { EvidenceAnalyst } from "./evidence-analyst";
import { EvaluationResults } from "./evaluation-results";
import { Findings, NotesAndAudit, ReportPanel } from "./incident-records";
import { api, ApiError } from "@/lib/api";
import { analysis, incident } from "@/test/fixtures";
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const mockedApi = vi.mocked(api);
const Public = ({ children }: { children: React.ReactNode }) => (
  <DemoModeProvider publicDemo>{children}</DemoModeProvider>
);
beforeEach(() => vi.clearAllMocks());

it("keeps public evidence navigation while hiding incident and evidence mutation controls", async () => {
  render(<IncidentWorkspace initial={incident} />, { wrapper: Public });
  expect(screen.queryByText("Manage incident")).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Inspect evidence EVD-001" }),
  );
  const drawer = screen.getByRole("dialog");
  expect(within(drawer).getByText("synthetic.engineer")).toBeVisible();
  expect(
    within(drawer).queryByLabelText("Evidence annotation"),
  ).not.toBeInTheDocument();
  expect(
    within(drawer).queryByRole("button", { name: "Save assessment" }),
  ).not.toBeInTheDocument();
  expect(
    within(drawer).getByText("Inspect canonical source event"),
  ).toBeVisible();
});

it("offers curated deterministic questions and citations without a persistent finding action or refresh", async () => {
  mockedApi.mockResolvedValue(analysis);
  const inspect = vi.fn(),
    refresh = vi.fn(),
    draft = vi.fn();
  render(
    <EvidenceAnalyst
      incidentId="INC-001"
      evidenceCount={1}
      onEvidence={inspect}
      onComplete={refresh}
      onDraft={draft}
    />,
    { wrapper: Public },
  );
  expect(screen.getByLabelText("Investigation question")).toHaveAttribute(
    "readonly",
  );
  expect(
    screen.getByText(/public demo uses the deterministic evidence analyst/),
  ).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "What most likely happened?" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Ask analyst" }));
  expect(
    await screen.findByText("Authentication used an unfamiliar source."),
  ).toBeVisible();
  await userEvent.click(
    screen.getAllByRole("button", { name: "Inspect evidence EVD-001" })[0],
  );
  expect(inspect).toHaveBeenCalledWith("EVD-001");
  expect(
    screen.queryByRole("button", { name: "Review as finding" }),
  ).not.toBeInTheDocument();
  expect(refresh).not.toHaveBeenCalled();
  expect(draft).not.toHaveBeenCalled();
  mockedApi.mockResolvedValue({
    ...analysis,
    status: "insufficient_evidence",
    findings: [],
    summary: "No evidence identifies a malware family.",
  });
  await userEvent.click(
    screen.getByRole("button", { name: "What malware family was used?" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Ask analyst" }));
  expect(await screen.findByText("Insufficient evidence")).toBeVisible();
  expect(mockedApi).toHaveBeenLastCalledWith("/incidents/INC-001/analysis", {
    method: "POST",
    body: JSON.stringify({ question: "What malware family was used?" }),
  });
});

it("preserves saved record viewing without findings, notes, reports, or evaluation write controls", async () => {
  mockedApi.mockRejectedValue(new ApiError("No report", 404));
  render(
    <>
      <Findings
        incident={incident}
        draft={null}
        onEvidence={vi.fn()}
        refresh={vi.fn()}
      />
      <NotesAndAudit incident={incident} refresh={vi.fn()} />
      <ReportPanel
        incidentId={incident.id}
        evidence={incident.evidence}
        onEvidence={vi.fn()}
        refresh={vi.fn()}
      />
      <EvaluationResults
        initial={{
          id: "saved-run",
          total: 1,
          passed: 1,
          failed: 0,
          cases: [
            {
              id: "case",
              name: "Scoped evidence",
              category: "grounding",
              passed: true,
            },
          ],
        }}
      />
    </>,
    { wrapper: Public },
  );
  expect(
    await screen.findByText("Reports are part of the local review workflow"),
  ).toBeVisible();
  for (const name of [
    "Save finding draft",
    "Approve finding",
    "Save note",
    "Generate report draft",
    "Approve report",
    "Run deterministic suite",
  ])
    expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
  expect(
    screen.getByText("Scoped evidence", { selector: "summary" }),
  ).toBeVisible();
  expect(screen.getByText("Audit history")).toBeVisible();
  expect(mockedApi).toHaveBeenCalledTimes(1);
  expect(mockedApi).toHaveBeenCalledWith("/incidents/INC-001/report");
});
