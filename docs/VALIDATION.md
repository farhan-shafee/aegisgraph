# Validation record

Local validation date: 2026-09-17 UTC. Dataset date: 2026-09-15 UTC.
Results here describe this implementation run, not continuous operational metrics.

## Environment and persisted data

- Windows, Python 3.14.7, Node.js 26.8.2.
- Real PostgreSQL 17.10 on loopback, plus isolated SQLite test databases.
- The Docker CLI was available but the Docker engine was unavailable. PostgreSQL
  validation used an isolated native cluster under ignored `.runtime/` instead;
  the Compose startup itself was not exercised locally.
- A clean database was migrated and seeded: **4,026 events, 10 alerts, 1 incident,
  26 incident evidence items, 10 detection definitions**.
- The schema has 15 application tables plus Alembic revision metadata. Ordinary
  event and audit UPDATE/DELETE operations were verified to fail in PostgreSQL
  and SQLite. Database-owner/DDL bypass is outside that guarantee.

## Backend and AI results

| Check | Executed result |
|---|---|
| Ruff lint | Passed |
| Ruff formatting | Passed |
| Backend and AI pytest | 112 passed |
| PostgreSQL clean migrations and seed | Passed |
| SQLite clean migrations, seed and reset | Passed |
| API/database smoke | Passed: health, counts, pagination, case graph/evidence, validation errors |
| Deterministic evaluation suite | 28 passed, 0 failed |
| Pinned Python dependency audit | No known vulnerabilities reported |
| Live deterministic analyst HTTP requests | Grounded answer and malware insufficient-evidence response verified |

Two upstream TestClient deprecation warnings were emitted (the HTTPX TestClient
adapter and AnyIO BlockingPortal alias). They did not fail tests. There is no
configured Python static type checker; no type-checking result is implied.

The optional OpenAI provider was checked with mocked HTTP responses, schema tests,
and boundary tests. **No live external model call was executed**, and no key was
required. Deterministic injection fixtures validate application enforcement;
they do not measure general live-model prompt-injection resistance.

## Frontend and browser results

| Check | Executed result |
|---|---|
| npm install with lockfile | Passed |
| ESLint | Passed, no warnings |
| TypeScript | Passed |
| Prettier formatting | Passed |
| Vitest component/unit tests | 15 passed |
| Next.js production build | Passed |
| npm dependency audit | 0 known vulnerabilities reported |
| Playwright suite | 10 passed, 0 failed, retries disabled |
| Browser investigation workflow | Passed: source inspection, annotation, graph selection/filtering, analyst citations, false premise, finding approval, incident update, report approval/download and audit |
| Event filtering and evaluation UI | Passed against the running API |
| Responsive route matrix | Passed at 320, 375, 430, 768, 1280, 1440 and 1920 pixels |
| Production browser smoke | 8 routes passed against PostgreSQL; no page errors, console errors or failed requests |

Responsive checks covered all eight primary routes and the entity graph view.
Intentional table scroll containers are allowed; document-level overflow was
absent. Desktop and mobile screenshots were visually inspected. Keyboard tests
cover tab navigation, accessible panel naming, and evidence-dialog dismissal.

Browser execution used fresh Playwright Chrome contexts. The agent-browser helper
could not launch reliably in this Windows sandbox. Playwright's automatic server
teardown also hung in the sandbox; local execution instead used dedicated
manually managed test servers and `E2E_REUSE_SERVERS=1`. This only changes process
ownership, not assertions or the isolated test database. CI retains automatic
server management on Linux. An initially ambiguous device/session test locator
was made exact before the successful workflow run; retries remain disabled.

## Review scope

The implementation was reviewed for environment-secret handling, ignored local
data, unsafe dynamic execution, ORM binding, untrusted HTML rendering, incident
evidence scoping, origin/host controls, body limits, model context, report approval
metadata and stale-state handling. The model has no mutation tool interface.

This is an engineering verification record, not a penetration test, security
certification, production readiness review, or proof that dependencies are free
from undisclosed vulnerabilities. CI configuration is versioned in
`.github/workflows/ci.yml`; hosted run status is reported separately after push.
