# Code and documentation guide

[Project overview](../README.md) · [Local setup](SETUP.md) ·
[Live demo](https://aegisgraph.farhan-shafee.com) ·
[Deployment record](DEPLOYMENT.md) · [Current validation](VALIDATION.md)

## Five-minute inspection

| Time        | Inspect                                                                                                               | What to look for                                                                                 |
| ----------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 00:00–01:00 | [System architecture](architecture/SYSTEM.md), [threat model](threat-model/THREAT_MODEL.md)                           | One web app/API/database; public versus local authority; explicit limits                         |
| 01:00–02:00 | [Replay](REPLAY.md), [rules](../packages/detections/rules.json), [correlation](../apps/api/aegisgraph/correlation.py) | Causal event prefixes, source-cited signals, principal/time/rule-family grouping                 |
| 02:00–03:00 | [Analyst boundary](../apps/api/aegisgraph/analyst.py), [hypotheses](HYPOTHESES.md)                                    | `build_context()`, `supported_claims()`, `validate_draft()`; machine support versus human review |
| 03:00–04:00 | [Rule workbench](DETECTION_WORKBENCH.md), [analyst benchmark](evaluations/BENCHMARK.md)                               | Immutable proposals, measured gates, independent fixture labels, explicit denominators           |
| 04:00–05:00 | [Evidence bundles](EVIDENCE_BUNDLES.md), [demo](DEMO.md), [validation](VALIDATION.md)                                 | Scoped committed exports, unsigned-manifest limits, reproducible workflow and executed results   |

## Core loop and code

Replay observations → inspect evidence → assess hypotheses → compare a rule
change → record a human decision → export and verify the investigation.

| Concern                    | Implementation                                                                                                                                                                         | Supporting material                                     |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Canonical telemetry        | [Schema](../apps/api/aegisgraph/schema.py), [adapters](../apps/api/aegisgraph/adapters.py)                                                                                             | [Canonical model](../packages/schemas/README.md)        |
| Eight inert scenarios      | [Corpus](../apps/api/aegisgraph/scenarios.py), [independent labels](../apps/api/aegisgraph/scenario_ground_truth.py)                                                                   | [Dataset guide](../packages/synthetic-data/README.md)   |
| Causal replay              | [Projection engine](../apps/api/aegisgraph/replay.py), [browser playback](../apps/web/src/components/scenario-replay.tsx)                                                              | [Replay contract](REPLAY.md)                            |
| Detection and correlation  | [Detector](../apps/api/aegisgraph/detection.py), [correlator](../apps/api/aegisgraph/correlation.py)                                                                                   | [Detection catalog](../packages/detections/README.md)   |
| Rule revision and review   | [Typed parameters](../apps/api/aegisgraph/rule_specs.py), [comparison](../apps/api/aegisgraph/regressions.py), [workflow](../apps/api/aegisgraph/rule_workflow.py)                     | [Workbench and gates](DETECTION_WORKBENCH.md)           |
| AI grounding and citations | [Projection, support predicates and draft validator](../apps/api/aegisgraph/analyst.py)                                                                                                | [Evaluation methodology](evaluations/README.md)         |
| Hypothesis review          | [Derivation](../apps/api/aegisgraph/hypotheses.py), [version/context checks](../apps/api/aegisgraph/hypothesis_workflow.py)                                                            | [Ledger and investigation gaps](HYPOTHESES.md)          |
| Analyst benchmark          | [Named obligations](../tests/fixtures/analyst_benchmark.json), [runner](../apps/api/aegisgraph/analyst_benchmark.py)                                                                   | [Definitions and limitations](evaluations/BENCHMARK.md) |
| Export and verification    | [Scoped snapshot](../apps/api/aegisgraph/evidence_export.py), [Python verifier](../apps/api/aegisgraph/evidence_bundle.py), [browser verifier](../apps/web/src/lib/evidence-bundle.ts) | [Format and integrity boundary](EVIDENCE_BUNDLES.md)    |
| Human findings and reports | [Case service](../apps/api/aegisgraph/services.py)                                                                                                                                     | [Report lifecycle decision](adr/ADR-009.md)             |

The canonical Atlas investigation remains a persisted case. Other scenario
projections are ephemeral; even a correlated replay result is not automatically
inserted into PostgreSQL. Observation scopes are shown when correlation does not
produce an incident. Evaluation labels do not enter runtime analyst context.

## Running and inspecting the system

The hosted path is browser → Vercel Next.js → Railway FastAPI → Railway PostgreSQL.
Public mode provides deterministic, read-only exploration; it does not save case
edits, rule proposals, reviews, or analyst answers. Local mode separately supports
those workflows and optional explicit OpenAI analysis. See the
[deployment record](DEPLOYMENT.md) for the verified hosted revision.

- [Setup](SETUP.md): deterministic local commands, PostgreSQL, configuration, and tests.
- [Seven-minute demo](DEMO.md): Atlas replay, canonical evidence, analyst boundaries,
  hypothesis inspection, a rule comparison, evaluations, and export verification.
- [Interview notes](INTERVIEW_NOTES.md): implemented choices and production tradeoffs.
- [Screenshots](screenshots/README.md): synthetic application views and captions.
- [Personal-site handoff](PERSONAL_SITE_HANDOFF.md): current portfolio copy, screenshot
  choices, and five résumé/five LinkedIn bullets; no website changes are implied.

## Evidence and validation

Three evaluation records have different meanings: the current deterministic V2
benchmark, the preserved original deterministic suite, and separately credentialed
historical OpenAI validation. Their totals should not be combined into a model
accuracy figure.

- [Current V2 validation](V2_VALIDATION.md): exact executed counts, CI, databases, browser
  verification, and material limitations.
- [V2 release report](V2_RELEASE_REPORT.md): the 26-part engineering assessment,
  delivery status, and interview/site handoff.
- [Evaluation methodology](evaluations/README.md): deterministic boundaries, optional
  live execution, and what successful fixtures do not establish.
- [Historical live record](evaluations/LIVE_VALIDATION.md): successful named scenarios
  and preserved provider-availability failures.
- [Public release review](PUBLIC_RELEASE_REVIEW.md): repository audit and release findings.
- [Original public-demo preparation](PUBLIC_DEMO_VALIDATION.md): dated September 17
  preparation evidence; it is not a substitute for current deployment verification.
- [Original UX audit](UX_AUDIT.md): baseline observations and earlier interface changes.

## Architecture decision records

| Decision                  | Topic                                                 |
| ------------------------- | ----------------------------------------------------- |
| [ADR-001](adr/ADR-001.md) | PostgreSQL for the original investigation system      |
| [ADR-002](adr/ADR-002.md) | Separate detection from correlation                   |
| [ADR-003](adr/ADR-003.md) | AI cannot mutate incident state                       |
| [ADR-004](adr/ADR-004.md) | Validate citations and claim support                  |
| [ADR-005](adr/ADR-005.md) | Telemetry is untrusted input                          |
| [ADR-006](adr/ADR-006.md) | Relational entity graph                               |
| [ADR-007](adr/ADR-007.md) | Deterministic correlation before model-based grouping |
| [ADR-008](adr/ADR-008.md) | Immutable observations and separate case annotations  |
| [ADR-009](adr/ADR-009.md) | Deterministic reports and explicit review state       |
| [ADR-010](adr/ADR-010.md) | Synthetic corpus and separate evaluation labels       |
| [ADR-011](adr/ADR-011.md) | Bounded replay and browser-owned playback             |
| [ADR-012](adr/ADR-012.md) | Typed rule revisions and synthetic regression gates   |
| [ADR-013](adr/ADR-013.md) | Evidence-derived hypotheses and separate human review |
| [ADR-014](adr/ADR-014.md) | Bounded JSON bundles and local hash verification      |

The [security policy](../SECURITY.md) explains reporting and project scope. The
[earlier portfolio summary](PORTFOLIO_SUMMARY.md) describes the original release;
use the [current handoff](PERSONAL_SITE_HANDOFF.md) for the expanded workflow.
