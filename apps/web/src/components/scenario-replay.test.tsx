import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ScenarioReplay } from "./scenario-replay";
import { api } from "@/lib/api";
import { analysis, evidence } from "@/test/fixtures";
import type { ReplayProjection, ScenarioDescription } from "@/lib/replay-types";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
vi.mock("./hypothesis-ledger", () => ({
  HypothesisLedger: () => <p>Completed hypothesis ledger</p>,
}));
const mockedApi = vi.mocked(api);
const scenarios: ScenarioDescription[] = [
  {
    id: "atlas-compromise",
    version: "1",
    title: "Atlas investigation",
    classification: "suspicious",
    purpose: "Inspect the sequence.",
    theme: "Account access",
    event_count: 4001,
    canonical_incident_id: "INC-Atlas",
  },
  {
    id: "isolated-anomaly",
    version: "1",
    title: "Isolated anomaly",
    classification: "insufficient_evidence",
    purpose: "Inspect one observation.",
    theme: "Missing context",
    event_count: 1,
    canonical_incident_id: null,
  },
];
function projection(id = "atlas-compromise"): ReplayProjection {
  return {
    format_version: "1",
    provenance: {
      scenario_id: id,
      scenario_version: "1",
      ruleset_digest: "a".repeat(64),
    },
    summary: {
      event_count: 4001,
      background_event_count: 4000,
      playback_event_count: 1,
      frame_count: 3,
    },
    initial_state: { event_count: 4000, alert_count: 0, incident_count: 0 },
    frames: [
      {
        seq: 0,
        timestamp: evidence.timestamp,
        stage: "context_initialized",
        data: {
          event_count: 4000,
          alert_count: 0,
          incident_count: 0,
          first_event_at: null,
          last_event_at: null,
        },
      },
      {
        seq: 1,
        timestamp: evidence.timestamp,
        stage: "telemetry",
        event_id: evidence.event_id,
        data: { source: "identity", event_type: "authentication" },
      },
      {
        seq: 2,
        timestamp: evidence.timestamp,
        stage: "normalized",
        event_id: evidence.event_id,
        data: { event: evidence.event },
      },
    ],
    final_state: {
      event_count: 4001,
      alerts: [],
      incidents: [],
      investigation: {
        id: `SCOPE-${id}`,
        kind: "observation_scope",
        incident_id: null,
        evidence: [evidence],
      },
    },
  };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function ready() {
  await act(async () => {});
  expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
}
function complete() {
  for (let i = 0; i < 3; i++)
    fireEvent.click(screen.getByRole("button", { name: "Step" }));
}
async function playFrames(amount: number) {
  for (let index = 0; index < amount; index++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
  }
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  mockedApi.mockResolvedValue(projection());
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("starts paused, steps one real frame, pauses and resumes, then resets completion", async () => {
  render(<ScenarioReplay scenarios={scenarios} hypothesesAvailable />);
  await ready();
  expect(
    screen.getByRole("progressbar", { name: "Replay progress" }),
  ).toHaveAttribute("value", "0");
  expect(
    screen.queryByText("Completed hypothesis ledger"),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("EVD-001")).not.toBeInTheDocument();
  expect(screen.getByText(/4,000 background/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Step" }));
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
  fireEvent.click(screen.getByRole("button", { name: "Resume" }));
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
  fireEvent.click(screen.getByRole("button", { name: "Resume" }));
  await playFrames(2);
  expect(screen.getByText("Completed hypothesis ledger")).toBeVisible();
  expect(screen.getByText("Observation scope")).toBeVisible();
  expect(mockedApi).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Reset" }));
  expect(
    screen.queryByText("Completed hypothesis ledger"),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
});

it("defaults to manual playback with reduced motion while allowing explicit Start", async () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  render(<ScenarioReplay scenarios={scenarios} />);
  await ready();
  expect(screen.getByText(/Reduced motion/)).toBeVisible();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await playFrames(3);
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "3");
});

it("aborts old projection requests and ignores late answers after scenario changes", async () => {
  const old = deferred<ReplayProjection>();
  mockedApi
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(projection("isolated-anomaly"));
  render(<ScenarioReplay scenarios={scenarios} />);
  const firstSignal = mockedApi.mock.calls[0][1]?.signal;
  fireEvent.change(screen.getByLabelText("Scenario"), {
    target: { value: "isolated-anomaly" },
  });
  await ready();
  expect(firstSignal?.aborted).toBe(true);
  await act(async () => {
    old.resolve(projection());
  });
  expect(
    screen.getByRole("heading", { name: "Isolated anomaly" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("link", { name: /canonical Atlas/ }),
  ).not.toBeInTheDocument();
  complete();
  expect(screen.getByText("SCOPE-isolated-anomaly")).toBeVisible();
});

it("shows fetch failure and retries without exposing a completed result", async () => {
  mockedApi.mockRejectedValueOnce(new Error("Replay temporarily unavailable"));
  render(<ScenarioReplay scenarios={scenarios} />);
  await act(async () => {});
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Replay temporarily unavailable",
  );
  expect(
    screen.queryByRole("button", { name: "Step" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry replay" }));
  await ready();
});

it("requests deterministic analysis only after completion and explicit choice; resetting aborts it", async () => {
  const answer = deferred<unknown>();
  mockedApi
    .mockResolvedValueOnce(projection())
    .mockReturnValueOnce(answer.promise);
  render(<ScenarioReplay scenarios={scenarios} hypothesesAvailable />);
  await ready();
  expect(
    screen.queryByRole("button", { name: "What most likely happened?" }),
  ).not.toBeInTheDocument();
  complete();
  fireEvent.click(
    screen.getByRole("button", { name: "What most likely happened?" }),
  );
  expect(mockedApi.mock.calls[1][0]).toBe(
    "/scenarios/atlas-compromise/analysis/summary",
  );
  const signal = mockedApi.mock.calls[1][1]?.signal;
  fireEvent.click(screen.getByRole("button", { name: "Reset" }));
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    answer.resolve({
      scope_id: "SCOPE-atlas-compromise",
      provenance: projection().provenance,
      analysis,
    });
  });
  expect(
    screen.queryByText(analysis.findings[0].statement),
  ).not.toBeInTheDocument();
});

it("opens completed evidence read-only even in local mode", async () => {
  render(<ScenarioReplay scenarios={scenarios} />);
  await ready();
  complete();
  fireEvent.click(
    screen.getByRole("button", { name: "Inspect evidence EVD-001" }),
  );
  const dialog = screen.getByRole("dialog");
  expect(
    within(dialog).queryByRole("button", { name: "Save assessment" }),
  ).not.toBeInTheDocument();
  expect(within(dialog).getByText("synthetic.engineer")).toBeVisible();
});

it("rejects analysis from a newly approved ruleset instead of mixing evidence snapshots", async () => {
  mockedApi.mockResolvedValueOnce(projection()).mockResolvedValueOnce({
    scope_id: "SCOPE-atlas-compromise",
    provenance: {
      ...projection().provenance,
      ruleset_digest: "b".repeat(64),
    },
    analysis,
  });
  render(<ScenarioReplay scenarios={scenarios} hypothesesAvailable />);
  await ready();
  complete();
  fireEvent.click(
    screen.getByRole("button", { name: "What most likely happened?" }),
  );
  await act(async () => {});
  expect(screen.getByRole("alert")).toHaveTextContent(/rules.*changed/i);
  expect(
    screen.queryByText(analysis.findings[0].statement),
  ).not.toBeInTheDocument();
});

it("cancels a running timer when changing scenario and leaves the next replay ready", async () => {
  mockedApi
    .mockResolvedValueOnce(projection())
    .mockResolvedValueOnce(projection("isolated-anomaly"));
  const view = render(<ScenarioReplay scenarios={scenarios} />);
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  fireEvent.change(screen.getByLabelText("Scenario"), {
    target: { value: "isolated-anomaly" },
  });
  await ready();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("shows a cited completed answer and handles a rejected second request", async () => {
  mockedApi
    .mockResolvedValueOnce(projection())
    .mockResolvedValueOnce({
      scope_id: "SCOPE-atlas-compromise",
      provenance: projection().provenance,
      analysis,
    })
    .mockRejectedValueOnce(new Error("Analysis temporarily unavailable"));
  render(<ScenarioReplay scenarios={scenarios} hypothesesAvailable />);
  await ready();
  complete();
  fireEvent.click(
    screen.getByRole("button", { name: "What most likely happened?" }),
  );
  await act(async () => {});
  expect(screen.getByText(analysis.findings[0].statement)).toBeVisible();
  fireEvent.click(
    screen.getByRole("button", { name: "Inspect analyst evidence EVD-001" }),
  );
  expect(screen.getByRole("dialog")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close evidence" }));
  fireEvent.click(
    screen.getByRole("button", { name: "What malware family was used?" }),
  );
  await act(async () => {});
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Analysis temporarily unavailable",
  );
  expect(
    screen.queryByText(analysis.findings[0].statement),
  ).not.toBeInTheDocument();
});

it("pauses playback when a reached frame is focused for keyboard inspection", async () => {
  render(<ScenarioReplay scenarios={scenarios} />);
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await playFrames(1);
  const history = screen.getByRole("list", { name: "Reached replay frames" });
  fireEvent.focus(
    within(history).getByText("Context initialized").closest("summary")!,
  );
  expect(screen.getByRole("button", { name: "Resume" })).toBeEnabled();
  await playFrames(3);
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
});

it("rejects a projection from a different scenario version than the selected catalog entry", async () => {
  mockedApi.mockResolvedValueOnce({
    ...projection(),
    provenance: { ...projection().provenance, scenario_version: "2" },
  });
  render(<ScenarioReplay scenarios={scenarios} />);
  await act(async () => {});
  expect(screen.getByRole("alert")).toHaveTextContent(
    "The replay projection is incompatible",
  );
  expect(
    screen.queryByRole("button", { name: "Start" }),
  ).not.toBeInTheDocument();
});
