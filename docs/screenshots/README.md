# Inspected demo screenshots

Captured and individually inspected on 2026-09-17 UTC using the production-built
application and synthetic Atlas telemetry. Browser chrome, local configuration,
credentials and unrelated desktop content are absent.

| Capture | View |
|---|---|
| [01](01-operations.png) | Operations overview |
| [02](02-incident.png) | Primary incident and actual correlation rationale |
| [03](03-evidence.png) | Timeline and source-evidence inspection |
| [04](04-entity-graph.png) | Selected entity, relationships and evidence |
| [05](05-grounded-answer.png) | Real OpenAI grounded answer with citations |
| [06](06-insufficient-evidence.png) | Real OpenAI malware question: insufficient evidence |
| [07](07-evaluations.png) | Executed deterministic evaluation results |
| [08](08-architecture.png) | Processing and analyst trust boundaries |
| [09](09-live-validation.png) | Live results and retained HTTP 429 attempt history |
| [10](10-light-incident.png) | Incident workspace in light theme |
| [Mobile](light-390.png) | Light theme at 390 pixels |
| [Tablet](light-768.png) | Light theme at 768 pixels |

The first eight are the requested portfolio views; the final four provide live
execution and responsive/theme context. Grounded and insufficient-evidence captures
show the provider that actually answered. The separate live report explains
request failures and the limited scope of these observations.

Twelve earlier captures in [baseline](baseline) support the numbered
[UX audit](../UX_AUDIT.md). They intentionally show the product before hardening.
