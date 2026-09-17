# System architecture

AegisGraph investigates a fictional Atlas Trading Platform environment. It is a
single API, one web application, and one relational database. It does not monitor
real infrastructure, execute responses, or connect to financial institutions.

```mermaid
flowchart LR
  G[Deterministic synthetic generator] --> S[Four source adapters]
  S --> N[Canonical Pydantic event]
  N --> P[(PostgreSQL)]
  N --> D[JSON detection rules]
  D --> A[Alerts]
  A --> C[Deterministic correlation]
  C --> I[Incident evidence associations]
  I --> W[Next.js investigation workspace]
  I --> X[Bounded retrieval and evidence projection]
  X --> V[Provider boundary]
  V --> O[Structured claim proposals]
  O --> Q[Schema, citation and claim validation]
  Q --> W
  W --> H[Explicit analyst actions]
  H --> P
  H --> U[Audit history]
```

## Ingestion and detection

Identity, API gateway, endpoint, and Atlas application adapters translate source
payloads to the same event vocabulary. The default generator produces 4,000
ordinary events and 26 scenario observations. Default rules derive 10 alerts and
one incident containing 26 evidence rows. These are fixture counts, not quality
or performance measurements. IP addresses use documentation ranges, account
identifiers are fictional, and location labels are simulation indicators.

Canonical event IDs identify immutable observations. An analyst changes the
case's relevance annotation, not the source event. No event edit or delete route
is available. ORM hooks block source-event update/delete, and Alembic installs
PostgreSQL/SQLite triggers rejecting ordinary updates and deletes for both events
and audit records. These guarantees apply to migrated tables. A database owner
can remove triggers, change schema, or use the explicit reset command; the design
does not claim privileged-owner resistance or cryptographic evidence integrity.
Production would add restricted database roles and independent retained copies.

Detection rules describe suspicious signals and temporal sequences. They produce
alerts containing evidence references. Correlation subsequently assembles related
alerts and context into an incident. A detection is neither a verdict of compromise
nor an incident by itself. Thresholds are inspectable in the rules and have explicit
units and windows; severity does not come from an unexplained numerical score.

Correlation groups alerts by principal and parsed event time. A cluster spans at
most 30 minutes from its first alert and becomes an incident only if it contains
at least three distinct rules across at least two rule-ID families. Session,
device, and IP links are context, not grouping predicates. Some detection rules,
such as MFA or privilege following unfamiliar authentication, separately require
the same session. The resulting case includes the principal's observations from
five minutes before its first alert through its last alert, plus alert-cited
events needed to explain the detections. Correlation can therefore include benign
context or older baseline evidence. Generic rule mixes receive a generic summary;
the flagship account-compromise hypothesis is conditional on its auth, privilege,
and sensitive-access rule mix.

Incident severity is an explicit V1 policy: high when the cluster contains both
IAM and APP families, otherwise medium. It is not a learned risk score or a
calibrated estimate of impact.

## Relational evidence and graph

Events, alerts, incidents, incident evidence, findings, entity links, analyses,
reports, and audit records live in SQLAlchemy models with Alembic migrations.
The entity graph is a view over relational links, with evidence IDs on edges.
An IP/device/session shared in a case is a relationship, not proof of attribution.
Timeline order comes from event time. Processing/audit time is recorded separately.

The browser fetches paginated events and case detail capped at 500 evidence rows.
The derived incident graph uses that same bounded detail set. Indexed timestamps,
identities, sessions, event types, and association keys support V1 queries.
SQLite is a convenience for local execution and isolated tests. PostgreSQL is the
intended persisted database and the database used by the CI integration job.

## Analyst trust boundaries

```mermaid
sequenceDiagram
  actor Human as Local analyst
  participant API as FastAPI
  participant DB as Database
  participant Model as Analyst provider
  Human->>API: Ask question for incident ID
  API->>DB: Resolve incident and allowed evidence
  DB-->>API: Scoped case observations
  API->>Model: Bounded, projected evidence as untrusted data
  Model-->>API: Structured claim proposals
  API->>API: Validate schema, context membership and claim support
  API-->>Human: Grounded answer or safe rejection
  Human->>API: Explicit save / approve action
  API->>DB: Validate references, write change and audit
```

The provider interface receives no database connection, application write
credentials, shell, retrieval tools, or incident mutation functions. The optional
OpenAI transport holds only the key needed to call the fixed provider endpoint;
the model itself receives no key or execution tools. Citation validity alone is too weak:
an existing event ID does not make arbitrary prose true. Claim types are validated
against the cited event fields, then rendered through server templates. This
limits expressiveness deliberately. The summary is derived from the same accepted
findings and cites their evidence. Arbitrary model-written prose is not admitted
to factual output. Uncertain interpretation remains labeled as a hypothesis.

The service retrieves the first 50 case evidence rows ordered by event time and
ID. The analyst boundary validates incident membership, unique IDs, and a separate
80-row cap, then excludes analyst-benign rows. The resulting answer reports both
the included count and benign-exclusion count. No replacement rows are retrieved
after that exclusion. The serialized projected context is limited to 64,000 UTF-8
bytes; questions are limited to 2,000 characters. This is bounded selection, not a
claim that every event in a larger incident reaches the provider.

Questions and all telemetry content are untrusted. Source text is never promoted
to system instructions. The live provider uses structured responses and the same
post-validation as the deterministic provider. Its prompt is defense in depth;
the deterministic output boundary carries the stronger enforcement.

Common false-premise questions use a conservative phrase guard. It identifies
missing malware, transfer, personal-data-field, identity, or location evidence.
The guard is not a general natural-language entailment test. Independent claim
validation still prevents novel question wording from adding arbitrary facts.

## Reports and human review

Reports are deterministic templates assembled from case evidence, entities,
status, and approved analyst findings. They are not model-written narratives.
Creating or approving a finding is a separate human API action; the provider
cannot invoke it. Report generation creates a draft. Case edits, evidence
annotations, findings, finding review, and notes invalidate an existing report,
clear approval metadata, and append a `report_invalidated` audit entry when its
status first changes to stale. Stale approval returns a conflict until the analyst
regenerates and reviews the report. Only the current report is stored; audit
records record lifecycle actions rather than complete historical report versions.

```mermaid
stateDiagram-v2
  [*] --> Draft: Generate template
  Draft --> Approved: Human approval
  Draft --> Stale: Case changes
  Approved --> Stale: Case changes
  Stale --> Draft: Regenerate and review
```

## Deployment boundary

The local browser communicates with the Next.js server, which proxies `/api` to
the loopback FastAPI service. Both development servers and Docker's PostgreSQL
port should remain bound to loopback. There is one fixed local analyst; there is
no login screen or claim of multi-user access control. Case-scoped evidence
validation is implemented, but all cases are accessible to that local analyst;
it is not user or tenant authorization. The API also checks trusted host names,
local client addresses by default, and mutation origins when an Origin header is
present. Those transport checks do not establish a human identity. Public deployment
requires identity, case entitlements, CSRF/session controls, rate limits, TLS,
restricted database roles, secret management, and independent audit retention.

The optional model provider is a separate data boundary. Only synthetic bounded
case context is sent; provider retention, data residency, and organizational
approval must be resolved before any future real-data use.

## Operational limits

Ingestion and correlation are synchronous for a bounded demonstration dataset.
There is no streaming ingestion, durable task queue, distributed rule scheduler,
or exactly-once event transport. Request IDs and structured request logs support
local diagnosis. Application logs omit telemetry bodies, model prompts, raw model
answers, and API keys. No HTTP ingestion, reset, arbitrary command, or file-upload
endpoint is exposed; the seed pipeline runs through the local CLI.
Evaluation records identify the provider and actual cases executed; deterministic
boundary tests do not establish live-model prompt-injection resistance.
