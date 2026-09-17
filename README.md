# AegisGraph

An evidence-grounded security investigation system for the fictional **Atlas
Trading Platform**. A deterministic synthetic dataset moves through normalization,
detection, incident correlation, evidence review, bounded AI analysis, and a
human-approved report.

This is a local engineering demonstration. All telemetry, identities, devices,
IPs and financial resources are synthetic. It has no real banking integration,
production identity system, autonomous response actions, or enterprise scale claim.

## What is implemented

- Four telemetry adapters and immutable persisted canonical events.
- A default seed with 4,000 baseline events and 26 scenario observations (4,026 total).
- Ten inspectable JSON detection rules, evidence-backed alerts, and deterministic
  incident correlation separate from detection.
- A paginated event explorer, alert and incident queues, chronological evidence
  timeline, entity relationship graph, and source-event inspection.
- Case evidence annotations, analyst notes, cited findings, deterministic template reports,
  explicit human approval, and audit history.
- A credential-free deterministic Evidence Analyst and optional OpenAI provider
  behind one interface.
- Structured claim proposals, deterministic citation/scope/support validation,
  false-premise responses, and executed AI/security evaluations.

## Architecture

```mermaid
flowchart LR
  Sources[Identity / API gateway / endpoint / Atlas] --> Normalize[Canonical events]
  Normalize --> DB[(PostgreSQL)]
  Normalize --> Rules[Detection rules]
  Rules --> Alerts[Alerts]
  Alerts --> Correlation[Deterministic correlation]
  Correlation --> Case[Incident evidence set]
  Case --> Web[Next.js analyst workspace]
  Case --> Context[Bounded evidence projection]
  Context --> Provider[Deterministic or OpenAI provider]
  Provider --> Validate[Schema + citation + claim validation]
  Validate --> Web
  Web --> Human[Explicit analyst actions]
  Human --> DB
```

Next.js App Router, TypeScript, React and Tailwind form the web application.
FastAPI, Pydantic, SQLAlchemy and Alembic form the single API. PostgreSQL is the
primary database; SQLite is supported for a lightweight local demo and isolated
tests. No Redis, Kafka, Elasticsearch, graph database or queue is required.

See [system architecture](docs/architecture/SYSTEM.md), the
[threat model](docs/threat-model/THREAT_MODEL.md), and [ADRs](docs/adr).

## Primary scenario

An Atlas engineer account has normal recognized-device activity, followed by a
new source/device, MFA acceptance, a privileged role grant, internal endpoint
enumeration, sensitive account access, abnormal data volume, a second unusual
session, and a quick role reversion. The sequence spans 13:57–14:24 UTC in the
fixed synthetic dataset. Weak signals acquire relevance through shared identity
and time; the graph exposes supporting device/session/IP relationships.

The default seed produces 10 alerts and one incident with 26 evidence items. These
are reproducible dataset counts, not detection-quality or operational-performance
metrics. Changing the generator, rules, or seed can change the derived results.

The data does **not** establish malware, SSN exfiltration, the real-world person
behind the account, or an attacker's country. The documented false-premise prompts
exercise explicit insufficient-evidence behavior.

## Local setup

Requirements: Python 3.12+, Node.js 24+, and Docker Compose for PostgreSQL (or an
existing PostgreSQL 17 instance). Run commands from the repository root. The
application runs without external AI credentials.

```sh
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
npm ci --prefix apps/web

docker compose up -d --wait postgres
alembic upgrade head
python -m aegisgraph.cli seed
python -m aegisgraph.cli evaluate
```

Start the API in one terminal and web application in another:

```sh
uvicorn aegisgraph.main:app --host 127.0.0.1 --port 8000
npm run dev --prefix apps/web
```

Open [the application](http://127.0.0.1:3000) and
[FastAPI OpenAPI](http://127.0.0.1:8000/docs). The web server proxies `/api` to the
loopback API. Keep all three services local; this release is not safe to expose
as a shared public service.

### Without Docker

Set the database URL **in every API/CLI terminal** before migrating and seeding.
On PowerShell:

```powershell
$env:DATABASE_URL = 'sqlite:///./aegisgraph.db'
alembic upgrade head
python -m aegisgraph.cli seed
uvicorn aegisgraph.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux use `export DATABASE_URL=sqlite:///./aegisgraph.db`. SQLite is a
convenience, not a claim of concurrency or type parity with PostgreSQL. For a
separate existing PostgreSQL instance, provide its SQLAlchemy `postgresql+psycopg`
URL instead. Database files and local runtime artifacts are ignored by Git.

### Reset the disposable demonstration

```sh
python -m aegisgraph.cli seed --reset
python -m aegisgraph.cli evaluate
```

Reset downgrades migrations to the base and reapplies them, dropping and recreating
application tables, including annotations, findings and review history. Use it only
against a disposable demo database. This maintenance path intentionally removes
and reinstalls the immutability triggers.
There is no remotely callable HTTP reset endpoint.

## Environment variables

The [example file](.env.example) is a reference; the API reads process environment
variables, not an automatically loaded `.env` file. Never commit live credentials.

| Variable | Default / purpose |
|---|---|
| `DATABASE_URL` | Local PostgreSQL URL from Compose; `postgresql+psycopg://aegisgraph:demo-local-only@127.0.0.1:5432/aegisgraph` |
| `AI_PROVIDER` | `deterministic`; use `openai` to opt into external model calls |
| `OPENAI_API_KEY` | Required only in OpenAI mode; server environment only |
| `OPENAI_MODEL` | Required only in OpenAI mode; choose an account-available model supporting Responses structured output |
| `API_INTERNAL_URL` | `http://127.0.0.1:8000`; Next.js server proxy target, set before build/start |
| `DEMO_ANALYST` | `demo.analyst`; local audit label, **not authentication** |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000`; accepted mutation origins |
| `ALLOW_REMOTE_DEMO` | `false`; retains the API's local-client restriction. Setting `true` does not add authentication or make public deployment supported |

The Compose password is a public local-only demo value, not a production secret.
OpenAI mode sends bounded synthetic context to the provider and may incur charges.
No live API call is necessary for the demo, test suite, or evaluation dashboard.

## Evidence and AI boundaries

The API checks that the incident exists and retrieves its earliest 50 evidence rows
in event-time order before calling a provider. All cases are visible to the fixed
local demo analyst; this is case scoping, not user or tenant authorization. The
analyst boundary separately rejects inputs above 80 evidence rows or 64,000 bytes
of projected context. Evidence marked benign by the analyst is excluded before
provider selection, and the result discloses the excluded count. This bounded
selection does not claim to include every observation in a larger incident.

Providers have
no database session, command tools, retrieval tools or state-changing functions.
They propose a strict set of claim types and evidence IDs. The server checks:

1. The response matches the structured schema with no extra fields.
2. Every cited evidence ID exists in the current incident and provided context.
3. Each claim's evidence satisfies a deterministic event predicate.
4. Only server-rendered supported statements are displayed.

The summary is derived from accepted findings and includes their citations; no
free-form model-written summary can bypass claim checks. One invalid claim rejects
the whole proposed answer. An existing citation is not sufficient to support
arbitrary prose. Raw telemetry and analyst questions are always untrusted data;
unnecessary metadata is omitted from model context. The same validator applies
to deterministic and external providers. Recognized false-premise questions receive
a fixed insufficient-evidence response and identify missing evidence. The question
guard is not a universal entailment classifier; novel wording may return only
supported case observations, but cannot create arbitrary new factual claims.

The confidence label is qualitative and fixed by the renderer, not a measured
probability of compromise. The sequence interpretation remains an investigation
hypothesis.

This deliberately constrains natural-language expressiveness. It does not prove
that the source telemetry is truthful, eliminate incomplete selection of facts,
or establish production-grade prompt-injection resistance. Read
[evaluation methodology](docs/evaluations/README.md) for exact guarantees.

## Detection and correlation

Definitions live in [rules.json](packages/detections/rules.json). Implemented
families cover repeated failures, unseen source/device, unusual synthetic
location, MFA after unfamiliar authentication, privileged role grant, privilege
after unfamiliar authentication, distinct internal endpoint enumeration,
sensitive account access, abnormal record volume, and rapid role reversion.

Detection emits alerts with source-event references. Correlation requires at
least three distinct rules across at least two families for one principal in a
thirty-minute cluster anchored at its first alert. Principal and event time are
the grouping keys; session/device/IP relationships provide investigation context,
not additional correlation predicates. Some temporal detection rules independently
require a matching session. Correlation brings the same principal's observations
from five minutes before the first alert through the last alert into the timeline,
plus all source events cited by those alerts. Generic clusters receive a generic
summary; the account-compromise hypothesis requires the corresponding auth, role,
and sensitive-access rules.
Rules are explicit synthetic policy examples, not calibrated production detectors.

## Data model

Canonical events include ID, timezone-aware event timestamp, source, event type,
action, outcome, actor, target, network, device, session, extensible attributes,
and a sanitized synthetic source reference. The generator adapters store only an
allowlisted source-reference object in `raw`. Canonical `attributes` and `raw` are
bounded JSON maps; they are not trusted instructions. Pydantic models are frozen
at their top-level fields, not recursively throughout nested Python dictionaries.
Persisted source observations are the system of record; annotations live separately.

Relational tables connect events to alerts, entities and incident evidence;
findings reference case evidence. Analyses, reports, notes, evaluations and audit
entries retain workflow context. Useful indexes cover time, event type, user,
session, severity and association keys. Alembic tracks the schema and installs
PostgreSQL/SQLite triggers that reject ordinary `UPDATE` and `DELETE` operations
on events and audit records. ORM guards also reject source-event edits and deletes.
These controls require migrated tables and do not defend against a database owner
who can disable triggers or change schema. No cryptographic tamper-proof storage
is claimed.

## Report review

Reports are generated by a deterministic template from current-case evidence,
entities, workflow state, and analyst-approved findings. The optional model does
not write the report. A generated report starts as a draft and requires an explicit
human approval action. Changes to case fields, evidence annotations, findings or
notes mark the report stale, clear its approval metadata, and record invalidation
in audit history. A stale report cannot be approved until regenerated and reviewed.
V1 keeps the current report in the database; it does not provide immutable report
version history or establish that a person actually read every statement.

## Verification

```sh
ruff check apps/api tests/backend
ruff format --check apps/api tests/backend
pytest -q
python -m aegisgraph.cli evaluate
python scripts/smoke.py

npm run format:check --prefix apps/web
npm run lint --prefix apps/web
npm run typecheck --prefix apps/web
npm test --prefix apps/web
npm run build --prefix apps/web

python scripts/prepare_e2e.py
node apps/web/node_modules/@playwright/test/cli.js install chromium
node apps/web/node_modules/@playwright/test/cli.js test --config playwright.config.ts

pip-audit -r requirements.lock
npm audit --prefix apps/web --audit-level=moderate
```

The E2E preparation command uses a separate ignored SQLite database, and browser
tests run separate loopback servers. They do not reset your main demo database.
Backend tests cover normalization, deterministic data, detection windows,
correlation, evidence scope, schema/citation/claim validation, injection fixtures,
false premises and workflow boundaries. Browser tests exercise the investigation
flow and responsive layouts. CI is configured to run clean PostgreSQL
migration/seed/smoke checks; a configured workflow is not itself a completed CI run.

Only actual executed results appear in the evaluation UI. Deterministic provider
tests are labeled accordingly; they are not live-model performance scores. See
[validation record](docs/VALIDATION.md) for locally executed checks and limitations.

## Repository structure

```text
apps/api/aegisgraph/      API, domain services, persistence, analyst providers
apps/api/migrations/     Alembic schema history
apps/web/                Next.js application and component tests
packages/schemas/        Canonical schema reference
packages/detections/     Versioned detection definitions
packages/synthetic-data/ Generator usage and dataset specification
tests/backend/           Backend and AI boundary tests
tests/fixtures/          Reproducible evaluation cases
tests/e2e/               Playwright investigation and responsive tests
scripts/                 Smoke and isolated E2E setup
docs/                    Architecture, ADRs, threat model and demo guides
```

## Demonstrate and discuss

Follow [the 5–7 minute demo](docs/DEMO.md), then use
[interview notes](docs/INTERVIEW_NOTES.md) for the technical tradeoffs. Start with
operations, open the correlated incident, inspect the timeline and entity links,
ask “What most likely happened?”, click citations, ask “What malware family was
used?”, run evaluations, and finish with analyst approval and architecture.

## Limits and future work

V1 has one fixed local analyst, synchronous bounded ingestion, deterministic
correlation, no multi-tenancy, no real-time queue, no enterprise IAM, no automatic
containment, and no compliance certification. Markdown reports are reviewable;
PDF export is outside the core implementation.

Production work would begin with real identity and case entitlements, source
authentication, tenant isolation, least-privilege database roles, immutable
external audit retention, operational limits, backup/recovery, provider privacy
review, and separate repeated live-model adversarial evaluations. Larger-scale
storage and streaming infrastructure should follow measured workload needs.
