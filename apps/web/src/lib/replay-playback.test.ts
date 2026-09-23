import { describe, expect, it } from "vitest";
import { frameDelay, replayPrefix } from "./replay-playback";
import type { ReplayFrame } from "./replay-types";

const frames: ReplayFrame[] = [
  {
    seq: 0,
    timestamp: "2026-09-15T14:00:00Z",
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
    timestamp: "2026-09-15T14:00:00Z",
    stage: "telemetry",
    event_id: "EV-1",
    data: { source: "identity", event_type: "authentication" },
  },
  {
    seq: 2,
    timestamp: "2026-09-15T14:10:00Z",
    stage: "correlation",
    data: {
      alert_count: 1,
      incident_count: 0,
      rule_ids: ["AUTH-001"],
      rule_families: ["AUTH"],
      minimum_rules: 3,
      minimum_families: 2,
      window_minutes: 30,
    },
  },
];

describe("replay prefix", () => {
  it("reveals only reached frames and starts with disclosed background counts", () => {
    expect(replayPrefix(frames, 0, 4000)).toMatchObject({
      frames: [],
      eventCount: 4000,
      alertCount: 0,
      incidentCount: 0,
    });
    const reached = replayPrefix(frames, 2, 4000);
    expect(reached.frames.map((frame) => frame.seq)).toEqual([0, 1]);
    expect(reached.eventCount).toBe(4001);
    expect(reached.correlation).toBeNull();
    expect(replayPrefix(frames, 3, 4000).correlation?.minimum_rules).toBe(3);
  });

  it("counts an incident only when the incident frame arrives", () => {
    const incident: ReplayFrame = {
      seq: 3,
      timestamp: frames[2].timestamp,
      stage: "incident",
      incident_id: "INC-1",
      data: {
        change: "created",
        incident: {
          id: "INC-1",
          title: "Observed sequence",
          summary: "Observed",
          severity: "high",
          user_id: "U-1",
          alert_ids: [],
          event_ids: [],
          evidence_ids: [],
        },
      },
    };
    const history = [
      ...frames,
      incident,
      {
        ...incident,
        seq: 4,
        data: { ...incident.data, change: "updated" as const },
      },
    ];
    expect(replayPrefix(history, 3, 4000).incidentCount).toBe(0);
    expect(replayPrefix(history, 4, 4000).incidentCount).toBe(1);
    expect(replayPrefix(history, 5, 4000).incidentCount).toBe(1);
  });
});

it("scales source time while bounding idle gaps and making same-time stages inspectable", () => {
  const oneSecond = { ...frames[1], timestamp: "2026-09-15T14:00:01Z" };
  expect(frameDelay(frames[0], oneSecond, 1)).toBe(1000);
  expect(frameDelay(frames[0], oneSecond, 10)).toBe(100);
  expect(frameDelay(frames[0], frames[2], 1)).toBe(3000);
  expect(frameDelay(frames[0], frames[0], 50)).toBe(100);
});
