export type Severity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "new" | "investigating" | "contained" | "resolved";
export interface SecurityEvent {
  event_id: string;
  timestamp: string;
  source: string;
  event_type: string;
  action: string;
  outcome: string;
  actor: { user_id?: string; username?: string; role?: string };
  target: {
    resource_id?: string;
    resource_type?: string;
    service?: string;
    endpoint?: string;
  };
  network: {
    source_ip?: string;
    destination_ip?: string;
    user_agent?: string;
    location?: string;
    geo?: string;
  };
  device: { device_id?: string; trusted?: boolean; posture?: string };
  session: { session_id?: string };
  attributes: Record<string, unknown>;
  raw?: Record<string, unknown>;
}
export interface Alert {
  id: string;
  rule_id: string;
  rule_name: string;
  severity: Severity;
  title: string;
  description: string;
  timestamp: string;
  user_id: string;
  event_ids: string[];
  incident_id?: string;
}
export interface Evidence {
  id: string;
  event_id: string;
  timestamp: string;
  relevance: string;
  note: string | null;
  event: SecurityEvent;
}
export interface Entity {
  id: string;
  type: string;
  label: string;
}
export interface Relationship {
  source: string;
  target: string;
  label: string;
  evidence_ids: string[];
}
export interface Finding {
  id: string;
  title: string;
  narrative: string;
  evidence_ids: string[];
  author?: string;
  created_at: string;
  ai_assisted: boolean;
  approved: boolean;
}
export interface AnalystNote {
  id: string;
  text: string;
  actor?: string;
  author?: string;
  created_at: string;
}
export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  actor_type?: "system" | "human" | "model";
  action: string;
  object?: string;
  before?: unknown;
  after?: unknown;
}
export interface Incident {
  correlation?: {
    principal_ids: string[];
    alert_count: number;
    distinct_rule_count: number;
    rule_ids: string[];
    rule_families: string[];
    first_alert_at: string;
    last_alert_at: string;
    span_minutes: number;
    window_minutes: number;
    minimum_rules: number;
    minimum_families: number;
    grouping_keys: string[];
    context_only: string[];
    explanation: string[];
  };
  id: string;
  title: string;
  severity: Severity;
  status: IncidentStatus;
  owner: string | null;
  summary: string;
  created_at: string;
  updated_at: string;
  alert_count?: number;
  evidence_count?: number;
  alerts: Alert[];
  evidence: Evidence[];
  entities: Entity[];
  relationships: Relationship[];
  findings: Finding[];
  notes: AnalystNote[];
  audit: AuditEntry[];
}
export interface Overview {
  counts: {
    events: number;
    alerts: number;
    incidents: number;
    active_incidents: number;
    high_incidents: number;
    review_required: number;
  };
  recent_alerts: Alert[];
  recent_events: SecurityEvent[];
  incidents: Incident[];
}
export interface Detection {
  id: string;
  name: string;
  severity: Severity;
  description: string;
  enabled: boolean;
  kind: string;
  window_minutes?: number;
  threshold?: number;
  alert_count: number;
}
export interface PageResult<T> {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
}
export interface Analysis {
  status: "answered" | "insufficient_evidence" | "rejected" | "unavailable";
  summary: string;
  confidence: "low" | "moderate" | "high";
  findings: {
    statement: string;
    evidence_ids: string[];
    claim_type?: string;
  }[];
  missing_evidence: string[];
  recommended_next_steps: string[];
  provider: string;
  context_evidence_count: number;
  validation_errors: string[];
  review_required: boolean;
  excluded_benign_count?: number;
  context_notice?: string | null;
}
export interface IncidentReport {
  id: string;
  incident_id: string;
  status: "draft" | "approved" | "stale";
  title: string;
  content: string;
  created_at: string;
  approved_at?: string;
  approved_by?: string;
  review_required: boolean;
}
export interface EvaluationCase {
  id: string;
  name: string;
  category: string;
  passed: boolean;
  detail?: string;
  details?: string;
  expected?: string;
  actual?: string;
  execution?: string;
  status?: "passed" | "failed" | "blocked" | "skipped";
}
export interface LiveEvaluationRun {
  id?: string;
  provider?: string;
  run_kind?: string;
  status: "not_run" | "partial" | "passed" | "blocked" | "failed";
  total?: number;
  passed?: number;
  failed?: number;
  skipped?: number;
  cases?: EvaluationCase[];
  live_cases?: {
    total: number;
    passed: number;
    failed: number;
    skipped: number;
  };
  boundary_cases?: { total: number; passed: number; failed: number };
  provider_requests_attempted?: number;
  provider_requests_succeeded?: number;
  provider_requests_failed?: number;
  attempts?: {
    attempt: number;
    case_id: string;
    status: string;
    http_status?: number;
    safe_error?: string;
  }[];
  live_model_tested?: boolean;
  scope?: string;
  completed_at?: string;
  created_at?: string;
}
export interface EvaluationRun {
  scope?: string;
  completed_at?: string;
  live_model_tested?: boolean;
  id?: string;
  run_id?: string;
  created_at?: string;
  executed_at?: string;
  provider?: string;
  total: number;
  passed: number;
  failed: number;
  cases: EvaluationCase[];
}
