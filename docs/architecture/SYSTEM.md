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

The explicit analyst write path describes local/interview mode. In
`APP_MODE=public_demo`, the same investigation data is explorable, but persistent
API writes are denied and the two curated deterministic answers are not saved.

V2 adds a finite scenario corpus, causal replay, typed rule regression, a hypothesis
ledger, a deterministic analyst benchmark, and portable evidence bundles. They
reuse this API, database, detector, correlation engine, and analyst boundary.
There is no additional service or public writable workspace.

## Code map

| Concern                              | Implementation and design                                                                                                                                                                                                           |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Detection and correlation            | [detection.py](../../apps/api/aegisgraph/detection.py), [correlation.py](../../apps/api/aegisgraph/correlation.py), [rule definitions](../../packages/detections/rules.json)                                                        |
| Scenario corpus and evaluator labels | [scenarios.py](../../apps/api/aegisgraph/scenarios.py), [scenario_ground_truth.py](../../apps/api/aegisgraph/scenario_ground_truth.py), [ADR-010](../adr/ADR-010.md)                                                                |
| Replay projection and playback       | [replay.py](../../apps/api/aegisgraph/replay.py), [scenario-replay.tsx](../../apps/web/src/components/scenario-replay.tsx), [ADR-011](../adr/ADR-011.md)                                                                            |
| Typed rules and review gates         | [rule_specs.py](../../apps/api/aegisgraph/rule_specs.py), [regressions.py](../../apps/api/aegisgraph/regressions.py), [rule_workflow.py](../../apps/api/aegisgraph/rule_workflow.py), [ADR-012](../adr/ADR-012.md)                  |
| Grounding and hypothesis review      | [analyst.py](../../apps/api/aegisgraph/analyst.py), [hypotheses.py](../../apps/api/aegisgraph/hypotheses.py), [hypothesis_workflow.py](../../apps/api/aegisgraph/hypothesis_workflow.py), [ADR-013](../adr/ADR-013.md)              |
| Benchmark obligations                | [analyst_benchmark.py](../../apps/api/aegisgraph/analyst_benchmark.py), [fixture](../../tests/fixtures/analyst_benchmark.json)                                                                                                      |
| Export and local verification        | [evidence_export.py](../../apps/api/aegisgraph/evidence_export.py), [evidence_bundle.py](../../apps/api/aegisgraph/evidence_bundle.py), [browser verifier](../../apps/web/src/lib/evidence-bundle.ts), [ADR-014](../adr/ADR-014.md) |

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

The incident API exposes these facts under `correlation`: observed principal IDs,
linked alert count, distinct rule IDs and families, first/last alert timestamps,
measured span, and the shared configured window/minimum thresholds. The primary
fixture has ten alerts from nine distinct rules across five families, spanning
22 minutes. `grouping_keys` identifies principal and event time, while
`context_only` names device/session/IP. The workspace renders these derived facts
rather than inventing an explanation from a model or graph appearance.

Incident severity is an explicit V1 policy: high when the cluster contains both
IAM and APP families, otherwise medium. It is not a learned risk score or a
calibrated estimate of impact.

## Scenarios, replay, and rule evolution

Eight code-owned scenarios cover suspicious, benign, ambiguous, mixed, and
insufficient-evidence observations. Atlas remains the persisted canonical fixture;
the other scenarios are ephemeral projections and do not create database cases.
The scenario generators do not import evaluator answer keys. Required/forbidden
detections, expected correlation, and claim/question expectations are separate
authored labels used by regression and benchmark execution. Neither labels nor
catalog descriptions enter the analyst provider context.

Replay orders events by timestamp and ID, evaluates detection once, and releases
each signal at its final supporting event. Correlation sees only the observed
prefix. Atlas explicitly folds its 4,000 earlier normal events into initialization
after checking they generated no alerts, then plays the 26 investigation events.
Bounds are 5,000 source events, 80 playback/evidence events, 600 frames, and 1 MiB
per projection. The browser owns its playback cursor; no visitor session is stored
on the server. The full projection is delivered up front, so playback is a causal
presentation, not a mechanism to hide future data. Completed-scenario inspection
is labeled separately from the currently displayed prefix.

Public replay uses repository rules. Its cache has eight serialized entries and
one cold computation at a time; each caller receives freshly decoded objects.
The three fixed public regression examples and one baseline benchmark use the
same bounded, serialized-cache approach. Local replay resolves approved rule
snapshots separately and cannot replace public baseline cache contents.

Rule edits accept only the declared integer parameters of fixed rule identities
and kinds. There is no executable rule language. A full-corpus comparison returns
PASS, WARN, or BLOCK with individual reasons and explicit synthetic denominators.
Local approval independently recomputes the comparison, verifies the selected
prior run and corpus/ruleset digests, and checks the whole-ruleset generation
under a transaction lock. BLOCK cannot be approved; every human decision requires
a reason. Approved changes affect subsequent local replay and rule comparison
without rewriting stored Atlas alerts or evidence. Public visitors see only baseline rules and fixed
comparisons; browsing never initializes rule workflow rows.

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

Additive migrations [004](../../apps/api/migrations/versions/004_rule_workflow.py)
and [005](../../apps/api/migrations/versions/005_hypothesis_workflow.py) create empty
local rule/hypothesis workflow tables. They do not reseed or rewrite existing
events, alerts, evidence, notes, reports, or evaluations. Rule versions, regression
runs, rule reviews, and hypothesis revisions receive append-only database guards;
their current-head records are mutable transactionally. Those guards still trust
the database owner. CI exercises both fresh public initialization and an upgrade
from a populated V1 schema with repeat-upgrade and ordinary SQL-mutation checks.

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

The hypothesis ledger derives four fixed propositions from validated observations
and narrowly matched recorded approval/job context. It separates supporting and
contradicting evidence, evidence-derived status, missing evidence, and human review.
Account compromise remains at most partially supported by this telemetry. A
recorded approval can contradict a proposition about that approval's scope; it
does not establish an account owner's identity or innocence. Local review binds
to the current evidence/annotation/finding digest and expected revision. A shared
incident lock serializes relevant case mutations. Changed context makes a review
stale, while human acceptance never upgrades its evidence-derived status. Public
ledgers omit persisted local review and finding state. Scenario analyst examples
always use the deterministic provider and one of two fixed questions.

## Reports and human review

Reports are deterministic templates assembled from case evidence, entities,
status, approved analyst findings, and current accepted hypotheses. Hypotheses
retain their evidence-derived status, citations, and gaps. Reports are not
model-written narratives.
Creating or approving a finding is a separate human API action; the provider
cannot invoke it. Report generation creates a draft. Case edits, evidence
annotations, findings, finding review, notes, and hypothesis reviews invalidate an existing report,
clear approval metadata, and append a `report_invalidated` audit entry when its
status first changes to stale. Stale approval returns a conflict until the analyst
regenerates and reviews the report. Only the current report is stored; audit
records record lifecycle actions rather than complete historical report versions.

Local author/reviewer labels are unauthenticated provenance labels. They do not
establish who performed a decision or create multi-user authorization.

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
the loopback FastAPI service. Both local development servers and Docker's PostgreSQL
port should remain bound to loopback. There is one fixed local analyst; there is
no login screen or claim of multi-user access control. Case-scoped evidence
validation is implemented, but all cases are accessible to that local analyst;
it is not user or tenant authorization. The API also checks trusted host names,
local client addresses by default, and mutation origins when an Origin header is
present. Those transport checks do not establish a human identity. A shared
writable service requires identity, case entitlements, CSRF/session controls,
restricted database roles, secret management, and independent audit retention.

The [hosted public demo](https://aegisgraph.farhan-shafee.com) follows
Browser → Vercel Next.js → Railway FastAPI → Railway PostgreSQL.
Both application services explicitly select `APP_MODE=public_demo`;
the frontend requires an HTTPS `API_INTERNAL_URL` and verifies that the backend
advertises the same read-only, deterministic contract. No backend address or
credential is passed to client components. The proxy preserves the actual
browser Origin for backend allowlist validation and does not forward browser
authorization headers or cookies. Public mode never falls back to SQLite or a
live model provider. All API writes are denied except the two curated,
non-persistent analysis requests. Source inspection and saved results remain
available. Exact host/origin configuration, request limits, safe errors, and
shared process budgets bound this intentionally small public surface. These are
demo controls, not production authentication or an availability guarantee. The
public analyst requires no OpenAI key and incurs no OpenAI spend.
See the current [deployment runbook](../DEPLOYMENT.md) for operating requirements.
The [September 17 preparation record](../PUBLIC_DEMO_VALIDATION.md) preserves the
earlier local validation evidence; it is not a statement of current hosting status
or independent verification of hosting-dashboard settings.

The runtime response advertises additive version-1 capabilities for scenarios,
replay, the rule workbench, hypotheses, the analyst benchmark, and evidence bundles.
The [frontend capability parser](../../apps/web/src/lib/capabilities.ts) accepts
only known exact versions. Missing or unknown capabilities hide the corresponding
navigation and prevent feature fetches against an older backend. The existing
public-mode contract remains mandatory and fails closed on a mode mismatch.
Capabilities describe availability; API method and service checks enforce access.

The optional model provider is a separate data boundary. Only synthetic bounded
case context is sent; provider retention, data residency, and organizational
approval must be resolved before any future real-data use.

Local configuration loads the repository-root `.env` once without overriding
explicit process variables. Public mode skips that file and uses process
environment configuration. Variable interpolation is disabled locally. Set
`AEGISGRAPH_LOAD_ENV=false` to disable file loading. Provider keys remain in the
server environment, never in serialized settings or health responses. Tests
disable workstation `.env` loading and use deterministic mode. These are local
configuration conveniences, not managed secrets or production identity controls.

## Reproducible disposable demo

`python -m aegisgraph.cli demo-reset` ignores the configured `DATABASE_URL` and
rebuilds only `.runtime/aegisgraph-demo.db`. The sequence drops/reapplies migrations,
seeds canonical events, evaluates detections, creates the correlated incident,
then executes and records deterministic evaluations. `demo-api` selects the same
reserved database and binds to loopback; its provider defaults to deterministic,
with OpenAI available only through explicit `--provider openai`.

Both commands accept `--postgres-port PORT` for a pre-created loopback PostgreSQL
database named exactly `aegisgraph_demo`, owned by the local `aegisgraph` demo role.
The database name, host and role are fixed; arbitrary database URLs are not accepted.
Legacy `seed --reset` is likewise limited to that PostgreSQL target or the two
reserved `.runtime` SQLite files used for demo and browser tests. SQLite symlinks,
directory redirection and hard-linked database files are rejected. Direct
database-owner tools can still bypass these accidental-reset protections.

`demo-health` performs read-only HTTP checks of the loopback API/database and
expected scenario counts, verifies fixture availability, and invokes an explicit
deterministic provider in process. It never calls an external provider. It checks
demo readiness, not production availability or source authenticity.

## Operational limits

### Evidence bundles

An explicit incident export takes a committed snapshot using a separate read-only
repeatable-read PostgreSQL transaction. It writes no audit/export row. Collection
counts and SQL payload sizes are checked before materializing large values; the
builder rejects out-of-scope event, evidence, finding, hypothesis, and audit
references. Public exports omit owner, evidence notes, findings, notes, audit,
and human review state and identify that projection explicitly. Local exports
include bounded committed human material. Over-capacity cases fail instead of
silently truncating evidence.

The [bundle format](../EVIDENCE_BUNDLES.md) is one JSON container, limited to 2 MiB,
100 logical files, and 256 KiB per file. Python and browser verification require
strict UTF-8, reject duplicate keys, lone surrogates, nonfinite numbers, excessive
depth/nodes, unknown schema fields, unsafe paths, and duplicate/colliding paths.
Fixed logical filenames are never extracted or opened. Exact UTF-8 content is
hashed without Unicode or newline normalization. A selected browser file stays
on the user's device and is never uploaded.

VALID means the files match the supplied SHA-256 hashes and byte lengths. The
manifest is unsigned and replaceable: changing content and its hash together
can still pass. Case, timestamp, projection, and application metadata are also
unauthenticated. Verification does not establish source truth, authorship,
privileged-database integrity, or chain of custody.

### Execution and evaluation

Ingestion and correlation are synchronous for a bounded demonstration dataset.
There is no streaming ingestion, durable task queue, distributed rule scheduler,
or exactly-once event transport. Request IDs and structured request logs support
local diagnosis. Application logs omit telemetry bodies, model prompts, raw model
answers, and API keys. No HTTP ingestion, reset, arbitrary command, or file-upload
endpoint is exposed; the seed pipeline runs through the local CLI.
Public deployment initialization is also an explicit administrator CLI workflow:
migrate, inspect, and seed only when requested. API startup never reseeds data.
Evaluation records identify the provider and actual cases executed; deterministic
boundary tests do not establish live-model prompt-injection resistance.
`GET /api/evaluations` selects deterministic records, and
`GET /api/evaluations/live` separately returns the latest recorded OpenAI run or
an explicit not-run state. Neither read endpoint performs evaluation calls. Live
results label external calls separately from application-boundary checks; only
the opt-in live evaluation runner can initiate those measured calls.

`GET /api/evaluations/benchmark` is a separate deterministic application benchmark:
its first request computes the bounded repository-owned obligations, then reads a
single serialized cache entry. `python -m aegisgraph.cli evaluate-benchmark`
executes it directly and exits nonzero on failed obligations. It compares authored
synthetic expectations and deliberately invalid provider drafts with actual
outcomes. It does not measure live-model accuracy or a population-level attack
success rate. Public scenario analyst GETs share the existing analyst request and
concurrency budgets; replay, regression examples, benchmark, and export use the
shared read budget. No public path selects a live provider.
