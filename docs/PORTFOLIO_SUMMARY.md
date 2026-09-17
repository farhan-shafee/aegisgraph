# AegisGraph portfolio summary

## One sentence

AegisGraph is an evidence-grounded security investigation application for a
simulated fintech environment, connecting deterministic detections and correlation
to a bounded, read-only AI analyst and explicit human review.

## Short description — approximately 75 words

AegisGraph turns synthetic fintech telemetry into an inspectable security
investigation. Four adapters normalize events, versioned rules produce alerts,
and deterministic correlation assembles a case. Analysts explore a timeline and
entity graph, inspect source evidence, annotate observations, and approve findings
and reports. An optional OpenAI provider selects structured observations through
the same evidence validator as a credential-free deterministic provider. The
project emphasizes reproducibility, citation support, clear trust boundaries, and
honest evaluation rather than production-scale claims.

## Technical description — approximately 150 words

AegisGraph uses Next.js, React, and TypeScript for an analyst workspace backed by
FastAPI, Pydantic, SQLAlchemy, Alembic, and PostgreSQL. A deterministic generator
produces 4,026 synthetic observations across identity, API gateway, endpoint, and
Atlas application sources. Ten inspectable rules produce evidence-backed alerts;
principal, event time, and rule diversity determine incident scope before AI runs.
Relational event/entity associations supply an interactive graph without another
database. Source-event and audit triggers reject ordinary updates and deletes,
while annotations remain separate. The analyst boundary projects bounded case
evidence, excludes analyst-benign observations, and accepts only typed claims with
exact supporting citation sets. Server templates render accepted statements;
models receive no retrieval tools or mutation authority. Findings and deterministic
reports require explicit human review, and case changes invalidate report approval.
Deterministic fixtures, API tests, browser workflows, and separately recorded live
provider attempts make implemented behavior inspectable. Authentication, tenant
isolation, streaming ingestion, independently retained audit records, and operational
scale remain production work.

## Architecture

```text
Synthetic sources -> adapters -> canonical events -> PostgreSQL
                                  |
                                  v
                              rule detections -> alerts -> correlation -> incident
                                                                             |
                      human review <- validated claims <- provider <- scoped evidence
                           |
                    findings / report / audit
```

The model is replaceable and read-only. The database and explicit analyst actions
remain authoritative. See [system architecture](architecture/SYSTEM.md),
[threat model](threat-model/THREAT_MODEL.md), and [decision records](adr).

## Strongest differentiators

- A detection is distinct from a correlated investigation, with explicit grouping
  conditions and evidence references.
- Citation existence, current-case membership, inclusion in the actual model
  context, and typed claim support are independently checked.
- The provider selects structured observations; it cannot smuggle arbitrary prose
  into a factual summary or approve its own suggestions.
- Evidence annotations do not rewrite observations. Report approval becomes stale
  after case changes and must be renewed through a human action.
- A reproducible scenario supports an interview walkthrough without API credentials.
  Real provider outcomes remain separate from deterministic boundary results.

## Technologies actually used

| Layer | Technologies |
|---|---|
| Web | Next.js App Router, React, TypeScript, Tailwind CSS, Lucide |
| API | Python, FastAPI, Pydantic, HTTPX, Uvicorn |
| Persistence | PostgreSQL, SQLAlchemy, Alembic; SQLite for isolated/demo use |
| AI | Deterministic provider and optional OpenAI Responses API with strict JSON Schema |
| Verification | pytest, Ruff, Vitest, Testing Library, Playwright, ESLint, Prettier, TypeScript |
| Delivery | GitHub Actions, dependency lockfiles, Docker Compose configuration |

Pinned package versions are in the lockfiles. Docker Compose configuration is not
evidence that Docker was exercised on every development machine; the validation
record distinguishes native PostgreSQL, SQLite, and hosted CI runs.

## Implemented versus future work

Implemented: four adapters; deterministic data; ten rules; deterministic correlation;
timeline and source inspection; entity relationships; annotations and notes; cited
AI findings; human approvals; report invalidation; audit history; evaluations; safe
local reset/health commands; dark and light themes; responsive investigation UI.

Future: authenticated identities and case permissions; tenant-aware associations
and storage; authenticated streaming ingestion; production replay and rule rollout;
restricted database roles; independent evidence/audit retention; provider privacy
review; retention and recovery procedures; workload-driven scaling and repeated
live-model adversarial measurement. No autonomous response is implemented.

## Portfolio screenshots

Use [the primary incident](screenshots/02-incident.png) as the lead image.

| Screenshot | What it demonstrates |
|---|---|
| [Operations](screenshots/01-operations.png) | Persisted counts and investigation focus |
| [Incident workspace](screenshots/02-incident.png) | Correlation rationale and incident chronology |
| [Evidence inspection](screenshots/03-evidence.png) | Canonical observation, source, and separate annotation |
| [Entity graph](screenshots/04-entity-graph.png) | Relationships with supporting evidence |
| [Grounded answer](screenshots/05-grounded-answer.png) | Structured findings and clickable citations |
| [Insufficient evidence](screenshots/06-insufficient-evidence.png) | Intentional handling of an unsupported malware question |
| [Evaluations](screenshots/07-evaluations.png) | Executed results with deterministic/live distinction |
| [Architecture](screenshots/08-architecture.png) | Processing sequence and trust boundaries |

Screenshots use synthetic data. The visible provider label identifies what actually
produced an answer; a deterministic screenshot is not evidence of live-model success.

## Interview talking points

1. Explain why ten alerts become one case, using actual principal/time/rule counts.
2. Follow one finding all the way back to immutable source evidence.
3. Explain why a real citation alone does not prove a claim.
4. Show the malware question and name the evidence that is missing.
5. Distinguish input projection from a model resisting an injection it actually saw.
6. Show that a case edit invalidates an approved report.
7. Explain the gap between local case scoping and production authorization.
8. Discuss scaling from measured requirements instead of adding infrastructure for appearance.

Use [the seven-minute walkthrough](DEMO.md) and [technical answers](INTERVIEW_NOTES.md).
Quote test and provider results only from the current [validation record](VALIDATION.md)
and [evaluation records](evaluations/README.md), with their execution dates and limits.
