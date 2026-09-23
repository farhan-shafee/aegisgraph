import type { Severity } from "./types";

export interface RuleDefinition {
  id: string;
  name: string;
  severity: Severity;
  kind: string;
  description: string;
  threshold: number;
  window_minutes: number;
}

export interface RuleRevision {
  id: string;
  rule_id: string;
  version: number;
  parent_version: number;
  base_generation: number;
  base_ruleset_digest: string;
  snapshot: RuleDefinition;
  reason: string;
  actor_label: string;
  created_at: string;
  status: "proposed" | "approved" | "rejected";
}

export interface DetectionWorkbenchData {
  rule: RuleDefinition;
  version: number;
  generation: number;
  ruleset_digest: string;
  parameters: {
    name: "threshold" | "window_minutes";
    label: string;
    minimum: number;
    maximum: number;
    step: number;
    default: number;
    value: number;
  }[];
  revisions: RuleRevision[];
  revision_count: number;
  read_only: boolean;
}

export interface RegressionMetrics {
  selected_rule: { tp: number; fp: number; fn: number; tn: number };
  selected_rule_required_scenarios: number;
  selected_rule_benign_scenarios: number;
  selected_rule_other_scenarios: number;
  required_detection_hits: number;
  required_detection_total: number;
  benign_alert_count: number;
  alert_count: number;
  incident_count: number;
  correlation_mismatches: number;
}

export interface ScenarioMeasurement {
  rule_ids: string[];
  rule_match_counts: Record<string, number>;
  alert_count: number;
  incident_count: number;
  missed_required_rule_ids: string[];
  unexpected_rule_ids: string[];
  forbidden_rule_ids: string[];
  correlation_matches: boolean;
}

export interface RegressionResult {
  selected_rule_id: string;
  measurement_scope: "synthetic_fixture";
  measurement_definitions: Record<string, string>;
  baseline_ruleset_digest: string;
  proposed_ruleset_digest: string;
  corpus_digest: string;
  parameter_changes: { parameter: string; before: number; after: number }[];
  metrics: { before: RegressionMetrics; after: RegressionMetrics };
  scenarios: {
    scenario_id: string;
    classification: string;
    expected_rule_ids: string[];
    required_rule_ids: string[];
    forbidden_rule_ids: string[];
    expected_incident_count: number;
    before: ScenarioMeasurement;
    after: ScenarioMeasurement;
    added_rule_ids: string[];
    removed_rule_ids: string[];
  }[];
  regression_count: number;
  gate: {
    decision: "PASS" | "WARN" | "BLOCK";
    reasons: {
      code: string;
      message: string;
      scenario_id?: string;
      rule_id?: string;
    }[];
  };
}

export interface RegressionRun {
  id: string;
  revision_id: string;
  result: RegressionResult;
  created_at: string;
}

export interface RevisionDetail {
  revision: RuleRevision;
  runs: RegressionRun[];
  review: {
    id: string;
    decision: "approve" | "reject";
    reason: string;
    actor_label: string;
    regression_id: string | null;
    created_at: string;
  } | null;
}
