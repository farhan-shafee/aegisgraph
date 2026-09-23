# Code and documentation guide

[Project overview](../README.md) · [Local setup](SETUP.md) ·
[Live demo](https://aegisgraph.farhan-shafee.com) ·
[Public demo deployment](DEPLOYMENT.md) ·
[Public release review](PUBLIC_RELEASE_REVIEW.md)

## Five-minute inspection

| Start here | What to inspect |
|---|---|
| [System architecture](architecture/SYSTEM.md) | Processing stages, data model, trust boundaries, and human review |
| [Threat model](threat-model/THREAT_MODEL.md) | Assets, attacker-controlled input, controls, and remaining risks |
| [Detection rules](../packages/detections/rules.json) and [engine](../apps/api/aegisgraph/detection.py) | Thresholds/windows and evidence-backed signal generation |
| [Detection workbench](DETECTION_WORKBENCH.md) | Typed revisions, full-corpus comparison, synthetic measurement definitions and human review gates |
| [Hypothesis ledger](HYPOTHESES.md) | Supporting and contradicting evidence, typed investigation gaps, and separate human review |
| [Correlation](../apps/api/aegisgraph/correlation.py#L26) | `correlate()` groups principal/time/rule families; `explain_correlation()` exposes the actual rationale |
| [Context projection](../apps/api/aegisgraph/analyst.py#L498) and [claim support](../apps/api/aegisgraph/analyst.py#L461) | `build_context()` scopes/projects input; `supported_claims()` derives support |
| [Citation and output validator](../apps/api/aegisgraph/analyst.py#L692) | `validate_draft()` checks the schema, exact evidence set, and typed claim support before rendering |
| [Analysis service and report workflow](../apps/api/aegisgraph/services.py) | `run_analysis()` performs bounded retrieval; report functions implement the separate human review lifecycle |
| [Evaluation fixtures](../tests/fixtures/ai_cases.json) and [runner](../apps/api/aegisgraph/evaluations.py) | Named positive/negative cases and observed outcomes |
| [Seven-minute demo](DEMO.md) | Reproduce the investigation and inspect insufficient-evidence behavior |
| [Public demo deployment](DEPLOYMENT.md) | Hosted Vercel/Railway architecture, public runtime boundary, initialization, updates, and recovery |

The [hosted demo](https://aegisgraph.farhan-shafee.com) uses a Vercel Next.js frontend,
Railway FastAPI backend, and Railway PostgreSQL database. `APP_MODE=public_demo`
preserves synthetic evidence exploration and two curated deterministic analyst
examples; answers do not persist, case writes remain disabled, and no OpenAI key
or public OpenAI spend is required. Local/interview mode separately supports case
edits, human approvals, and optional OpenAI analysis.

## Evidence and validation

- [Evaluation methodology](evaluations/README.md): deterministic checks, live-run
  instructions, bounds, and what the results cannot establish.
- [Recorded live validation](evaluations/LIVE_VALIDATION.md): successful scenarios,
  preserved availability failures, and separate local/browser checks.
- [Validation record](VALIDATION.md): executed tests and environment limitations.
- [Public release review](PUBLIC_RELEASE_REVIEW.md): repository audit, licensing
  decision, release status, and validation counts recorded at review time.
- [Public demo preparation validation](PUBLIC_DEMO_VALIDATION.md): historical
  September 17 local/CI preparation evidence, preceding the hosted deployment.
- [Screenshots](screenshots/README.md): reviewed synthetic investigation views.
- [UX audit](UX_AUDIT.md): observed baseline issues and the changes made.

## Architecture decision records

| Decision | Topic |
|---|---|
| [ADR-001](adr/ADR-001.md) | PostgreSQL for V1 |
| [ADR-002](adr/ADR-002.md) | Separate detection from correlation |
| [ADR-003](adr/ADR-003.md) | AI cannot mutate incident state |
| [ADR-004](adr/ADR-004.md) | Validate citations and claim support |
| [ADR-005](adr/ADR-005.md) | Telemetry is untrusted input |
| [ADR-006](adr/ADR-006.md) | Relational entity graph |
| [ADR-007](adr/ADR-007.md) | Deterministic correlation before model-based grouping |
| [ADR-008](adr/ADR-008.md) | Immutable observations and case annotations |
| [ADR-009](adr/ADR-009.md) | Deterministic reports and explicit review state |
| [ADR-010](adr/ADR-010.md) | Synthetic scenario corpus and separate evaluation labels |
| [ADR-011](adr/ADR-011.md) | Bounded replay projections and browser-owned playback |
| [ADR-012](adr/ADR-012.md) | Typed rule revisions and synthetic regression gates |
| [ADR-013](adr/ADR-013.md) | Evidence-derived hypotheses and separate human review |

## Explore further

[Canonical schema](../packages/schemas/README.md),
[synthetic dataset](../packages/synthetic-data/README.md), and
[detection catalog](../packages/detections/README.md) describe the domain inputs.
[Interview notes](INTERVIEW_NOTES.md) explain tradeoffs and future production
work. The [portfolio summary](PORTFOLIO_SUMMARY.md) offers reusable descriptions;
the [security policy](../SECURITY.md) explains private reporting and project scope.
