import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvidenceAnalyst, CitedText } from "./evidence-analyst";
import { EvidenceDrawer } from "./evidence-drawer";
import { EntityGraph } from "./entity-graph";
import { IncidentWorkspace } from "./incident-workspace";
import { Findings, ReportPanel } from "./incident-records";
import { api } from "@/lib/api";
import { analysis, evidence, incident } from "@/test/fixtures";
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const mockedApi = vi.mocked(api);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("investigation evidence workflow", () => {
  it("keeps keyboard-selected tab panels named by valid stable IDs", async () => {
    const user = userEvent.setup();
    render(<IncidentWorkspace initial={incident} />);
    await user.click(screen.getByRole("tab", { name: /Timeline/ }));
    await user.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}{ArrowRight}");
    const notesTab = screen.getByRole("tab", { name: "Notes & audit" });
    expect(notesTab).toHaveFocus();
    expect(notesTab).toHaveAttribute("aria-selected", "true");
    expect(notesTab.id).toBe("tab-notes-audit");
    expect(
      screen.getByRole("tabpanel", { name: "Notes & audit" }),
    ).toHaveAttribute("aria-labelledby", notesTab.id);
    expect(screen.getAllByRole("tab").every((tab) => !/\s/.test(tab.id))).toBe(
      true,
    );
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: /Timeline/ })).toHaveFocus();
    expect(screen.getByRole("tabpanel", { name: /Timeline/ })).toBeVisible();
  });
  it("renders the incident and opens the actual source event from a timeline citation", async () => {
    const user = userEvent.setup();
    render(<IncidentWorkspace initial={incident} />);
    expect(screen.getByRole("heading", { name: incident.title })).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Inspect evidence EVD-001" }),
    );
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText("synthetic.engineer")).toBeVisible();
    expect(within(drawer).getByText("192.0.2.10")).toBeVisible();
    expect(
      within(drawer).getByLabelText("Evidence annotation"),
    ).toHaveAttribute("maxlength", "2000");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("saves relevance and annotations only after explicit submission", async () => {
    const user = userEvent.setup(),
      save = vi.fn().mockResolvedValue(undefined);
    render(
      <EvidenceDrawer evidence={evidence} onClose={vi.fn()} onSave={save} />,
    );
    await user.selectOptions(screen.getByLabelText("Relevance"), "benign");
    await user.type(
      screen.getByLabelText("Evidence annotation"),
      "Verified with the account owner.",
    );
    expect(save).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Save assessment" }));
    expect(save).toHaveBeenCalledWith(
      "EVD-001",
      "benign",
      "Verified with the account owner.",
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Evidence assessment saved",
    );
  });
  it("surfaces save errors without claiming that evidence changed", async () => {
    render(
      <EvidenceDrawer
        evidence={evidence}
        onClose={vi.fn()}
        onSave={vi.fn().mockRejectedValue(new Error("Save rejected"))}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save assessment" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Save rejected");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
  it("links selected entities to their evidence and related alerts", async () => {
    const filter = vi.fn(),
      inspect = vi.fn();
    render(
      <EntityGraph
        entities={incident.entities}
        relationships={incident.relationships}
        evidence={incident.evidence}
        alerts={incident.alerts}
        onEvidence={inspect}
        onFilter={filter}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Device · DEV-01" }),
    );
    expect(screen.getByText("Unfamiliar source")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "EVD-001" }));
    expect(inspect).toHaveBeenCalledWith("EVD-001");
    await userEvent.click(
      screen.getByRole("button", { name: "Filter timeline to this entity" }),
    );
    expect(filter).toHaveBeenCalledWith(incident.entities[1]);
  });
});

describe("grounded analyst", () => {
  it("uses the current case endpoint and makes validated summary citations inspectable", async () => {
    mockedApi.mockResolvedValue(analysis);
    const inspect = vi.fn(),
      draft = vi.fn(),
      refresh = vi.fn().mockResolvedValue(undefined);
    render(
      <EvidenceAnalyst
        incidentId="INC-001"
        evidenceCount={1}
        onEvidence={inspect}
        onDraft={draft}
        onComplete={refresh}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "What most likely happened?" }),
    );
    expect(mockedApi).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Ask analyst" }));
    expect(
      await screen.findByText("Authentication used an unfamiliar source."),
    ).toBeVisible();
    expect(mockedApi).toHaveBeenCalledWith("/incidents/INC-001/analysis", {
      method: "POST",
      body: JSON.stringify({ question: "What most likely happened?" }),
    });
    await userEvent.click(
      screen.getAllByRole("button", { name: "Inspect evidence EVD-001" })[0],
    );
    expect(inspect).toHaveBeenCalledWith("EVD-001");
    await userEvent.click(
      screen.getByRole("button", { name: "Review as finding" }),
    );
    expect(draft).toHaveBeenCalledWith(
      expect.objectContaining({ evidence_ids: ["EVD-001"], ai_assisted: true }),
    );
    expect(mockedApi).toHaveBeenCalledTimes(1);
  });
  it("renders a false-premise result with evidence gaps and no draft findings", async () => {
    mockedApi.mockResolvedValue({
      ...analysis,
      status: "insufficient_evidence",
      summary: "No available evidence confirms malware execution.",
      findings: [],
    });
    render(
      <EvidenceAnalyst
        incidentId="INC-001"
        evidenceCount={1}
        onEvidence={vi.fn()}
        onDraft={vi.fn()}
        onComplete={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "What malware family was used?" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Ask analyst" }));
    expect(await screen.findByText("Insufficient evidence")).toBeVisible();
    expect(
      screen.getByText("No available evidence confirms malware execution."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Review as finding" }),
    ).not.toBeInTheDocument();
  });
  it("keeps unknown citations and telemetry-like HTML as inert text", () => {
    render(
      <CitedText
        text={"<script>alert(1)</script> EVD-unknown EVD-001"}
        allowedIds={new Set(["EVD-001"])}
        onEvidence={vi.fn()}
      />,
    );
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText(/<script>alert/)).toBeInTheDocument();
  });
});

describe("human approval", () => {
  it("requires supporting evidence and saves findings as unapproved drafts", async () => {
    mockedApi.mockResolvedValue({});
    render(
      <Findings
        incident={incident}
        draft={null}
        onEvidence={vi.fn()}
        refresh={vi.fn().mockResolvedValue(undefined)}
      />,
    );
    await userEvent.type(
      screen.getByLabelText("Finding title"),
      "Unfamiliar authentication",
    );
    await userEvent.type(
      screen.getByLabelText("Narrative"),
      "An unfamiliar source was observed.",
    );
    expect(
      screen.getByRole("button", { name: "Save finding draft" }),
    ).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(
      screen.getByRole("button", { name: "Save finding draft" }),
    );
    expect(mockedApi).toHaveBeenCalledWith(
      "/incidents/INC-001/findings",
      expect.objectContaining({
        body: expect.stringContaining('"approved":false'),
      }),
    );
  });
  it("requires explicit review before report approval", async () => {
    mockedApi.mockResolvedValue({
      id: "RPT-01",
      incident_id: "INC-001",
      status: "draft",
      title: "Report",
      content: "Grounded report EVD-001",
      created_at: evidence.timestamp,
      review_required: true,
    });
    render(
      <ReportPanel
        incidentId="INC-001"
        refresh={vi.fn().mockResolvedValue(undefined)}
        evidence={incident.evidence}
        onEvidence={vi.fn()}
      />,
    );
    const approve = await screen.findByRole("button", {
      name: "Approve report",
    });
    expect(approve).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    expect(approve).toBeEnabled();
    await userEvent.click(approve);
    await waitFor(() =>
      expect(mockedApi).toHaveBeenCalledWith(
        "/incidents/INC-001/report/approve",
        { method: "POST" },
      ),
    );
  });
  it("withholds approval of a stale report until regeneration", async () => {
    mockedApi.mockResolvedValue({
      id: "RPT-01",
      incident_id: "INC-001",
      status: "stale",
      title: "Report",
      content: "Prior report",
      created_at: evidence.timestamp,
      review_required: true,
    });
    render(
      <ReportPanel
        incidentId="INC-001"
        refresh={vi.fn().mockResolvedValue(undefined)}
        evidence={incident.evidence}
        onEvidence={vi.fn()}
      />,
    );
    expect(await screen.findByText(/This incident changed/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Approve report" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Regenerate draft" }),
    ).toBeEnabled();
  });
});
