import type {
  Alert,
  Analysis,
  Evidence,
  SecurityEvent,
  Severity,
} from "./types";

export interface ScenarioDescription {
  id: string;
  version: string;
  title: string;
  classification: string;
  purpose: string;
  theme: string;
  event_count: number;
  canonical_incident_id: string | null;
}

export interface ReplayProvenance {
  scenario_id: string;
  scenario_version: string;
  ruleset_digest: string;
}

// Signals have no display title or database incident_id in the replay API.
export type ReplayAlert = Omit<Alert, "title" | "incident_id">;
export interface ReplayIncident {
  id: string;
  title: string;
  summary: string;
  severity: Severity;
  user_id: string;
  alert_ids: string[];
  event_ids: string[];
  evidence_ids: string[];
}
export interface ReplayCorrelation {
  alert_count: number;
  incident_count: number;
  rule_ids: string[];
  rule_families: string[];
  window_minutes: number;
  minimum_rules: number;
  minimum_families: number;
}
interface FrameBase {
  seq: number;
  timestamp: string;
  event_id?: string;
  alert_id?: string;
  incident_id?: string;
}
export type ReplayFrame = FrameBase &
  (
    | {
        stage: "context_initialized";
        data: {
          event_count: number;
          alert_count: 0;
          incident_count: 0;
          first_event_at: string | null;
          last_event_at: string | null;
        };
      }
    | { stage: "telemetry"; data: { source: string; event_type: string } }
    | { stage: "normalized"; data: { event: SecurityEvent } }
    | {
        stage: "rule_match";
        data: {
          rule_id: string;
          rule_name: string;
          event_ids: string[];
          severity: Severity;
        };
      }
    | { stage: "alert"; data: ReplayAlert }
    | { stage: "correlation"; data: ReplayCorrelation }
    | {
        stage: "incident";
        data: { change: "created" | "updated"; incident: ReplayIncident };
      }
  );
export interface ReplayProjection {
  format_version: "1";
  provenance: ReplayProvenance;
  summary: {
    event_count: number;
    background_event_count: number;
    playback_event_count: number;
    frame_count: number;
  };
  initial_state: { event_count: number; alert_count: 0; incident_count: 0 };
  frames: ReplayFrame[];
  final_state: {
    event_count: number;
    alerts: ReplayAlert[];
    incidents: ReplayIncident[];
    investigation: {
      id: string;
      kind: "correlated_incident" | "observation_scope";
      incident_id: string | null;
      evidence: Evidence[];
    };
  };
}
export interface ScenarioAnalysis {
  view: "completed_scenario";
  scope_id: string;
  scope_kind: "correlated_incident" | "observation_scope";
  read_only: true;
  provenance: ReplayProvenance;
  analysis: Analysis;
}
