import type {
  ReplayCorrelation,
  ReplayFrame,
  ReplayIncident,
} from "./replay-types";

export type ReplaySpeed = 1 | 10 | 20 | 50;
export const replaySpeeds: ReplaySpeed[] = [1, 10, 20, 50];

/** Source timestamps drive pacing. The UI discloses both presentation bounds. */
export function frameDelay(
  previous: ReplayFrame | undefined,
  next: ReplayFrame,
  speed: ReplaySpeed,
): number {
  const sourceGap = previous
    ? Date.parse(next.timestamp) - Date.parse(previous.timestamp)
    : 0;
  return Math.max(100, Math.min(3000, sourceGap / speed));
}

/** This function intentionally cannot access a projection's completed result. */
export function replayPrefix(
  allFrames: ReplayFrame[],
  cursor: number,
  backgroundCount: number,
) {
  const frames = allFrames.slice(0, Math.max(0, cursor));
  let eventCount = backgroundCount;
  let alertCount = 0;
  let correlation: ReplayCorrelation | null = null;
  const incidents = new Map<string, ReplayIncident>();
  for (const frame of frames) {
    if (frame.stage === "telemetry") eventCount++;
    if (frame.stage === "alert") alertCount++;
    if (frame.stage === "correlation") correlation = frame.data;
    if (frame.stage === "incident")
      incidents.set(frame.data.incident.id, frame.data.incident);
  }
  return {
    frames,
    eventCount,
    alertCount,
    incidentCount: incidents.size,
    correlation,
    incidents: [...incidents.values()],
  };
}
