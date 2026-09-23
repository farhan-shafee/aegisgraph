export interface ReplayProvenance {
  scenario_id: string;
  scenario_version: string;
  ruleset_digest: string;
}
export interface Hypothesis {
  id: string;
  kind: string;
  title: string;
  epistemic_status: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  missing_evidence: { category: string; guidance: string }[];
  related_finding_ids: string[];
  provenance: Record<string, unknown>;
  first_observed_at: string | null;
  as_of: string | null;
  review: {
    version: number;
    status: "open" | "accepted" | "rejected" | "stale";
    recorded_status: string;
    actor_label: string | null;
    reason: string | null;
    created_at: string | null;
    related_finding_ids: string[];
  };
}
export interface HypothesisData {
  scope_id: string;
  read_only: boolean;
  context_digest?: string;
  evidence_digest: string;
  provenance?: ReplayProvenance;
  items: Hypothesis[];
}
