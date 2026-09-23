export interface AnalystBenchmark {
  format_version: string;
  fixture_version: string;
  provider: "deterministic";
  live_model_tested: false;
  scope: string;
  total: number;
  passed: number;
  failed: number;
  provenance: {
    fixture_digest: string;
    corpus_digest: string;
    ruleset_digest: string;
  };
  metrics: {
    id: string;
    label: string;
    passed: number;
    total: number;
    definition: string;
  }[];
  cases: {
    id: string;
    category: string;
    name: string;
    passed: boolean;
    expected: Record<string, unknown>;
    actual: Record<string, unknown>;
  }[];
}
