# Inspected demo screenshots

## V2 public-mode views — 2026-09-23

These five captures come from the actual production-built, read-only application
over local HTTPS and PostgreSQL. Each was visually inspected. Only synthetic
application content is visible; there are no keys, headers, private paths,
personal machine details, browser chrome, or unrelated content.

| Capture                                             | Verified state                                                                               |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [Replay](v2-replay.png)                             | Atlas causal frame 17/91: first incident at 14:03 UTC, three alerts, paused at 20×           |
| [Hypotheses](v2-hypotheses.png)                     | Evidence-derived status, inspectable citations, conditional gaps, separate human review      |
| [Detection regression](v2-detection-regression.png) | Computed APP-002 threshold 1,000 → 1,500 comparison; PASS and explicit synthetic populations |
| [Bundle verification](v2-bundle-verification.png)   | Real 35-file public export verified VALID against its unsigned manifest                      |
| [Evaluations](v2-evaluations.png)                   | Executed 145-obligation benchmark, metric denominators and limitations                       |

Reproduce with [the capture utility](../../scripts/capture_v2_screenshots.mjs)
after starting the production HTTPS rehearsal described in
[deployment](../DEPLOYMENT.md). It checks the public runtime contract, permits
only same-origin reads, asserts actual rendered results, and compares the
canonical case before and after capture. Files are published only after all
captures and browser checks pass. These are local rehearsal captures, not proof
of which revision is hosted; hosted verification is recorded separately.

## Historical V1 views — 2026-09-17

Captured and individually inspected on 2026-09-17 UTC using the production-built
application and synthetic Atlas telemetry. Browser chrome, local configuration,
credentials and unrelated desktop content are absent.

| Capture                            | View                                                |
| ---------------------------------- | --------------------------------------------------- |
| [01](01-operations.png)            | Operations overview                                 |
| [02](02-incident.png)              | Primary incident and actual correlation rationale   |
| [03](03-evidence.png)              | Timeline and source-evidence inspection             |
| [04](04-entity-graph.png)          | Selected entity, relationships and evidence         |
| [05](05-grounded-answer.png)       | Real OpenAI grounded answer with citations          |
| [06](06-insufficient-evidence.png) | Real OpenAI malware question: insufficient evidence |
| [07](07-evaluations.png)           | Executed deterministic evaluation results           |
| [08](08-architecture.png)          | Processing and analyst trust boundaries             |
| [09](09-live-validation.png)       | Live results and retained HTTP 429 attempt history  |
| [10](10-light-incident.png)        | Incident workspace in light theme                   |
| [Mobile](light-390.png)            | Light theme at 390 pixels                           |
| [Tablet](light-768.png)            | Light theme at 768 pixels                           |

The first eight are the requested portfolio views; the final four provide live
execution and responsive/theme context. Grounded and insufficient-evidence captures
show the provider that actually answered. The separate live report explains
request failures and the limited scope of these observations.

Twelve earlier captures in [baseline](baseline) support the numbered
[UX audit](../UX_AUDIT.md). They intentionally show the product before hardening.
